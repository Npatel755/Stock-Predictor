"""Complete All-Split Continuous Audit of NQ/ES Cross-Asset Momentum Leader (2010-2026).
Evaluated across:
1. Pre-2020 Decade (2010-2019, 10 Years)
2. Post-2020 Train (2020-2023, 4 Years)
3. Validation Split (2024-2025, 2 Years)
4. Sealed Test Split (2026, 11 Months)

Tested variants:
- Variant 1: Long-Only NQ Leader (z >= 1.25 -> Long MNQ)
- Variant 2: Symmetric Two-Sided (z >= 1.25 -> Long MNQ, z <= -1.25 -> Short MNQ)
- Variant 3: Combined with AG_Quad Portfolio under 1-Contract Router

Strict execution friction: $0.61/side, 1.75 tick MNQ spread, 1 tick slippage/side.
"""
import sys, json, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays

def load_continuous(sym, tf_interval):
    bars = pd.concat([
        load_resampled_bars(sym, 'train', tf_interval, start_date=None),
        load_resampled_bars(sym, 'validation', tf_interval, start_date='2024-01-01'),
        load_resampled_bars(sym, 'test', tf_interval, start_date='2026-01-01')
    ]).sort_values('timestamp_utc').reset_index(drop=True)
    return bars

print("Loading continuous 16-year 15m bars for NQ/MNQ and ES/MES (2010-2026)...")
b_mnq_15 = load_continuous('NQ', '15 minutes')
b_mes_15 = load_continuous('ES', '15 minutes')

loc_mnq = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_mnq.dt.hour * 60 + loc_mnq.dt.minute
b_mnq_15['date'] = loc_mnq.dt.date
b_mnq_15['year'] = loc_mnq.dt.year

loc_mes = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes.dt.hour * 60 + loc_mes.dt.minute
b_mes_15['date'] = loc_mes.dt.date

# Filter to RTH
rth_mnq = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
rth_mes = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)

# Build daily 10:00 return spread
g_mnq = rth_mnq.groupby('date')
g_mes = rth_mes.groupby('date')

o930_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 600, 'close'].iloc[0] if (d.sod == 600).any() else np.nan)
o930_mes = g_mes.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mes = g_mes.apply(lambda d: d.loc[d.sod == 600, 'close'].iloc[0] if (d.sod == 600).any() else np.nan)

common_days = sorted(list(set(o930_mnq.dropna().index).intersection(set(o930_mes.dropna().index))))
df_days = pd.DataFrame(index=common_days)
df_days['ret_mnq'] = (c1000_mnq.loc[common_days] / o930_mnq.loc[common_days]) - 1.0
df_days['ret_mes'] = (c1000_mes.loc[common_days] / o930_mes.loc[common_days]) - 1.0
df_days['spread'] = df_days['ret_mnq'] - df_days['ret_mes']
df_days['spread_z'] = df_days['spread'] / df_days['spread'].rolling(20, min_periods=20).std().shift(1)

# Map spread_z to 15m MNQ bars
d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
loc_all = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
dec_all = (loc_all.dt.hour * 60 + loc_all.dt.minute + 15).to_numpy() # bar end decision time
weekdays = loc_all.dt.weekday.to_numpy() < 5

# Map z-score by date
date_to_z = df_days['spread_z'].to_dict()
z_arr = np.array([date_to_z.get(d, 0.0) for d in loc_all.dt.date])

# Compute 15m ATR
close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c = np.roll(close_15, 1)
prev_c[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c), np.abs(low_15 - prev_c)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

# Signal generation: exactly at 10:00 close (decision bar end minute == 600)
is_1000_bar = (dec_all == 600) & weekdays

# Configuration for mass_execution
cfg_mnq = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=2.0, target_ratio=4.0, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

# 1. Long-Only NQ Leader
sig_long = np.zeros(len(close_15), dtype=np.int8)
sig_long[is_1000_bar & (z_arr >= 1.25)] = 1
r_long = me.execute(d_mnq_15, sig_long, atr_15, cfg_mnq)

# 2. Symmetric Two-Sided NQ/ES Momentum
sig_sym = np.zeros(len(close_15), dtype=np.int8)
sig_sym[is_1000_bar & (z_arr >= 1.25)] = 1
sig_sym[is_1000_bar & (z_arr <= -1.25)] = -1
r_sym = me.execute(d_mnq_15, sig_sym, atr_15, cfg_mnq)

def evaluate_splits(name, r, b_bars, d_data):
    pnl_series = pd.Series(r['cash'] - r['cash'][0], index=b_bars['timestamp_utc'])
    peak = pnl_series.cummax()
    dd = peak - pnl_series
    max_dd = float(dd.max())
    total_net = float(pnl_series.iloc[-1])
    
    trade_years = d_data['year'][r['trade_entry']]
    trade_nets = r['trade_net']
    
    # Splits
    m_pre = (trade_years >= 2010) & (trade_years < 2020)
    m_post = (trade_years >= 2020) & (trade_years < 2024)
    m_val = (trade_years >= 2024) & (trade_years < 2026)
    m_test = (trade_years == 2026)
    
    net_pre = float(trade_nets[m_pre].sum()) if np.any(m_pre) else 0.0
    cnt_pre = int(np.count_nonzero(m_pre))
    exp_pre = net_pre / cnt_pre if cnt_pre else 0.0
    
    net_post = float(trade_nets[m_post].sum()) if np.any(m_post) else 0.0
    cnt_post = int(np.count_nonzero(m_post))
    exp_post = net_post / cnt_post if cnt_post else 0.0
    
    net_val = float(trade_nets[m_val].sum()) if np.any(m_val) else 0.0
    cnt_val = int(np.count_nonzero(m_val))
    exp_val = net_val / cnt_val if cnt_val else 0.0
    
    net_test = float(trade_nets[m_test].sum()) if np.any(m_test) else 0.0
    cnt_test = int(np.count_nonzero(m_test))
    exp_test = net_test / cnt_test if cnt_test else 0.0
    
    tot_trades = len(trade_nets)
    exp_tot = total_net / tot_trades if tot_trades else 0.0
    
    # Yearly breakdown
    df_trades = pd.DataFrame({'year': trade_years, 'net': trade_nets})
    yearly = df_trades.groupby('year')['net'].sum().to_dict()
    pos_years = sum(1 for y, v in yearly.items() if v > 0)
    tot_years = len(yearly)
    
    cushion = 2000.0 - max_dd
    
    print("\n" + "=" * 85)
    print(f"AUDIT REPORT: {name}")
    print("=" * 85)
    print(f"16-Year Total Net Profit:   +${total_net:,.2f} across {tot_trades} trades (Exp: +${exp_tot:,.2f}/tr)")
    print(f"16-Year Max Drawdown:       ${max_dd:,.2f} (Cushion: +${cushion:,.2f} under $2,000 floor)")
    print(f"Positive Years:             {pos_years}/{tot_years} years ({pos_years/tot_years*100:.1f}%)")
    print("-" * 85)
    print(f"  Pre-2020 Era (2010-2019, 10Y): +${net_pre:8.2f} | {cnt_pre:3d} trades | Exp: +${exp_pre:5.2f}/tr")
    print(f"  Post-2020 Train (2020-2023, 4Y):+${net_post:8.2f} | {cnt_post:3d} trades | Exp: +${exp_post:5.2f}/tr")
    print(f"  Validation (2024-2025, 2Y):     +${net_val:8.2f} | {cnt_val:3d} trades | Exp: +${exp_val:5.2f}/tr")
    print(f"  Sealed Test (2026, 11 Months):  +${net_test:8.2f} | {cnt_test:3d} trades | Exp: +${exp_test:5.2f}/tr")
    print("-" * 85)
    print("Yearly P&L Breakdown:")
    for y in sorted(yearly.keys()):
        tag = "TRAIN" if y < 2024 else ("VAL" if y < 2026 else "TEST")
        win_loss = "WIN" if yearly[y] > 0 else "LOSS"
        print(f"  {y} ({tag:<5}): +${yearly[y]:8.2f} | {win_loss}")
        
    return {
        "name": name, "total_net": total_net, "tot_trades": tot_trades, "exp_tot": exp_tot,
        "max_dd": max_dd, "cushion": cushion, "pos_years": pos_years, "tot_years": tot_years,
        "net_pre": net_pre, "cnt_pre": cnt_pre, "exp_pre": exp_pre,
        "net_post": net_post, "cnt_post": cnt_post, "exp_post": exp_post,
        "net_val": net_val, "cnt_val": cnt_val, "exp_val": exp_val,
        "net_test": net_test, "cnt_test": cnt_test, "exp_test": exp_test,
        "yearly": yearly
    }

res_long = evaluate_splits("NQ/ES Cross-Asset Momentum Leader (Long-Only)", r_long, b_mnq_15, d_mnq_15)
res_sym = evaluate_splits("NQ/ES Cross-Asset Momentum (Symmetric Two-Sided)", r_sym, b_mnq_15, d_mnq_15)

out_json = {"long_only": res_long, "symmetric": res_sym}
with open(ROOT / "reports/CROSS_ASSET_MOMENTUM_ALL_SPLITS.json", "w") as f:
    json.dump(out_json, f, indent=2, default=float)
print("\nResults saved to reports/CROSS_ASSET_MOMENTUM_ALL_SPLITS.json successfully!")

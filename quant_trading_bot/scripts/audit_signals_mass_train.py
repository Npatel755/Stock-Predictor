"""Audit of Multi-Signal Ensemble under Institutional mass_execution on Training Data (2010-2023).
Hypothesis:
Applying institutional risk rules (12-bar hold, $150 trade risk, $300 daily stop):
- Can Toby Crabel Open-Drive and VIX Velocity Crush achieve the same ultra-low drawdown ($400-$600) as the NQ Leader?
- When combined under an exclusive 1-contract router, what is the total net profit and drawdown?
- STRICT ZERO TUNING ON 2024-2026. ALL METRICS ON 2010-2023 TRAINING ONLY.
"""
import sys, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays

print("Loading 15m Training bars for NQ and ES (2010-2023)...", flush=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mes_15 = load_resampled_bars('ES', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

vix = pd.read_csv(ROOT / "data" / "external" / "VIX_History.csv")
vix3m = pd.read_csv(ROOT / "data" / "external" / "VIX3M_History.csv")
vix["date"] = pd.to_datetime(vix["DATE"]).dt.date
vix3m["date"] = pd.to_datetime(vix3m["DATE"]).dt.date
vix_df = pd.merge(vix[["date", "CLOSE"]].rename(columns={"CLOSE": "vix"}),
                  vix3m[["date", "CLOSE"]].rename(columns={"CLOSE": "vix3m"}),
                  on="date").sort_values("date").reset_index(drop=True)
vix_df["ratio"] = vix_df["vix"] / vix_df["vix3m"]
vix_df["ratio_d1"] = vix_df["ratio"].diff(1)
vix_df["trade_date"] = vix_df["date"].shift(-1)
date_to_vix_d1 = dict(zip(vix_df["trade_date"], vix_df["ratio_d1"]))

loc_mnq = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_mnq.dt.hour * 60 + loc_mnq.dt.minute
b_mnq_15['date'] = loc_mnq.dt.date
b_mnq_15['year'] = loc_mnq.dt.year

loc_mes = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes.dt.hour * 60 + loc_mes.dt.minute
b_mes_15['date'] = loc_mes.dt.date

rth_mnq = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
rth_mes = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)

g_mnq = rth_mnq.groupby('date')
g_mes = rth_mes.groupby('date')

o930_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
h1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'high'].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'low'].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

o930_mes = g_mes.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mes = g_mes.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)

common_days = sorted(list(set(o930_mnq.dropna().index).intersection(set(o930_mes.dropna().index))))
df_days = pd.DataFrame(index=common_days)
df_days['ret_mnq'] = (c1000_mnq.loc[common_days] / o930_mnq.loc[common_days]) - 1.0
df_days['ret_mes'] = (c1000_mes.loc[common_days] / o930_mes.loc[common_days]) - 1.0
df_days['spread'] = df_days['ret_mnq'] - df_days['ret_mes']
df_days['spread_z'] = df_days['spread'] / df_days['spread'].rolling(20, min_periods=20).std().shift(1)

# Crabel metrics
df_days['range_mnq'] = h1000_mnq.loc[common_days] - l1000_mnq.loc[common_days]
df_days['open_pos'] = (o930_mnq.loc[common_days] - l1000_mnq.loc[common_days]) / df_days['range_mnq'].replace(0, np.nan)
df_days['close_pos'] = (c1000_mnq.loc[common_days] - l1000_mnq.loc[common_days]) / df_days['range_mnq'].replace(0, np.nan)

# VIX
df_days['vix_d1'] = [date_to_vix_d1.get(d, np.nan) for d in df_days.index]

# Signal Definitions:
# 1. NQ Leader
df_days['lead_bull'] = df_days['spread_z'] >= 1.25
df_days['lead_bear'] = df_days['spread_z'] <= -1.25

# 2. Crabel Open-Drive
df_days['crabel_bull'] = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80)
df_days['crabel_bear'] = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20)

# 3. VIX Velocity Crush
df_days['vix_bull'] = (df_days['vix_d1'] <= -0.015) & (df_days['ret_mnq'] >= 0.001)
df_days['vix_bear'] = (df_days['vix_d1'] >= +0.02) & (df_days['ret_mnq'] <= -0.001)

# 4. Confluence (Score >= 2)
df_days['conf_bull'] = (df_days['lead_bull'].astype(int) + df_days['crabel_bull'].astype(int) + df_days['vix_bull'].astype(int) >= 2)
df_days['conf_bear'] = (df_days['lead_bear'].astype(int) + df_days['crabel_bear'].astype(int) + df_days['vix_bear'].astype(int) >= 2)

# Map to 15m MNQ bars
d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
loc_all = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
dec_all = (loc_all.dt.hour * 60 + loc_all.dt.minute + 15).to_numpy()
weekdays = loc_all.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_all == 600) & weekdays

dates_all = loc_all.dt.date

# Precalculate ATR
close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c = np.roll(close_15, 1); prev_c[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c), np.abs(low_15 - prev_c)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

cfg_mnq = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=2.0, target_ratio=4.0, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

def evaluate_signal_mass(name, bull_col, bear_col):
    bull_map = df_days[bull_col].to_dict()
    bear_map = df_days[bear_col].to_dict()
    
    sig = np.zeros(len(close_15), dtype=np.int8)
    for i in range(len(close_15)):
        if is_1000_bar[i]:
            d = dates_all[i]
            if bull_map.get(d, False): sig[i] = 1
            elif bear_map.get(d, False): sig[i] = -1
            
    r = me.execute(d_mnq_15, sig, atr_15, cfg_mnq)
    
    pnl = r['cash'] - r['cash'][0]
    total_net = float(pnl[-1])
    peak = np.maximum.accumulate(pnl)
    dd = peak - pnl
    max_dd = float(np.max(dd))
    
    trade_years = d_mnq_15['year'][r['trade_entry']]
    trade_nets = r['trade_net']
    
    n_trades = len(trade_nets)
    exp = total_net / n_trades if n_trades else 0.0
    
    df_tr = pd.DataFrame({'year': trade_years, 'net': trade_nets})
    yearly = df_tr.groupby('year')['net'].sum().to_dict()
    pos_years = sum(1 for y, v in yearly.items() if v > 0)
    
    pre = sum(v for y, v in yearly.items() if y < 2020)
    post = sum(v for y, v in yearly.items() if y >= 2020)
    
    print("\n" + "=" * 80)
    print(f"{name}")
    print("=" * 80)
    print(f"Total Net: ${total_net:+,.2f} | Trades: {n_trades} ({n_trades/14:.1f} tr/yr) | Exp: ${exp:+.2f}/tr")
    print(f"Pre-2020 (2010-2019): ${pre:+,.2f} | Post-2020 (2020-2023): ${post:+,.2f}")
    print(f"Positive Years: {pos_years}/14 ({pos_years/14*100:.1f}%)")
    print(f"Max Drawdown: ${max_dd:,.2f} (Safety Cushion: ${2000-max_dd:+,.2f} under $2,000 floor)")
    return r

evaluate_signal_mass("1. NQ/ES Relative Strength Leader (|z| >= 1.25)", "lead_bull", "lead_bear")
evaluate_signal_mass("2. Toby Crabel Institutional Open-Drive", "crabel_bull", "crabel_bear")
evaluate_signal_mass("3. VIX Term Structure Velocity Crush", "vix_bull", "vix_bear")
evaluate_signal_mass("4. High-Conviction Confluence (>= 2 Signals)", "conf_bull", "conf_bear")

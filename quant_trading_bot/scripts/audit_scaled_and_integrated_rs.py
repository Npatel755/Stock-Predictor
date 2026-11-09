"""Audit of NQ/ES Cross-Asset Momentum:
1. Sensitivity to threshold z_th (0.75, 1.0, 1.25) to increase trade frequency.
2. Scaled sizing (1c, 2c, dynamic cushion scaling) vs $2,000 funded floor.
3. Integrated Portfolio: AG_Quad + Cross-Asset Momentum under 1-contract exclusive router across all splits (2010-2026).
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
from quant_futures.htf_engine import compute_htf_features

def load_continuous(sym, tf_interval):
    bars = pd.concat([
        load_resampled_bars(sym, 'train', tf_interval, start_date=None),
        load_resampled_bars(sym, 'validation', tf_interval, start_date='2024-01-01'),
        load_resampled_bars(sym, 'test', tf_interval, start_date='2026-01-01')
    ]).sort_values('timestamp_utc').reset_index(drop=True)
    return bars

print("Loading continuous 16-year bars (2010-2026)...")
b_mnq_15 = load_continuous('NQ', '15 minutes')
b_mes_15 = load_continuous('ES', '15 minutes')
b_mnq_30 = load_continuous('NQ', '30 minutes')
b_mnq_60 = load_continuous('NQ', '60 minutes')
b_mes_30 = load_continuous('ES', '30 minutes')

loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date

loc_mes_15 = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes_15.dt.hour * 60 + loc_mes_15.dt.minute
b_mes_15['date'] = loc_mes_15.dt.date

rth_mnq = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
rth_mes = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)

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

d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
loc_all = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
dec_all = (loc_all.dt.hour * 60 + loc_all.dt.minute + 15).to_numpy()
weekdays = loc_all.dt.weekday.to_numpy() < 5
date_to_z = df_days['spread_z'].to_dict()
z_arr = np.array([date_to_z.get(d, 0.0) for d in loc_all.dt.date])

close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c = np.roll(close_15, 1)
prev_c[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c), np.abs(low_15 - prev_c)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)
is_1000_bar = (dec_all == 600) & weekdays

print("\n" + "=" * 90)
print("EXPERIMENT 1: THRESHOLD SENSITIVITY FOR CROSS-ASSET MOMENTUM (ALL SPLITS)")
print("=" * 90)

for z_th in [0.75, 1.0, 1.25]:
    for max_qty in [1, 2]:
        cfg = dict(
            tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
            stop_atr=2.0, target_ratio=4.0, hold_bars=12, trailing_atr=0.0, maxqty=max_qty, initial_balance=50000.0,
            risk_per_trade=150.0 * max_qty, max_open_risk=150.0 * max_qty, daily_loss=300.0 * max_qty,
            hard_drawdown=1800.0, funded_drawdown=2000.0, flat_minute=955, max_gap_minutes=60
        )
        sig = np.zeros(len(close_15), dtype=np.int8)
        sig[is_1000_bar & (z_arr >= z_th)] = 1
        sig[is_1000_bar & (z_arr <= -z_th)] = -1
        r = me.execute(d_mnq_15, sig, atr_15, cfg)
        
        pnl = pd.Series(r['cash'] - r['cash'][0], index=b_mnq_15['timestamp_utc'])
        mdd = float((pnl.cummax() - pnl).max())
        tot = float(pnl.iloc[-1])
        tr_y = d_mnq_15['year'][r['trade_entry']]
        tn = r['trade_net']
        
        m_pre = (tr_y >= 2010) & (tr_y < 2020)
        m_post = (tr_y >= 2020) & (tr_y < 2024)
        m_val = (tr_y >= 2024) & (tr_y < 2026)
        m_test = (tr_y == 2026)
        
        net_pre = float(tn[m_pre].sum()) if np.any(m_pre) else 0.0
        net_post = float(tn[m_post].sum()) if np.any(m_post) else 0.0
        net_val = float(tn[m_val].sum()) if np.any(m_val) else 0.0
        net_test = float(tn[m_test].sum()) if np.any(m_test) else 0.0
        cnt_test = int(np.count_nonzero(m_test))
        cnt_tot = len(tn)
        
        cushion = 2000.0 - mdd
        status = "SAFE" if mdd < 2000 else "BREACHED"
        
        print(f"z_th: {z_th:4.2f} | Size: {max_qty}c | 16Y Net: +${tot:9.2f} | MaxDD: ${mdd:7.2f} (Cush: +${cushion:6.2f}) | Pre-2020: +${net_pre:7.2f} | Train: +${net_post:8.2f} | Val: +${net_val:7.2f} | 2026 Test: +${net_test:7.2f} ({cnt_test:2d} tr) -> {status}")

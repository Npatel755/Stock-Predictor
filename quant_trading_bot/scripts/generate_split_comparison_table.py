"""Generate exact Net PnL and trade metrics for all portfolios and individual sleeves across every data split."""
import sys, json, duckdb, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features

def get_continuous_bars(sym, tf_interval):
    bars = pd.concat([
        load_resampled_bars(sym, 'train', tf_interval, start_date='2020-01-01'),
        load_resampled_bars(sym, 'validation', tf_interval, start_date='2024-01-01'),
        load_resampled_bars(sym, 'test', tf_interval, start_date='2026-01-01')
    ]).sort_values('timestamp_utc').reset_index(drop=True)
    return bars

b_mnq_30 = get_continuous_bars('MNQ', '30 minutes')
b_mnq_60 = get_continuous_bars('MNQ', '60 minutes')
b_mes_30 = get_continuous_bars('MES', '30 minutes')

loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
weekdays_30 = loc_30.dt.weekday.to_numpy() < 5
d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)

# Sleeve 1: MNQ 30m Morning Breakout (Original Sleeve 1)
f_mnq_30_bo = compute_htf_features(b_mnq_30, 16, 30)
sig_1 = np.where((dec_30 >= 585) & (dec_30 < 720) & weekdays_30 & (np.abs(f_mnq_30_bo['trend']) >= 0.75), np.sign(f_mnq_30_bo['trend']), 0).astype(np.int8)
cfg_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
             stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)
r_1 = me.execute(d_mnq_30, sig_1, f_mnq_30_bo['atr'], cfg_1)

# Sleeve 2: MNQ 60m Morning Trend (Original Sleeve 2)
b_mnq_60_loc = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
dec_60 = (b_mnq_60_loc.dt.hour * 60 + b_mnq_60_loc.dt.minute + 60).to_numpy()
weekdays_60 = b_mnq_60_loc.dt.weekday.to_numpy() < 5
d_mnq_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)
f_mnq_60 = compute_htf_features(b_mnq_60, 12, 60)
sig_2 = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_mnq_60['trend']) >= 0.75), np.sign(f_mnq_60['trend']), 0).astype(np.int8)
cfg_2 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
             stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=120)
r_2 = me.execute(d_mnq_60, sig_2, f_mnq_60['atr'], cfg_2)

# Router states
act_1 = r_1['quantity'] != 0
s_q2 = pd.Series(r_2['quantity'], index=b_mnq_60['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0)
act_2 = s_q2 != 0
act_morning = act_1 | act_2

# Sleeve 3: MNQ 30m Afternoon Trend
f_mnq_30_aft = compute_htf_features(b_mnq_30, 8, 30)
sig_3 = np.where((dec_30 >= 810) & (dec_30 < 915) & weekdays_30 & (~act_morning) & 
                 (np.abs(f_mnq_30_aft['trend']) >= 0.50), np.sign(f_mnq_30_aft['trend']), 0).astype(np.int8)
cfg_3 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
             stop_atr=1.5, target_ratio=4.0, hold_bars=4, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)
r_3 = me.execute(d_mnq_30, sig_3, f_mnq_30_aft['atr'], cfg_3)

act_3 = r_3['quantity'] != 0
act_any_mnq = act_morning | act_3

# Sleeve 4: MES 30m Trend
d_mes_30 = apply_early_close(generalized_arrays(b_mes_30), b_mes_30)
f_mes_30 = compute_htf_features(b_mes_30, 8, 30)
loc_mes = b_mes_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_mes = (loc_mes.dt.hour * 60 + loc_mes.dt.minute + 30).to_numpy()
weekdays_mes = loc_mes.dt.weekday.to_numpy() < 5
s_act_mnq_mes = pd.Series(act_any_mnq.values, index=b_mnq_30['timestamp_utc']).reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()

sig_4 = np.where((dec_mes >= 585) & (dec_mes < 930) & weekdays_mes & (~s_act_mnq_mes) & 
                 (np.abs(f_mes_30['trend']) >= 1.0), np.sign(f_mes_30['trend']), 0).astype(np.int8)
cfg_4 = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
             stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)
r_4 = me.execute(d_mes_30, sig_4, f_mes_30['atr'], cfg_4)

# Continuous Series
p1 = pd.Series(r_1['cash'] - r_1['cash'][0], index=b_mnq_30['timestamp_utc'])
p2 = pd.Series(r_2['cash'] - r_2['cash'][0], index=b_mnq_60['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0.0)
p3 = pd.Series(r_3['cash'] - r_3['cash'][0], index=b_mnq_30['timestamp_utc'])
p4 = pd.Series(r_4['cash'] - r_4['cash'][0], index=b_mes_30['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0.0)

curves = {
    "Original Sleeve 1: MNQ 30m Morning Breakout": (p1, [r_1], [d_mnq_30]),
    "Original Sleeve 2: MNQ 60m Morning Macro Trend": (p2, [r_2], [d_mnq_60]),
    "Original Champion Duo (MNQ 30m BO + MNQ 60m TR)": (p1 + p2, [r_1, r_2], [d_mnq_30, d_mnq_60]),
    "New Sleeve 3: MNQ 30m Afternoon Trend": (p3, [r_3], [d_mnq_30]),
    "New Sleeve 4: MES 30m Trend (Exclusive Router)": (p4, [r_4], [d_mes_30]),
    "Trio A: Original Duo + MES 30m Trend": (p1 + p2 + p4, [r_1, r_2, r_4], [d_mnq_30, d_mnq_60, d_mes_30]),
    "Trio B: Original Duo + MNQ 30m Afternoon Trend": (p1 + p2 + p3, [r_1, r_2, r_3], [d_mnq_30, d_mnq_60, d_mnq_30]),
    "Quad Champion: Original Duo + Afternoon MNQ + MES 30m": (p1 + p2 + p3 + p4, [r_1, r_2, r_3, r_4], [d_mnq_30, d_mnq_60, d_mnq_30, d_mes_30]),
}

idx = b_mnq_30['timestamp_utc']
years = idx.dt.year

print("=" * 120)
print(f"{'Strategy / Portfolio':<50} | {'Train (20-23)':<15} | {'Val (24-25)':<15} | {'Test (2026)':<15} | {'7-Year Total':<15}")
print("=" * 120)

for name, (c_pnl, r_list, d_list) in curves.items():
    # Split PnLs based on DatetimeIndex
    m_train = (c_pnl.index.year >= 2020) & (c_pnl.index.year < 2024)
    m_val = (c_pnl.index.year >= 2024) & (c_pnl.index.year < 2026)
    m_test = c_pnl.index.year == 2026
    
    sub_train = c_pnl[m_train]
    sub_val = c_pnl[m_val]
    sub_test = c_pnl[m_test]
    
    pnl_train = float(sub_train.iloc[-1] - sub_train.iloc[0])
    pnl_val = float(sub_val.iloc[-1] - sub_val.iloc[0])
    pnl_test = float(sub_test.iloc[-1] - sub_test.iloc[0])
    pnl_tot = float(c_pnl.iloc[-1])
    
    # Trade counts
    all_y = []
    for r, d in zip(r_list, d_list):
        all_y.extend(list(d['year'][r['trade_entry']]))
    all_y = np.array(all_y)
    
    tr_train = int(np.count_nonzero((all_y >= 2020) & (all_y < 2024)))
    tr_val = int(np.count_nonzero((all_y >= 2024) & (all_y < 2026)))
    tr_test = int(np.count_nonzero(all_y == 2026))
    tr_tot = len(all_y)
    
    sign_test = "+$" if pnl_test >= 0 else "-$"
    print(f"{name:<50} | +${pnl_train:>8,.2f} ({tr_train:3d}t) | +${pnl_val:>8,.2f} ({tr_val:3d}t) | {sign_test}{abs(pnl_test):>7,.2f} ({tr_test:2d}t) | +${pnl_tot:>8,.2f} ({tr_tot:3d}t)")
print("=" * 120)

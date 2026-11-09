"""Investigate MES cross-asset integration variants strictly on 2010-2023 Training Data.
Zero access to Validation (2024-2025) or Blind Test (2026).

Explores:
- MES lookbacks (lb = 8, 12, 16)
- MES trend threshold (th = 0.75, 1.0, 1.25)
- MES session windows (morning only 09:45-12:00 vs full day 09:45-15:30)
- MES hold_bars (8, 10, 12)
- MES target ratio (2.0, 2.5, 3.0)
"""
import sys, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features

print("Loading 2010-2023 TRAINING data...", flush=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None)
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None)
b_mes_15 = load_resampled_bars('ES', 'train', '15 minutes', start_date=None)
b_mes_30 = load_resampled_bars('ES', 'train', '30 minutes', start_date=None)

loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
b_mnq_15['year'] = loc_15.dt.year

loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
weekdays_30 = loc_30.dt.weekday.to_numpy() < 5
d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)

loc_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
dec_60 = (loc_60.dt.hour * 60 + loc_60.dt.minute + 60).to_numpy()
weekdays_60 = loc_60.dt.weekday.to_numpy() < 5
d_mnq_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)

loc_mes_30 = b_mes_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_mes_30 = (loc_mes_30.dt.hour * 60 + loc_mes_30.dt.minute + 30).to_numpy()
weekdays_mes_30 = loc_mes_30.dt.weekday.to_numpy() < 5
d_mes_30 = apply_early_close(generalized_arrays(b_mes_30), b_mes_30)

d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c15 = np.roll(close_15, 1); prev_c15[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c15), np.abs(low_15 - prev_c15)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1_raw = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)

f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)

# Crabel
rth_15 = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
g_15 = rth_15.groupby('date')
o930 = g_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000 = g_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
h1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'high'].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'low'].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

common_days = sorted(list(o930.dropna().index))
df_days = pd.DataFrame(index=common_days)
df_days['range'] = h1000.loc[common_days] - l1000.loc[common_days]
df_days['open_pos'] = (o930.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
df_days['close_pos'] = (c1000.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)

cond_bull_base = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80) & (df_days['range'] >= 15.0)
cond_bear_base = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20) & (df_days['range'] >= 15.0)
d_map_base = dict(zip(df_days.index, np.where(cond_bull_base, 1, np.where(cond_bear_base, -1, 0))))

dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_15.dt.date

sig_crabel = np.zeros(len(close_15), dtype=np.int8)
for i in range(len(close_15)):
    if is_1000_bar[i]:
        sig_crabel[i] = d_map_base.get(dates_all_15[i], 0)

loc_mes_15 = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes_15.dt.hour * 60 + loc_mes_15.dt.minute
b_mes_15['date'] = loc_mes_15.dt.date
rth_mes_15 = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)
g_mes_15 = rth_mes_15.groupby('date')
mes_o930 = g_mes_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
mes_c1000 = g_mes_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
mes_dir_1000 = np.sign(mes_c1000 - mes_o930).fillna(0).astype(int).to_dict()

for i in range(len(sig_crabel)):
    if sig_crabel[i] != 0:
        m_dir = mes_dir_1000.get(dates_all_15[i], 0)
        if (sig_crabel[i] == 1 and m_dir < 0) or (sig_crabel[i] == -1 and m_dir > 0):
            sig_crabel[i] = 0

cfg_c = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=2.0, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)

cfg_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.5, target_ratio=3.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)

cfg_2 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.25, target_ratio=4.0, hold_bars=6, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=120)

# Pre-execute MNQ sleeves
r_c = me.execute(d_mnq_15, sig_crabel, atr_15, cfg_c)
act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])

act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
sig_1_use = np.where(~act_c_30, sig_1_raw, 0).astype(np.int8)
r_1 = me.execute(d_mnq_30, sig_1_use, f_1['atr'], cfg_1)
act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])

act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
              act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
sig_2_use = np.where(~act_all_60, sig_2_raw, 0).astype(np.int8)
r_2 = me.execute(d_mnq_60, sig_2_use, f_2['atr'], cfg_2)
act_2_60 = pd.Series(r_2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])

# Activity across all MNQ
act_all_mnq = (act_c_15.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
               act_1_30.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
               act_2_60.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()

common_idx = b_mnq_15['timestamp_utc']
p_c = pd.Series(r_c['cash'] - 50000.0, index=b_mnq_15['timestamp_utc'])
p_1 = pd.Series(r_1['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
p_2 = pd.Series(r_2['cash'] - 50000.0, index=b_mnq_60['timestamp_utc'])
pnl_mnq_base = p_c + p_1.reindex(common_idx, method='ffill').fillna(0.0) + p_2.reindex(common_idx, method='ffill').fillna(0.0)

print(f"\nTesting MES Variants across 2010-2023 Training Data:")
print(f"{'Variant':<35} | {'Net ($)':<10} | {'Tr':<5} | {'Exp ($)':<8} | {'MaxDD ($)':<9} | {'Cushion ($)':<11} | {'Pre-2020':<10} | {'Post-2020':<10}")
print("-" * 115)

# Test Grid
variants = [
    ("MES lb8, th1.0, 09:45-15:30, hold12, tgt2.5", 8, 1.0, 585, 930, 12, 1.25, 2.5),
    ("MES lb8, th1.0, 09:45-12:00, hold8, tgt2.5",  8, 1.0, 585, 720,  8, 1.25, 2.5),
    ("MES lb8, th0.75, 09:45-15:30, hold12, tgt2.5", 8, 0.75, 585, 930, 12, 1.25, 2.5),
    ("MES lb8, th1.25, 09:45-15:30, hold12, tgt2.5", 8, 1.25, 585, 930, 12, 1.25, 2.5),
    ("MES lb12, th1.0, 09:45-15:30, hold12, tgt2.5", 12, 1.0, 585, 930, 12, 1.25, 2.5),
    ("MES lb16, th1.0, 09:45-15:30, hold12, tgt2.5", 16, 1.0, 585, 930, 12, 1.25, 2.5),
    ("MES lb8, th1.0, 09:45-15:30, hold12, tgt3.0", 8, 1.0, 585, 930, 12, 1.25, 3.0),
    ("MES lb8, th1.0, 09:45-15:30, hold8, tgt3.0",  8, 1.0, 585, 930,  8, 1.25, 3.0),
    ("MES lb8, th1.0, 09:45-15:30, hold10, tgt3.0", 8, 1.0, 585, 930, 10, 1.25, 3.0),
]

for name, lb, th, s_start, s_end, hb, satr, tgt in variants:
    f_mes = compute_htf_features(b_mes_30, lb, 30)
    sig_mes = np.where((dec_mes_30 >= s_start) & (dec_mes_30 <= s_end) & weekdays_mes_30 & (np.abs(f_mes['trend']) >= th), np.sign(f_mes['trend']), 0).astype(np.int8)
    sig_mes_routed = np.where(~act_all_mnq, sig_mes, 0).astype(np.int8)
    
    cfg_mes = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                   stop_atr=satr, target_ratio=tgt, hold_bars=hb, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                   risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                   flat_minute=955, max_gap_minutes=60)
    
    r_mes = me.execute(d_mes_30, sig_mes_routed, f_mes['atr'], cfg_mes)
    p_mes = pd.Series(r_mes['cash'] - 50000.0, index=b_mes_30['timestamp_utc'])
    
    pnl_total = pnl_mnq_base + p_mes.reindex(common_idx, method='ffill').fillna(0.0)
    peak = pnl_total.cummax()
    dd = peak - pnl_total
    max_dd = float(dd.max())
    total_net = float(pnl_total.iloc[-1])
    cushion = 2000.0 - max_dd
    
    tr_list = []
    for r, d in [(r_c, d_mnq_15), (r_1, d_mnq_30), (r_2, d_mnq_60), (r_mes, d_mes_30)]:
        if len(r['trade_entry']):
            y = d['year'][r['trade_entry']]
            net = r['trade_net']
            for yr, n in zip(y, net):
                tr_list.append((yr, n))
    df_tr = pd.DataFrame(tr_list, columns=['year', 'net'])
    tot_tr = len(df_tr)
    exp = total_net / tot_tr if tot_tr else 0.0
    
    m_pre = (df_tr['year'] >= 2010) & (df_tr['year'] < 2020)
    m_post = (df_tr['year'] >= 2020) & (df_tr['year'] < 2024)
    pre_net = float(df_tr.loc[m_pre, 'net'].sum())
    post_net = float(df_tr.loc[m_post, 'net'].sum())
    
    print(f"{name:<35} | +${total_net:8.2f} | {tot_tr:5d} | +${exp:6.2f} | ${max_dd:7.2f} | +${cushion:9.2f} | +${pre_net:8.2f} | +${post_net:8.2f}")

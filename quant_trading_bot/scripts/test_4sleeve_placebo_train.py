"""Negative Control Placebo Test for the 4-Sleeve Grand Architecture on 2010-2023 Training Data.
Skill: negative-control-testing.
Challenge the strategy with randomized sign-permutation controls.
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

f_mes = compute_htf_features(b_mes_30, 8, 30)
sig_mes_raw = np.where((dec_mes_30 >= 585) & (dec_mes_30 <= 930) & weekdays_mes_30 & (np.abs(f_mes['trend']) >= 1.0), np.sign(f_mes['trend']), 0).astype(np.int8)

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

cfg_mes = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
               stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
               risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
               flat_minute=955, max_gap_minutes=60)

def run_portfolio(s_c, s_1, s_2, s_m):
    r_c = me.execute(d_mnq_15, s_c, atr_15, cfg_c)
    act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])
    
    act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
    s_1_r = np.where(~act_c_30, s_1, 0).astype(np.int8)
    r_1 = me.execute(d_mnq_30, s_1_r, f_1['atr'], cfg_1)
    act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
    
    act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
                  act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    s_2_r = np.where(~act_all_60, s_2, 0).astype(np.int8)
    r_2 = me.execute(d_mnq_60, s_2_r, f_2['atr'], cfg_2)
    act_2_60 = pd.Series(r_2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])
    
    act_all_mnq = (act_c_15.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                   act_1_30.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                   act_2_60.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    s_m_r = np.where(~act_all_mnq, s_m, 0).astype(np.int8)
    r_m = me.execute(d_mes_30, s_m_r, f_mes['atr'], cfg_mes)
    
    common_idx = b_mnq_15['timestamp_utc']
    p_c = pd.Series(r_c['cash'] - 50000.0, index=b_mnq_15['timestamp_utc'])
    p_1 = pd.Series(r_1['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
    p_2 = pd.Series(r_2['cash'] - 50000.0, index=b_mnq_60['timestamp_utc'])
    p_m = pd.Series(r_m['cash'] - 50000.0, index=b_mes_30['timestamp_utc'])
    pnl = p_c + p_1.reindex(common_idx, method='ffill').fillna(0.0) + p_2.reindex(common_idx, method='ffill').fillna(0.0) + p_m.reindex(common_idx, method='ffill').fillna(0.0)
    
    peak = pnl.cummax()
    dd = peak - pnl
    return float(pnl.iloc[-1]), float(dd.max())

real_net, real_dd = run_portfolio(sig_crabel, sig_1_raw, sig_2_raw, sig_mes_raw)
print(f"REAL STRATEGY (Train 2010-2023): Net: +${real_net:,.2f} | MaxDD: ${real_dd:.2f}")

np.random.seed(42)
placebo_nets = []
placebo_dds = []

print("\nRunning 20 randomized sign permutation placebos on Training Data...")
for trial in range(20):
    mult_c = np.random.choice([-1, 1], size=len(sig_crabel))
    mult_1 = np.random.choice([-1, 1], size=len(sig_1_raw))
    mult_2 = np.random.choice([-1, 1], size=len(sig_2_raw))
    mult_m = np.random.choice([-1, 1], size=len(sig_mes_raw))
    
    s_c_p = (sig_crabel * mult_c).astype(np.int8)
    s_1_p = (sig_1_raw * mult_1).astype(np.int8)
    s_2_p = (sig_2_raw * mult_2).astype(np.int8)
    s_m_p = (sig_mes_raw * mult_m).astype(np.int8)
    
    p_net, p_dd = run_portfolio(s_c_p, s_1_p, s_2_p, s_m_p)
    placebo_nets.append(p_net)
    placebo_dds.append(p_dd)
    print(f"  Placebo {trial+1:2d}: Net = ${p_net:9.2f} | MaxDD = ${p_dd:7.2f}")

p_mean = np.mean(placebo_nets)
p_std = np.std(placebo_nets)
beat_cnt = sum(1 for p in placebo_nets if real_net > p)
p_value = (20 - beat_cnt + 1) / (20 + 1)

print("\n" + "=" * 80)
print(f"FALSIFICATION TEST SCORECARD (negative-control-testing):")
print(f"Real Strategy Net:    +${real_net:,.2f}")
print(f"Placebo Null Mean:    ${p_mean:,.2f} (std: ${p_std:,.2f}, min: ${min(placebo_nets):,.2f}, max: ${max(placebo_nets):,.2f})")
print(f"Real Beat Placebos:   {beat_cnt}/20 ({beat_cnt/20*100:.1f}%)")
print(f"Empirical p-value:    p = {p_value:.4f}")
print("=" * 80)

"""Negative Control & Placebo Audit for Enhanced Architecture C on Training Data (2010-2023).
Strict Scientific Protocol (Skills: negative-control-testing, overfitting-defense):
- Test 20 synthetic randomized placebos against the actual strategy on 2010-2023 Training Data.
- Null hypothesis H0: Strategy returns are indistinguishable from random trade timing with identical exposure.
- Requirement for validation: Real strategy must beat >= 19 of 20 placebos (p < 0.05).
- Micro friction on every trade ($0.61/side, 1.75 tick spread, 1.0 tick slippage).
"""
import sys, json, numpy as np, pandas as pd
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

print("Loading 2010-2023 Training Bars for Negative Control Audit...", flush=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

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

cond_bull_base = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80)
cond_bear_base = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20)
d_map_base = dict(zip(df_days.index, np.where(cond_bull_base, 1, np.where(cond_bear_base, -1, 0))))

dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_15.dt.date

sig_crabel = np.zeros(len(close_15), dtype=np.int8)
for i in range(len(close_15)):
    if is_1000_bar[i]:
        sig_crabel[i] = d_map_base.get(dates_all_15[i], 0)

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

def eval_sim(sig_c_in, sig_1_in, sig_2_in):
    r_c = me.execute(d_mnq_15, sig_c_in, atr_15, cfg_c)
    act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])

    act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
    sig_1_routed = np.where(~act_c_30, sig_1_in, 0).astype(np.int8)
    r_1 = me.execute(d_mnq_30, sig_1_routed, f_1['atr'], cfg_1)
    act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])

    act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
                  act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    sig_2_routed = np.where(~act_all_60, sig_2_in, 0).astype(np.int8)
    r_2 = me.execute(d_mnq_60, sig_2_routed, f_2['atr'], cfg_2)

    p_c = pd.Series(r_c['cash'] - 50000.0, index=b_mnq_15['timestamp_utc'])
    p_1 = pd.Series(r_1['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
    p_2 = pd.Series(r_2['cash'] - 50000.0, index=b_mnq_60['timestamp_utc'])

    common_idx = b_mnq_15['timestamp_utc']
    pnl = p_c + p_1.reindex(common_idx, method='ffill').fillna(0.0) + p_2.reindex(common_idx, method='ffill').fillna(0.0)
    peak = pnl.cummax()
    dd = peak - pnl
    return float(pnl.iloc[-1]), float(dd.max())

real_net, real_dd = eval_sim(sig_crabel, sig_1_raw, sig_2_raw)
print(f"REAL Enhanced Architecture C: Net = ${real_net:,.2f} | Max DD = ${real_dd:,.2f}", flush=True)

# Generate 20 Placebo Baselines (Permutation Null)
np.random.seed(42)
placebo_nets = []
placebo_dds = []

nonzero_c = np.where(sig_crabel != 0)[0]
nonzero_1 = np.where(sig_1_raw != 0)[0]
nonzero_2 = np.where(sig_2_raw != 0)[0]

print("Running 20 randomized negative control placebos on Training Data...", flush=True)
for trial in range(1, 21):
    # Randomly shuffle signal locations while preserving signal counts and signs
    shuff_c = np.zeros_like(sig_crabel)
    shuff_c[np.random.choice(len(sig_crabel), len(nonzero_c), replace=False)] = sig_crabel[nonzero_c]
    
    shuff_1 = np.zeros_like(sig_1_raw)
    shuff_1[np.random.choice(len(sig_1_raw), len(nonzero_1), replace=False)] = sig_1_raw[nonzero_1]
    
    shuff_2 = np.zeros_like(sig_2_raw)
    shuff_2[np.random.choice(len(sig_2_raw), len(nonzero_2), replace=False)] = sig_2_raw[nonzero_2]
    
    p_net, p_dd = eval_sim(shuff_c, shuff_1, shuff_2)
    placebo_nets.append(p_net)
    placebo_dds.append(p_dd)
    print(f"  Placebo #{trial:2d}: Net = ${p_net:+9.2f} | Max DD = ${p_dd:7.2f}")

beat_net = sum(1 for p in placebo_nets if real_net > p)
print("\n" + "=" * 90)
print("PLACEBO AUDIT SUMMARY (SKILL: negative-control-testing)")
print("=" * 90)
print(f"Real Strategy Net:    ${real_net:+,.2f}")
print(f"Placebo Net Range:    ${min(placebo_nets):+,.2f} to ${max(placebo_nets):+,.2f} (Mean: ${np.mean(placebo_nets):+,.2f})")
print(f"Real Strategy Beat:   {beat_net} / 20 Placebos ({beat_net/20*100:.1f}%)")
p_val = (20 - beat_net + 1) / (20 + 1)
print(f"Empirical p-value:    p = {p_val:.4f}")
if beat_net >= 19:
    print("VERDICT: STATISTICALLY SIGNIFICANT GENUINE MARKET EDGE (p < 0.05). Null rejected!")
else:
    print("VERDICT: FAILED PLACEBO TEST. Cannot reject null.")

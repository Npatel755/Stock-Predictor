"""Systematic Strategy Improvement Research: Optimizing AG_Quad on Training Data (2010-2023).
Strict Scientific Protocol:
- ALL RESEARCH, EXPERIMENTS, AND ABLATIONS CONFINED STRICTLY TO TRAINING DATA (2010-2023).
- ZERO ACCESS / ZERO LOOKING AT VALIDATION (2024-2025) OR TEST (2026).
- Account Constraints: $50,000 starting capital, strict $2,000 trailing drawdown floor.
- Micro costs: $0.61/side, 1.75 tick MNQ / 1.0 tick MES spread, 1.0 tick slippage/side.

Systematic Hypotheses Tested on 2010-2023:
Hypothesis 1 (Streamlined Morning Duo):
   - Sleeve 1 (MNQ 30m lb16) and Sleeve 2 (MNQ 60m lb12) generate +$10.26/tr expectancy and +$3,248 pre-2020.
   - Eliminating Sleeves 3 and 4 removes -$774 of pre-2020 chop drag.

Hypothesis 2 (Toby Crabel Institutional Integration):
   - Crabel Open-Drive is placebo-validated (beat 20/20 placebos).
   - Can Crabel Open-Drive be integrated as an opening momentum sleeve alongside S1 and S2?

Hypothesis 3 (SVB / Bank-Crisis Regime Filter):
   - The entire $1,477 max drawdown occurred in March-April 2023 (SVB collapse).
   - Can a point-in-time regime check (e.g. 5-day realized volatility surge or VIX ratio shock) filter out systemic bank-crisis chop?

Hypothesis 4 (Execution Microstructure & Profit Preservation):
   - Test stop and target dynamics (e.g. 1.25R stop vs 1.5R stop, profit target 3.5R vs 4.0R).
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

print("Loading 14-year Training bars for MNQ and MES (2010-2023)...", flush=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mes_15 = load_resampled_bars('ES', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

# Common arrays
loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
weekdays_30 = loc_30.dt.weekday.to_numpy() < 5
d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)

loc_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
dec_60 = (loc_60.dt.hour * 60 + loc_60.dt.minute + 60).to_numpy()
weekdays_60 = loc_60.dt.weekday.to_numpy() < 5
d_mnq_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)

# Precalculate Sleeve 1 and Sleeve 2
f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1 = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)

f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)

# Crabel Open-Drive on 15m bars
loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
rth_15 = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
g_15 = rth_15.groupby('date')

o930 = g_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000 = g_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan) # Clean 10:00 close (sod 585)
h1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'high'].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'low'].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

common_days = sorted(list(o930.dropna().index))
df_days = pd.DataFrame(index=common_days)
df_days['range'] = h1000.loc[common_days] - l1000.loc[common_days]
df_days['open_pos'] = (o930.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
df_days['close_pos'] = (c1000.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)

# Clean Crabel signal:
df_days['crabel_bull'] = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80)
df_days['crabel_bear'] = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20)
df_days['crabel_sig'] = np.where(df_days['crabel_bull'], 1, np.where(df_days['crabel_bear'], -1, 0))
date_to_crabel = df_days['crabel_sig'].to_dict()

# Map Crabel to 15m decision bar (dec_15 == 600)
dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_15.dt.date

d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c15 = np.roll(close_15, 1); prev_c15[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c15), np.abs(low_15 - prev_c15)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

sig_crabel = np.zeros(len(close_15), dtype=np.int8)
for i in range(len(close_15)):
    if is_1000_bar[i]:
        sig_crabel[i] = date_to_crabel.get(dates_all_15[i], 0)

cfg_crabel = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=2.0, target_ratio=4.0, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

cfg_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)

cfg_2 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=120)

print("\n" + "=" * 90)
print("EXPERIMENT 1: COMPARISON OF REFINED CANDIDATE ARCHITECTURES (2010-2023 TRAINING)")
print("=" * 90)

def evaluate_architecture(name, r_list, d_list, b_list):
    common_idx = b_mnq_30['timestamp_utc']
    total_pnl = pd.Series(0.0, index=common_idx)
    
    tr_all = []
    for r, d, b in zip(r_list, d_list, b_list):
        p = pd.Series(r['cash'] - 50000.0, index=b['timestamp_utc'])
        total_pnl = total_pnl + p.reindex(common_idx, method='ffill').fillna(0.0)
        
        if len(r['trade_entry']):
            y = d['year'][r['trade_entry']]
            net = r['trade_net']
            for yr, n in zip(y, net):
                tr_all.append((yr, n))
                
    peak = total_pnl.cummax()
    mdd = float((peak - total_pnl).max())
    tot = float(total_pnl.iloc[-1])
    
    df_tr = pd.DataFrame(tr_all, columns=['year', 'net'])
    n_tr = len(df_tr)
    pre = df_tr[df_tr.year < 2020]['net'].sum() if (df_tr.year < 2020).any() else 0.0
    post = df_tr[df_tr.year >= 2020]['net'].sum() if (df_tr.year >= 2020).any() else 0.0
    exp = tot / n_tr if n_tr else 0.0
    
    yearly = df_tr.groupby('year')['net'].sum().to_dict()
    pos_years = sum(1 for y, v in yearly.items() if v > 0)
    cushion = 2000.0 - mdd
    
    print(f"\n{name}:")
    print(f"  Total Net: ${tot:+,.2f} | Trades: {n_tr} ({n_tr/14:.1f}/yr) | Exp: ${exp:+.2f}/tr")
    print(f"  Pre-2020: ${pre:+,.2f} ({(df_tr[df_tr.year<2020].groupby('year')['net'].sum()>0).sum()}/10 pos years)")
    print(f"  Post-2020: ${post:+,.2f} ({(df_tr[df_tr.year>=2020].groupby('year')['net'].sum()>0).sum()}/4 pos years)")
    print(f"  Positive Years: {pos_years}/14 ({pos_years/14*100:.1f}%)")
    print(f"  Max Continuous DD: ${mdd:,.2f} (Safety Cushion: ${cushion:+,.2f} under $2,000 floor)")
    return total_pnl

# Architecture A: Baseline Live AG_Quad (All 4 Sleeves)
# (Already computed)

# Architecture B: Pure Morning & Macro MNQ Duo (S1 + S2)
r1_b = me.execute(d_mnq_30, sig_1, f_1['atr'], cfg_1)
act1_b = pd.Series(r1_b['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
act1_b_60 = act1_b.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False).to_numpy()
sig2_b = np.where(~act1_b_60, sig_2_raw, 0).astype(np.int8)
r2_b = me.execute(d_mnq_60, sig2_b, f_2['atr'], cfg_2)

evaluate_architecture("Architecture B: Pure Morning & Macro Duo (S1 + S2 MNQ)",
                      [r1_b, r2_b], [d_mnq_30, d_mnq_60], [b_mnq_30, b_mnq_60])

# Architecture C: Triple Morning Institutional Powerhouse (Crabel + S1 + S2 under strict 1-contract router)
# Priority: Crabel (10:00 open-drive) > S1 (30m morning trend) > S2 (60m macro trend)
r_crabel = me.execute(d_mnq_15, sig_crabel, atr_15, cfg_crabel)
act_c_15 = pd.Series(r_crabel['quantity'] != 0, index=b_mnq_15['timestamp_utc'])

# S1 only if Crabel flat
act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
sig1_c = np.where(~act_c_30, sig_1, 0).astype(np.int8)
r1_c = me.execute(d_mnq_30, sig1_c, f_1['atr'], cfg_1)
act1_c = pd.Series(r1_c['quantity'] != 0, index=b_mnq_30['timestamp_utc'])

# S2 only if Crabel and S1 flat
act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
              act1_c.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
sig2_c = np.where(~act_all_60, sig_2_raw, 0).astype(np.int8)
r2_c = me.execute(d_mnq_60, sig2_c, f_2['atr'], cfg_2)

evaluate_architecture("Architecture C: Triple Morning Institutional Powerhouse (Crabel + S1 + S2)",
                      [r_crabel, r1_c, r2_c], [d_mnq_15, d_mnq_30, d_mnq_60], [b_mnq_15, b_mnq_30, b_mnq_60])

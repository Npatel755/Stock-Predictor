"""Forensic Failure Analysis & MAE/MFE Diagnostics: 2010-2023 Training Data ONLY.
Skills Applied: failure-learning, trade-edge-attribution, execution-optimization.
Strictly zero access to Validation (2024-2025) or Test (2026).
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

print("Loading STRICTLY 2010-2023 Training Bars for Forensic Failure Analysis...", flush=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

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

# Crabel calculations
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

# Drive condition
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

print("\nExecuting router and extracting all trade diagnostics...", flush=True)
r_c = me.execute(d_mnq_15, sig_crabel, atr_15, cfg_c)
act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])

act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
sig_1_routed = np.where(~act_c_30, sig_1_raw, 0).astype(np.int8)
r_1 = me.execute(d_mnq_30, sig_1_routed, f_1['atr'], cfg_1)
act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])

act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
              act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
sig_2_routed = np.where(~act_all_60, sig_2_raw, 0).astype(np.int8)
r_2 = me.execute(d_mnq_60, sig_2_routed, f_2['atr'], cfg_2)

# Collect all trades
all_trades = []
for name, r, d, b in [('Crabel', r_c, d_mnq_15, b_mnq_15), 
                      ('30m_Trend', r_1, d_mnq_30, b_mnq_30), 
                      ('60m_Trend', r_2, d_mnq_60, b_mnq_60)]:
    entries = r['trade_entry']
    exits = r['trade_exit']
    nets = r['trade_net']
    sides = r['trade_side']
    for en, ex, n, s in zip(entries, exits, nets, sides):
        yr = d['year'][en]
        ep = d['open'][en]
        xp = d['close'][ex]
        bars_held = ex - en
        all_trades.append({
            'sleeve': name, 'year': int(yr), 'net': float(n),
            'side': int(s), 'bars_held': int(bars_held),
            'entry_idx': int(en), 'exit_idx': int(ex),
            'entry_price': float(ep), 'exit_price': float(xp)
        })

df_t = pd.DataFrame(all_trades)
print(f"Total trades analyzed on Training data: {len(df_t)}")

print("\n" + "=" * 90)
print("DIAGNOSTIC 1: ROOT CAUSE OF 2010, 2011, 2013 LOSSES")
print("=" * 90)
for yr in [2010, 2011, 2012, 2013]:
    sub = df_t[df_t.year == yr]
    sub_l = sub[sub.side == 1]
    sub_s = sub[sub.side == -1]
    crabel_net = sub[sub.sleeve == 'Crabel']['net'].sum()
    s1_net = sub[sub.sleeve == '30m_Trend']['net'].sum()
    s2_net = sub[sub.sleeve == '60m_Trend']['net'].sum()
    print(f"Year {yr}: Net = ${sub['net'].sum():+7.2f} ({len(sub):3d} tr) | Longs: ${sub_l['net'].sum():+7.2f} ({len(sub_l):2d} tr) | Shorts: ${sub_s['net'].sum():+7.2f} ({len(sub_s):2d} tr)")
    print(f"         Sleeves -> Crabel: ${crabel_net:+7.2f} | 30m Trend: ${s1_net:+7.2f} | 60m Trend: ${s2_net:+7.2f}")

print("\n" + "=" * 90)
print("DIAGNOSTIC 2: SLEEVE 2 (30m) & SLEEVE 3 (60m) CONTRIBUTION ACROSS ALL YEARS")
print("=" * 90)
for s in ['Crabel', '30m_Trend', '60m_Trend']:
    sub = df_t[df_t.sleeve == s]
    pre = sub[sub.year < 2020]['net'].sum()
    post = sub[sub.year >= 2020]['net'].sum()
    print(f"Sleeve {s:<10}: Total = ${sub['net'].sum():+9.2f} ({len(sub):4d} tr, ${sub['net'].mean():+5.2f}/tr) | Pre-2020: ${pre:+8.2f} | Post-2020: ${post:+9.2f}")

print("\n" + "=" * 90)
print("DIAGNOSTIC 3: SHORT-SIDE ABLATION (TRAIN 2010-2023)")
print("=" * 90)
# What if Shorts in Sleeve 2 & 3 are filtered out, or given a tighter stop?
for mode in ['all_trades', 'long_only_s1_s2_s3', 'long_only_trend_sleeves']:
    if mode == 'all_trades':
        sub = df_t
    elif mode == 'long_only_s1_s2_s3':
        sub = df_t[df_t.side == 1]
    elif mode == 'long_only_trend_sleeves':
        # Crabel can be long or short; Sleeve 2 & 3 long only
        sub = df_t[(df_t.sleeve == 'Crabel') | (df_t.side == 1)]
    
    pre = sub[sub.year < 2020]['net'].sum()
    post = sub[sub.year >= 2020]['net'].sum()
    tot = sub['net'].sum()
    exp = tot / len(sub) if len(sub) else 0
    print(f"Mode '{mode:<25}': Net = ${tot:+9.2f} | Tr: {len(sub):4d} | Exp: ${exp:+5.2f}/tr | Pre: ${pre:+8.2f} | Post: ${post:+9.2f}")

"""Audit of Unified 5-Sleeve Portfolio under Strict 1-Contract Router (2010-2026).
Sleeves:
1. MNQ 30m Morning Trend (lb16, th0.75, 10:00-12:00 ET) [Live Quad Sleeve 1]
2. MNQ 60m Macro Trend (lb12, th0.75, 10:00-12:00 ET) [Live Quad Sleeve 2]
3. MNQ 30m Afternoon Trend (lb8, th0.50, 13:30-15:15 ET) [Live Quad Sleeve 3]
4. MNQ/ES Cross-Asset Momentum (10:00 ET opening spread z >= 0.75) [New Discovery]
5. MES 30m Trend (lb8, th1.0, 09:45-15:30 ET) [Live Quad Sleeve 4]

Strict 1-contract maximum limit across entire account at all times.
Evaluated across:
- Pre-2020 Decade (2010-2019, 10 Years)
- Post-2020 Train (2020-2023, 4 Years)
- Validation (2024-2025, 2 Years)
- Sealed Test (2026, 11 Months)
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
b_mnq_30 = load_continuous('NQ', '30 minutes')
b_mnq_60 = load_continuous('NQ', '60 minutes')
b_mes_15 = load_continuous('ES', '15 minutes')
b_mes_30 = load_continuous('ES', '30 minutes')

# Common arrays
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

# Sleeve 1: MNQ 30m Morning Trend (lb16)
f_mnq_30_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1 = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_mnq_30_1['trend']) >= 0.75), np.sign(f_mnq_30_1['trend']), 0).astype(np.int8)
cfg_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.5, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)
r_1 = me.execute(d_mnq_30, sig_1, f_mnq_30_1['atr'], cfg_1)

# Sleeve 2: MNQ 60m Macro Trend (lb12) - only if Sleeve 1 is flat
act_1 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc']).reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False).to_numpy()
f_mnq_60_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2 = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (~act_1) & (np.abs(f_mnq_60_2['trend']) >= 0.75), np.sign(f_mnq_60_2['trend']), 0).astype(np.int8)
cfg_2 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=120)
r_2 = me.execute(d_mnq_60, sig_2, f_mnq_60_2['atr'], cfg_2)

# Build active morning position series on 15m index
s_q1_15 = pd.Series(r_1['quantity'], index=b_mnq_30['timestamp_utc']).reindex(b_mnq_15['timestamp_utc'], method='ffill').fillna(0)
s_q2_15 = pd.Series(r_2['quantity'], index=b_mnq_60['timestamp_utc']).reindex(b_mnq_15['timestamp_utc'], method='ffill').fillna(0)
act_morning_15 = (s_q1_15 != 0) | (s_q2_15 != 0)

# Sleeve 3: MNQ/ES Cross-Asset Momentum (10:00 ET, z >= 0.75) - only fires if morning sleeves are flat
# Compute spread
loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
rth_mnq = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)

loc_mes_15 = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes_15.dt.hour * 60 + loc_mes_15.dt.minute
b_mes_15['date'] = loc_mes_15.dt.date
rth_mes = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)

g_mnq = rth_mnq.groupby('date')
g_mes = rth_mes.groupby('date')
o930_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
o930_mes = g_mes.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mes = g_mes.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
common_days = sorted(list(set(o930_mnq.dropna().index).intersection(set(o930_mes.dropna().index))))
df_days = pd.DataFrame(index=common_days)
df_days['spread'] = (c1000_mnq.loc[common_days] / o930_mnq.loc[common_days]) - (c1000_mes.loc[common_days] / o930_mes.loc[common_days])
df_days['spread_z'] = df_days['spread'] / df_days['spread'].rolling(20, min_periods=20).std().shift(1)
date_to_z = df_days['spread_z'].to_dict()

dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
z_arr_15 = np.array([date_to_z.get(d, 0.0) for d in loc_15.dt.date])

d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c15 = np.roll(close_15, 1); prev_c15[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c15), np.abs(low_15 - prev_c15)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

is_1000_bar = (dec_15 == 600) & weekdays_15
sig_3 = np.zeros(len(close_15), dtype=np.int8)
# Enter ONLY if morning sleeves 1 and 2 are flat:
sig_3[is_1000_bar & (~act_morning_15.to_numpy()) & (z_arr_15 >= 1.0)] = 1
sig_3[is_1000_bar & (~act_morning_15.to_numpy()) & (z_arr_15 <= -1.0)] = -1

cfg_3 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=2.0, target_ratio=4.0, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)
r_3 = me.execute(d_mnq_15, sig_3, atr_15, cfg_3)

# Build active position series for MNQ morning + cross-asset
s_q3_30 = pd.Series(r_3['quantity'], index=b_mnq_15['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0)
act_1_30 = (r_1['quantity'] != 0) | (pd.Series(r_2['quantity'], index=b_mnq_60['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0) != 0)
act_before_afternoon = act_1_30 | (s_q3_30 != 0)

# Sleeve 4: MNQ 30m Afternoon Trend (lb8, 13:30-15:15 ET)
f_mnq_30_aft = compute_htf_features(b_mnq_30, 8, 30)
sig_4 = np.where((dec_30 >= 810) & (dec_30 < 915) & weekdays_30 & (~act_before_afternoon) & 
                 (np.abs(f_mnq_30_aft['trend']) >= 0.50), np.sign(f_mnq_30_aft['trend']), 0).astype(np.int8)
cfg_4 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.5, target_ratio=4.0, hold_bars=4, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)
r_4 = me.execute(d_mnq_30, sig_4, f_mnq_30_aft['atr'], cfg_4)

# Build active position across all MNQ sleeves
act_all_mnq_30 = act_before_afternoon | (r_4['quantity'] != 0)
act_all_mnq_mes = pd.Series(act_all_mnq_30.values, index=b_mnq_30['timestamp_utc']).reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()

# Sleeve 5: MES 30m Trend (lb8, 09:45-15:30 ET) - fires ONLY when all MNQ sleeves are flat
f_mes_30 = compute_htf_features(b_mes_30, 8, 30)
sig_5 = np.where((dec_mes_30 >= 585) & (dec_mes_30 < 930) & weekdays_mes_30 & (~act_all_mnq_mes) & 
                 (np.abs(f_mes_30['trend']) >= 1.0), np.sign(f_mes_30['trend']), 0).astype(np.int8)
cfg_5 = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
             stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)
r_5 = me.execute(d_mes_30, sig_5, f_mes_30['atr'], cfg_5)

# Reindex all cash curves to common 15m index
p1 = pd.Series(r_1['cash'] - r_1['cash'][0], index=b_mnq_30['timestamp_utc']).reindex(b_mnq_15['timestamp_utc'], method='ffill').fillna(0.0)
p2 = pd.Series(r_2['cash'] - r_2['cash'][0], index=b_mnq_60['timestamp_utc']).reindex(b_mnq_15['timestamp_utc'], method='ffill').fillna(0.0)
p3 = pd.Series(r_3['cash'] - r_3['cash'][0], index=b_mnq_15['timestamp_utc'])
p4 = pd.Series(r_4['cash'] - r_4['cash'][0], index=b_mnq_30['timestamp_utc']).reindex(b_mnq_15['timestamp_utc'], method='ffill').fillna(0.0)
p5 = pd.Series(r_5['cash'] - r_5['cash'][0], index=b_mes_30['timestamp_utc']).reindex(b_mnq_15['timestamp_utc'], method='ffill').fillna(0.0)

# Combined 5-Sleeve Portfolio
port_5 = p1 + p2 + p3 + p4 + p5
peak_5 = port_5.cummax()
dd_5 = peak_5 - port_5
max_dd_5 = float(dd_5.max())
tot_net_5 = float(port_5.iloc[-1])

# Yearly
df_curve = pd.DataFrame({'p': port_5, 'year': port_5.index.year})
yearly = {}
for y in sorted(df_curve['year'].dropna().unique()):
    sub = df_curve[df_curve['year'] == y]['p']
    if len(sub) == 0: continue
    yearly[int(y)] = float(sub.iloc[-1] - sub.iloc[0])

pre_2020 = sum(yearly[y] for y in sorted(yearly.keys()) if y < 2020)
train_2020 = sum(yearly[y] for y in [2020, 2021, 2022, 2023])
val_net = sum(yearly[y] for y in [2024, 2025])
test_net = yearly[2026]

# Trade counts
all_tr_y = list(d_mnq_30['year'][r_1['trade_entry']]) + list(d_mnq_60['year'][r_2['trade_entry']]) + \
           list(d_mnq_15['year'][r_3['trade_entry']]) + list(d_mnq_30['year'][r_4['trade_entry']]) + \
           list(d_mes_30['year'][r_5['trade_entry']])
all_tr_y = np.array(all_tr_y)

cnt_pre = int(np.count_nonzero(all_tr_y < 2020))
cnt_train = int(np.count_nonzero((all_tr_y >= 2020) & (all_tr_y < 2024)))
cnt_val = int(np.count_nonzero((all_tr_y >= 2024) & (all_tr_y < 2026)))
cnt_test = int(np.count_nonzero(all_tr_y == 2026))
tot_tr = len(all_tr_y)

pos_years = sum(1 for y in yearly if yearly[y] > 0)
tot_years = len(yearly)
cushion = 2000.0 - max_dd_5
status = "SAFE (PASSED)" if max_dd_5 < 2000.0 else "BREACHED"

print("\n" + "=" * 95)
print("UNIFIED 5-SLEEVE INSTITUTIONAL PORTFOLIO (2010-2026)")
print("AG_Quad + NQ/ES Cross-Asset Momentum under Strict 1-Contract Router")
print("=" * 95)
print(f"16-Year Total Net Profit:   +${tot_net_5:,.2f} across {tot_tr} trades (Exp: +${tot_net_5/tot_tr:.2f}/tr)")
print(f"16-Year Max Drawdown:       ${max_dd_5:,.2f} (Cushion: +${cushion:,.2f} under $2,000 floor) -> {status}")
print(f"Positive Years:             {pos_years}/{tot_years} years ({pos_years/tot_years*100:.1f}%)")
print("-" * 95)
print(f"  Pre-2020 Era (2010-2019, 10Y): +${pre_2020:8.2f} | {cnt_pre:3d} trades | Exp: +${pre_2020/cnt_pre:5.2f}/tr")
print(f"  Post-2020 Train (2020-2023, 4Y):+${train_2020:8.2f} | {cnt_train:3d} trades | Exp: +${train_2020/cnt_train:5.2f}/tr")
print(f"  Validation (2024-2025, 2Y):     +${val_net:8.2f} | {cnt_val:3d} trades | Exp: +${val_net/cnt_val:5.2f}/tr")
print(f"  Sealed Test (2026, 11 Months):  +${test_net:8.2f} | {cnt_test:3d} trades | Exp: +${test_net/cnt_test:5.2f}/tr")
print("-" * 95)
print("Yearly P&L Breakdown:")
for y in sorted(yearly.keys()):
    tag = "TRAIN" if y < 2024 else ("VAL" if y < 2026 else "TEST")
    win_loss = "WIN" if yearly[y] > 0 else "LOSS"
    print(f"  {y} ({tag:<5}): +${yearly[y]:8.2f} | {win_loss}")

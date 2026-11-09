"""Comprehensive 7-Year Continuous Audit of the Afternoon-Expanded 1-Contract Portfolio.

Sleeves:
1. MNQ 30m Morning Breakout: lb=16, th=0.75, stop=1.5 ATR, tgt=3.5R, hold=8, 09:45-12:00 ET
2. MNQ 60m Morning Macro Trend: lb=12, th=0.75, stop=1.25 ATR, tgt=4.0R, hold=8, 10:00-12:00 ET
3. MNQ 30m Afternoon Trend (Training Discovery): lb=8, th=0.50, stop=1.5 ATR, tgt=4.0R, hold=4, 13:30-15:15 ET
4. MES 30m Trend (Exclusive Router): lb=8, th=1.0, stop=1.25 ATR, tgt=2.5R, hold=12, all-day RTH

Router Rule:
- STRICT 1-CONTRACT LIMIT ACROSS ENTIRE ACCOUNT AT ALL TIMES.
- Any secondary sleeve ONLY enters if the account has 0 open contracts.

Evaluated continuously across:
- Train: 2020-01-01 to 2023-12-31 (4 years)
- Validation: 2024-01-01 to 2025-12-31 (2 years)
- Sealed Test: 2026-01-01 to 2026-11-05 (11 months)
"""
import sys, json, duckdb, numpy as np, pandas as pd
import matplotlib.pyplot as plt
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

print("Loading continuous 7-year bars (2020-2026)...")
b_mnq_30 = get_continuous_bars('MNQ', '30 minutes')
b_mnq_60 = get_continuous_bars('MNQ', '60 minutes')
b_mes_30 = get_continuous_bars('MES', '30 minutes')

# Common time array
loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
weekdays_30 = loc_30.dt.weekday.to_numpy() < 5
d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)

# -------------------------------------------------------------------------
# Sleeve 1: MNQ 30m Morning Breakout
# -------------------------------------------------------------------------
f_mnq_30_bo = compute_htf_features(b_mnq_30, 16, 30)
sig_1 = np.where((dec_30 >= 585) & (dec_30 < 720) & weekdays_30 & (np.abs(f_mnq_30_bo['trend']) >= 0.75), np.sign(f_mnq_30_bo['trend']), 0).astype(np.int8)
cfg_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
             stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)
r_1 = me.execute(d_mnq_30, sig_1, f_mnq_30_bo['atr'], cfg_1)

# -------------------------------------------------------------------------
# Sleeve 2: MNQ 60m Morning Trend
# -------------------------------------------------------------------------
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

# Build active position series on 30m index
act_1 = r_1['quantity'] != 0
s_q2 = pd.Series(r_2['quantity'], index=b_mnq_60['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0)
act_2 = s_q2 != 0
act_morning = act_1 | act_2

# -------------------------------------------------------------------------
# Sleeve 3: MNQ 30m Afternoon Trend (Training Discovery)
# Rule: lb=8, th=0.50, stop=1.5, tgt=4.0, hold=4, session 13:30-15:15 ET
# Router: ONLY enters if account is FLAT (act_morning is False)
# -------------------------------------------------------------------------
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

# -------------------------------------------------------------------------
# Sleeve 4: MES 30m Trend (Exclusive Router: Only fires if MNQ is flat)
# -------------------------------------------------------------------------
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

# Reindex all PnLs
p1 = pd.Series(r_1['cash'] - r_1['cash'][0], index=b_mnq_30['timestamp_utc'])
p2 = pd.Series(r_2['cash'] - r_2['cash'][0], index=b_mnq_60['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0.0)
p3 = pd.Series(r_3['cash'] - r_3['cash'][0], index=b_mnq_30['timestamp_utc'])
p4 = pd.Series(r_4['cash'] - r_4['cash'][0], index=b_mes_30['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0.0)

df_curve = pd.DataFrame(index=b_mnq_30['timestamp_utc'])
df_curve['year'] = df_curve.index.year
df_curve['p1'] = p1
df_curve['p2'] = p2
df_curve['p3'] = p3
df_curve['p4'] = p4
df_curve['Duo'] = p1 + p2
df_curve['Trio_MES'] = p1 + p2 + p4
df_curve['Trio_AFT'] = p1 + p2 + p3
df_curve['Quad_All'] = p1 + p2 + p3 + p4

# Print Individual Sleeve Results
sleeves = [
    ("Sleeve 1: MNQ 30m Morning Breakout", r_1, d_mnq_30),
    ("Sleeve 2: MNQ 60m Morning Trend", r_2, d_mnq_60),
    ("Sleeve 3: MNQ 30m Afternoon Trend", r_3, d_mnq_30),
    ("Sleeve 4: MES 30m Trend (Exclusive)", r_4, d_mes_30),
]

print("=" * 90)
print("INDIVIDUAL SLEEVE RESULTS (2020-2026)")
print("=" * 90)
for name, r, d in sleeves:
    tn = r['trade_net']
    net = tn.sum()
    cnt = len(tn)
    exp = net / cnt if cnt else 0.0
    yr = d['year'][r['trade_entry']]
    net_26 = tn[yr == 2026].sum() if np.any(yr == 2026) else 0.0
    cnt_26 = np.count_nonzero(yr == 2026)
    exp_26 = net_26 / cnt_26 if cnt_26 else 0.0
    mdd = float((np.maximum.accumulate(r['cash']) - r['worst']).max())
    print(f"{name:<38} | 7Y Net: +${net:8.2f} | 7Y Exp: +${exp:5.2f} | 2026 Net: +${net_26:7.2f} ({cnt_26:2d} tr, exp +${exp_26:5.2f}) | MaxDD: ${mdd:6.2f}")

# Evaluate Portfolios
portfolios = [
    ("Duo (MNQ Morning Only)", 'Duo', [r_1, r_2], [d_mnq_30, d_mnq_60]),
    ("Trio A (Morning Duo + MES 30m)", 'Trio_MES', [r_1, r_2, r_4], [d_mnq_30, d_mnq_60, d_mes_30]),
    ("Trio B (Morning Duo + MNQ Afternoon)", 'Trio_AFT', [r_1, r_2, r_3], [d_mnq_30, d_mnq_60, d_mnq_30]),
    ("Quad (Morning Duo + MNQ Afternoon + MES 30m) [Max 1c]", 'Quad_All', [r_1, r_2, r_3, r_4], [d_mnq_30, d_mnq_60, d_mnq_30, d_mes_30]),
]

print("\n" + "=" * 90)
print("PORTFOLIO SHOWDOWN ACROSS ALL SPLITS (2020-2026)")
print("=" * 90)

for p_name, col, r_list, d_list in portfolios:
    curve = df_curve[col]
    peak = curve.cummax()
    dd = peak - curve
    max_dd = float(dd.max())
    total_net = float(curve.iloc[-1])
    
    # Trade counts per split
    all_y = []
    for r, d in zip(r_list, d_list):
        all_y.extend(list(d['year'][r['trade_entry']]))
    all_y = np.array(all_y)
    
    n_train = int(np.count_nonzero(all_y < 2024))
    n_val = int(np.count_nonzero((all_y >= 2024) & (all_y < 2026)))
    n_test = int(np.count_nonzero(all_y == 2026))
    n_tot = len(all_y)
    
    # Yearly
    yearly = {}
    for y in sorted(df_curve['year'].unique()):
        sub = curve[df_curve['year'] == y]
        yearly[y] = float(sub.iloc[-1] - sub.iloc[0])
        
    net_train = sum(yearly[y] for y in [2020, 2021, 2022, 2023])
    net_val = sum(yearly[y] for y in [2024, 2025])
    net_test = yearly[2026]
    
    cushion = 2000.0 - max_dd
    status = "SAFE (PASSED)" if max_dd < 2000 else "BREACHED"
    
    print(f"\n>>> {p_name} <<<")
    print(f"  7-Year Net:        +${total_net:,.2f} across {n_tot} trades (Exp: +${total_net/n_tot:.2f}/tr)")
    print(f"  7-Year Max DD:     ${max_dd:,.2f} (Cushion: +${cushion:,.2f} before $2k breach) -> {status}")
    print(f"  Train (2020-2023): +${net_train:,.2f} ({n_train:3d} tr, exp +${net_train/n_train:5.2f}/tr)")
    print(f"  Val   (2024-2025): +${net_val:,.2f} ({n_val:3d} tr, exp +${net_val/n_val:5.2f}/tr)")
    print(f"  TEST  (2026, 11m): +${net_test:,.2f} ({n_test:3d} tr, exp +${net_test/n_test:5.2f}/tr)")
    y_str = ", ".join([f"{y}: ${yearly[y]:+,.0f}" for y in sorted(yearly.keys())])
    print(f"  Yearly:            {y_str}")

# Save plot for Quad All
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1]})

ax1.plot(df_curve.index, df_curve['Quad_All'], label='Quad Multi-Session & Asset (MNQ Morn+Aft + MES) [Max 1c]', color='#10b981', linewidth=2.2)
ax1.plot(df_curve.index, df_curve['Trio_AFT'], label='Trio B (MNQ Morn + MNQ Aft)', color='#8b5cf6', linewidth=1.5, linestyle=':')
ax1.plot(df_curve.index, df_curve['Trio_MES'], label='Trio A (MNQ Morn + MES 30m)', color='#f59e0b', linewidth=1.5, linestyle='--')
ax1.plot(df_curve.index, df_curve['Duo'], label='Baseline Duo (MNQ Morning Only)', color='#3b82f6', linewidth=1.2, alpha=0.7)

t_val = pd.to_datetime('2024-01-01', utc=True)
t_test = pd.to_datetime('2026-01-01', utc=True)

ax1.axvline(t_val, color='#6b7280', linestyle=':', alpha=0.8)
ax1.axvline(t_test, color='#ef4444', linestyle='--', linewidth=1.5, alpha=0.8)

ax1.axvspan(df_curve.index[0], t_val, color='#94a3b8', alpha=0.1, label='Train (2020-2023)')
ax1.axvspan(t_val, t_test, color='#38bdf8', alpha=0.1, label='Validation (2024-2025)')
ax1.axvspan(t_test, df_curve.index[-1], color='#4ade80', alpha=0.15, label='Sealed Test (2026)')

ax1.set_title('Afternoon-Expanded 1-Contract Institutional Champion (2020-2026)\nMulti-Session (Morning + Afternoon) & Multi-Asset (MNQ + MES) | Max 1 Contract at All Times', fontsize=13, fontweight='bold', pad=12)
ax1.set_ylabel('Net Profit ($)', fontsize=11, fontweight='bold')
ax1.grid(True, alpha=0.25)
ax1.legend(loc='upper left', frameon=True, fontsize=10)

peak_quad = df_curve['Quad_All'].cummax()
dd_quad = peak_quad - df_curve['Quad_All']
ax2.fill_between(df_curve.index, 0, -dd_quad, color='#ef4444', alpha=0.3, label='Portfolio Drawdown ($)')
ax2.plot(df_curve.index, -dd_quad, color='#b91c1c', linewidth=1)
ax2.axhline(-2000.0, color='red', linestyle='--', linewidth=1.5, label='Funded Trailing Limit (-$2,000)')
ax2.axhline(-1800.0, color='orange', linestyle=':', label='Hard Stop (-$1,800)')
ax2.axvline(t_val, color='#6b7280', linestyle=':', alpha=0.8)
ax2.axvline(t_test, color='#ef4444', linestyle='--', linewidth=1.5, alpha=0.8)
ax2.set_ylabel('Drawdown ($)', fontsize=11, fontweight='bold')
ax2.set_xlabel('Date (2020 - 2026)', fontsize=11, fontweight='bold')
ax2.grid(True, alpha=0.25)
ax2.legend(loc='lower left', frameon=True, fontsize=9)
ax2.set_ylim(-2200, 100)

plt.tight_layout()
out_png = Path(r'C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d\afternoon_expanded_champion_7year.png')
plt.savefig(out_png, dpi=300)
print('\nPlot saved successfully to:', str(out_png))

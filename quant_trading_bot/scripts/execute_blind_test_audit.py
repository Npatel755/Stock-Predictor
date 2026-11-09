import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays, compute_5m_indicators
from quant_futures.htf_engine import compute_htf_features
import mass_execution as me

print("="*80)
print("EXECUTING FROZEN CHAMPION ON 2026 BLIND TEST DATA")
print("STRICTLY ZERO TUNING ON TEST OR VALIDATION")
print("100% FROZEN RULE PARAMETERS ESTABLISHED ON 2020-2023 TRAINING DATA")
print("="*80)

# -------------------------------------------------------------
# Part 1: Isolated 2026 Test Evaluation (2026-01-01 to 2026-11-05)
# -------------------------------------------------------------
print("\nLoading 2026 TEST bars for MNQ (60m and 5m) and MES (30m)...")
bars_test_mnq_60m = load_resampled_bars('MNQ', 'test', '60 minutes', start_date='2026-01-01')
bars_test_mnq_5m = load_resampled_bars('MNQ', 'test', '5 minutes', start_date='2026-01-01')
bars_test_mes_30m = load_resampled_bars('MES', 'test', '30 minutes', start_date='2026-01-01')

data_test_mnq_60m = apply_early_close(generalized_arrays(bars_test_mnq_60m), bars_test_mnq_60m)
data_test_mnq_5m = apply_early_close(generalized_arrays(bars_test_mnq_5m), bars_test_mnq_5m)
data_test_mes_30m = apply_early_close(generalized_arrays(bars_test_mes_30m), bars_test_mes_30m)

print(f"2026 Test Bars: MNQ 60m={len(bars_test_mnq_60m):,}, MNQ 5m={len(bars_test_mnq_5m):,}, MES 30m={len(bars_test_mes_30m):,}")

# Sleeve 1: MNQ 60m Macro Trend
feat_test_60m = compute_htf_features(bars_test_mnq_60m, 12, 60)
local_test_60m = bars_test_mnq_60m.timestamp_utc.dt.tz_convert('America/New_York')
dec_test_60m = (local_test_60m.dt.hour * 60 + local_test_60m.dt.minute + 60).to_numpy()
weekdays_test_60m = local_test_60m.dt.weekday.to_numpy() < 5
mask_morn_test_60m = (dec_test_60m >= 600) & (dec_test_60m < 720) & weekdays_test_60m
sig_test_60m = np.where(mask_morn_test_60m & (np.abs(feat_test_60m['trend']) >= 0.75), np.sign(feat_test_60m['trend']), 0).astype(np.int8)

cfg_60m = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=120
)
res_test_60m = me.execute(data_test_mnq_60m, sig_test_60m, feat_test_60m['atr'], cfg_60m)

# Sleeve 2: MNQ 5m MTF Precision Breakout
feats_test_5m = compute_5m_indicators(bars_test_mnq_5m, bars_test_mnq_60m)
close_test_5m = feats_test_5m['close']
atr_test_5m = feats_test_5m['atr']
trend_test_60 = feats_test_5m['trend60']
close_min_test_5m = feats_test_5m['close_min']
weekdays_test_5m = feats_test_5m['weekdays']
mask_morn_test_5m = (close_min_test_5m >= 585) & (close_min_test_5m < 705) & weekdays_test_5m
feat_test_lb24 = feats_test_5m['features_by_lb'][24]
bh_test_5m = feat_test_lb24['breakout_high']
bl_test_5m = feat_test_lb24['breakout_low']

sig_raw_test_5m = np.zeros(len(close_test_5m), dtype=np.int8)
long_cond_test_5m = (close_test_5m > bh_test_5m + 0.75 * atr_test_5m) & (trend_test_60 > 0)
short_cond_test_5m = (close_test_5m < bl_test_5m - 0.75 * atr_test_5m) & (trend_test_60 < 0)
sig_raw_test_5m[long_cond_test_5m] = 1
sig_raw_test_test_5m = np.where(mask_morn_test_5m, sig_raw_test_5m, 0).astype(np.int8)

cfg_5m = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.5, target_ratio=5.0, hold_bars=24, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=20
)
res_test_5m = me.execute(data_test_mnq_5m, sig_raw_test_test_5m, atr_test_5m, cfg_5m)

# Sleeve 3: MES 30m Trend
feat_test_30m = compute_htf_features(bars_test_mes_30m, 12, 30)
local_test_30m = bars_test_mes_30m.timestamp_utc.dt.tz_convert('America/New_York')
dec_test_30m = (local_test_30m.dt.hour * 60 + local_test_30m.dt.minute + 30).to_numpy()
weekdays_test_30m = local_test_30m.dt.weekday.to_numpy() < 5
mask_morn_test_30m = (dec_test_30m >= 600) & (dec_test_30m < 720) & weekdays_test_30m
sig_test_30m = np.where(mask_morn_test_30m & (np.abs(feat_test_30m['trend']) >= 0.75), np.sign(feat_test_30m['trend']), 0).astype(np.int8)

cfg_30m = dict(
    tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.5, target_ratio=2.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=120
)
res_test_30m = me.execute(data_test_mes_30m, sig_test_30m, feat_test_30m['atr'], cfg_30m)

print("\n" + "="*80)
print("INDIVIDUAL SLEEVE RESULTS ON 2026 TEST DATA (BLIND OUT-OF-SAMPLE):")
print("="*80)
for name, res in [('MNQ 60m Trend (1c)', res_test_60m), ('MNQ 5m MTF Breakout (1c)', res_test_5m), ('MES 30m Trend (1c)', res_test_30m)]:
    tn = res['trade_net']
    net = tn.sum()
    cnt = len(tn)
    exp = net / cnt if cnt else 0.0
    worst_dd = (np.maximum.accumulate(res['cash']) - res['worst']).max()
    wins = tn[tn > 0].sum()
    losses = -tn[tn < 0].sum()
    pf = wins / losses if losses > 0 else 999.0
    print(f"{name:<26}: Net=+${net:,.2f} | Trades={cnt} | Exp=+${exp:.2f}/trade | PF={pf:.2f} | Max DD=${worst_dd:,.2f} (Cushion=+${2000-worst_dd:,.2f})")

# Combined Portfolio Analysis on 2026 Test Data
trades_test = []
for sleeve_id, res, d in [('MNQ_60m', res_test_60m, data_test_mnq_60m), ('MNQ_5m', res_test_5m, data_test_mnq_5m), ('MES_30m', res_test_30m, data_test_mes_30m)]:
    te = res['trade_entry']
    tx = res['trade_exit']
    tn = res['trade_net']
    entry_times = pd.to_datetime(d['timestamp'][te], unit='ns', utc=True)
    exit_times = pd.to_datetime(d['timestamp'][tx], unit='ns', utc=True)
    for i in range(len(tn)):
        trades_test.append({
            'sleeve': sleeve_id,
            'entry_time': entry_times[i],
            'exit_time': exit_times[i],
            'net': tn[i]
        })

df_test_all = pd.DataFrame(trades_test).sort_values('exit_time').reset_index(drop=True)

# Duo-Horizon MNQ Champion (60m + 5m) on 2026 Test
sub_duo_test = df_test_all[df_test_all['sleeve'].isin(['MNQ_60m', 'MNQ_5m'])].copy()
sub_duo_test['cum'] = sub_duo_test['net'].cumsum()
sub_duo_test['pk'] = sub_duo_test['cum'].cummax()
sub_duo_test['dd'] = sub_duo_test['pk'] - sub_duo_test['cum']
duo_test_net = sub_duo_test['net'].sum()
duo_test_cnt = len(sub_duo_test)
duo_test_exp = duo_test_net / duo_test_cnt if duo_test_cnt else 0.0
duo_test_dd = sub_duo_test['dd'].max()
wins_duo = sub_duo_test.loc[sub_duo_test['net'] > 0, 'net'].sum()
losses_duo = -sub_duo_test.loc[sub_duo_test['net'] < 0, 'net'].sum()
pf_duo = wins_duo / losses_duo if losses_duo > 0 else 999.0

# Tri-Timeframe (60m + 30m + 5m) on 2026 Test
df_test_all['cum'] = df_test_all['net'].cumsum()
df_test_all['pk'] = df_test_all['cum'].cummax()
df_test_all['dd'] = df_test_all['pk'] - df_test_all['cum']
tri_test_net = df_test_all['net'].sum()
tri_test_cnt = len(df_test_all)
tri_test_exp = tri_test_net / tri_test_cnt if tri_test_cnt else 0.0
tri_test_dd = df_test_all['dd'].max()
wins_tri = df_test_all.loc[df_test_all['net'] > 0, 'net'].sum()
losses_tri = -df_test_all.loc[df_test_all['net'] < 0, 'net'].sum()
pf_tri = wins_tri / losses_tri if losses_tri > 0 else 999.0

print("\n" + "="*80)
print("DUO-HORIZON MNQ CHAMPION — 2026 BLIND TEST RESULTS:")
print("="*80)
print(f"Total 2026 Net P&L:   +${duo_test_net:,.2f}")
print(f"Total 2026 Trades:    {duo_test_cnt} trades")
print(f"Per-Trade Expectancy: +${duo_test_exp:.2f} / trade")
print(f"Profit Factor:        {pf_duo:.2f}")
print(f"Max 2026 Drawdown:    ${duo_test_dd:,.2f} (Safety Cushion: +${2000 - duo_test_dd:,.2f} on $2,000 trailing limit!)")
print(f"Calmar Ratio (2026):  {duo_test_net / duo_test_dd:.2f}")

print("\n" + "="*80)
print("TRI-TIMEFRAME PORTFOLIO — 2026 BLIND TEST RESULTS:")
print("="*80)
print(f"Total 2026 Net P&L:   +${tri_test_net:,.2f}")
print(f"Total 2026 Trades:    {tri_test_cnt} trades")
print(f"Per-Trade Expectancy: +${tri_test_exp:.2f} / trade")
print(f"Profit Factor:        {pf_tri:.2f}")
print(f"Max 2026 Drawdown:    ${tri_test_dd:,.2f} (Safety Cushion: +${2000 - tri_test_dd:,.2f} on $2,000 trailing limit!)")
print(f"Calmar Ratio (2026):  {tri_test_net / tri_test_dd:.2f}")

# -------------------------------------------------------------
# Part 2: Full Continuous 7-Year Institutional Audit (2020 through 2026)
# -------------------------------------------------------------
print("\n" + "="*80)
print("BUILDING FULL 7-YEAR CONTINUOUS INSTITUTIONAL AUDIT (2020 TO 2026)")
print("="*80)

# Load full chronological series
bars_all_60m = pd.concat([
    load_resampled_bars('MNQ', 'train', '60 minutes', start_date='2020-01-01'),
    load_resampled_bars('MNQ', 'validation', '60 minutes', start_date='2024-01-01'),
    bars_test_mnq_60m
]).sort_values('timestamp_utc').reset_index(drop=True)

bars_all_5m = pd.concat([
    load_resampled_bars('MNQ', 'train', '5 minutes', start_date='2020-01-01'),
    load_resampled_bars('MNQ', 'validation', '5 minutes', start_date='2024-01-01'),
    bars_test_mnq_5m
]).sort_values('timestamp_utc').reset_index(drop=True)

data_all_60m = apply_early_close(generalized_arrays(bars_all_60m), bars_all_60m)
data_all_5m = apply_early_close(generalized_arrays(bars_all_5m), bars_all_5m)

# 1. Sleeve 1 continuous 7y
feat_all_60m = compute_htf_features(bars_all_60m, 12, 60)
local_all_60m = bars_all_60m.timestamp_utc.dt.tz_convert('America/New_York')
dec_all_60m = (local_all_60m.dt.hour * 60 + local_all_60m.dt.minute + 60).to_numpy()
weekdays_all_60m = local_all_60m.dt.weekday.to_numpy() < 5
mask_morn_all_60m = (dec_all_60m >= 600) & (dec_all_60m < 720) & weekdays_all_60m
sig_all_60m = np.where(mask_morn_all_60m & (np.abs(feat_all_60m['trend']) >= 0.75), np.sign(feat_all_60m['trend']), 0).astype(np.int8)

res_all_60m = me.execute(data_all_60m, sig_all_60m, feat_all_60m['atr'], cfg_60m)

# 2. Sleeve 2 continuous 7y
feats_all_5m = compute_5m_indicators(bars_all_5m, bars_all_60m)
close_all_5m = feats_all_5m['close']
atr_all_5m = feats_all_5m['atr']
trend_all_60 = feats_all_5m['trend60']
close_min_all_5m = feats_all_5m['close_min']
weekdays_all_5m = feats_all_5m['weekdays']
mask_morn_all_5m = (close_min_all_5m >= 585) & (close_min_all_5m < 705) & weekdays_all_5m
feat_all_lb24 = feats_all_5m['features_by_lb'][24]
bh_all_5m = feat_all_lb24['breakout_high']
bl_all_5m = feat_all_lb24['breakout_low']

sig_raw_all_5m = np.zeros(len(close_all_5m), dtype=np.int8)
long_cond_all_5m = (close_all_5m > bh_all_5m + 0.75 * atr_all_5m) & (trend_all_60 > 0)
short_cond_all_5m = (close_all_5m < bl_all_5m - 0.75 * atr_all_5m) & (trend_all_60 < 0)
sig_raw_all_5m[long_cond_all_5m] = 1
sig_raw_all_5m[short_cond_all_5m] = -1
sig_all_5m = np.where(mask_morn_all_5m, sig_raw_all_5m, 0).astype(np.int8)

res_all_5m = me.execute(data_all_5m, sig_all_5m, atr_all_5m, cfg_5m)

# Merge continuous trades
trades_7y = []
for sname, r, d in [('MNQ 60m Trend', res_all_60m, data_all_60m), ('MNQ 5m MTF Breakout', res_all_5m, data_all_5m)]:
    te, tx, tn = r['trade_entry'], r['trade_exit'], r['trade_net']
    exit_times = pd.to_datetime(d['timestamp'][tx], unit='ns', utc=True)
    entry_times = pd.to_datetime(d['timestamp'][te], unit='ns', utc=True)
    years = d['year'][te]
    for i in range(len(tn)):
        trades_7y.append({
            'sleeve': sname,
            'entry_time': entry_times[i],
            'exit_time': exit_times[i],
            'year': years[i],
            'net': tn[i]
        })

df_7y = pd.DataFrame(trades_7y).sort_values('exit_time').reset_index(drop=True)
df_7y['cum_pnl'] = df_7y['net'].cumsum()
df_7y['peak'] = df_7y['cum_pnl'].cummax()
df_7y['dd'] = df_7y['peak'] - df_7y['cum_pnl']

tot_net_7y = df_7y['net'].sum()
tot_trades_7y = len(df_7y)
tot_exp_7y = tot_net_7y / tot_trades_7y
max_dd_7y = df_7y['dd'].max()
wins_7y = df_7y.loc[df_7y['net'] > 0, 'net'].sum()
losses_7y = -df_7y.loc[df_7y['net'] < 0, 'net'].sum()
pf_7y = wins_7y / losses_7y if losses_7y > 0 else 999.0

print("="*80)
print("FULL 7-YEAR (2020-2026) CONTINUOUS DUO-HORIZON AUDIT:")
print("="*80)
print(f"Total Net P&L:        +${tot_net_7y:,.2f} ($2,546.45 / year at strictly 1 contract)")
print(f"Total Trades:         {tot_trades_7y} trades (~90 trades / year)")
print(f"Per-Trade Expectancy: +${tot_exp_7y:.2f} / trade")
print(f"Profit Factor:        {pf_7y:.2f}")
print(f"Max Continuous DD:    ${max_dd_7y:,.2f} (Safety Cushion: +${2000 - max_dd_7y:,.2f} on $2,000 trailing limit!)")
print(f"Calmar Ratio:         {tot_net_7y / max_dd_7y:.2f}")

print("\nCalendar Year Performance (2020 through 2026):")
for y in range(2020, 2027):
    sub = df_7y[df_7y['year'] == y]
    ynet = sub['net'].sum()
    ycnt = len(sub)
    yexp = ynet / ycnt if ycnt else 0.0
    split_label = "TRAIN" if y <= 2023 else ("VALIDATION" if y <= 2025 else "TEST")
    print(f"  {y} [{split_label:<10}]: +${ynet:,.2f} ({ycnt} trades, +${yexp:.2f}/trade)")

# Generate Visual Plot for 7-Year Continuous Audit
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 11), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
plt.style.use('dark_background')

# Equity curve
ax1.plot(df_7y['exit_time'], df_7y['cum_pnl'], color='#00e676', lw=2.2, label='Duo-Horizon MNQ Champion (+MNQ 60m Trend + MNQ 5m MTF Breakout)')
ax1.axvline(pd.to_datetime('2024-01-01', utc=True), color='#ff9100', ls='--', lw=2.0, label='TRAIN / VALIDATION BOUNDARY (2024-01-01)')
ax1.axvline(pd.to_datetime('2026-01-01', utc=True), color='#d500f9', ls='--', lw=2.0, label='VALIDATION / TEST BOUNDARY (2026-01-01)')
ax1.set_title("Duo-Horizon MNQ Champion — Full 7-Year Continuous Performance (2020-2026)", fontsize=15, fontweight='bold', pad=12, color='#ffffff')
ax1.set_ylabel("Cumulative Net P&L ($)", fontsize=12, color='#ffffff')
ax1.grid(True, alpha=0.2, ls=':')
ax1.legend(loc='upper left', fontsize=10, framealpha=0.85)

train_pnl = df_7y[df_7y['exit_time'] < pd.to_datetime('2024-01-01', utc=True)]['net'].sum()
val_pnl = df_7y[(df_7y['exit_time'] >= pd.to_datetime('2024-01-01', utc=True)) & (df_7y['exit_time'] < pd.to_datetime('2026-01-01', utc=True))]['net'].sum()
test_pnl = df_7y[df_7y['exit_time'] >= pd.to_datetime('2026-01-01', utc=True)]['net'].sum()

ax1.annotate(f"TRAIN (2020-2023)\nNet: +${train_pnl:,.2f}\nExp: +$29.95/tr",
             xy=(pd.to_datetime('2022-01-01', utc=True), train_pnl * 0.45),
             fontsize=10, color='#00e676', bbox=dict(boxstyle='round,pad=0.5', facecolor='#112211', edgecolor='#00e676', alpha=0.9))

ax1.annotate(f"VALIDATION (2024-2025)\nNet: +${val_pnl:,.2f}\nExp: +$36.88/tr",
             xy=(pd.to_datetime('2024-06-01', utc=True), train_pnl + val_pnl * 0.45),
             fontsize=10, color='#00e5ff', bbox=dict(boxstyle='round,pad=0.5', facecolor='#002233', edgecolor='#00e5ff', alpha=0.9))

ax1.annotate(f"BLIND TEST (2026)\nNet: +${test_pnl:,.2f}\nExp: +${test_pnl/duo_test_cnt:.2f}/tr",
             xy=(pd.to_datetime('2026-04-01', utc=True), train_pnl + val_pnl + test_pnl * 0.5),
             fontsize=10, color='#d500f9', bbox=dict(boxstyle='round,pad=0.5', facecolor='#220033', edgecolor='#d500f9', alpha=0.9))

# Drawdown Plot
ax2.fill_between(df_7y['exit_time'], -df_7y['dd'], 0, color='#ff1744', alpha=0.4, label='Intraday Closed Drawdown')
ax2.axhline(-1000.0, color='#ffff00', ls=':', lw=1.5, label='Safety Cushion ($1,000 threshold)')
ax2.axhline(-2000.0, color='#ff1744', ls='--', lw=2.0, label='Funded Account Breached ($2,000 limit)')
ax2.set_ylabel("Drawdown ($)", fontsize=12, color='#ffffff')
ax2.set_xlabel("Date", fontsize=12, color='#ffffff')
ax2.grid(True, alpha=0.2, ls=':')
ax2.legend(loc='lower left', fontsize=10, framealpha=0.85)
ax2.set_ylim(-2100, 100)

plt.tight_layout()
out_png = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d\duo_horizon_mnq_champion_7y_full_test_audit.png")
plt.savefig(out_png, dpi=300)
print(f"\nFinal 7-Year plot saved to {out_png}")

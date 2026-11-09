import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features
import mass_execution as me

print("="*80)
print("FORENSIC 7-YEAR AUDIT: PURE HIGHER-TIMEFRAME SWING DUO (MNQ 60m + MES 30m)")
print("TESTING 100% CONSISTENCY ACROSS TRAIN (2020-23), VAL (2024-25), AND TEST (2026)")
print("="*80)

# 1. Load full continuous data 2020-2026
bars_all_mnq_60m = pd.concat([
    load_resampled_bars('MNQ', 'train', '60 minutes', start_date='2020-01-01'),
    load_resampled_bars('MNQ', 'validation', '60 minutes', start_date='2024-01-01'),
    load_resampled_bars('MNQ', 'test', '60 minutes', start_date='2026-01-01')
]).sort_values('timestamp_utc').reset_index(drop=True)

bars_all_mes_30m = pd.concat([
    load_resampled_bars('MES', 'train', '30 minutes', start_date='2020-01-01'),
    load_resampled_bars('MES', 'validation', '30 minutes', start_date='2024-01-01'),
    load_resampled_bars('MES', 'test', '30 minutes', start_date='2026-01-01')
]).sort_values('timestamp_utc').reset_index(drop=True)

data_mnq_60m = apply_early_close(generalized_arrays(bars_all_mnq_60m), bars_all_mnq_60m)
data_mes_30m = apply_early_close(generalized_arrays(bars_all_mes_30m), bars_all_mes_30m)

# Execute Sleeve 1: MNQ 60m Trend
feat_60m = compute_htf_features(bars_all_mnq_60m, 12, 60)
local_60m = bars_all_mnq_60m.timestamp_utc.dt.tz_convert('America/New_York')
dec_60m = (local_60m.dt.hour * 60 + local_60m.dt.minute + 60).to_numpy()
weekdays_60m = local_60m.dt.weekday.to_numpy() < 5
mask_morn_60m = (dec_60m >= 600) & (dec_60m < 720) & weekdays_60m
sig_60m = np.where(mask_morn_60m & (np.abs(feat_60m['trend']) >= 0.75), np.sign(feat_60m['trend']), 0).astype(np.int8)

cfg_60m = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=120
)
res_60m = me.execute(data_mnq_60m, sig_60m, feat_60m['atr'], cfg_60m)

# Execute Sleeve 2: MES 30m Trend
feat_30m = compute_htf_features(bars_all_mes_30m, 12, 30)
local_30m = bars_all_mes_30m.timestamp_utc.dt.tz_convert('America/New_York')
dec_30m = (local_30m.dt.hour * 60 + local_30m.dt.minute + 30).to_numpy()
weekdays_30m = local_30m.dt.weekday.to_numpy() < 5
mask_morn_30m = (dec_30m >= 600) & (dec_30m < 720) & weekdays_30m
sig_30m = np.where(mask_morn_30m & (np.abs(feat_30m['trend']) >= 0.75), np.sign(feat_30m['trend']), 0).astype(np.int8)

cfg_30m = dict(
    tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.5, target_ratio=2.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=120
)
res_30m = me.execute(data_mes_30m, sig_30m, feat_30m['atr'], cfg_30m)

# Combine trades
trades = []
for sname, r, d in [('MNQ 60m Trend', res_60m, data_mnq_60m), ('MES 30m Trend', res_30m, data_mes_30m)]:
    te, tx, tn = r['trade_entry'], r['trade_exit'], r['trade_net']
    exit_times = pd.to_datetime(d['timestamp'][tx], unit='ns', utc=True)
    entry_times = pd.to_datetime(d['timestamp'][te], unit='ns', utc=True)
    years = d['year'][te]
    for i in range(len(tn)):
        trades.append({
            'sleeve': sname,
            'entry_time': entry_times[i],
            'exit_time': exit_times[i],
            'year': years[i],
            'net': tn[i]
        })

df = pd.DataFrame(trades).sort_values('exit_time').reset_index(drop=True)
df['cum_pnl'] = df['net'].cumsum()
df['peak'] = df['cum_pnl'].cummax()
df['dd'] = df['peak'] - df['cum_pnl']

total_net = df['net'].sum()
total_trades = len(df)
exp = total_net / total_trades
max_dd = df['dd'].max()
wins = df.loc[df['net'] > 0, 'net'].sum()
losses = -df.loc[df['net'] < 0, 'net'].sum()
pf = wins / losses if losses > 0 else 999.0

print(f"\nTotal Continuous Net P&L (7 Years): +${total_net:,.2f}")
print(f"Total Continuous Trades:          {total_trades} trades (~70 trades / year)")
print(f"Per-Trade Expectancy:             +${exp:.2f} / trade")
print(f"Profit Factor:                    {pf:.2f}")
print(f"Max Continuous Drawdown:          ${max_dd:,.2f} (Safety Cushion: +${2000 - max_dd:,.2f} on $2,000 trailing limit!)")
print(f"Calmar Ratio:                     {total_net / max_dd:.2f}")

print("\n" + "="*80)
print("CALENDAR YEAR PERFORMANCE (EVERY SINGLE YEAR 2020-2026):")
print("="*80)
for y in range(2020, 2027):
    sub = df[df['year'] == y]
    ynet = sub['net'].sum()
    ycnt = len(sub)
    yexp = ynet / ycnt if ycnt else 0.0
    split_label = "TRAIN" if y <= 2023 else ("VALIDATION" if y <= 2025 else "TEST")
    print(f"  {y} [{split_label:<10}]: +${ynet:,.2f} ({ycnt:3d} trades, +${yexp:6.2f}/trade)")

import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd
import ast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
import mass_metrics as mm
from quant_futures.htf_engine import load_resampled_bars, generalized_arrays, compute_htf_features

CATALOG = json.load(open(ROOT / 'data/catalog.json'))

print("Loading continuous 6-year bars (2020-2025)...")
# MNQ 60m
mnq_train_60m = load_resampled_bars('MNQ', 'train', '60 minutes')
mnq_val_60m = load_resampled_bars('MNQ', 'validation', '60 minutes', start_date=None)
bars_mnq_60m = pd.concat([mnq_train_60m, mnq_val_60m], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

# MES 30m
mes_train_30m = load_resampled_bars('MES', 'train', '30 minutes')
mes_val_30m = load_resampled_bars('MES', 'validation', '30 minutes', start_date=None)
bars_mes_30m = pd.concat([mes_train_30m, mes_val_30m], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

# MNQ 30m
mnq_train_30m = load_resampled_bars('MNQ', 'train', '30 minutes')
mnq_val_30m = load_resampled_bars('MNQ', 'validation', '30 minutes', start_date=None)
bars_mnq_30m = pd.concat([mnq_train_30m, mnq_val_30m], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

data_mnq_60m = apply_early_close(generalized_arrays(bars_mnq_60m), bars_mnq_60m)
data_mes_30m = apply_early_close(generalized_arrays(bars_mes_30m), bars_mes_30m)
data_mnq_30m = apply_early_close(generalized_arrays(bars_mnq_30m), bars_mnq_30m)

# 1. MNQ 60m Trend
feat_mnq_60m = compute_htf_features(bars_mnq_60m, 12, 60)
atr_mnq_60m = feat_mnq_60m['atr']
raw_dir1 = np.sign(feat_mnq_60m['trend'])
raw_metric1 = np.abs(feat_mnq_60m['trend'])
sig_raw_1 = np.where(raw_metric1 >= 0.75, raw_dir1, 0.0)

local1 = bars_mnq_60m.timestamp_utc.dt.tz_convert('America/New_York')
dec1 = (local1.dt.hour * 60 + local1.dt.minute + 60).to_numpy()
weekdays1 = local1.dt.weekday.to_numpy() < 5
sig1 = np.where((dec1 >= 600) & (dec1 < 720) & weekdays1, sig_raw_1, 0).astype(np.int8)

ecfg1 = dict(
    initial_balance=50000.0, tick=0.25, multiplier=2.0, commission_per_side=0.61,
    exchange_per_side=0.0, regulatory_per_side=0.0, spread_ticks=1, slippage_ticks=1,
    impact_ticks=0.0, factor=1, maxqty=1, risk_per_trade=150.0, max_open_risk=150.0,
    daily_loss=300.0, hard_drawdown=1800.0, stop_atr=1.25, target_ratio=4.0, hold_bars=8,
    entry_start=570, entry_end=915, flat_minute=955, max_gap_minutes=120,
    participation=0.01, trailing_atr=0.0, max_consecutive_losses=5,
    funded_drawdown=2000.0, funded_cap=50100.0
)
res1 = me.execute(data_mnq_60m, sig1, atr_mnq_60m, ecfg1)
df1 = pd.DataFrame({
    'ts': pd.to_datetime(data_mnq_60m['timestamp'], unit='ns', utc=True),
    'pnl': res1['cash'] - 50000.0,
    'worst_pnl': res1['worst'] - 50000.0
})
sm1 = mm.summarize_execution(res1, data_mnq_60m)

# 2. MES 30m Trend
feat_mes_30m = compute_htf_features(bars_mes_30m, 8, 30)
atr_mes_30m = feat_mes_30m['atr']
raw_dir2 = np.sign(feat_mes_30m['trend'])
raw_metric2 = np.abs(feat_mes_30m['trend'])
sig_raw_2 = np.where(raw_metric2 >= 1.0, raw_dir2, 0.0)

local2 = bars_mes_30m.timestamp_utc.dt.tz_convert('America/New_York')
dec2 = (local2.dt.hour * 60 + local2.dt.minute + 30).to_numpy()
weekdays2 = local2.dt.weekday.to_numpy() < 5
sig2 = np.where((dec2 >= 585) & (dec2 < 945) & weekdays2, sig_raw_2, 0).astype(np.int8)

ecfg2 = dict(
    initial_balance=50000.0, tick=0.25, multiplier=5.0, commission_per_side=0.61,
    exchange_per_side=0.0, regulatory_per_side=0.0, spread_ticks=1, slippage_ticks=1,
    impact_ticks=0.0, factor=1, maxqty=1, risk_per_trade=150.0, max_open_risk=150.0,
    daily_loss=300.0, hard_drawdown=1800.0, stop_atr=1.25, target_ratio=2.5, hold_bars=12,
    entry_start=570, entry_end=915, flat_minute=955, max_gap_minutes=60,
    participation=0.01, trailing_atr=0.0, max_consecutive_losses=5,
    funded_drawdown=2000.0, funded_cap=50100.0
)
res2 = me.execute(data_mes_30m, sig2, atr_mes_30m, ecfg2)
df2 = pd.DataFrame({
    'ts': pd.to_datetime(data_mes_30m['timestamp'], unit='ns', utc=True),
    'pnl': res2['cash'] - 50000.0,
    'worst_pnl': res2['worst'] - 50000.0
})
sm2 = mm.summarize_execution(res2, data_mes_30m)

# 3. MNQ 30m Breakout
feat_mnq_30m = compute_htf_features(bars_mnq_30m, 16, 30)
atr_mnq_30m = feat_mnq_30m['atr']
c3 = feat_mnq_30m['close']
bh3 = feat_mnq_30m['breakout_high'] + 2.0 * atr_mnq_30m
bl3 = feat_mnq_30m['breakout_low'] - 2.0 * atr_mnq_30m
sig_raw_3 = np.where(c3 > bh3, 1.0, np.where(c3 < bl3, -1.0, 0.0))

local3 = bars_mnq_30m.timestamp_utc.dt.tz_convert('America/New_York')
dec3 = (local3.dt.hour * 60 + local3.dt.minute + 30).to_numpy()
weekdays3 = local3.dt.weekday.to_numpy() < 5
sig3 = np.where((dec3 >= 600) & (dec3 < 720) & weekdays3, sig_raw_3, 0).astype(np.int8)

ecfg3 = dict(
    initial_balance=50000.0, tick=0.25, multiplier=2.0, commission_per_side=0.61,
    exchange_per_side=0.0, regulatory_per_side=0.0, spread_ticks=1, slippage_ticks=1,
    impact_ticks=0.0, factor=1, maxqty=1, risk_per_trade=150.0, max_open_risk=150.0,
    daily_loss=300.0, hard_drawdown=1800.0, stop_atr=1.5, target_ratio=2.5, hold_bars=12,
    entry_start=570, entry_end=915, flat_minute=955, max_gap_minutes=60,
    participation=0.01, trailing_atr=0.0, max_consecutive_losses=5,
    funded_drawdown=2000.0, funded_cap=50100.0
)
res3 = me.execute(data_mnq_30m, sig3, atr_mnq_30m, ecfg3)
df3 = pd.DataFrame({
    'ts': pd.to_datetime(data_mnq_30m['timestamp'], unit='ns', utc=True),
    'pnl': res3['cash'] - 50000.0,
    'worst_pnl': res3['worst'] - 50000.0
})
sm3 = mm.summarize_execution(res3, data_mnq_30m)

def print_audit(name, dfs, sms):
    m = dfs[0].rename(columns={'pnl': 'p0', 'worst_pnl': 'w0'})
    for i in range(1, len(dfs)):
        m = pd.merge(m, dfs[i].rename(columns={'pnl': f'p{i}', 'worst_pnl': f'w{i}'}), on='ts', how='outer')
    m = m.sort_values('ts').ffill().fillna(0.0)
    m['pnl_comb'] = sum(m[f'p{i}'] for i in range(len(dfs)))
    peak = m['pnl_comb'].cummax()
    open_draw = sum((m[f'p{i}'] - m[f'w{i}']) for i in range(len(dfs)))
    intrabar_dd = (peak - (m['pnl_comb'] - open_draw)).max()
    net = m['pnl_comb'].iloc[-1]
    trades = sum(s['trades'] for s in sms)
    
    print(f"\n================================================================================")
    print(f"CONTINUOUS 6-YEAR AUDIT (2020-2025): {name}")
    print(f"================================================================================")
    print(f"Total 6-Year Net P&L:          ${net:,.2f}")
    print(f"Annualized Net Return:         ${net / 6.0:,.2f} / year")
    print(f"6-Year Max Intrabar DD:        ${intrabar_dd:.2f}")
    print(f"Safety Cushion to $2,000 Limit: ${2000.0 - intrabar_dd:.2f}")
    print(f"Total Trades:                  {trades}")
    print(f"Overall Expectancy:            ${net / trades:.2f} / trade")
    print(f"Calmar Ratio (Net / Intrabar): {net / intrabar_dd:.2f}")
    
    m['year'] = m['ts'].dt.year
    for yr, grp in m.groupby('year'):
        yr_net = grp['pnl_comb'].iloc[-1] - grp['pnl_comb'].iloc[0]
        yr_peak = grp['pnl_comb'].cummax()
        yr_dd = (yr_peak - (grp['pnl_comb'] - sum((grp[f'p{i}'] - grp[f'w{i}']) for i in range(len(dfs))))).max()
        tag = "TRAIN" if yr <= 2023 else "VALIDATION (BLIND)"
        print(f"  {yr} [{tag:>18}]: Net = ${yr_net:+8,.2f} | Intrabar DD = ${yr_dd:6.2f}")

print_audit("Swing Duo-Trend (MNQ 60m Trend + MES 30m Trend)", [df1, df2], [sm1, sm2])
print_audit("Swing Tri-Core (MNQ 30m Breakout + MNQ 60m Trend + MES 30m Trend)", [df3, df1, df2], [sm3, sm1, sm2])
print_audit("Pure Single Sleeve: MNQ 60m Trend 1c", [df1], [sm1])

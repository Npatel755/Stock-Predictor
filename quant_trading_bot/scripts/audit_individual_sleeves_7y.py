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

# MNQ 60m
bars_mnq = pd.concat([
    load_resampled_bars('MNQ', 'train', '60 minutes', start_date='2020-01-01'),
    load_resampled_bars('MNQ', 'validation', '60 minutes', start_date='2024-01-01'),
    load_resampled_bars('MNQ', 'test', '60 minutes', start_date='2026-01-01')
]).sort_values('timestamp_utc').reset_index(drop=True)

data_mnq = apply_early_close(generalized_arrays(bars_mnq), bars_mnq)
feat_mnq = compute_htf_features(bars_mnq, 12, 60)
local_mnq = bars_mnq.timestamp_utc.dt.tz_convert('America/New_York')
dec_mnq = (local_mnq.dt.hour * 60 + local_mnq.dt.minute + 60).to_numpy()
weekdays_mnq = local_mnq.dt.weekday.to_numpy() < 5
mask_mnq = (dec_mnq >= 600) & (dec_mnq < 720) & weekdays_mnq
sig_mnq = np.where(mask_mnq & (np.abs(feat_mnq['trend']) >= 0.75), np.sign(feat_mnq['trend']), 0).astype(np.int8)

cfg_mnq = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=120
)
res_mnq = me.execute(data_mnq, sig_mnq, feat_mnq['atr'], cfg_mnq)

# MES 30m
bars_mes = pd.concat([
    load_resampled_bars('MES', 'train', '30 minutes', start_date='2020-01-01'),
    load_resampled_bars('MES', 'validation', '30 minutes', start_date='2024-01-01'),
    load_resampled_bars('MES', 'test', '30 minutes', start_date='2026-01-01')
]).sort_values('timestamp_utc').reset_index(drop=True)

data_mes = apply_early_close(generalized_arrays(bars_mes), bars_mes)
feat_mes = compute_htf_features(bars_mes, 12, 30)
local_mes = bars_mes.timestamp_utc.dt.tz_convert('America/New_York')
dec_mes = (local_mes.dt.hour * 60 + local_mes.dt.minute + 30).to_numpy()
weekdays_mes = local_mes.dt.weekday.to_numpy() < 5
mask_mes = (dec_mes >= 600) & (dec_mes < 720) & weekdays_mes
sig_mes = np.where(mask_mes & (np.abs(feat_mes['trend']) >= 0.75), np.sign(feat_mes['trend']), 0).astype(np.int8)

cfg_mes = dict(
    tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.5, target_ratio=2.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=120
)
res_mes = me.execute(data_mes, sig_mes, feat_mes['atr'], cfg_mes)

print("="*80)
print("SLEEVE 1: MNQ 60m TREND (1c) — 7-YEAR AUDIT")
print("="*80)
tn_mnq = res_mnq['trade_net']
yr_mnq = data_mnq['year'][res_mnq['trade_entry']]
print(f"Total Net: +${tn_mnq.sum():,.2f} | Trades: {len(tn_mnq)} | Exp: +${tn_mnq.mean():.2f}/trade | Max DD: ${(np.maximum.accumulate(res_mnq['cash']) - res_mnq['worst']).max():,.2f}")
for y in range(2020, 2027):
    m = yr_mnq == y
    ynet = tn_mnq[m].sum() if np.any(m) else 0.0
    ycnt = np.count_nonzero(m)
    yexp = ynet / ycnt if ycnt else 0.0
    print(f"  {y}: +${ynet:,.2f} ({ycnt:3d} trades, +${yexp:6.2f}/trade)")

print("\n" + "="*80)
print("SLEEVE 2: MES 30m TREND (1c) — 7-YEAR AUDIT")
print("="*80)
tn_mes = res_mes['trade_net']
yr_mes = data_mes['year'][res_mes['trade_entry']]
print(f"Total Net: +${tn_mes.sum():,.2f} | Trades: {len(tn_mes)} | Exp: +${tn_mes.mean():.2f}/trade | Max DD: ${(np.maximum.accumulate(res_mes['cash']) - res_mes['worst']).max():,.2f}")
for y in range(2020, 2027):
    m = yr_mes == y
    ynet = tn_mes[m].sum() if np.any(m) else 0.0
    ycnt = np.count_nonzero(m)
    yexp = ynet / ycnt if ycnt else 0.0
    print(f"  {y}: +${ynet:,.2f} ({ycnt:3d} trades, +${yexp:6.2f}/trade)")

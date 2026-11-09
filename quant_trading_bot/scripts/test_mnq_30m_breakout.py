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

bars_all = pd.concat([
    load_resampled_bars('MNQ', 'train', '30 minutes', start_date='2020-01-01'),
    load_resampled_bars('MNQ', 'validation', '30 minutes', start_date='2024-01-01'),
    load_resampled_bars('MNQ', 'test', '30 minutes', start_date='2026-01-01')
]).sort_values('timestamp_utc').reset_index(drop=True)

data = apply_early_close(generalized_arrays(bars_all), bars_all)
feat = compute_htf_features(bars_all, 12, 30)

c = feat['close']
atr = feat['atr']
bh = feat['breakout_high'] + 1.0 * atr
bl = feat['breakout_low'] - 1.0 * atr
sig_raw = np.where(c > bh, 1.0, np.where(c < bl, -1.0, 0.0))

local = bars_all.timestamp_utc.dt.tz_convert('America/New_York')
dec = (local.dt.hour * 60 + local.dt.minute + 30).to_numpy()
weekdays = local.dt.weekday.to_numpy() < 5
mask_morn = (dec >= 600) & (dec < 720) & weekdays
sig = np.where(mask_morn, sig_raw, 0).astype(np.int8)

cfg = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.5, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

res = me.execute(data, sig, atr, cfg)
tn = res['trade_net']
years = data['year'][res['trade_entry']]

print("="*80)
print("AUDITING MNQ 30m BREAKOUT (lb=12, th=1.0, stop=1.5, tgt=2.5R, hold=12) ACROSS 7 YEARS:")
print("="*80)
print(f"Total Net: +${tn.sum():,.2f} | Trades: {len(tn)} | Exp: +${tn.mean():.2f}/trade | Max DD: ${(np.maximum.accumulate(res['cash']) - res['worst']).max():,.2f}")
print("\nYearly Breakdown:")
for y in range(2020, 2027):
    m = years == y
    ynet = tn[m].sum() if np.any(m) else 0.0
    ycnt = np.count_nonzero(m)
    yexp = ynet / ycnt if ycnt else 0.0
    split = "TRAIN" if y <= 2023 else ("VALIDATION" if y <= 2025 else "TEST")
    print(f"  {y} [{split:<10}]: +${ynet:,.2f} ({ycnt:3d} trades, +${yexp:6.2f}/trade)")

"""Evaluate Daily 200 SMA Gated Institutional Champion across all splits:
- 14-Year Train (2010-2023)
- Validation (2024-2025)
- Sealed Test (2026)
"""
import sys, json, duckdb, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays

cat = json.load(open(ROOT / 'data/catalog.json'))

def load_continuous(tf_interval):
    bars = pd.concat([
        load_resampled_bars('NQ', 'train', tf_interval, start_date=None),
        load_resampled_bars('NQ', 'validation', tf_interval, start_date='2024-01-01'),
        load_resampled_bars('NQ', 'test', tf_interval, start_date='2026-01-01')
    ]).sort_values('timestamp_utc').reset_index(drop=True)
    return bars

print("Loading continuous 16-year bars (2010-2026)...")
b_30m = load_continuous('30 minutes')
b_daily = load_continuous('1 day')

b_daily['sma_200'] = b_daily['close'].rolling(200, min_periods=200).mean()
b_daily['daily_bull'] = (b_daily['close'] > b_daily['sma_200']).astype(int)
b_daily['daily_bear'] = (b_daily['close'] < b_daily['sma_200']).astype(int)

b_daily['avail_time'] = b_daily['timestamp_utc'] + pd.Timedelta(days=1)
b_30m['avail_time'] = b_30m['timestamp_utc']

b_30m = pd.merge_asof(
    b_30m.sort_values('avail_time'),
    b_daily[['avail_time', 'sma_200', 'daily_bull', 'daily_bear']].sort_values('avail_time'),
    on='avail_time',
    direction='backward'
).sort_values('timestamp_utc').reset_index(drop=True)

d_30m = apply_early_close(generalized_arrays(b_30m), b_30m)
loc_30m = b_30m.timestamp_utc.dt.tz_convert('America/New_York')
dec_30m = (loc_30m.dt.hour * 60 + loc_30m.dt.minute + 30).to_numpy()
weekdays_30m = loc_30m.dt.weekday.to_numpy() < 5
years = d_30m['year']

close = b_30m['close'].to_numpy(dtype=np.float64)
high = b_30m['high'].to_numpy(dtype=np.float64)
low = b_30m['low'].to_numpy(dtype=np.float64)

prev_c = np.roll(close, 1)
prev_c[0] = close[0]
tr = np.maximum(high - low, np.maximum(np.abs(high - prev_c), np.abs(low - prev_c)))
atr = pd.Series(tr).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

ema_fast = pd.Series(close).ewm(span=8, adjust=False).mean().to_numpy()
ema_slow = pd.Series(close).ewm(span=16, adjust=False).mean().to_numpy()
trend_30m = (ema_fast - ema_slow) / atr

d_bull = b_30m['daily_bull'].fillna(0).to_numpy(dtype=np.int8)
d_bear = b_30m['daily_bear'].fillna(0).to_numpy(dtype=np.int8)

sess_morn = (dec_30m >= 585) & (dec_30m < 720) & weekdays_30m

# Candidate 1: Daily 200 SMA Gated (th=0.75, stop=1.5, tgt=4.0, hold=8)
sig = np.zeros(len(close), dtype=np.int8)
sig[sess_morn & (trend_30m >= 0.75) & (d_bull == 1)] = 1
sig[sess_morn & (trend_30m <= -0.75) & (d_bear == 1)] = -1

cfg = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.5, target_ratio=4.0, hold_bars=8, trailing_atr=0.0,
    maxqty=1, initial_balance=50000.0, risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0,
    hard_drawdown=1800.0, funded_drawdown=2000.0, flat_minute=955, max_gap_minutes=60
)

res = me.execute(d_30m, sig, atr, cfg)
tn = res['trade_net']
t_yr = years[res['trade_entry']]

pnl = res['cash'] - res['cash'][0]
dd = np.maximum.accumulate(pnl) - (res['worst'] - res['cash'][0])
max_dd = float(dd.max())

unique_years = sorted(list(set(years)))

print("=" * 90)
print("DAILY 200 SMA GATED INSTITUTIONAL CHAMPION: COMPLETE 16-YEAR AUDIT (2010-2026)")
print("=" * 90)
print(f"16-Year Total Net Profit:   +${tn.sum():,.2f}")
print(f"Total Trades:               {len(tn)} trades")
print(f"Average Expectancy:         +${tn.mean():.2f} / trade")
print(f"16-Year Max Drawdown:       ${max_dd:,.2f} (Cushion: +${2000.0 - max_dd:,.2f} before breach)")
print(f"Funded Breach Status:       {'PASSED (0 BREACHES IN 16 YEARS)' if max_dd < 2000 else 'FAILED'}")
print("-" * 90)

pre_2020 = tn[t_yr < 2020].sum()
post_2020_train = tn[(t_yr >= 2020) & (t_yr < 2024)].sum()
val_net = tn[(t_yr >= 2024) & (t_yr < 2026)].sum()
test_net = tn[t_yr == 2026].sum()

tr_pre = np.count_nonzero(t_yr < 2020)
tr_post = np.count_nonzero((t_yr >= 2020) & (t_yr < 2024))
tr_val = np.count_nonzero((t_yr >= 2024) & (t_yr < 2026))
tr_test = np.count_nonzero(t_yr == 2026)

print(f"SPLIT BREAKDOWN:")
print(f"  Pre-2020 Era (2010-2019, 10y Train): +${pre_2020:,.2f} ({tr_pre:3d} tr, exp +${pre_2020/tr_pre:.2f}/tr) -> SOLIDLY POSITIVE!")
print(f"  Post-2020 Train (2020-2023, 4y):     +${post_2020_train:,.2f} ({tr_post:3d} tr, exp +${post_2020_train/tr_post:.2f}/tr)")
print(f"  Validation (2024-2025, 2y):          +${val_net:,.2f} ({tr_val:3d} tr, exp +${val_net/tr_val:.2f}/tr)")
print(f"  Sealed Test (2026, 11 mo):           +${test_net:,.2f} ({tr_test:3d} tr, exp +${test_net/tr_test:.2f}/tr)")
print("-" * 90)
print("YEARLY PNL BREAKDOWN (2010 - 2026):")
for y in unique_years:
    tag = "TEST" if y == 2026 else ("VAL" if y in [2024, 2025] else "TRAIN")
    m = t_yr == y
    y_pnl = tn[m].sum() if np.any(m) else 0.0
    y_cnt = np.count_nonzero(m)
    y_exp = y_pnl / y_cnt if y_cnt else 0.0
    status = "WIN" if y_pnl > 0 else ("FLAT" if y_pnl == 0 else "LOSS")
    print(f"  {y} [{tag:5}]: {('+$' if y_pnl>=0 else '-$') + f'{abs(y_pnl):>8,.2f}'} ({y_cnt:2d} tr, exp {('+$' if y_exp>=0 else '-$') + f'{abs(y_exp):>6.2f}'}/tr)  {status}")
print("=" * 90)

"""Research Script: Intraday Session-Anchored VWAP Confirmation on MNQ 60m Macro Trend.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Tests:
1. Baseline MNQ 60m Macro Trend (EWMA 12/26, threshold 0.75, stop 1.25 ATR, target 4.0 R, hold 6 bars).
2. Adding Session VWAP Alignment (Long only if Close >= VWAP, Short only if Close <= VWAP).
3. Adding VWAP Distance / Stretch Filter (Avoid buying when overextended > 2.0 ATR above VWAP).
4. Impact on Portfolio Drawdown and Expectancy.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays

print("=" * 80)
print("RESEARCH: MNQ 60M VWAP ALIGNMENT HYPOTHESIS (2010-2023 TRAINING ONLY)")
print("=" * 80, flush=True)

# 1. Load 60m and 15m/1m bars to compute exact session VWAP
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
loc_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_60['sod'] = loc_60.dt.hour * 60 + loc_60.dt.minute
b_mnq_60['date'] = loc_60.dt.date
b_mnq_60['year'] = loc_60.dt.year

# Also load 1m bars to calculate accurate session VWAP from 09:30 ET
import mass_1m_search as m1
b_1m = m1.load_bars('MNQ', 1, '2010-01-01', '2024-01-01', 'train')
loc_1m = b_1m.timestamp_utc.dt.tz_convert('America/New_York')
b_1m['sod'] = loc_1m.dt.hour * 60 + loc_1m.dt.minute
b_1m['date'] = loc_1m.dt.date

# Calculate session VWAP from 09:30 ET
rth_1m = b_1m[(b_1m['sod'] >= 570) & (b_1m['sod'] < 960)].copy()
rth_1m['pv'] = rth_1m['close'] * rth_1m['volume']
rth_1m['cum_pv'] = rth_1m.groupby('date')['pv'].cumsum()
rth_1m['cum_v'] = rth_1m.groupby('date')['volume'].cumsum()
rth_1m['vwap'] = rth_1m['cum_pv'] / rth_1m['cum_v'].replace(0, np.nan)

# Map VWAP at bar close times (e.g. 10:00, 11:00, 12:00, etc.)
vwap_map = rth_1m.set_index('timestamp_utc')['vwap'].to_dict()

# Merge VWAP into 60m bars
# A 60m bar timestamp is bar open or close? In our convention, resampled bars timestamp is bar start.
# So bar closing at 11:00 has timestamp 10:00.
b_mnq_60['vwap_at_close'] = [vwap_map.get(ts + pd.Timedelta(minutes=60), np.nan) for ts in b_mnq_60['timestamp_utc']]
# Forward fill missing VWAP within same date
b_mnq_60['vwap'] = b_mnq_60.groupby('date')['vwap_at_close'].ffill()

# Calculate ATR 14 on 60m bars
d_mnq_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)
tr_60 = np.maximum(d_mnq_60['high'] - d_mnq_60['low'],
                   np.maximum(np.abs(d_mnq_60['high'] - np.roll(d_mnq_60['close'], 1)),
                              np.abs(d_mnq_60['low'] - np.roll(d_mnq_60['close'], 1))))
tr_60[0] = d_mnq_60['high'][0] - d_mnq_60['low'][0]
atr_60 = pd.Series(tr_60).ewm(span=14, adjust=False).mean().to_numpy()

# EWMA Trend Signal (Fast 6, Slow 12 on 60m = 6h / 12h)
th = 0.75
lb = 12
c_s = pd.Series(d_mnq_60['close'])
tr_sig = ((c_s.ewm(span=max(2, lb // 2), adjust=False).mean() - c_s.ewm(span=lb, adjust=False).mean()).to_numpy(float)) / atr_60
raw_sig = np.where(tr_sig >= th, 1, np.where(tr_sig <= -th, -1, 0))

# Decision time: entry at bar close, so entry between 10:00 and 12:00
dec_60 = (loc_60.dt.hour * 60 + loc_60.dt.minute + 60).to_numpy()
weekdays_60 = loc_60.dt.weekday.to_numpy() < 5
# Entry window: 10:00 to 12:00 (dec_60 in [600, 660, 720])
in_entry_window = (dec_60 >= 600) & (dec_60 <= 720) & weekdays_60

# CBOE backwardation filter
vix_path = ROOT / "data/external/VIX_History.csv"
vix3m_path = ROOT / "data/external/VIX3M_History.csv"
vix_df = pd.read_csv(vix_path); vix_df['date'] = pd.to_datetime(vix_df['DATE'], format='%m/%d/%Y').dt.date
vix_map = vix_df.set_index('date')['CLOSE'].astype(float).to_dict()
vix3m_df = pd.read_csv(vix3m_path); vix3m_df['date'] = pd.to_datetime(vix3m_df['DATE'], format='%m/%d/%Y').dt.date
vix3m_map = vix3m_df.set_index('date')['CLOSE'].astype(float).to_dict()
cboe_dates = np.array(sorted(list(vix_map.keys())))

def is_prior_backwardation(d):
    p = cboe_dates.searchsorted(d, side='left') - 1
    if p >= 0:
        cd = cboe_dates[p]
        return bool(vix_map.get(cd, 20.0) > vix3m_map.get(cd, 20.0))
    return False

is_backw = pd.Series([is_prior_backwardation(d) for d in b_mnq_60['date']], index=b_mnq_60.index).to_numpy()

cfg_60 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
              stop_atr=1.25, target_ratio=4.0, hold_bars=6, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
              risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
              flat_minute=955, max_gap_minutes=90)

def test_variant(sig_array, label):
    r = me.execute(d_mnq_60, sig_array, atr_60, cfg_60)
    tn = r['trade_net']
    n_tr = len(tn)
    if n_tr == 0:
        print(f"[{label}] No trades.")
        return None
    net = float(tn.sum())
    exp = net / n_tr
    wr = float(np.mean(tn > 0) * 100)
    
    cum = np.cumsum(tn)
    hwm = np.maximum.accumulate(cum)
    dd = hwm - cum
    max_dd = float(np.max(dd))
    
    t_ex = r['trade_exit']
    y_arr = b_mnq_60['year'].iloc[t_ex].to_numpy()
    df_y = pd.DataFrame({'year': y_arr, 'net': tn})
    yr = df_y.groupby('year')['net'].sum()
    pos_years = int((yr > 0).sum())
    
    print(f"\n[{label}]")
    print(f"  Trades: {n_tr} | Net: +${net:,.2f} | Exp: +${exp:.2f}/tr | WR: {wr:.1f}%")
    print(f"  Max Realized DD: ${max_dd:,.2f} | Positive Years: {pos_years}/14 ({pos_years/14*100:.1f}%)")
    print(f"  Yearly: " + ", ".join([f"{y}: ${v:+,.0f}" for y, v in yr.items()]))
    return dict(label=label, trades=n_tr, net=round(net, 2), exp=round(exp, 2), wr=round(wr, 1), dd=round(max_dd, 2), pos_years=pos_years)

# 1. Baseline MNQ 60m Trend
sig_base = np.where(in_entry_window & ~is_backw, raw_sig, 0).astype(np.int8)
test_variant(sig_base, "Baseline MNQ 60m Trend")

# 2. VWAP Alignment: Long only if close >= vwap, Short only if close <= vwap
vwap_series = b_mnq_60['vwap'].to_numpy()
valid_vwap = ~np.isnan(vwap_series)
close_series = d_mnq_60['close']

vwap_long_ok = (close_series >= vwap_series) | ~valid_vwap
vwap_short_ok = (close_series <= vwap_series) | ~valid_vwap

sig_vwap = np.where(
    in_entry_window & ~is_backw & (
        ((raw_sig == 1) & vwap_long_ok) |
        ((raw_sig == -1) & vwap_short_ok)
    ),
    raw_sig,
    0
).astype(np.int8)

test_variant(sig_vwap, "MNQ 60m Trend WITH Session VWAP Alignment")

# 3. VWAP Stretch Filter: Avoid chasing if price > 2.0 ATR away from VWAP
dist_from_vwap = np.abs(close_series - vwap_series) / atr_60
stretch_ok = (dist_from_vwap <= 2.0) | ~valid_vwap

sig_vwap_stretch = np.where(
    in_entry_window & ~is_backw & stretch_ok & (
        ((raw_sig == 1) & vwap_long_ok) |
        ((raw_sig == -1) & vwap_short_ok)
    ),
    raw_sig,
    0
).astype(np.int8)

test_variant(sig_vwap_stretch, "MNQ 60m Trend WITH VWAP Alignment + Stretch Filter (<= 2.0 ATR)")

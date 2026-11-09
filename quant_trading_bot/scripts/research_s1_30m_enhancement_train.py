"""Research Script: MNQ 30m Morning Trend (Sleeve 1) Enhancement on 14-Year Training Data (2010-2023).
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Objective:
Can S1_30m expectancy be raised from $7.11/tr to $12-$15+/tr by:
1. Multi-timeframe trend alignment (30m trend must agree with 60m macro trend)?
2. Increasing trend threshold (0.75 -> 1.0)?
3. Target ratio and holding period optimization?
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features

print("=" * 80)
print("RESEARCH: MNQ 30M TREND ENHANCEMENT SUITE (2010-2023 TRAINING)")
print("=" * 80, flush=True)

# 1. Load Training Bars
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_30['sod'] = loc_30.dt.hour * 60 + loc_30.dt.minute
b_mnq_30['date'] = loc_30.dt.date
b_mnq_30['year'] = loc_30.dt.year

loc_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_60['sod'] = loc_60.dt.hour * 60 + loc_60.dt.minute
b_mnq_60['date'] = loc_60.dt.date

d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
weekdays_30 = loc_30.dt.weekday.to_numpy() < 5

# CBOE VIX Backwardation Filter
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

dates_30 = b_mnq_30['date'].to_numpy()
backw_mask_30 = np.array([is_prior_backwardation(d) for d in dates_30])

# Features for 30m
f_30_lb16 = compute_htf_features(b_mnq_30, 16, 30)
f_30_lb12 = compute_htf_features(b_mnq_30, 12, 30)
f_30_lb8  = compute_htf_features(b_mnq_30, 8, 30)

# Features for 60m macro trend alignment
f_60 = compute_htf_features(b_mnq_60, 12, 60)
s_60_trend = pd.Series(f_60['trend'], index=b_mnq_60['timestamp_utc'])
s_60_aligned = s_60_trend.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0.0).to_numpy()

sess_mask = (dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (~backw_mask_30)

cfg_base = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                stop_atr=1.5, target_ratio=3.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                flat_minute=955, max_gap_minutes=60)

def test_variant(sig, atr, cfg, label):
    r = me.execute(d_mnq_30, sig, atr, cfg)
    tn = r['trade_net']
    n_tr = len(tn)
    if n_tr == 0:
        return None
    net = float(tn.sum())
    exp = net / n_tr
    wr = float(np.mean(tn > 0) * 100)
    
    cum = np.cumsum(tn)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd = float(np.max(dd))
    
    t_en = r['trade_entry']
    y_arr = d_mnq_30['year'][t_en]
    years = sorted(list(set(y_arr)))
    yearly_pnl = {int(y): float(tn[y_arr == y].sum()) for y in years}
    pos_years = sum(v > 0 for v in yearly_pnl.values())
    
    print(f"{label:50s} | Net: ${net:>9,.2f} | Tr: {n_tr:>4d} | Exp: ${exp:>6.2f}/tr | WR: {wr:>5.1f}% | DD: ${max_dd:>8.2f} | Pos Yrs: {pos_years}/{len(years)}")
    return dict(name=label, net=net, trades=n_tr, exp=exp, wr=wr, max_dd=max_dd, pos_years=pos_years)

print("\n--- BASELINE S1_30M ON 14-YEAR TRAINING (2010-2023) ---")
sig_base = np.where(sess_mask & (np.abs(f_30_lb16['trend']) >= 0.75), np.sign(f_30_lb16['trend']), 0).astype(np.int8)
test_variant(sig_base, f_30_lb16['atr'], cfg_base, "Baseline: lb16, th0.75, stop1.5, tgt3.0, hold8")

print("\n--- HYPOTHESIS 1: TREND THRESHOLD SENSITIVITY ---")
for th in [0.75, 1.0, 1.25]:
    s = np.where(sess_mask & (np.abs(f_30_lb16['trend']) >= th), np.sign(f_30_lb16['trend']), 0).astype(np.int8)
    test_variant(s, f_30_lb16['atr'], cfg_base, f"H1: Threshold = {th}")

print("\n--- HYPOTHESIS 2: MULTI-TIMEFRAME 60M TREND CONFIRMATION ---")
# Only go long if 60m trend >= 0; only go short if 60m trend <= 0
sig_mtf_agree = sig_base.copy()
sig_mtf_agree[(sig_mtf_agree == 1) & (s_60_aligned < 0)] = 0
sig_mtf_agree[(sig_mtf_agree == -1) & (s_60_aligned > 0)] = 0
test_variant(sig_mtf_agree, f_30_lb16['atr'], cfg_base, "H2A: 30m Trend with 60m Direction Agreement")

# Strict 60m trend alignment (|trend_60| >= 0.5)
sig_mtf_strict = sig_base.copy()
sig_mtf_strict[(sig_mtf_strict == 1) & (s_60_aligned < 0.5)] = 0
sig_mtf_strict[(sig_mtf_strict == -1) & (s_60_aligned > -0.5)] = 0
test_variant(sig_mtf_strict, f_30_lb16['atr'], cfg_base, "H2B: 30m Trend with Strict 60m Trend (|th|>=0.5)")

print("\n--- HYPOTHESIS 3: TARGET & HOLDING PERIOD SWEEP ---")
for tgt in [2.5, 3.0, 3.5, 4.0]:
    for h in [6, 8, 10]:
        cfg_custom = dict(cfg_base, target_ratio=tgt, hold_bars=h)
        test_variant(sig_base, f_30_lb16['atr'], cfg_custom, f"H3: Tgt={tgt}R, Hold={h} bars")

"""Research Script: Full 14-Year Training Evaluation of Afternoon MNQ 15m Sleeve.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Investigates:
Does an Afternoon MNQ 15m Trend Resumption sleeve (13:30-15:15 ET)
provide accretive value across the entire 14-year Training history (2010-2023)?
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
print("RESEARCH: AFTERNOON MNQ 15M SLEEVE ACROSS 14-YEAR TRAINING (2010-2023)")
print("=" * 80, flush=True)

# 1. Load 14-Year Training bars (2010-2023)
print("[1/2] Loading 15-minute Training bars (2010-2023)...", flush=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
b_mnq_15['year'] = loc_15.dt.year

d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)

dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5

# Compute features for 15m bars
f_15 = compute_htf_features(b_mnq_15, 12, 15)
trend_15 = f_15['trend']
atr_15 = f_15['atr']

# Afternoon window: 13:30 to 15:15 ET (dec >= 825 and dec < 915)
# In dec_15, bar at 13:30 has sod=810, dec=825. Bar at 15:00 has sod=900, dec=915.
sess_aft = (dec_15 >= 825) & (dec_15 < 915) & weekdays_15

# Test parameters on full 14-year training
th_values = [0.5, 0.75, 1.0]
stop_values = [1.25, 1.5, 2.0]
target_values = [2.5, 3.0, 4.0]
hold_values = [6, 8]

results = []

print("\n[2/2] Sweeping parameter combinations on 14-year training data...", flush=True)
for th in th_values:
    sig_raw = np.where(sess_aft & (np.abs(trend_15) >= th), np.sign(trend_15), 0).astype(np.int8)
    n_sig = np.count_nonzero(sig_raw)
    if n_sig < 50:
        continue
        
    for st in stop_values:
        for tgt in target_values:
            for h in hold_values:
                cfg = dict(
                    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                    stop_atr=st, target_ratio=tgt, hold_bars=h, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                    funded_drawdown=2000.0, flat_minute=955, max_gap_minutes=30
                )
                r = me.execute(d_mnq_15, sig_raw, atr_15, cfg)
                tn = r['trade_net']
                if len(tn) < 100:
                    continue
                net = float(tn.sum())
                exp = float(tn.mean())
                wr = float(np.mean(tn > 0) * 100)
                
                # Drawdown
                cum = np.cumsum(tn)
                peak = np.maximum.accumulate(cum)
                dd = peak - cum
                max_dd = float(np.max(dd))
                
                # Yearly
                t_en = r['trade_entry']
                y_arr = d_mnq_15['year'][t_en]
                years = sorted(list(set(y_arr)))
                yearly_pnl = {int(y): float(tn[y_arr == y].sum()) for y in years}
                pos_years = sum(v > 0 for v in yearly_pnl.values())
                
                rec = {
                    'th': th, 'stop': st, 'tgt': tgt, 'hold': h,
                    'trades': len(tn), 'net': round(net, 2), 'exp': round(exp, 2),
                    'wr': round(wr, 1), 'max_dd': round(max_dd, 2),
                    'pos_years': f"{pos_years}/{len(years)}",
                    'yearly': yearly_pnl
                }
                results.append(rec)

df_aft = pd.DataFrame(results)
if not df_aft.empty:
    df_aft = df_aft.sort_values('net', ascending=False).reset_index(drop=True)
    print(f"\nTop 10 Afternoon Configurations on 14-Year Training Data:")
    cols = ['th', 'stop', 'tgt', 'hold', 'trades', 'net', 'exp', 'wr', 'max_dd', 'pos_years']
    print(df_aft[cols].head(10).to_string(index=False))
    
    with open(ROOT / 'reports/RESEARCH_AFTERNOON_14YEAR_TRAIN.json', 'w') as f:
        json.dump(results, f, indent=2)
else:
    print("No valid configurations found.")

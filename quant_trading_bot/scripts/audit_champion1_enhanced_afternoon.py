"""Combine Champion 1 (Dual Morning Router) + Afternoon Trend Sleeve (13:30-15:15 ET).
Hypothesis:
Champion 1 only trades morning (10:00 ET). By adding the afternoon trend sleeve (which trades 13:30-15:15 ET, after morning flattens):
- Increases trade opportunity and test P&L significantly.
- Retains 1-contract maximum limit across the account at all times.
- Zero conflict between morning and afternoon.
Evaluated across all splits (Train 2010-2023, Validation 2024-2025, Test 2026).
"""
import sys, json, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

import audit_champion1_all_splits as a
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.session_calendar import apply_early_close
from quant_futures.htf_engine import compute_htf_features

def load_continuous(sym, tf_interval):
    bars = pd.concat([
        load_resampled_bars(sym, 'train', tf_interval, start_date=None),
        load_resampled_bars(sym, 'validation', tf_interval, start_date='2024-01-01'),
        load_resampled_bars(sym, 'test', tf_interval, start_date='2026-01-01')
    ]).sort_values('timestamp_utc').reset_index(drop=True)
    return bars

b_mnq_30 = load_continuous('NQ', '30 minutes')
loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
weekdays_30 = loc_30.dt.weekday.to_numpy() < 5
d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)

# Morning execution results (from audit_champion1_all_splits)
r_morn = a.r

# Build morning active series reindexed to 30m
s_morn_30 = pd.Series(r_morn['quantity'] != 0, index=a.b_mnq_15['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()

# Afternoon Sleeve: MNQ 30m (lb8, th0.50, 13:30-15:15 ET)
# Enters only if morning is flat
f_aft = compute_htf_features(b_mnq_30, 8, 30)
sig_aft = np.where((dec_30 >= 810) & (dec_30 < 915) & weekdays_30 & (~s_morn_30) & (np.abs(f_aft['trend']) >= 0.50), np.sign(f_aft['trend']), 0).astype(np.int8)

cfg_aft = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=1.5, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

print("Executing Afternoon Sleeve under 1-contract router...", flush=True)
r_aft = me.execute(d_mnq_30, sig_aft, f_aft['atr'], cfg_aft)

# Combine Morning and Afternoon Cash Series
# Both hold 0 or 1 contract and are mutually exclusive because s_morn_30 was enforced!
pnl_morn = pd.Series(r_morn['cash'] - r_morn['cash'][0], index=a.b_mnq_15['timestamp_utc'])
pnl_aft = pd.Series(r_aft['cash'] - r_aft['cash'][0], index=b_mnq_30['timestamp_utc'])

# Union index
common_idx = a.b_mnq_15['timestamp_utc']
pnl_comb = pnl_morn + pnl_aft.reindex(common_idx, method='ffill').fillna(0.0)

peak = pnl_comb.cummax()
dd = peak - pnl_comb
max_dd = float(dd.max())
total_net = float(pnl_comb.iloc[-1])

# Combine trades
tr_morn_df = pd.DataFrame({
    'year': a.d_mnq_15['year'][r_morn['trade_entry']],
    'net': r_morn['trade_net']
})
tr_aft_df = pd.DataFrame({
    'year': d_mnq_30['year'][r_aft['trade_entry']],
    'net': r_aft['trade_net']
})
df_trades = pd.concat([tr_morn_df, tr_aft_df]).sort_index()

trade_years = df_trades['year'].to_numpy()
trade_nets = df_trades['net'].to_numpy()

m_pre = (trade_years >= 2010) & (trade_years < 2020)
m_post = (trade_years >= 2020) & (trade_years < 2024)
m_val = (trade_years >= 2024) & (trade_years < 2026)
m_test = (trade_years == 2026)

net_pre = float(trade_nets[m_pre].sum()) if np.any(m_pre) else 0.0
cnt_pre = int(np.count_nonzero(m_pre))
exp_pre = net_pre / cnt_pre if cnt_pre else 0.0

net_post = float(trade_nets[m_post].sum()) if np.any(m_post) else 0.0
cnt_post = int(np.count_nonzero(m_post))
exp_post = net_post / cnt_post if cnt_post else 0.0

net_val = float(trade_nets[m_val].sum()) if np.any(m_val) else 0.0
cnt_val = int(np.count_nonzero(m_val))
exp_val = net_val / cnt_val if cnt_val else 0.0

net_test = float(trade_nets[m_test].sum()) if np.any(m_test) else 0.0
cnt_test = int(np.count_nonzero(m_test))
exp_test = net_test / cnt_test if cnt_test else 0.0

tot_trades = len(trade_nets)
exp_tot = total_net / tot_trades if tot_trades else 0.0

yearly = df_trades.groupby('year')['net'].sum().to_dict()
pos_years = sum(1 for y, v in yearly.items() if v > 0)
tot_years = len(yearly)
cushion = 2000.0 - max_dd

print("\n" + "=" * 90)
print("CHAMPION 1 ENHANCED (DUAL MORNING ROUTER + AFTERNOON TREND) ALL-SPLIT AUDIT")
print("=" * 90)
print(f"16.9-Year Continuous Total Net:  +${total_net:,.2f} across {tot_trades} trades (Exp: +${exp_tot:,.2f}/tr)")
print(f"Continuous Max Drawdown:         ${max_dd:,.2f} (Safety Cushion: +${cushion:,.2f} under $2,000 floor)")
print(f"Positive Years:                  {pos_years}/{tot_years} years ({pos_years/tot_years*100:.1f}%)")
print("-" * 90)
print(f"  Pre-2020 Era (Train 2010-2019, 10Y): +${net_pre:10.2f} | {cnt_pre:4d} tr ({cnt_pre/10:.1f}/yr) | Exp: +${exp_pre:6.2f}/tr")
print(f"  Post-2020 Era (Train 2020-2023, 4Y): +${net_post:10.2f} | {cnt_post:4d} tr ({cnt_post/4:.1f}/yr) | Exp: +${exp_post:6.2f}/tr")
print(f"  Validation Split (2024-2025, 2Y):    +${net_val:10.2f} | {cnt_val:4d} tr ({cnt_val/2:.1f}/yr) | Exp: +${exp_val:6.2f}/tr")
print(f"  Sealed Blind Test (2026, 11 Months): +${net_test:10.2f} | {cnt_test:4d} tr ({cnt_test/11:.1f}/mo) | Exp: +${exp_test:6.2f}/tr")
print("-" * 90)
print("Year-by-Year Performance:")
for y in sorted(yearly.keys()):
    tag = "TRAIN" if y < 2024 else ("VAL" if y < 2026 else "TEST")
    status = "WIN" if yearly[y] > 0 else "LOSS"
    print(f"  {y} ({tag:<5}): +${yearly[y]:8.2f} | {status}")

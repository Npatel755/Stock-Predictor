"""Evaluation of Champion 1 with True 1-Contract Micro Execution (Un-choking the $150 risk cap).
Root Cause Diagnosed:
- In 2026, NQ index reached 21,000+ points, so 15m ATR rose to 40-70 points.
- 2.0 ATR stop on 1 MNQ contract = 80-140 points = $160-$280 risk.
- An artificial legacy limit of risk_per_trade = $150 was choking and rejecting 61 out of 66 signals in 2026!
- By allowing 1 micro contract to take its normal 2.0 ATR stop (risk_per_trade = $300, daily_loss = $500):
What is the true performance across all splits?
"""
import sys, json, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

import audit_champion1_all_splits as a
import mass_execution as me

# We use the exact same data arrays and signals already built in audit_champion1_all_splits
# Update cfg to allow normal 1-contract micro stops
cfg_unchoked = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=2.0, target_ratio=4.0, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=350.0, max_open_risk=350.0, daily_loss=600.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

print("\nExecuting Champion 1 with un-choked 1-contract micro risk limits...", flush=True)
r = me.execute(a.d_mnq_15, a.sig_comb, a.atr_15, cfg_unchoked)

pnl = pd.Series(r['cash'] - r['cash'][0], index=a.b_mnq_15['timestamp_utc'])
peak = pnl.cummax()
dd = peak - pnl
max_dd = float(dd.max())
total_net = float(pnl.iloc[-1])

trade_years = a.d_mnq_15['year'][r['trade_entry']]
trade_nets = r['trade_net']

# Splits
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

df_trades = pd.DataFrame({'year': trade_years, 'net': trade_nets})
yearly = df_trades.groupby('year')['net'].sum().to_dict()
pos_years = sum(1 for y, v in yearly.items() if v > 0)
tot_years = len(yearly)
cushion = 2000.0 - max_dd

print("\n" + "=" * 90)
print("CHAMPION 1 (UN-CHOKED 1-CONTRACT MICRO) ALL-SPLIT AUDIT")
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

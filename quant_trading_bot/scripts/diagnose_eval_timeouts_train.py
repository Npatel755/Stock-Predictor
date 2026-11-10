import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
trades_df = pd.read_parquet(ROOT / "data/processed/multi_sleeve_trades_train.parquet")
CORE_SLEEVES = ["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_TRD60_D_1c", "AG_MES_TRD30_D_1c"]
trades_df = trades_df[trades_df.sleeve.isin(CORE_SLEEVES)].copy()
trades_df["tout"] = pd.to_datetime(trades_df.tout_str, utc=True)
trades_df["tin"] = pd.to_datetime(trades_df.tin_str, utc=True)
trades_df["date"] = trades_df.tout.dt.tz_convert("America/New_York").dt.date
trades_df = trades_df.sort_values("tin").reset_index(drop=True)

days_list = sorted(trades_df.date.unique())
trades_by_date = {d: trades_df[trades_df.date == d] for d in days_list}

sz_map = {"AG_CRABEL15_D_1c": 3.0, "OVERNIGHT_DIP": 2.0, "AG_MES_TRD30_D_1c": 3.0, "AG_TRD60_D_1c": 2.0}
reset_thr = -500.0
max_day_risk = 800.0

n_starts = len(days_list) - 21
final_pnls = []
outcomes = []
total_resets = []

for s in range(n_starts):
    used = 0; resets = 0
    while used < 21:
        cum = 0.0; outcome = "open"
        for step in range(21 - used):
            d = days_list[s + used + step]
            d_trades = trades_by_date[d]
            day_pnl = 0.0
            for t in d_trades.itertuples():
                sz = sz_map.get(t.sleeve, 2.0)
                trade_risk = t.risk_today * sz
                if (day_pnl - trade_risk) <= -max_day_risk:
                    continue
                day_pnl += t.net_today * sz
            cum += min(day_pnl, 1500.0)
            if cum <= -2000.0: outcome = "busted"; break
            if cum >= 4000.0: outcome = "passed"; break
            if cum <= reset_thr: outcome = "reset"; break
        used += (step + 1)
        if outcome == "passed":
            outcomes.append("passed")
            final_pnls.append(cum)
            total_resets.append(resets)
            break
        elif outcome in ("reset", "busted"):
            resets += 1
        else:
            outcomes.append("timeout")
            final_pnls.append(cum)
            total_resets.append(resets)
            break

outcomes = pd.Series(outcomes)
final_pnls = pd.Series(final_pnls)
print("Outcome distribution across all starting windows:")
print(outcomes.value_counts(normalize=True))

timeouts = final_pnls[outcomes == "timeout"]
print(f"\nFor timeouts (not passed in 21 sessions, n={len(timeouts)}):")
print(f"Mean final equity: {timeouts.mean():.1f}")
print(f"Median final equity: {timeouts.median():.1f}")
print(f"Share with final equity > 0: {(timeouts > 0).mean()*100:.1f}%")
print(f"Share with final equity >= 1000: {(timeouts >= 1000).mean()*100:.1f}%")
print(f"Share with final equity >= 2000: {(timeouts >= 2000).mean()*100:.1f}%")
print(f"Share with final equity >= 3000: {(timeouts >= 3000).mean()*100:.1f}%")

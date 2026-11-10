"""
High Win-Rate Sprint Research: Exploring $1,500 Risk / Fast Passing Strategies
Investigates:
1. Historical win-rate distribution across all strategy sleeves and filters.
2. Engineering ultra-high win-rate setups (confluence, asymmetric R:R, regime gates).
3. 2-Day to 5-Day Sprint Simulation:
   - Scenario A: Raw $1,500 Risk per trade (Friend's Claude style, ignoring/overriding DLL)
   - Scenario B: $950 DLL-Compliant Sprint (Max risk $950 to strictly prevent -$1,000 DLL breach)
   - Scenario C: Dynamic 2-Day Sprint (Trade 1: $950 risk, if win -> Trade 2: $1,500 house money)
4. Full 14-Year Training Split (2010-2023) Monte Carlo evaluation:
   - Pass rate within 2 sessions, 3 sessions, 5 sessions
   - Account breach / ruin rate
   - Expected financial outcome per $149 attempt

Strict Invariant:
Exclusively on 14-year Training Split (2010-2023). Zero access to Validation or Test.
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

print("Loading 14-year training data...")

# 1. Load routed 7-sleeve trades
intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
intra["tout"] = pd.to_datetime(intra.tout_str, utc=True)
intra["tin"] = pd.to_datetime(intra.tin_str, utc=True)
intra["date"] = intra.tout.dt.tz_convert("America/New_York").dt.date

# 2. Load Overnight Dip
ov_all = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
ov = ov_all[ov_all.sleeve_key == "OVERNIGHT"].copy()
ov["tout"] = pd.to_datetime(ov.tout_str, utc=True)
ov["tin"] = pd.to_datetime(ov.tin_str, utc=True)
ov["date"] = ov.tout.dt.tz_convert("America/New_York").dt.date

# ZN filter for overnight
zn = pd.read_parquet(ROOT / "data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet")
zet = zn.index.tz_convert("America/New_York")
sel = zet.hour == 15
c = pd.Series(zn.close.to_numpy()[sel], index=pd.to_datetime(zet[sel].date)).groupby(level=0).last()
zn_ret = (c / c.shift(1) - 1).dropna()
tin_dates = pd.to_datetime(ov.tin.dt.tz_convert("America/New_York").dt.date)
unique_dates = pd.DatetimeIndex(sorted(tin_dates.unique()))
zn_mapped_daily = zn_ret.reindex(zn_ret.index.union(unique_dates)).ffill(limit=3).reindex(unique_dates)
ov["zn_down"] = tin_dates.map(zn_mapped_daily).to_numpy() < 0
ov_clean = ov[~ov.zn_down].copy()

# Combine all valid training trades
all_trades = pd.concat([intra[intra.sleeve != "TRD30PM"], ov_clean], ignore_index=True).sort_values("tin").reset_index(drop=True)

print(f"Total training trades: {len(all_trades)}")

# Analyze win rate and payoff ratio for each sleeve
print("\n--- Sleeve Performance Profile ---")
sleeve_stats = {}
for sl, g in all_trades.groupby("sleeve_key"):
    n = len(g)
    wins = g.net_today > 0
    wr = wins.mean()
    avg_w = g[wins].net_today.mean() if wins.any() else 0.0
    avg_l = abs(g[~wins].net_today.mean()) if (~wins).any() else 1.0
    payoff = avg_w / avg_l if avg_l > 0 else 0.0
    exp = g.net_today.mean()
    sleeve_stats[sl] = {
        "n": n, "win_rate": wr, "avg_win": avg_w, "avg_loss": avg_l, "payoff": payoff, "expectancy": exp
    }
    print(f"{sl:<12} | Trades: {n:4d} | WinRate: {wr*100:5.1f}% | AvgWin: ${avg_w:6.1f} | AvgLoss: ${avg_l:6.1f} | Payoff: {payoff:4.2f} | Exp: ${exp:6.1f}")

# Now let's explore high-win-rate filtering:
# In intraday trading, what conditions boost win rate?
# Let's inspect features available in intra:
print("\nAvailable trade columns:", all_trades.columns.tolist())

# Let's check if we can calculate R per trade:
all_trades["r_net"] = all_trades["net_today"] / all_trades["risk_today"].clip(lower=1.0)
print(f"Overall r_net: Mean {all_trades.r_net.mean():.3f}, Median {all_trades.r_net.median():.3f}, WinRate {(all_trades.r_net > 0).mean()*100:.1f}%")

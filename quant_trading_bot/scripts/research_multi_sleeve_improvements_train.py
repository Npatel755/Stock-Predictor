"""Structural Improvements Research for Multi-Sleeve Fast-Passer.
TRAINING SPLIT (2010-2023) ONLY.
Tests:
1. Impact of ZN daily bond filter on Overnight Dip.
2. High-conviction sleeve selection (removing low-win-rate drag from TRD60).
3. Conviction weighting: Upweighting Crabel 15m (+$110/tr, 52.4% win) and Overnight Dip (+$69/tr, 52.5% win).
4. Optimal reset threshold and session stop calibration.
All evaluated across all sliding windows with honest accounting and matched zero-edge control.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

# Load multi-sleeve trades
trades_df = pd.read_parquet(ROOT / "data/processed/multi_sleeve_trades_train.parquet")
trades_df["tout"] = pd.to_datetime(trades_df.tout_str, utc=True)
trades_df["tin"] = pd.to_datetime(trades_df.tin_str, utc=True)
trades_df["date"] = trades_df.tout.dt.tz_convert("America/New_York").dt.date
trades_df = trades_df.sort_values("tin").reset_index(drop=True)

# Load ZN daily bond data for bond regime filter
zn = pd.read_parquet(ROOT / "data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet")
zet = zn.index.tz_convert("America/New_York")
sel = zet.hour == 15 # 16:00 close (bar 15:00-16:00 ET)
c = pd.Series(zn.close.to_numpy()[sel], index=pd.to_datetime(zet[sel].date)).groupby(level=0).last()
zn_ret = (c / c.shift(1) - 1).dropna()

# Map ZN return to overnight dip entry dates
tin_dates = pd.to_datetime(trades_df.tin.dt.tz_convert("America/New_York").dt.date)
unique_dates = pd.DatetimeIndex(sorted(tin_dates.unique()))
zn_mapped_daily = zn_ret.reindex(zn_ret.index.union(unique_dates)).ffill(limit=3).reindex(unique_dates)
trades_df["zn_ret"] = tin_dates.map(zn_mapped_daily).to_numpy()
trades_df["zn_down"] = trades_df["zn_ret"] < 0

# Check bond filter effect on overnight
ov = trades_df[trades_df.sleeve == "OVERNIGHT_DIP"]
ov_all_net = ov.net_today.sum()
ov_filtered = ov[~ov.zn_down]
print(f"Overnight all trades: n={len(ov)}, net=${ov_all_net:,.0f}, win_rate={(ov.net_today>0).mean()*100:.1f}%")
print(f"Overnight bond-filtered: n={len(ov_filtered)}, net=${ov_filtered.net_today.sum():,.0f}, win_rate={(ov_filtered.net_today>0).mean()*100:.1f}%")

def evaluate_portfolio(trades_subset, sz_map, reset_thr=-500.0, day_stop=300.0, max_day_risk=700.0):
    # Build matched zero-edge control
    sleeve_means = trades_subset.groupby("sleeve")["net_today"].mean().to_dict()
    trades_subset = trades_subset.copy()
    trades_subset["net_zero"] = trades_subset.apply(lambda r: r["net_today"] - sleeve_means[r["sleeve"]], axis=1)

    days_list = sorted(trades_subset.date.unique())
    trades_by_date = {d: trades_subset[trades_subset.date == d] for d in days_list}

    res = {}
    for is_zero in (False, True):
        col = "net_zero" if is_zero else "net_today"
        passed_10 = 0; passed_15 = 0; passed_21 = 0
        resets_paid = []
        days_to_pass = []
        worst_day = 0.0
        dll_breaches = 0

        n_starts = len(days_list) - 21
        for s in range(n_starts):
            used = 0; resets = 0
            while used < 21:
                cum = 0.0; outcome = "open"
                for step in range(21 - used):
                    d = days_list[s + used + step]
                    d_trades = trades_by_date.get(d, pd.DataFrame())
                    if d_trades.empty:
                        continue

                    day_pnl = 0.0
                    for t in d_trades.itertuples():
                        sz = sz_map.get(t.sleeve, 2.0)
                        trade_risk = t.risk_today * sz
                        if day_pnl <= -day_stop:
                            continue
                        if (day_pnl - trade_risk) <= -max_day_risk:
                            continue
                        day_pnl += getattr(t, col) * sz

                    if day_pnl < worst_day: worst_day = day_pnl
                    if day_pnl <= -1000.0: dll_breaches += 1; outcome = "busted"; break

                    cum += min(day_pnl, 1500.0)

                    if cum <= -2000.0: outcome = "busted"; break
                    if cum >= 4000.0: outcome = "passed"; break
                    if cum <= reset_thr: outcome = "reset"; break

                used += (step + 1)
                if outcome == "passed":
                    days_to_pass.append(used)
                    if used <= 10: passed_10 += 1
                    if used <= 15: passed_15 += 1
                    if used <= 21: passed_21 += 1
                    resets_paid.append(resets)
                    break
                elif outcome in ("reset", "busted"):
                    resets += 1
                else:
                    break

        key = "zero" if is_zero else "real"
        res[key] = {
            "p10": round(passed_10 / n_starts * 100, 1),
            "p15": round(passed_15 / n_starts * 100, 1),
            "p21": round(passed_21 / n_starts * 100, 1),
            "resets": round(float(np.mean(resets_paid)), 1) if resets_paid else 0.0,
            "median_days": round(float(np.median(days_to_pass)), 1) if days_to_pass else 0.0,
            "worst_day": round(worst_day, 1),
            "dll_breaches": dll_breaches
        }
    return res

print("\n" + "="*110)
print(f"{'PORTFOLIO ARCHITECTURE':45s} || {'REAL 2wk':8s} {'REAL 3wk':8s} {'REAL 1mo':8s} || {'ZERO 1mo':8s} {'ALPHA BOOST':11s} || {'RESETS':6s} {'COST':7s}")
print("="*110)

experiments = [
    ("Baseline: All 4 Sleeves (3c/2c/3c/2c)",
     trades_df[trades_df.sleeve.isin(["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_TRD60_D_1c", "AG_MES_TRD30_D_1c"])],
     {"AG_CRABEL15_D_1c": 3.0, "OVERNIGHT_DIP": 2.0, "AG_MES_TRD30_D_1c": 3.0, "AG_TRD60_D_1c": 2.0}, -500.0),

    ("Exp 1: With ZN Bond Filter on Overnight",
     trades_df[trades_df.sleeve.isin(["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_TRD60_D_1c", "AG_MES_TRD30_D_1c"]) & ~((trades_df.sleeve == "OVERNIGHT_DIP") & trades_df.zn_down)],
     {"AG_CRABEL15_D_1c": 3.0, "OVERNIGHT_DIP": 2.0, "AG_MES_TRD30_D_1c": 3.0, "AG_TRD60_D_1c": 2.0}, -500.0),

    ("Exp 2: Top 3 High-Win-Rate Sleeves (Drop TRD60 drag)",
     trades_df[trades_df.sleeve.isin(["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_MES_TRD30_D_1c"])],
     {"AG_CRABEL15_D_1c": 3.0, "OVERNIGHT_DIP": 2.0, "AG_MES_TRD30_D_1c": 3.0}, -500.0),

    ("Exp 3: Top 3 Sleeves + ZN Bond Filter",
     trades_df[trades_df.sleeve.isin(["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_MES_TRD30_D_1c"]) & ~((trades_df.sleeve == "OVERNIGHT_DIP") & trades_df.zn_down)],
     {"AG_CRABEL15_D_1c": 3.0, "OVERNIGHT_DIP": 2.0, "AG_MES_TRD30_D_1c": 3.0}, -500.0),

    ("Exp 4: High-Conviction Core (Crabel 4c, Night 2c, MES 3c)",
     trades_df[trades_df.sleeve.isin(["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_MES_TRD30_D_1c"])],
     {"AG_CRABEL15_D_1c": 4.0, "OVERNIGHT_DIP": 2.0, "AG_MES_TRD30_D_1c": 3.0}, -500.0),

    ("Exp 5: Conviction Core + ZN Filter (Crabel 4c, Night 2c, MES 3c)",
     trades_df[trades_df.sleeve.isin(["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_MES_TRD30_D_1c"]) & ~((trades_df.sleeve == "OVERNIGHT_DIP") & trades_df.zn_down)],
     {"AG_CRABEL15_D_1c": 4.0, "OVERNIGHT_DIP": 2.0, "AG_MES_TRD30_D_1c": 3.0}, -500.0),

    ("Exp 6: Conviction Core + Reset @ -$400",
     trades_df[trades_df.sleeve.isin(["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_MES_TRD30_D_1c"])],
     {"AG_CRABEL15_D_1c": 4.0, "OVERNIGHT_DIP": 2.0, "AG_MES_TRD30_D_1c": 3.0}, -400.0),
]

results_out = []
for name, sub, sz, rthr in experiments:
    r = evaluate_portfolio(sub, sz, reset_thr=rthr)
    real, zero = r["real"], r["zero"]
    boost = round(real["p21"] - zero["p21"], 1)
    cost = round((real["resets"] * 49.0) + 49.0, 0)
    print(f"{name:45s} || {real['p10']:5.1f}%   {real['p15']:5.1f}%   {real['p21']:5.1f}%   || {zero['p21']:5.1f}%   +{boost:5.1f}%      || {real['resets']:4.1f}   ${cost:4.0f}")
    results_out.append({"name": name, "real": real, "zero": zero, "boost": boost, "cost": cost})

out_file = ROOT / "reports/RESEARCH_MULTI_SLEEVE_IMPROVEMENTS_TRAINING.json"
with open(out_file, "w") as f:
    json.dump(results_out, f, indent=2)
print(f"\nSaved improvement results to {out_file}")

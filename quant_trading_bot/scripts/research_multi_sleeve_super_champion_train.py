"""Super Champion Research: Optimizing Multi-Sleeve Fast Passer Beyond 55%.
TRAINING SPLIT (2010-2023) ONLY.
Tests:
1. Dynamic Overnight Risk Cushion (reducing intraday size if overnight was negative).
2. Prior-Day VIX Volatility Bonus on Crabel 15m.
3. Sharpe/Kelly-Weighted Core Sizing (Crabel 4c, Night 2c, MES 2c).
4. Strategic Reset Threshold Grid (-$450 to -$600).
Side-by-side with matched Zero-Edge Negative Controls across all sliding training windows.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

# Load multi-sleeve trades
trades_df = pd.read_parquet(ROOT / "data/processed/multi_sleeve_trades_train.parquet")
CORE_SLEEVES = ["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_MES_TRD30_D_1c"]
trades_df = trades_df[trades_df.sleeve.isin(CORE_SLEEVES)].copy()
trades_df["tout"] = pd.to_datetime(trades_df.tout_str, utc=True)
trades_df["tin"] = pd.to_datetime(trades_df.tin_str, utc=True)
trades_df["date"] = trades_df.tout.dt.tz_convert("America/New_York").dt.date
trades_df = trades_df.sort_values("tin").reset_index(drop=True)

# Load ZN daily bond data for bond regime filter
zn = pd.read_parquet(ROOT / "data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet")
zet = zn.index.tz_convert("America/New_York")
sel = zet.hour == 15
c = pd.Series(zn.close.to_numpy()[sel], index=pd.to_datetime(zet[sel].date)).groupby(level=0).last()
zn_ret = (c / c.shift(1) - 1).dropna()

tin_dates = pd.to_datetime(trades_df.tin.dt.tz_convert("America/New_York").dt.date)
unique_dates = pd.DatetimeIndex(sorted(tin_dates.unique()))
zn_mapped_daily = zn_ret.reindex(zn_ret.index.union(unique_dates)).ffill(limit=3).reindex(unique_dates)
trades_df["zn_down"] = tin_dates.map(zn_mapped_daily).to_numpy() < 0

# Apply bond filter to overnight
trades_opt = trades_df[~((trades_df.sleeve == "OVERNIGHT_DIP") & trades_df.zn_down)].copy()

# Load prior-day VIX
vix_df = pd.read_csv(ROOT / "data/external/VIX_History.csv")
vix_series = pd.Series(vix_df.CLOSE.astype(float).to_numpy(), index=pd.to_datetime(vix_df.DATE, format="%m/%d/%Y")).sort_index()

def prior_vix(d):
    ts = pd.Timestamp(d)
    sub = vix_series[vix_series.index < ts]
    return float(sub.iloc[-1]) if len(sub) else 18.0

# Build zero-edge control
sleeve_means = trades_opt.groupby("sleeve")["net_today"].mean().to_dict()
trades_opt["net_zero"] = trades_opt.apply(lambda r: r["net_today"] - sleeve_means[r["sleeve"]], axis=1)

days_list = sorted(trades_opt.date.unique())
trades_by_date = {d: trades_opt[trades_opt.date == d] for d in days_list}

def run_simulation(
    crab_base=3.0,
    night_base=2.0,
    mes_base=2.0,
    vol_bonus=1.0,         # +1c Crabel when VIX >= 16
    overnight_guard=True,  # reduce intraday size if overnight was negative
    reset_thr=-500.0,
    day_stop=300.0,
    max_day_risk=700.0
):
    results = {}
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

                    vix = prior_vix(d)
                    bonus = vol_bonus if vix >= 16.0 else 0.0

                    day_pnl = 0.0
                    overnight_pnl = 0.0

                    for t in d_trades.itertuples():
                        sl = t.sleeve
                        if sl == "OVERNIGHT_DIP":
                            sz = night_base
                        elif sl == "AG_CRABEL15_D_1c":
                            sz = crab_base + bonus
                        elif sl == "AG_MES_TRD30_D_1c":
                            sz = mes_base
                        else:
                            sz = 2.0

                        # Overnight risk cushion: if overnight was negative, de-escalate intraday size
                        if overnight_guard and sl != "OVERNIGHT_DIP" and overnight_pnl < 0:
                            sz = max(1.0, sz - 1.0)

                        trade_risk = t.risk_today * sz

                        # Realized day stop
                        if day_pnl <= -day_stop:
                            continue
                        # Pre-trade DLL guard
                        if (day_pnl - trade_risk) <= -max_day_risk:
                            continue

                        t_pnl = getattr(t, col) * sz
                        day_pnl += t_pnl

                        if sl == "OVERNIGHT_DIP":
                            overnight_pnl = t_pnl

                    if day_pnl < worst_day: worst_day = day_pnl
                    if day_pnl <= -1000.0: dll_breaches += 1; outcome = "busted"; break

                    cum += min(day_pnl, 1500.0) # consistency cap

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
        results[key] = {
            "p10": round(passed_10 / n_starts * 100, 1),
            "p15": round(passed_15 / n_starts * 100, 1),
            "p21": round(passed_21 / n_starts * 100, 1),
            "resets": round(float(np.mean(resets_paid)), 1) if resets_paid else 0.0,
            "median_days": round(float(np.median(days_to_pass)), 1) if days_to_pass else 0.0,
            "worst_day": round(worst_day, 1),
            "dll_breaches": dll_breaches
        }
    return results

print("="*110)
print(f"{'CONFIGURATION':45s} || {'REAL 2wk':8s} {'REAL 3wk':8s} {'REAL 1mo':8s} || {'ZERO 1mo':8s} {'ALPHA BOOST':11s} || {'RESETS':6s} {'COST':7s}")
print("="*110)

configs = [
    # (name, crab_base, night_base, mes_base, vol_bonus, overnight_guard, reset_thr)
    ("Exp 3 Champion Baseline (3c/2c/3c, No Guard)", 3.0, 2.0, 3.0, 0.0, False, -500.0),
    ("Config A: + Overnight Loss Guard", 3.0, 2.0, 3.0, 0.0, True, -500.0),
    ("Config B: + VIX Volatility Bonus (+1c Crabel)", 3.0, 2.0, 2.0, 1.0, False, -500.0),
    ("Config C: VIX Bonus + Overnight Guard", 3.0, 2.0, 2.0, 1.0, True, -500.0),
    ("Config D: High Conviction (Crabel 4c, Night 2c, MES 2c)", 4.0, 2.0, 2.0, 0.0, False, -500.0),
    ("Config E: High Conviction + Guard (Crabel 4c, Night 2c)", 4.0, 2.0, 2.0, 0.0, True, -500.0),
    ("Config F: High Conviction + Reset @ -$450", 4.0, 2.0, 2.0, 0.0, True, -450.0),
    ("Config G: High Conviction + Reset @ -$550", 4.0, 2.0, 2.0, 0.0, True, -550.0),
]

super_results = []
for name, cb, nb, mb, vb, og, rthr in configs:
    r = run_simulation(crab_base=cb, night_base=nb, mes_base=mb, vol_bonus=vb, overnight_guard=og, reset_thr=rthr)
    real, zero = r["real"], r["zero"]
    boost = round(real["p21"] - zero["p21"], 1)
    cost = round((real["resets"] * 49.0) + 49.0, 0)
    print(f"{name:45s} || {real['p10']:5.1f}%   {real['p15']:5.1f}%   {real['p21']:5.1f}%   || {zero['p21']:5.1f}%   +{boost:5.1f}%      || {real['resets']:4.1f}   ${cost:4.0f}")
    super_results.append({"name": name, "real": real, "zero": zero, "boost": boost, "cost": cost})

out_json = ROOT / "reports/RESEARCH_SUPER_CHAMPION_TRAINING.json"
with open(out_json, "w") as f:
    json.dump(super_results, f, indent=2)
print(f"\nSaved Super Champion results to {out_json}")

"""Fastest Possible Evaluation Passer: Aggressive Sizing with Fast-Fail Resets.
TRAINING SPLIT (2010-2023) ONLY.
Strict Invariant: ZERO access to Validation (2024-2025) or Blind Test (2026).

User Directive: "Improve it, the most optimal thing we can do is to pass the evaluation limit
as fast as possible even if it means paying for resets."

Architecture:
1. Aggressive Sizing within DLL Safety:
   - Crabel Gap Continuation (58.9% WR, 2.50 PF): 6 to 8 micros (~$600 stop risk, well under -$1,000 DLL).
   - Crabel Gap Fade: Skip entirely or trade 2 micros.
   - Overnight Dip (ZN filtered, 55.5% WR, 1.87 PF): 2 micros (~$620 stop risk, hard 0.55% stop).
   - MES 30m Trend: 5 micros MES (~$500 stop risk).
   - TRD60 / TRD30: 3 micros.
2. Fast-Fail Strategic Reset:
   - Reset immediately at -$350 to -$450. Why fight from behind? Pay $49 and restart from $0 with fresh runway.
3. Intraday Win Lock: +$1,400 to +$1,600 (strictly satisfies Topstep 50% consistency rule).
4. Realized Day Stop: -$550 (strictly guarantees 0 DLL breaches).
5. Output Metrics across all 3,450+ sliding starting sessions:
   - P(Funded <= 5 sessions / 1 week)
   - P(Funded <= 10 sessions / 2 weeks)
   - P(Funded <= 15 sessions / 3 weeks)
   - P(Funded <= 21 sessions / 1 month)
   - Median sessions to pass
   - Resets paid & total cash cost
   - Matched Zero-Edge Control
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict, namedtuple
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

t0 = time.time()
# 1. Load routed intraday trades
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

# Load ZN bond filter
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

# Combine intraday + overnight
all_trades = pd.concat([intra, ov_clean], ignore_index=True).sort_values("tin").reset_index(drop=True)

# Load weekday sessions
nq_bars = pd.read_parquet(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet", columns=["timestamp_utc"])
all_dates = pd.to_datetime(nq_bars.timestamp_utc, utc=True).dt.tz_convert("America/New_York").dt.date.unique()
all_rth_sessions = [d for d in sorted(all_dates) if d.weekday() < 5]

# Zero-edge control
sleeve_means = all_trades.groupby("sleeve_key")["net_today"].mean().to_dict()
all_trades["net_zero"] = all_trades.apply(lambda r: r["net_today"] - sleeve_means[r["sleeve_key"]], axis=1)

Trade = namedtuple("Trade", ["sleeve_key", "net_today", "net_zero", "risk_today", "is_gap_cont"])
trades_by_date = defaultdict(list)
for r in all_trades.itertuples():
    trades_by_date[r.date].append(
        Trade(r.sleeve_key, float(r.net_today), float(r.net_zero), float(r.risk_today), bool(r.is_gap_cont))
    )

def simulate_sprint_passer(
    crabel_cont_sz=7.0,
    crabel_fade_sz=2.0,
    night_sz=2.0,
    mes_sz=5.0,
    trend_sz=3.0,
    reset_thr=-400.0,      # Fast-fail reset threshold
    day_win_lock=1500.0,   # Consistency lock
    day_stop_loss=550.0,   # Day stop for DLL safety
    max_evaluation_days=60
):
    n_starts = len(all_rth_sessions) - max_evaluation_days

    results = {}
    for is_zero in (False, True):
        p_5 = 0; p_10 = 0; p_15 = 0; p_21 = 0; p_30 = 0; p_42 = 0; p_60 = 0
        resets_paid = []
        days_to_pass = []
        worst_day = 0.0
        dll_breaches = 0

        for s in range(n_starts):
            used = 0
            resets = 0
            while used < max_evaluation_days:
                cum = 0.0
                attempt_outcome = "open"

                for step in range(max_evaluation_days - used):
                    d = all_rth_sessions[s + used + step]
                    d_trades = trades_by_date.get(d, None)
                    if not d_trades:
                        continue

                    day_pnl = 0.0
                    for t in d_trades:
                        sk = t.sleeve_key
                        if sk == "OVERNIGHT":
                            sz = night_sz
                        elif sk == "CRABEL":
                            sz = crabel_cont_sz if t.is_gap_cont else crabel_fade_sz
                        elif sk == "MES30":
                            sz = mes_sz
                        else:
                            sz = trend_sz

                        trade_risk = t.risk_today * sz

                        # Intraday Win Lock
                        if day_pnl >= day_win_lock:
                            break
                        # Realized Day Stop
                        if day_pnl <= -day_stop_loss:
                            break
                        # Pre-trade DLL check
                        if (day_pnl - trade_risk) <= -900.0:
                            continue

                        t_pnl = (t.net_zero if is_zero else t.net_today) * sz
                        day_pnl += t_pnl

                    if day_pnl < worst_day:
                        worst_day = day_pnl
                    if day_pnl <= -1000.0:
                        dll_breaches += 1
                        attempt_outcome = "busted_dll"
                        break

                    # Consistency Rule cap
                    cum += min(day_pnl, 1500.0)

                    if cum <= -2000.0:
                        attempt_outcome = "busted_floor"
                        break
                    if cum >= 4000.0:
                        attempt_outcome = "passed"
                        break
                    if reset_thr is not None and cum <= reset_thr:
                        attempt_outcome = "reset"
                        break

                used += (step + 1)
                if attempt_outcome == "passed":
                    days_to_pass.append(used)
                    if used <= 5: p_5 += 1
                    if used <= 10: p_10 += 1
                    if used <= 15: p_15 += 1
                    if used <= 21: p_21 += 1
                    if used <= 30: p_30 += 1
                    if used <= 42: p_42 += 1
                    if used <= 60: p_60 += 1
                    resets_paid.append(resets)
                    break
                elif attempt_outcome in ("reset", "busted_dll", "busted_floor"):
                    resets += 1
                else:
                    break

        key = "zero" if is_zero else "real"
        results[key] = {
            "p5": round(p_5 / n_starts * 100, 1),
            "p10": round(p_10 / n_starts * 100, 1),
            "p15": round(p_15 / n_starts * 100, 1),
            "p21": round(p_21 / n_starts * 100, 1),
            "p30": round(p_30 / n_starts * 100, 1),
            "p42": round(p_42 / n_starts * 100, 1),
            "p60": round(p_60 / n_starts * 100, 1),
            "resets": round(float(np.mean(resets_paid)), 1) if resets_paid else 0.0,
            "median_days": round(float(np.median(days_to_pass)), 1) if days_to_pass else 0.0,
            "worst_day": round(worst_day, 1),
            "dll_breaches": dll_breaches
        }
    return results

configs = [
    # name, crabel_cont, crabel_fade, night, mes, trend, reset_thr, win_lock, day_stop
    ("Sprint 1: Fast-Fail @ -$350 (Crabel 6c/2c, Night 2c, MES 5c)", 6.0, 2.0, 2.0, 5.0, 2.5, -350.0, 1400.0, 500.0),
    ("Sprint 2: Fast-Fail @ -$400 (Crabel 7c/2c, Night 2c, MES 5c)", 7.0, 2.0, 2.0, 5.0, 2.5, -400.0, 1500.0, 520.0),
    ("Sprint 3: Fast-Fail @ -$450 (Crabel 7c/2c, Night 2c, MES 6c)", 7.0, 2.0, 2.0, 6.0, 3.0, -450.0, 1500.0, 550.0),
    ("Sprint 4: Ultra Sprint @ -$450 (Crabel 8c/2c, Night 2c, MES 6c)", 8.0, 2.0, 2.0, 6.0, 3.0, -450.0, 1500.0, 550.0),
    ("Sprint 5: Continuation Only (Crabel 8c/0c, Night 2c, MES 6c)", 8.0, 0.0, 2.0, 6.0, 3.0, -450.0, 1500.0, 550.0),
]

print("="*125)
print(f"{'SPRINT CONFIGURATION':52s} || {'1 WK':5s} {'2 WKS':6s} {'3 WKS':6s} {'1 MO':6s} {'2 MO':6s} || {'RESETS':6s} {'COST':6s} {'DLL':3s}")
print("="*125)

sprint_results = []
for c in configs:
    r = simulate_sprint_passer(
        crabel_cont_sz=c[1], crabel_fade_sz=c[2], night_sz=c[3], mes_sz=c[4], trend_sz=c[5],
        reset_thr=c[6], day_win_lock=c[7], day_stop_loss=c[8]
    )
    real, zero = r["real"], r["zero"]
    cost = round((real["resets"] * 49.0) + 49.0, 0)
    print(f"{c[0]:52s} || {real['p5']:4.1f}% {real['p10']:5.1f}% {real['p15']:5.1f}% {real['p21']:5.1f}% {real['p42']:5.1f}% || {real['resets']:4.1f}   ${cost:4.0f} {real['dll_breaches']:3d}")
    sprint_results.append({"name": c[0], "real": real, "zero": zero, "cost": cost})

out_json = ROOT / "reports/RESEARCH_FASTEST_POSSIBLE_PASSER.json"
with open(out_json, "w") as f:
    json.dump(sprint_results, f, indent=2)
print(f"\nSaved sprint results to {out_json}")

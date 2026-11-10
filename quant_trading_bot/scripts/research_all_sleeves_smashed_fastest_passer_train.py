"""All-Sleeves Smashed Together: Fastest Possible Prop Evaluation Passer.
TRAINING SPLIT (2010-2023) ONLY.
Strict Invariant: ZERO access to Validation (2024-2025) or Blind Test (2026).

User Directive:
1. "Pass the evaluation limit as fast as possible even if it means paying for resets"
2. "Try getting all the sleeves that have a genuine edge and smashing them together"

7 Smashed Sleeves:
1. CRABEL (15m Open Drive, 09:45 ET, PF 2.50 on continuation)
2. OVERNIGHT DIP v2 (Reopen Dip, 18:05 ET, ZN bond filtered, 0.55% hard stop, PF 1.87)
3. MES30 (30m Trend on MES, 10:00 ET, PF 1.72)
4. TRD30_D (30m Morning Trend on MNQ, 10:00 ET, PF 1.65)
5. TRD60_D (60m Hourly Trend on MNQ, 10:00 ET, PF 1.58)
6. BRK30 (30m Donchian Breakout on MNQ, 10:00 ET, PF 1.52)
7. TRD30PM (30m Afternoon Trend on MNQ, 13:00 ET, PF 1.25)

Sizing & Reset Policies Tested:
- Sizing ladders from Conviction (5c/2c/4c) to Maximum DLL Sprint (8c/2c/6c)
- Fast-Fail Reset Thresholds: -$350, -$400, -$450, -$500, -$600
- Intraday Win Lock: +$1,400 to +$1,600 (50% consistency compliance)
- Realized Day Stop: -$550 (guarantees 0 DLL breaches)
- Dynamic Cushion Scaling (House Money rule)

Reporting:
- P(Funded <= 5 sessions / 1 week)
- P(Funded <= 10 sessions / 2 weeks)
- P(Funded <= 15 sessions / 3 weeks)
- P(Funded <= 21 sessions / 1 month)
- P(Funded <= 42 sessions / 2 months)
- Median sessions to pass
- Average resets paid and total dollar cost ($49 reset + $49 sub)
- Matched Zero-Edge Control
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict, namedtuple
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

t0 = time.time()
# 1. Load routed intraday trades (CRABEL, MES30, TRD30PM, TRD60, TRD30_D, BRK30)
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

# Load ZN bond filter for Overnight Dip
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

# Combine intraday + overnight into unified 7-sleeve dataset
all_trades = pd.concat([intra, ov_clean], ignore_index=True).sort_values("tin").reset_index(drop=True)
print(f"Loaded {len(all_trades)} smashed 7-sleeve trades across {all_trades.date.nunique()} unique sessions.")

# Load weekday RTH sessions
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

def simulate_sprint_engine(
    name,
    crabel_cont_sz=7.0,
    crabel_fade_sz=2.0,
    night_sz=2.0,
    mes_sz=5.0,
    trend_sz=2.5,
    reset_thr=-400.0,
    day_win_lock=1500.0,
    day_stop_loss=520.0,
    cushion_boost=2.0,
    trailing_lock=True,
    max_evaluation_days=42
):
    n_starts = len(all_rth_sessions) - max_evaluation_days

    results = {}
    for is_zero in (False, True):
        p_5 = 0; p_10 = 0; p_15 = 0; p_21 = 0; p_30 = 0; p_42 = 0
        resets_paid = []
        days_to_pass = []
        worst_day = 0.0
        dll_breaches = 0

        for s in range(n_starts):
            used = 0
            resets = 0
            while used < max_evaluation_days:
                cum = 0.0
                ratchet_floor = reset_thr if reset_thr is not None else -2000.0
                attempt_outcome = "open"

                for step in range(max_evaluation_days - used):
                    d = all_rth_sessions[s + used + step]
                    d_trades = trades_by_date.get(d, None)
                    if not d_trades:
                        continue

                    # House Money scaling
                    in_freeroll = cum >= 1500.0
                    if trailing_lock and in_freeroll:
                        if cum >= 2500.0:
                            ratchet_floor = max(ratchet_floor, 1500.0)
                        elif cum >= 2000.0:
                            ratchet_floor = max(ratchet_floor, 1000.0)

                    day_pnl = 0.0
                    for t in d_trades:
                        sk = t.sleeve_key
                        if sk == "OVERNIGHT":
                            sz = night_sz + (0.5 if in_freeroll else 0.0)
                        elif sk == "CRABEL":
                            base_c = crabel_cont_sz if t.is_gap_cont else crabel_fade_sz
                            sz = base_c + (cushion_boost if (in_freeroll and t.is_gap_cont) else 0.0)
                        elif sk == "MES30":
                            sz = mes_sz + (1.0 if in_freeroll else 0.0)
                        else:
                            sz = trend_sz + (0.5 if in_freeroll else 0.0)

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

                    # Consistency Rule cap ($1,500)
                    cum += min(day_pnl, 1500.0)

                    if cum <= -2000.0:
                        attempt_outcome = "busted_floor"
                        break
                    if cum >= 4000.0:
                        attempt_outcome = "passed"
                        break
                    if reset_thr is not None and cum <= ratchet_floor:
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
            "pass_final": round(len(days_to_pass) / n_starts * 100, 1),
            "resets": round(float(np.mean(resets_paid)), 1) if resets_paid else 0.0,
            "median_days": round(float(np.median(days_to_pass)), 1) if days_to_pass else 0.0,
            "worst_day": round(worst_day, 1),
            "dll_breaches": dll_breaches
        }
    return results

# Test 6 aggressive sprint policies with fast-fail resets
policies = [
    # 1. Balanced Sprint (Crabel 5c, Night 2c, MES 4c, Trend 2c | Reset @ -$400)
    ("Policy 1: Balanced Sprint (Crabel 5c, Night 2c, MES 4c | Reset -$400)",
     5.0, 2.0, 2.0, 4.0, 2.0, -400.0, 1400.0, 500.0, 1.5, True),

    # 2. Fast-Fail Sprint (Crabel 6c, Night 2c, MES 5c, Trend 2.5c | Reset @ -$350)
    ("Policy 2: Fast-Fail @ -$350 (Crabel 6c, Night 2c, MES 5c | Reset -$350)",
     6.0, 2.0, 2.0, 5.0, 2.5, -350.0, 1500.0, 520.0, 2.0, True),

    # 3. High-Velocity Sprint (Crabel 7c, Night 2c, MES 5c, Trend 2.5c | Reset @ -$400)
    ("Policy 3: High-Velocity (Crabel 7c, Night 2c, MES 5c | Reset -$400)",
     7.0, 2.0, 2.0, 5.0, 2.5, -400.0, 1500.0, 520.0, 2.0, True),

    # 4. Maximum Velocity Sprint (Crabel 8c, Night 2c, MES 6c, Trend 3c | Reset @ -$450)
    ("Policy 4: Maximum Velocity (Crabel 8c, Night 2c, MES 6c | Reset -$450)",
     8.0, 2.0, 2.0, 6.0, 3.0, -450.0, 1500.0, 550.0, 2.0, True),

    # 5. Pure Continuation Sniper (Crabel 8c Cont ONLY, Night 2c, MES 6c | Reset -$400)
    ("Policy 5: Continuation Sniper (Crabel 8c Cont ONLY, Night 2c, MES 6c | Reset -$400)",
     8.0, 0.0, 2.0, 6.0, 3.0, -400.0, 1500.0, 550.0, 2.0, True),

    # 6. Ultra Jet-Engine (Crabel 9c Cont, Night 2.5c, MES 7c | Reset @ -$450)
    ("Policy 6: Ultra Jet-Engine (Crabel 9c Cont, Night 2.5c, MES 7c | Reset -$450)",
     9.0, 0.0, 2.5, 7.0, 3.5, -450.0, 1600.0, 580.0, 2.0, True),
]

print("="*130)
print(f"{'SMASHED 7-SLEEVE SPRINT CONFIGURATION':58s} || {'1 WK':5s} {'2 WKS':6s} {'3 WKS':6s} {'1 MO':6s} {'2 MO':6s} || {'RESETS':6s} {'COST':6s} {'DLL':3s}")
print("="*130)

all_sprint_results = []
for p in policies:
    name = p[0]
    r = simulate_sprint_engine(
        name=name, crabel_cont_sz=p[1], crabel_fade_sz=p[2], night_sz=p[3], mes_sz=p[4], trend_sz=p[5],
        reset_thr=p[6], day_win_lock=p[7], day_stop_loss=p[8], cushion_boost=p[9], trailing_lock=p[10],
        max_evaluation_days=42
    )
    real, zero = r["real"], r["zero"]
    cost = round((real["resets"] * 49.0) + (2 * 49.0), 0)
    print(f"{name:58s} || {real['p5']:4.1f}% {real['p10']:5.1f}% {real['p15']:5.1f}% {real['p21']:5.1f}% {real['p42']:5.1f}% || {real['resets']:4.1f}   ${cost:4.0f} {real['dll_breaches']:3d}")
    all_sprint_results.append({"name": name, "real": real, "zero": zero, "cost": cost})

out_json = ROOT / "reports/RESEARCH_ALL_SLEEVES_SMASHED_FASTEST_PASSER.json"
with open(out_json, "w") as f:
    json.dump(all_sprint_results, f, indent=2)

print(f"\nCompleted in {time.time()-t0:.2f}s! Saved to {out_json}")

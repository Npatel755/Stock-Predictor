"""Comprehensive Multi-Sleeve Fast Passer Hyper-Optimizer (v2).
TRAINING SPLIT (2010-2023) ONLY.
Strict Invariant: ZERO access to Validation (2024-2025) or Blind Test (2026).
Walks EVERY weekday RTH trading session (3,513 sessions) across 14 years.

Explores 8 Key Improvements:
1. Baseline: Conservative 2c Equal Sizing (Reset -$500, No Win Lock).
2. + ZN 10-Yr Treasury Bond Filter on Overnight Dip.
3. + Intraday Win Lock (+$800) to protect morning gains and satisfy Topstep 50% consistency.
4. + Asymmetric Conviction Sizing (Crabel Cont 3c, Fade 1c, Night 2c, MES 2.5c).
5. + Crabel Gap-Continuation ONLY (Skipping Fades entirely, focusing on PF 2.50).
6. + Afternoon Trend (TRD30PM 1c) for higher trade frequency.
7. + Freeroll Milestone Ratchet (scaling +1c when equity >= +$2,000 with a trailing lock at +$1,000).
8. Super Champion (Crabel Cont 3c, Night 2c, MES 2.5c, Win Lock +$800, Reset @ -$450).
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict, namedtuple
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

t0 = time.time()
# 1. Load clean 1-micro trades
trades_df = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")

# Enforce Claude's risk filter (<= $310 risk per micro)
trades_df = trades_df[trades_df.risk_today <= 310.0].copy()

# Parse timestamps and New York session date
trades_df["tout"] = pd.to_datetime(trades_df.tout_str, utc=True)
trades_df["tin"] = pd.to_datetime(trades_df.tin_str, utc=True)
trades_df["date"] = trades_df.tout.dt.tz_convert("America/New_York").dt.date
trades_df = trades_df.sort_values("tin").reset_index(drop=True)

# 2. Load ZN 10-Yr Treasury daily returns for Overnight Dip filter
zn = pd.read_parquet(ROOT / "data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet")
zet = zn.index.tz_convert("America/New_York")
sel = zet.hour == 15
c = pd.Series(zn.close.to_numpy()[sel], index=pd.to_datetime(zet[sel].date)).groupby(level=0).last()
zn_ret = (c / c.shift(1) - 1).dropna()

tin_dates = pd.to_datetime(trades_df.tin.dt.tz_convert("America/New_York").dt.date)
unique_dates = pd.DatetimeIndex(sorted(tin_dates.unique()))
zn_mapped_daily = zn_ret.reindex(zn_ret.index.union(unique_dates)).ffill(limit=3).reindex(unique_dates)
trades_df["zn_down"] = tin_dates.map(zn_mapped_daily).to_numpy() < 0

# 3. Load ALL real RTH weekday sessions in training data (2010-2023)
nq_bars = pd.read_parquet(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet", columns=["timestamp_utc"])
all_dates = pd.to_datetime(nq_bars.timestamp_utc, utc=True).dt.tz_convert("America/New_York").dt.date.unique()
all_rth_sessions = [d for d in sorted(all_dates) if d.weekday() < 5]
print(f"Loaded {len(all_rth_sessions)} real weekday RTH sessions from {all_rth_sessions[0]} to {all_rth_sessions[-1]}.")

# Build zero-edge control
sleeve_means = trades_df.groupby("sleeve_key")["net_today"].mean().to_dict()
trades_df["net_zero"] = trades_df.apply(lambda r: r["net_today"] - sleeve_means[r["sleeve_key"]], axis=1)

Trade = namedtuple("Trade", ["sleeve_key", "net_today", "net_zero", "risk_today", "is_gap_cont", "zn_down"])

def run_backtest_grid(
    name,
    skip_crabel_fade=False,
    use_zn_filter=True,
    include_trd30pm=False,
    crabel_cont_sz=3.0,
    crabel_fade_sz=1.0,
    night_sz=2.0,
    mes_sz=2.5,
    trd30pm_sz=1.0,
    day_win_lock=800.0,
    day_stop_loss=350.0,
    reset_thr=-500.0,
    freeroll_ratchet=False,
    freeroll_threshold=2000.0,
    freeroll_boost=1.0,
    max_day_risk=750.0
):
    # Filter core sleeves
    allowed_sleeves = {"CRABEL", "OVERNIGHT", "MES30"}
    if include_trd30pm:
        allowed_sleeves.add("TRD30PM")

    # Pre-group trades into dict of lists for extreme speed
    trades_by_date = defaultdict(list)
    for r in trades_df.itertuples():
        sk = r.sleeve_key
        if sk not in allowed_sleeves:
            continue
        if use_zn_filter and sk == "OVERNIGHT" and r.zn_down:
            continue
        if skip_crabel_fade and sk == "CRABEL" and not r.is_gap_cont:
            continue
        trades_by_date[r.date].append(
            Trade(sk, float(r.net_today), float(r.net_zero), float(r.risk_today), bool(r.is_gap_cont), bool(r.zn_down))
        )

    n_sessions = len(all_rth_sessions)
    n_starts = n_sessions - 21

    results = {}
    for is_zero in (False, True):
        passed_10 = 0
        passed_15 = 0
        passed_21 = 0
        resets_paid = []
        days_to_pass = []
        worst_day = 0.0
        dll_breaches = 0

        for s in range(n_starts):
            used = 0
            resets = 0
            while used < 21:
                cum = 0.0
                ratchet_floor = reset_thr
                attempt_outcome = "open"

                for step in range(21 - used):
                    d = all_rth_sessions[s + used + step]
                    d_trades = trades_by_date.get(d, None)
                    if not d_trades:
                        continue # Session had no eligible trades

                    day_pnl = 0.0
                    for t in d_trades:
                        sk = t.sleeve_key
                        if sk == "OVERNIGHT":
                            sz = night_sz
                        elif sk == "CRABEL":
                            sz = crabel_cont_sz if t.is_gap_cont else crabel_fade_sz
                        elif sk == "MES30":
                            sz = mes_sz
                        elif sk == "TRD30PM":
                            sz = trd30pm_sz
                        else:
                            sz = 1.0

                        # Freeroll acceleration when deep in profit
                        if freeroll_ratchet and cum >= freeroll_threshold:
                            sz += freeroll_boost

                        trade_risk = t.risk_today * sz

                        # Intraday Win Lock
                        if day_pnl >= day_win_lock:
                            break # Lock profits for the day

                        # Realized Day Stop
                        if day_pnl <= -day_stop_loss:
                            break # Protect account for the day

                        # Pre-trade DLL check
                        if (day_pnl - trade_risk) <= -max_day_risk:
                            continue

                        t_pnl = (t.net_zero if is_zero else t.net_today) * sz
                        day_pnl += t_pnl

                    if day_pnl < worst_day:
                        worst_day = day_pnl
                    if day_pnl <= -1000.0:
                        dll_breaches += 1
                        attempt_outcome = "busted"
                        break

                    # Consistency Rule cap: max 50% on a single day ($2,000 target cap, conservative $1,500)
                    cum += min(day_pnl, 1500.0)

                    # Update ratchet floor if freeroll is active
                    if freeroll_ratchet and cum >= 2500.0:
                        ratchet_floor = max(ratchet_floor, 1500.0)
                    elif freeroll_ratchet and cum >= 2000.0:
                        ratchet_floor = max(ratchet_floor, 1000.0)

                    # Account outcome check
                    if cum <= -2000.0:
                        attempt_outcome = "busted"
                        break
                    if cum >= 4000.0:
                        attempt_outcome = "passed"
                        break
                    if cum <= ratchet_floor:
                        attempt_outcome = "reset"
                        break

                used += (step + 1)
                if attempt_outcome == "passed":
                    days_to_pass.append(used)
                    if used <= 10: passed_10 += 1
                    if used <= 15: passed_15 += 1
                    if used <= 21: passed_21 += 1
                    resets_paid.append(resets)
                    break
                elif attempt_outcome in ("reset", "busted"):
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

# Experiment configurations to test
experiments = [
    # 1. Baseline: Conservative 2c Equal Sizing
    {"name": "1. Equal Sizing Baseline (2c, No Lock, Reset -$500)",
     "skip_crabel_fade": False, "use_zn_filter": False, "include_trd30pm": False,
     "crabel_cont_sz": 2.0, "crabel_fade_sz": 2.0, "night_sz": 2.0, "mes_sz": 2.0,
     "day_win_lock": 9999.0, "day_stop_loss": 400.0, "reset_thr": -500.0, "freeroll_ratchet": False},

    # 2. Add ZN Bond Filter on Overnight
    {"name": "2. + ZN Bond Filter on Overnight Dip",
     "skip_crabel_fade": False, "use_zn_filter": True, "include_trd30pm": False,
     "crabel_cont_sz": 2.0, "crabel_fade_sz": 2.0, "night_sz": 2.0, "mes_sz": 2.0,
     "day_win_lock": 9999.0, "day_stop_loss": 400.0, "reset_thr": -500.0, "freeroll_ratchet": False},

    # 3. Add Intraday Win Lock (+800 USD)
    {"name": "3. + Intraday Win Lock (+$800)",
     "skip_crabel_fade": False, "use_zn_filter": True, "include_trd30pm": False,
     "crabel_cont_sz": 2.0, "crabel_fade_sz": 2.0, "night_sz": 2.0, "mes_sz": 2.0,
     "day_win_lock": 800.0, "day_stop_loss": 350.0, "reset_thr": -500.0, "freeroll_ratchet": False},

    # 4. Asymmetric Conviction Sizing: Crabel Cont 3c, Fade 1c
    {"name": "4. + Asymmetric Conviction Sizing (Crabel Cont 3c, Fade 1c)",
     "skip_crabel_fade": False, "use_zn_filter": True, "include_trd30pm": False,
     "crabel_cont_sz": 3.0, "crabel_fade_sz": 1.0, "night_sz": 2.0, "mes_sz": 2.5,
     "day_win_lock": 800.0, "day_stop_loss": 350.0, "reset_thr": -500.0, "freeroll_ratchet": False},

    # 5. Skip Crabel Fade completely (Continuation Only, PF 2.50)
    {"name": "5. + Crabel Gap-Continuation ONLY (Skip Fades)",
     "skip_crabel_fade": True, "use_zn_filter": True, "include_trd30pm": False,
     "crabel_cont_sz": 3.0, "crabel_fade_sz": 0.0, "night_sz": 2.0, "mes_sz": 2.5,
     "day_win_lock": 800.0, "day_stop_loss": 350.0, "reset_thr": -500.0, "freeroll_ratchet": False},

    # 6. Add Afternoon Trend (TRD30PM 1c)
    {"name": "6. + Afternoon Trend (TRD30PM 1c for Frequency)",
     "skip_crabel_fade": False, "use_zn_filter": True, "include_trd30pm": True,
     "crabel_cont_sz": 3.0, "crabel_fade_sz": 1.0, "night_sz": 2.0, "mes_sz": 2.5, "trd30pm_sz": 1.0,
     "day_win_lock": 800.0, "day_stop_loss": 350.0, "reset_thr": -500.0, "freeroll_ratchet": False},

    # 7. Add Milestone Ratchet (+1c when >= +$2,000, locking +$1,000)
    {"name": "7. + Freeroll Milestone Ratchet (Scale at +$2k)",
     "skip_crabel_fade": False, "use_zn_filter": True, "include_trd30pm": False,
     "crabel_cont_sz": 3.0, "crabel_fade_sz": 1.0, "night_sz": 2.0, "mes_sz": 2.5,
     "day_win_lock": 850.0, "day_stop_loss": 350.0, "reset_thr": -500.0, "freeroll_ratchet": True, "freeroll_boost": 1.0},

    # 8. Super Champion (Crabel Cont 3c, Night 2c, MES 2.5c | Reset -$450)
    {"name": "8. Super Champion (Crabel Cont 3c, Night 2c, MES 2.5c | Reset -$450)",
     "skip_crabel_fade": False, "use_zn_filter": True, "include_trd30pm": False,
     "crabel_cont_sz": 3.0, "crabel_fade_sz": 1.0, "night_sz": 2.0, "mes_sz": 2.5,
     "day_win_lock": 800.0, "day_stop_loss": 350.0, "reset_thr": -450.0, "freeroll_ratchet": False},
]

print("\n" + "="*115)
print(f"{'EXPERIMENT CONFIGURATION':58s} || {'REAL 2w':7s} {'REAL 3w':7s} {'REAL 1m':7s} || {'ZERO 1m':7s} {'ALPHA':7s} || {'RST':4s} {'DLL':3s}")
print("="*115)

all_results = []
for exp in experiments:
    name = exp.pop("name")
    r = run_backtest_grid(name=name, **exp)
    real, zero = r["real"], r["zero"]
    alpha = round(real["p21"] - zero["p21"], 1)
    cost = round((real["resets"] * 49.0) + 49.0, 0)
    print(f"{name:58s} || {real['p10']:5.1f}%  {real['p15']:5.1f}%  {real['p21']:5.1f}%  || {zero['p21']:5.1f}%  +{alpha:5.1f}% || {real['resets']:4.1f} {real['dll_breaches']:3d}")

    p1 = real["p21"] / 100.0
    p2 = 1.0 - (1.0 - p1)**2
    p3 = 1.0 - (1.0 - p1)**3
    p1_10 = real["p10"] / 100.0
    p2_10 = 1.0 - (1.0 - p1_10)**2
    p3_10 = 1.0 - (1.0 - p1_10)**3

    all_results.append({
        "name": name,
        "params": exp,
        "real": real,
        "zero": zero,
        "alpha_boost": alpha,
        "est_total_cost": cost,
        "multi_account": {
            "p1_acc_2wk": round(p1_10 * 100, 1),
            "p2_acc_2wk": round(p2_10 * 100, 1),
            "p3_acc_2wk": round(p3_10 * 100, 1),
            "p1_acc_1mo": round(p1 * 100, 1),
            "p2_acc_1mo": round(p2 * 100, 1),
            "p3_acc_1mo": round(p3 * 100, 1),
        }
    })

out_json = ROOT / "reports/RESEARCH_MULTI_SLEEVE_V2_HYPER_OPTIMIZER.json"
with open(out_json, "w") as f:
    json.dump(all_results, f, indent=2)

print(f"\nCompleted in {time.time()-t0:.2f}s! All hyper-optimizer results saved to {out_json}")

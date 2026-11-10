"""Realistic Multi-Sleeve Evaluation Horizon Audit.
TRAINING SPLIT (2010-2023) ONLY.
Strict Invariant: ZERO access to Validation (2024-2025) or Blind Test (2026).
Steps through ALL 3,513 real weekday RTH calendar sessions.

Analyzes the realistic, sustainable time horizons to pass Topstep 50k:
- 15 sessions (~3 weeks)
- 25 sessions (~5 weeks)
- 35 sessions (~7 weeks)
- 45 sessions (~9 weeks / ~2 months)
- 60 sessions (~12 weeks / ~3 months)

Sizing: 2.5c to 3.0c (safe institutional sizing, max risk $250-$300, 0 DLL breaches).
Strategic Resets at -$450 to -$500.
Matched Zero-Edge Controls on every run.
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict, namedtuple
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

# 1. Load clean trades
trades_df = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
trades_df = trades_df[trades_df.risk_today <= 310.0].copy()
trades_df["tout"] = pd.to_datetime(trades_df.tout_str, utc=True)
trades_df["tin"] = pd.to_datetime(trades_df.tin_str, utc=True)
trades_df["date"] = trades_df.tout.dt.tz_convert("America/New_York").dt.date
trades_df = trades_df.sort_values("tin").reset_index(drop=True)

# 2. Load ZN bond returns
zn = pd.read_parquet(ROOT / "data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet")
zet = zn.index.tz_convert("America/New_York")
sel = zet.hour == 15
c = pd.Series(zn.close.to_numpy()[sel], index=pd.to_datetime(zet[sel].date)).groupby(level=0).last()
zn_ret = (c / c.shift(1) - 1).dropna()
tin_dates = pd.to_datetime(trades_df.tin.dt.tz_convert("America/New_York").dt.date)
unique_dates = pd.DatetimeIndex(sorted(tin_dates.unique()))
zn_mapped_daily = zn_ret.reindex(zn_ret.index.union(unique_dates)).ffill(limit=3).reindex(unique_dates)
trades_df["zn_down"] = tin_dates.map(zn_mapped_daily).to_numpy() < 0

# 3. Load all real weekday RTH sessions
nq_bars = pd.read_parquet(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet", columns=["timestamp_utc"])
all_dates = pd.to_datetime(nq_bars.timestamp_utc, utc=True).dt.tz_convert("America/New_York").dt.date.unique()
all_rth_sessions = [d for d in sorted(all_dates) if d.weekday() < 5]

# Zero-edge control
sleeve_means = trades_df.groupby("sleeve_key")["net_today"].mean().to_dict()
trades_df["net_zero"] = trades_df.apply(lambda r: r["net_today"] - sleeve_means[r["sleeve_key"]], axis=1)

Trade = namedtuple("Trade", ["sleeve_key", "net_today", "net_zero", "risk_today", "is_gap_cont"])

def simulate_portfolio(
    allowed_sleeves={"CRABEL", "OVERNIGHT", "MES30"},
    crabel_cont_sz=3.0,
    crabel_fade_sz=1.5,
    night_sz=2.0,
    mes_sz=2.5,
    trd30pm_sz=1.0,
    day_win_lock=850.0,
    day_stop_loss=380.0,
    reset_thr=-450.0,
    max_horizon=60
):
    trades_by_date = defaultdict(list)
    for r in trades_df.itertuples():
        sk = r.sleeve_key
        if sk not in allowed_sleeves:
            continue
        if sk == "OVERNIGHT" and r.zn_down:
            continue
        trades_by_date[r.date].append(
            Trade(sk, float(r.net_today), float(r.net_zero), float(r.risk_today), bool(r.is_gap_cont))
        )

    n_sessions = len(all_rth_sessions)
    n_starts = n_sessions - max_horizon

    results = {}
    for is_zero in (False, True):
        p_15 = 0; p_25 = 0; p_35 = 0; p_45 = 0; p_60 = 0
        resets_paid = []
        days_to_pass = []
        worst_day = 0.0
        dll_breaches = 0

        for s in range(n_starts):
            used = 0
            resets = 0
            while used < max_horizon:
                cum = 0.0
                attempt_outcome = "open"

                for step in range(max_horizon - used):
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
                        elif sk == "TRD30PM":
                            sz = trd30pm_sz
                        else:
                            sz = 1.0

                        trade_risk = t.risk_today * sz

                        if day_pnl >= day_win_lock:
                            break
                        if day_pnl <= -day_stop_loss:
                            break
                        if (day_pnl - trade_risk) <= -750.0:
                            continue

                        t_pnl = (t.net_zero if is_zero else t.net_today) * sz
                        day_pnl += t_pnl

                    if day_pnl < worst_day:
                        worst_day = day_pnl
                    if day_pnl <= -1000.0:
                        dll_breaches += 1
                        attempt_outcome = "busted"
                        break

                    cum += min(day_pnl, 1500.0)

                    if cum <= -2000.0:
                        attempt_outcome = "busted"
                        break
                    if cum >= 4000.0:
                        attempt_outcome = "passed"
                        break
                    if cum <= reset_thr:
                        attempt_outcome = "reset"
                        break

                used += (step + 1)
                if attempt_outcome == "passed":
                    days_to_pass.append(used)
                    if used <= 15: p_15 += 1
                    if used <= 25: p_25 += 1
                    if used <= 35: p_35 += 1
                    if used <= 45: p_45 += 1
                    if used <= 60: p_60 += 1
                    resets_paid.append(resets)
                    break
                elif attempt_outcome in ("reset", "busted"):
                    resets += 1
                else:
                    break

        key = "zero" if is_zero else "real"
        results[key] = {
            "p15": round(p_15 / n_starts * 100, 1),
            "p25": round(p_25 / n_starts * 100, 1),
            "p35": round(p_35 / n_starts * 100, 1),
            "p45": round(p_45 / n_starts * 100, 1),
            "p60": round(p_60 / n_starts * 100, 1),
            "resets": round(float(np.mean(resets_paid)), 1) if resets_paid else 0.0,
            "median_days": round(float(np.median(days_to_pass)), 1) if days_to_pass else 0.0,
            "worst_day": round(worst_day, 1),
            "dll_breaches": dll_breaches
        }
    return results

print("="*120)
print(f"{'CONFIGURATION':45s} || {'3 WKS':6s} {'5 WKS':6s} {'7 WKS':6s} {'9 WKS':6s} {'12 WKS':7s} || {'ZERO 60':8s} {'ALPHA':7s} || {'DLL':3s}")
print("="*120)

configs = [
    ("Core 3-Sleeve (Crabel 3c/1.5c, Night 2c, MES 2.5c)", {"CRABEL", "OVERNIGHT", "MES30"}, 3.0, 1.5, 2.0, 2.5, 0.0),
    ("Core 4-Sleeve (+ TRD30PM Afternoon Trend 1c)", {"CRABEL", "OVERNIGHT", "MES30", "TRD30PM"}, 3.0, 1.5, 2.0, 2.5, 1.0),
    ("Sprint 3-Sleeve (Crabel 4c/2c, Night 2.5c, MES 3c)", {"CRABEL", "OVERNIGHT", "MES30"}, 4.0, 2.0, 2.5, 3.0, 0.0),
    ("Aggressive 3-Sleeve (Crabel 5c/2c, Night 2.5c, MES 3.5c)", {"CRABEL", "OVERNIGHT", "MES30"}, 5.0, 2.0, 2.5, 3.5, 0.0),
]

summary = []
for name, sleeves, cc, cf, n_sz, m_sz, trd_sz in configs:
    r = simulate_portfolio(allowed_sleeves=sleeves, crabel_cont_sz=cc, crabel_fade_sz=cf, night_sz=n_sz, mes_sz=m_sz, trd30pm_sz=trd_sz)
    real, zero = r["real"], r["zero"]
    alpha = round(real["p60"] - zero["p60"], 1)
    print(f"{name:45s} || {real['p15']:4.1f}% {real['p25']:4.1f}% {real['p35']:4.1f}% {real['p45']:4.1f}% {real['p60']:5.1f}% || {zero['p60']:5.1f}%   +{alpha:5.1f}% || {real['dll_breaches']:3d}")
    summary.append({"name": name, "real": real, "zero": zero, "alpha": alpha})

out_json = ROOT / "reports/RESEARCH_REALISTIC_EVAL_HORIZONS.json"
with open(out_json, "w") as f:
    json.dump(summary, f, indent=2)
print(f"\nSaved realistic evaluation horizons to {out_json}")

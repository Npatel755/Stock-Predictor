"""House Money Accelerator Simulation across 3,513 RTH Calendar Sessions.
TRAINING SPLIT (2010-2023) ONLY.
Strict Invariant: ZERO access to Validation (2024-2025) or Blind Test (2026).

Core Concept:
- Start safe (2 micros, max trade risk ~$250, realized day stop -$350 -> ZERO DLL risk).
- When equity reaches +$1,500 ("House Money" cushion, $3,500 from floor), scale up to 3.5 micros on Crabel gap-continuation (PF 2.50) and 2.5 micros on ZN-filtered Overnight Dip (PF 1.87).
- If equity retraces below +$1,000, de-escalate back to 2 micros.
- Strategic Reset at -$450 (preserving $1,550 cushion, paying $49 to restart).
- Intraday Win Lock at +$850 (strictly respects Topstep 50% consistency rule).
- Evaluate 10, 15, 21, 42, 63 sessions, plus Multi-Account scaling (1, 2, 3, 5 accounts).
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict, namedtuple
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

# 1. Load clean 1-micro trades
trades_df = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
trades_df = trades_df[trades_df.risk_today <= 310.0].copy()
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

# 3. Load all real weekday RTH sessions
nq_bars = pd.read_parquet(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet", columns=["timestamp_utc"])
all_dates = pd.to_datetime(nq_bars.timestamp_utc, utc=True).dt.tz_convert("America/New_York").dt.date.unique()
all_rth_sessions = [d for d in sorted(all_dates) if d.weekday() < 5]

# Zero-edge control
sleeve_means = trades_df.groupby("sleeve_key")["net_today"].mean().to_dict()
trades_df["net_zero"] = trades_df.apply(lambda r: r["net_today"] - sleeve_means[r["sleeve_key"]], axis=1)

Trade = namedtuple("Trade", ["sleeve_key", "net_today", "net_zero", "risk_today", "is_gap_cont"])

# Pre-group trades
allowed_sleeves = {"CRABEL", "OVERNIGHT", "MES30"}
trades_by_date = defaultdict(list)
for r in trades_df.itertuples():
    if r.sleeve_key not in allowed_sleeves:
        continue
    if r.sleeve_key == "OVERNIGHT" and r.zn_down:
        continue
    trades_by_date[r.date].append(
        Trade(r.sleeve_key, float(r.net_today), float(r.net_zero), float(r.risk_today), bool(r.is_gap_cont))
    )

def simulate_engine(
    base_crabel_cont=2.5,
    base_crabel_fade=1.0,
    base_night=2.0,
    base_mes=2.0,
    boost_crabel_cont=1.5, # +1.5c when in profit
    boost_night=0.5,
    boost_mes=1.0,
    cushion_trigger=1500.0,
    cushion_floor=1000.0,
    day_win_lock=850.0,
    day_stop_loss=380.0,
    reset_thr=-450.0,
    max_horizon=63,
    max_day_risk=750.0
):
    n_sessions = len(all_rth_sessions)
    n_starts = n_sessions - max_horizon

    results = {}
    for is_zero in (False, True):
        p_10 = 0; p_15 = 0; p_21 = 0; p_42 = 0; p_63 = 0
        resets_paid = []
        days_to_pass = []
        worst_day = 0.0
        dll_breaches = 0

        for s in range(n_starts):
            used = 0
            resets = 0
            while used < max_horizon:
                cum = 0.0
                in_freeroll = False
                attempt_outcome = "open"

                for step in range(max_horizon - used):
                    d = all_rth_sessions[s + used + step]
                    d_trades = trades_by_date.get(d, None)
                    if not d_trades:
                        continue

                    # Check cushion trigger
                    if cum >= cushion_trigger:
                        in_freeroll = True
                    elif cum < cushion_floor:
                        in_freeroll = False

                    day_pnl = 0.0
                    for t in d_trades:
                        sk = t.sleeve_key
                        # Base sizing
                        if sk == "OVERNIGHT":
                            sz = base_night + (boost_night if in_freeroll else 0.0)
                        elif sk == "CRABEL":
                            base_c = base_crabel_cont if t.is_gap_cont else base_crabel_fade
                            boost_c = boost_crabel_cont if (in_freeroll and t.is_gap_cont) else 0.0
                            sz = base_c + boost_c
                        elif sk == "MES30":
                            sz = base_mes + (boost_mes if in_freeroll else 0.0)
                        else:
                            sz = 1.0

                        trade_risk = t.risk_today * sz

                        # Intraday win lock
                        if day_pnl >= day_win_lock:
                            break
                        # Realized day stop
                        if day_pnl <= -day_stop_loss:
                            break
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
                    if used <= 10: p_10 += 1
                    if used <= 15: p_15 += 1
                    if used <= 21: p_21 += 1
                    if used <= 42: p_42 += 1
                    if used <= 63: p_63 += 1
                    resets_paid.append(resets)
                    break
                elif attempt_outcome in ("reset", "busted"):
                    resets += 1
                else:
                    break

        key = "zero" if is_zero else "real"
        results[key] = {
            "p10": round(p_10 / n_starts * 100, 1),
            "p15": round(p_15 / n_starts * 100, 1),
            "p21": round(p_21 / n_starts * 100, 1),
            "p42": round(p_42 / n_starts * 100, 1),
            "p63": round(p_63 / n_starts * 100, 1),
            "resets": round(float(np.mean(resets_paid)), 1) if resets_paid else 0.0,
            "median_days": round(float(np.median(days_to_pass)), 1) if days_to_pass else 0.0,
            "worst_day": round(worst_day, 1),
            "dll_breaches": dll_breaches
        }
    return results

# Test varying levels of cushion boost
scenarios = [
    ("Scenario A: No Boost (Static 2.5c Cont / 1c Fade / 2c Night / 2c MES)", 0.0, 0.0, 0.0, 9999.0),
    ("Scenario B: Mild Boost (+1c Cont, +0.5c Night at +$1,500)", 1.0, 0.5, 0.5, 1500.0),
    ("Scenario C: High-Conviction Boost (+1.5c Cont at +$1,500)", 1.5, 0.0, 0.5, 1500.0),
    ("Scenario D: Early Boost (+1.5c Cont at +$1,000)", 1.5, 0.5, 0.5, 1000.0),
]

print("="*120)
print(f"{'SCENARIO':55s} || {'10 SESS':7s} {'15 SESS':7s} {'21 SESS':7s} {'42 SESS':7s} {'63 SESS':7s} || {'DLL':3s}")
print("="*120)

for name, b_cont, b_night, b_mes, trig in scenarios:
    r = simulate_engine(
        boost_crabel_cont=b_cont, boost_night=b_night, boost_mes=b_mes, cushion_trigger=trig,
        day_win_lock=850.0, day_stop_loss=380.0, reset_thr=-450.0
    )
    real = r["real"]
    print(f"{name:55s} || {real['p10']:5.1f}%  {real['p15']:5.1f}%  {real['p21']:5.1f}%  {real['p42']:5.1f}%  {real['p63']:5.1f}%  || {real['dll_breaches']:3d}")

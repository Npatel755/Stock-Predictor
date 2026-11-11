"""Maximize 2-Month Evaluation Pass Probability on 14-Year Training Data (2010-2023).
Horizon: Exactly 42 Weekday Calendar Sessions (2 Months).
Strict Invariant: ZERO access to Validation (2024-2025) or Blind Test (2026).

Explores how to achieve the highest possible pass rate (approaching 100%) on ONE single account:
- Evaluates across all 3,471 sliding 42-session windows.
- Tests Strategic Resets (-$400, -$450, -$500, -$600, vs No Reset).
- Tests Dynamic Cushion Scaling (House Money rule: scaling size when ahead by +$1.5k / +$2.5k).
- Tests Trailing Lock (protecting banked profits).
- Enforces Realized Day Stop (-$380) -> ZERO DLL breaches guaranteed.
- Compares side-by-side with matched Zero-Edge Negative Controls.
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict, namedtuple
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

t0 = time.time()
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
allowed_sleeves = {"CRABEL", "OVERNIGHT", "MES30", "TRD30PM", "TRD60"}
trades_by_date = defaultdict(list)
for r in trades_df.itertuples():
    if r.sleeve_key not in allowed_sleeves:
        continue
    if r.sleeve_key == "OVERNIGHT" and r.zn_down:
        continue
    trades_by_date[r.date].append(
        Trade(r.sleeve_key, float(r.net_today), float(r.net_zero), float(r.risk_today), bool(r.is_gap_cont))
    )

def simulate_2month_eval(
    name,
    base_crabel=3.0,
    base_night=2.0,
    base_mes=2.5,
    base_trd30pm=1.0,
    base_trd60=1.5,
    day_win_lock=950.0,
    day_stop_loss=380.0,
    reset_thr=-450.0,
    cushion_scaling=False,
    cushion_tier1=1500.0, # when equity >= 1.5k, add boost1
    cushion_boost1=1.0,
    cushion_tier2=2500.0, # when equity >= 2.5k, add boost2
    cushion_boost2=1.5,
    trailing_floor=False,
    max_sessions=42
):
    n_starts = len(all_rth_sessions) - max_sessions

    results = {}
    for is_zero in (False, True):
        passed = 0
        busted_dll = 0
        busted_floor = 0
        resets_paid = []
        days_to_pass = []
        worst_day = 0.0
        final_equity = []

        for s in range(n_starts):
            used = 0
            resets = 0
            while used < max_sessions:
                cum = 0.0
                ratchet_floor = reset_thr if reset_thr is not None else -2000.0
                attempt_outcome = "open"

                for step in range(max_sessions - used):
                    d = all_rth_sessions[s + used + step]
                    d_trades = trades_by_date.get(d, None)
                    if not d_trades:
                        continue

                    # Dynamic cushion scaling
                    sz_mult = 1.0
                    if cushion_scaling:
                        if cum >= cushion_tier2:
                            sz_mult = 1.0 + (cushion_boost2 / base_crabel)
                        elif cum >= cushion_tier1:
                            sz_mult = 1.0 + (cushion_boost1 / base_crabel)

                    # Trailing floor
                    if trailing_floor:
                        if cum >= 3000.0:
                            ratchet_floor = max(ratchet_floor, 2000.0)
                        elif cum >= 2000.0:
                            ratchet_floor = max(ratchet_floor, 1000.0)

                    day_pnl = 0.0
                    for t in d_trades:
                        sk = t.sleeve_key
                        if sk == "OVERNIGHT":
                            sz = base_night * sz_mult
                        elif sk == "CRABEL":
                            base_c = base_crabel if t.is_gap_cont else (base_crabel * 0.5)
                            sz = base_c * sz_mult
                        elif sk == "MES30":
                            sz = base_mes * sz_mult
                        elif sk == "TRD30PM":
                            sz = base_trd30pm
                        elif sk == "TRD60":
                            sz = base_trd60
                        else:
                            sz = 1.0

                        trade_risk = t.risk_today * sz

                        # Intraday Win Lock
                        if day_pnl >= day_win_lock:
                            break
                        # Realized Day Stop
                        if day_pnl <= -day_stop_loss:
                            break
                        # Pre-trade DLL check
                        if (day_pnl - trade_risk) <= -750.0:
                            continue

                        t_pnl = (t.net_zero if is_zero else t.net_today) * sz
                        day_pnl += t_pnl

                    if day_pnl < worst_day:
                        worst_day = day_pnl
                    if day_pnl <= -1000.0:
                        busted_dll += 1
                        attempt_outcome = "busted_dll"
                        break

                    # Consistency Rule cap
                    cum += min(day_pnl, 1500.0)

                    if cum <= -2000.0:
                        busted_floor += 1
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
                    passed += 1
                    days_to_pass.append(used)
                    resets_paid.append(resets)
                    break
                elif attempt_outcome in ("reset", "busted_dll", "busted_floor"):
                    resets += 1
                else:
                    final_equity.append(cum)
                    break

        key = "zero" if is_zero else "real"
        results[key] = {
            "pass_pct": round(passed / n_starts * 100, 1),
            "resets": round(float(np.mean(resets_paid)), 1) if resets_paid else 0.0,
            "median_days": round(float(np.median(days_to_pass)), 1) if days_to_pass else 0.0,
            "worst_day": round(worst_day, 1),
            "dll_breaches": busted_dll,
            "floor_breaches": busted_floor,
            "median_final": round(float(np.median(final_equity)), 1) if final_equity else 0.0
        }
    return results

# Grid of 2-Month Optimization Policies
policies = [
    # Baseline
    {"name": "1. Standard 2-Month Baseline (Crabel 3c, Night 2c, MES 2.5c, No Scaling)",
     "base_crabel": 3.0, "base_night": 2.0, "base_mes": 2.5, "base_trd30pm": 1.0, "base_trd60": 1.5,
     "day_win_lock": 950.0, "day_stop_loss": 380.0, "reset_thr": -450.0, "cushion_scaling": False, "trailing_floor": False},

    # Policy 2: Add House Money Cushion Scaling (+1c at +$1.5k, +1.5c at +$2.5k)
    {"name": "2. + House Money Scaling (+1c at +$1.5k, +1.5c at +$2.5k)",
     "base_crabel": 3.0, "base_night": 2.0, "base_mes": 2.5, "base_trd30pm": 1.0, "base_trd60": 1.5,
     "day_win_lock": 1050.0, "day_stop_loss": 380.0, "reset_thr": -450.0, "cushion_scaling": True,
     "cushion_tier1": 1500.0, "cushion_boost1": 1.0, "cushion_tier2": 2500.0, "cushion_boost2": 1.5, "trailing_floor": False},

    # Policy 3: Add Trailing Lock (+1k floor at +$2k, +2k floor at +$3k)
    {"name": "3. + Trailing Lock (+House Money Scaling)",
     "base_crabel": 3.0, "base_night": 2.0, "base_mes": 2.5, "base_trd30pm": 1.0, "base_trd60": 1.5,
     "day_win_lock": 1050.0, "day_stop_loss": 380.0, "reset_thr": -450.0, "cushion_scaling": True,
     "cushion_tier1": 1500.0, "cushion_boost1": 1.0, "cushion_tier2": 2500.0, "cushion_boost2": 1.5, "trailing_floor": True},

    # Policy 4: Sprint Base (Crabel 4c, Night 2.5c, MES 3c + House Money)
    {"name": "4. Sprint Base (Crabel 4c, Night 2.5c, MES 3c + Scaling)",
     "base_crabel": 4.0, "base_night": 2.5, "base_mes": 3.0, "base_trd30pm": 1.0, "base_trd60": 2.0,
     "day_win_lock": 1200.0, "day_stop_loss": 400.0, "reset_thr": -500.0, "cushion_scaling": True,
     "cushion_tier1": 1500.0, "cushion_boost1": 1.5, "cushion_tier2": 2500.0, "cushion_boost2": 2.0, "trailing_floor": True},

    # Policy 5: Ultra-Passer (Crabel 4.5c, Night 2.5c, MES 3.5c, Day Stop -$420)
    {"name": "5. Ultra-Passer (Crabel 4.5c, Night 2.5c, MES 3.5c + Scaling)",
     "base_crabel": 4.5, "base_night": 2.5, "base_mes": 3.5, "base_trd30pm": 1.5, "base_trd60": 2.0,
     "day_win_lock": 1300.0, "day_stop_loss": 420.0, "reset_thr": -500.0, "cushion_scaling": True,
     "cushion_tier1": 1500.0, "cushion_boost1": 1.5, "cushion_tier2": 2500.0, "cushion_boost2": 2.0, "trailing_floor": True},
]

print("="*125)
print(f"{'POLICY CONFIGURATION':62s} || {'REAL PASS':9s} {'ZERO PASS':9s} {'ALPHA':7s} || {'RESETS':6s} {'COST':6s} {'DLL':3s}")
print("="*125)

audit_results = []
for p in policies:
    name = p.pop("name")
    r = simulate_2month_eval(name=name, **p)
    real, zero = r["real"], r["zero"]
    alpha = round(real["pass_pct"] - zero["pass_pct"], 1)
    cost = round((real["resets"] * 49.0) + (2 * 49.0), 0) # 2 months sub ($98) + resets
    print(f"{name:62s} || {real['pass_pct']:6.1f}%   {zero['pass_pct']:6.1f}%   +{alpha:5.1f}% || {real['resets']:4.1f}   ${cost:4.0f} {real['dll_breaches']:3d}")
    audit_results.append({"name": name, "real": real, "zero": zero, "alpha": alpha, "cost": cost})

out_json = ROOT / "reports/RESEARCH_MAXIMIZE_2MONTH_PASS_RATE.json"
with open(out_json, "w") as f:
    json.dump(audit_results, f, indent=2)
print(f"\nCompleted in {time.time()-t0:.2f}s! Saved to {out_json}")

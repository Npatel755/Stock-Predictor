"""Zero-Reset Optimization for Topstep $50K Static Daily Payouts Combine ($149 One-Time Fee).
TRAINING SPLIT (2010-2023) ONLY.
Strict Invariant: ZERO access to Validation (2024-2025) or Blind Test (2026).

Account Specifications (From User Image):
- $50K Buying Power
- $149 One-Time Fee (NO recurring subscription pressure)
- $2K Static Max Loss Limit (NEVER trails, fixed at -$2,000)
- $1K Daily Loss Limit (-$1,000 hard stop)
- $8,000 Payout Cap
- Target: +$4,000 (Topstep 50k Static Combine)
- USER DIRECTIVE: "MINIMIZE RESETS" -> Target: 0.0 Resets, 0% Ruin, 0 DLL breaches.

Tests:
1. Ultra-Defensive Fixed Sizing (1.5c - 2c)
2. Balanced Fixed Sizing (2c - 2.5c)
3. Dynamic Cushion Staging (1.5c base -> 2.5c at +$1k -> 3.5c at +$2.5k)
4. Floor-Adaptive Preservation (1c floor guard when in drawdown -> 3c when in profit)
5. Asymmetric Conviction (Crabel continuation 3c, fade 1c, overnight 1.5c, MES 2.5c)

Evaluates:
- Pass Rate at 30, 42, 60, 90 sessions
- Resets Paid (Target: 0.0)
- Static Floor Breaches / Ruin Rate (Target: 0.0%)
- DLL Breaches (Target: 0)
- Worst Account Drawdown ($)
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict, namedtuple
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

t0 = time.time()
# 1. Load routed 7-sleeve trades
intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
intra["tout"] = pd.to_datetime(intra.tout_str, utc=True)
intra["tin"] = pd.to_datetime(intra.tin_str, utc=True)
intra["date"] = intra.tout.dt.tz_convert("America/New_York").dt.date

ov_all = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
ov = ov_all[ov_all.sleeve_key == "OVERNIGHT"].copy()
ov["tout"] = pd.to_datetime(ov.tout_str, utc=True)
ov["tin"] = pd.to_datetime(ov.tin_str, utc=True)
ov["date"] = ov.tout.dt.tz_convert("America/New_York").dt.date

# ZN bond filter for Overnight Dip
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

all_trades = pd.concat([intra, ov_clean], ignore_index=True).sort_values("tin").reset_index(drop=True)

# Weekday RTH sessions
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

STATIC_FLOOR = -2000.0
DLL_LIMIT = -1000.0

def evaluate_zero_reset_policy(
    name,
    base_crabel=2.5,
    crabel_fade_ratio=0.5,
    base_night=1.5,
    base_mes=2.5,
    base_trend=1.5,
    day_win_lock=1000.0,
    day_stop_loss=380.0,
    cushion_mode=None, # None, 'staged', 'floor_guard', 'adaptive'
    max_sessions=60
):
    n_starts = len(all_rth_sessions) - max_sessions

    results = {}
    for is_zero in (False, True):
        p_30 = 0; p_42 = 0; p_60 = 0
        busted_floor = 0
        busted_dll = 0
        worst_dd = 0.0
        worst_day = 0.0
        days_to_pass = []

        for s in range(n_starts):
            cum = 0.0
            peak = 0.0
            status = "open"

            for step in range(max_sessions):
                d = all_rth_sessions[s + step]
                d_trades = trades_by_date.get(d, None)
                if not d_trades:
                    continue

                # Sizing modulation based on cushion mode
                mult = 1.0
                if cushion_mode == "staged":
                    if cum >= 2500.0:
                        mult = 1.4
                    elif cum >= 1000.0:
                        mult = 1.2
                    elif cum <= -500.0:
                        mult = 0.7
                elif cushion_mode == "floor_guard":
                    if cum <= -400.0:
                        mult = 0.5 # De-escalate to preserve account
                    elif cum >= 1500.0:
                        mult = 1.3
                elif cushion_mode == "adaptive":
                    # Linear cushion sizing: distance from -$2,000 floor
                    cushion = cum - STATIC_FLOOR # $2,000 at start
                    mult = np.clip(cushion / 2000.0, 0.5, 1.5)

                day_pnl = 0.0
                for t in d_trades:
                    sk = t.sleeve_key
                    if sk == "OVERNIGHT":
                        sz = base_night * mult
                    elif sk == "CRABEL":
                        base_c = base_crabel if t.is_gap_cont else (base_crabel * crabel_fade_ratio)
                        sz = base_c * mult
                    elif sk == "MES30":
                        sz = base_mes * mult
                    else:
                        sz = base_trend * mult

                    trade_risk = t.risk_today * sz

                    if day_pnl >= day_win_lock:
                        break
                    if day_pnl <= -day_stop_loss:
                        break
                    if (day_pnl - trade_risk) <= -800.0:
                        continue

                    t_pnl = (t.net_zero if is_zero else t.net_today) * sz
                    day_pnl += t_pnl

                if day_pnl < worst_day:
                    worst_day = day_pnl
                if day_pnl <= DLL_LIMIT:
                    busted_dll += 1
                    status = "busted_dll"
                    break

                # Consistency Rule: max $1,500/day
                cum += min(day_pnl, 1500.0)

                # Track drawdown
                if cum > peak:
                    peak = cum
                dd = peak - cum
                if dd > worst_dd:
                    worst_dd = dd

                # Static Floor check
                if cum <= STATIC_FLOOR:
                    busted_floor += 1
                    status = "busted_floor"
                    break

                # Target check
                if cum >= 4000.0:
                    status = "passed"
                    days_to_pass.append(step + 1)
                    if step < 30:
                        p_30 += 1
                    if step < 42:
                        p_42 += 1
                    p_60 += 1
                    break

        key = "zero" if is_zero else "real"
        results[key] = {
            "p30": round(p_30 / n_starts * 100, 1),
            "p42": round(p_42 / n_starts * 100, 1),
            "p60": round(p_60 / n_starts * 100, 1),
            "median_days": round(float(np.median(days_to_pass)), 1) if days_to_pass else 0.0,
            "busted_floor_pct": round(busted_floor / n_starts * 100, 2),
            "busted_dll": busted_dll,
            "worst_day": round(worst_day, 1),
            "worst_dd": round(worst_dd, 1)
        }
    return results

policies = [
    # 1. Ultra-Safe (1.5c Crabel, 1c Night, 1.5c MES, 1c Trend)
    ("Policy 1: Ultra-Safe Capital Preservation (1.5c/1c/1.5c)", 1.5, 0.5, 1.0, 1.5, 1.0, 800.0, 320.0, None),

    # 2. Conservative Fixed (2c Crabel, 1.5c Night, 2c MES, 1c Trend)
    ("Policy 2: Conservative Fixed (2c/1.5c/2c)", 2.0, 0.5, 1.5, 2.0, 1.0, 900.0, 350.0, None),

    # 3. Balanced Fixed (2.5c Crabel, 1.5c Night, 2.5c MES, 1.5c Trend)
    ("Policy 3: Balanced Fixed (2.5c/1.5c/2.5c)", 2.5, 0.5, 1.5, 2.5, 1.5, 1000.0, 380.0, None),

    # 4. Floor-Guard Defensive (2.5c base -> cut to 1.2c if balance <= -$400)
    ("Policy 4: Floor-Guard Defensive (Cut size at -$400)", 2.5, 0.5, 1.5, 2.5, 1.5, 1000.0, 380.0, "floor_guard"),

    # 5. Dynamic Cushion Staging (Start 2c -> 2.8c at +$1k -> 3.5c at +$2.5k)
    ("Policy 5: Dynamic Cushion Staging (Scale in Profit)", 2.0, 0.5, 1.5, 2.0, 1.2, 1100.0, 380.0, "staged"),

    # 6. Adaptive Distance-to-Floor (Continuous scaling)
    ("Policy 6: Adaptive Distance-to-Floor", 2.2, 0.5, 1.5, 2.2, 1.2, 1100.0, 380.0, "adaptive"),
]

print("="*130)
print(f"{'STATIC 50K POLICY (ZERO RESETS)':50s} || {'1.4 MO':6s} {'2 MO':6s} {'3 MO':6s} || {'FLOOR RUIN':10s} {'DLL':3s} || {'WORST DAY':10s} {'MAX DD':8s}")
print("="*130)

audit_results = []
for p in policies:
    r = evaluate_zero_reset_policy(
        name=p[0], base_crabel=p[1], crabel_fade_ratio=p[2], base_night=p[3], base_mes=p[4], base_trend=p[5],
        day_win_lock=p[6], day_stop_loss=p[7], cushion_mode=p[8], max_sessions=60
    )
    real, zero = r["real"], r["zero"]
    print(f"{p[0]:50s} || {real['p30']:5.1f}% {real['p42']:5.1f}% {real['p60']:5.1f}% || {real['busted_floor_pct']:8.2f}% {real['busted_dll']:3d} || ${real['worst_day']:8.1f} ${real['worst_dd']:7.1f}")
    audit_results.append({"name": p[0], "real": real, "zero": zero})

out_json = ROOT / "reports/RESEARCH_ZERO_RESET_50K_STATIC.json"
with open(out_json, "w") as f:
    json.dump(audit_results, f, indent=2)

print(f"\nCompleted in {time.time()-t0:.2f}s! Saved to {out_json}")

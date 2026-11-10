"""Audit of ONE Single Account Evaluation Limits on 14-Year Training Data (2010-2023).
Strict Invariant: ZERO access to Validation (2024-2025) or Blind Test (2026).
Simulates ONE SINGLE ACCOUNT with its exact evaluation rules:
- Target: +$4,000
- Daily Loss Limit (DLL): -$1,000
- Static Max Drawdown Floor: -$2,000
- Topstep Consistency Rule: No single day > $2,000 (we cap at $1,500)
- Sizing regimes from 1 micro to 14 micros.
- Evaluates across ALL 3,492 sliding windows of 21 sessions (1 calendar month).
"""
import sys, json
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

# Pre-group trades
allowed_sleeves = {"CRABEL", "OVERNIGHT", "MES30", "TRD30PM"}
Trade = namedtuple("Trade", ["sleeve_key", "net_today", "risk_today", "is_gap_cont"])
trades_by_date = defaultdict(list)
for r in trades_df.itertuples():
    if r.sleeve_key not in allowed_sleeves:
        continue
    if r.sleeve_key == "OVERNIGHT" and r.zn_down:
        continue
    trades_by_date[r.date].append(
        Trade(r.sleeve_key, float(r.net_today), float(r.risk_today), bool(r.is_gap_cont))
    )

def audit_single_account(
    name,
    crabel_sz=3.0,
    night_sz=2.0,
    mes_sz=2.5,
    trd30pm_sz=1.0,
    day_stop_loss=380.0,
    reset_thr=-450.0,
    window_sessions=21
):
    n_starts = len(all_rth_sessions) - window_sessions
    
    passed_10 = 0
    passed_15 = 0
    passed_21 = 0
    busted_dll = 0
    busted_floor = 0
    reset_count = 0
    open_positive = 0
    open_negative = 0
    worst_single_day = 0.0
    final_balances = []

    for s in range(n_starts):
        cum = 0.0
        status = "open"
        resets = 0

        for step in range(window_sessions):
            d = all_rth_sessions[s + step]
            d_trades = trades_by_date.get(d, None)
            if not d_trades:
                continue

            day_pnl = 0.0
            for t in d_trades:
                sk = t.sleeve_key
                if sk == "OVERNIGHT":
                    sz = night_sz
                elif sk == "CRABEL":
                    sz = crabel_sz if t.is_gap_cont else (crabel_sz * 0.5)
                elif sk == "MES30":
                    sz = mes_sz
                elif sk == "TRD30PM":
                    sz = trd30pm_sz
                else:
                    sz = 1.0

                # Day stop protection
                if day_stop_loss > 0 and day_pnl <= -day_stop_loss:
                    break

                day_pnl += t.net_today * sz

            if day_pnl < worst_single_day:
                worst_single_day = day_pnl

            # Topstep DLL check
            if day_pnl <= -1000.0:
                busted_dll += 1
                status = "busted_dll"
                break

            # Daily consistency cap
            cum += min(day_pnl, 1500.0)

            # Max floor check
            if cum <= -2000.0:
                busted_floor += 1
                status = "busted_floor"
                break

            # Profit target check
            if cum >= 4000.0:
                status = "passed"
                if step < 10:
                    passed_10 += 1
                if step < 15:
                    passed_15 += 1
                passed_21 += 1
                break

            # Strategic reset check (if used)
            if reset_thr is not None and cum <= reset_thr:
                reset_count += 1
                cum = 0.0 # Account reset, start fresh from 0

        final_balances.append(cum)
        if status == "open":
            if cum > 0:
                open_positive += 1
            else:
                open_negative += 1

    return {
        "name": name,
        "p10_pct": round(passed_10 / n_starts * 100, 1),
        "p15_pct": round(passed_15 / n_starts * 100, 1),
        "p21_pct": round(passed_21 / n_starts * 100, 1),
        "dll_breaches": busted_dll,
        "floor_breaches": busted_floor,
        "avg_resets": round(reset_count / n_starts, 2),
        "worst_day": round(worst_single_day, 1),
        "median_final": round(float(np.median(final_balances)), 1),
        "open_positive_pct": round(open_positive / n_starts * 100, 1)
    }

configs = [
    # name, crabel_sz, night_sz, mes_sz, trd30pm_sz, day_stop, reset_thr
    ("1. Pure 1-Micro Baseline (Safe)", 1.0, 1.0, 1.0, 1.0, 300.0, None),
    ("2. 2-Micro Balanced (No Reset)", 2.0, 2.0, 2.0, 1.0, 350.0, None),
    ("3. 2-Micro Balanced (Reset @ -$450)", 2.0, 2.0, 2.0, 1.0, 350.0, -450.0),
    ("4. 3-Micro Conviction (Reset @ -$450)", 3.0, 2.0, 2.5, 1.0, 380.0, -450.0),
    ("5. 4-Micro Sprint (Reset @ -$500)", 4.0, 2.5, 3.0, 1.5, 450.0, -500.0),
    ("6. 6-Micro Aggressive (No Day Stop)", 6.0, 3.0, 4.0, 2.0, 0.0, -600.0),
    ("7. 12-Micro Hyper-Velocity (Single Sleeve Crabel)", 12.0, 0.0, 0.0, 0.0, 0.0, -600.0),
]

print("="*125)
print(f"{'SINGLE ACCOUNT CONFIGURATION':45s} || {'2 WEEKS':7s} {'3 WEEKS':7s} {'1 MONTH':7s} || {'WORST DAY':10s} {'DLL FAILS':9s} {'MEDIAN BAL':10s}")
print("="*125)

results = []
for c in configs:
    r = audit_single_account(c[0], c[1], c[2], c[3], c[4], c[5], c[6])
    print(f"{r['name']:45s} || {r['p10_pct']:5.1f}%  {r['p15_pct']:5.1f}%  {r['p21_pct']:5.1f}%  || ${r['worst_day']:8.1f}  {r['dll_breaches']:8d}  +${r['median_final']:8.1f}")
    results.append(r)

out_json = ROOT / "reports/AUDIT_ONE_ACCOUNT_LIMITS.json"
with open(out_json, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved audit to {out_json}")

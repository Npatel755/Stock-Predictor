"""Test 7-Sleeve High-Frequency Portfolio on 2-Month Evaluation Passing.
TRAINING SPLIT (2010-2023) ONLY.
Simulates ONE SINGLE ACCOUNT across all 3,471 sliding 42-session windows.
Combines all 7 proven sleeves:
1. CRABEL (15m Open Drive)
2. OVERNIGHT DIP (with ZN bond filter & 0.55% stop)
3. MES30 (30m Trend on MES)
4. TRD30PM (Afternoon 30m Trend)
5. TRD60 (60m Hourly Trend)
6. TRD30_D (Morning 30m Trend)
7. BRK30 (30m Donchian Breakout)

Tests sizing from 2c to 4c, strategic resets at -$450 to -$550, and dynamic scaling.
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
print(f"Total active trades in 7-sleeve portfolio: {len(all_trades)} across {all_trades.date.nunique()} unique sessions.")

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

def test_engine(
    name,
    base_crabel=3.5,
    base_night=2.0,
    base_mes=2.5,
    base_trend=1.5,
    day_win_lock=1100.0,
    day_stop_loss=400.0,
    reset_thr=-500.0,
    cushion_boost=1.5,
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

                    # House Money scaling when in profit
                    in_freeroll = cum >= 1500.0
                    if in_freeroll and cum >= 2500.0:
                        ratchet_floor = max(ratchet_floor, 1500.0)

                    day_pnl = 0.0
                    for t in d_trades:
                        sk = t.sleeve_key
                        if sk == "OVERNIGHT":
                            sz = base_night + (0.5 if in_freeroll else 0.0)
                        elif sk == "CRABEL":
                            base_c = base_crabel if t.is_gap_cont else (base_crabel * 0.5)
                            sz = base_c + (cushion_boost if (in_freeroll and t.is_gap_cont) else 0.0)
                        elif sk == "MES30":
                            sz = base_mes + (0.5 if in_freeroll else 0.0)
                        else:
                            sz = base_trend

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

grid = [
    # name, crabel, night, mes, trend, win_lock, day_stop, reset_thr, cushion_boost
    ("1. 7-Sleeve Moderate (Crabel 3c, Night 2c, MES 2c, Trend 1c)", 3.0, 2.0, 2.0, 1.0, 1000.0, 380.0, -450.0, 1.0),
    ("2. 7-Sleeve Conviction (Crabel 3.5c, Night 2c, MES 2.5c, Trend 1.5c)", 3.5, 2.0, 2.5, 1.5, 1100.0, 400.0, -500.0, 1.5),
    ("3. 7-Sleeve High-Octane (Crabel 4c, Night 2.5c, MES 3c, Trend 1.5c)", 4.0, 2.5, 3.0, 1.5, 1200.0, 420.0, -500.0, 1.5),
    ("4. 7-Sleeve Aggressive (Crabel 4.5c, Night 2.5c, MES 3c, Trend 2c)", 4.5, 2.5, 3.0, 2.0, 1300.0, 450.0, -550.0, 2.0),
    ("5. 7-Sleeve Sprint (Crabel 5c, Night 2.5c, MES 3.5c, Trend 2c)", 5.0, 2.5, 3.5, 2.0, 1400.0, 480.0, -600.0, 2.0),
]

print("="*125)
print(f"{'7-SLEEVE CONFIGURATION':58s} || {'REAL PASS':9s} {'ZERO PASS':9s} {'ALPHA':7s} || {'RESETS':6s} {'COST':6s} {'DLL':3s}")
print("="*125)

for g in grid:
    r = test_engine(g[0], g[1], g[2], g[3], g[4], g[5], g[6], g[7], g[8])
    real, zero = r["real"], r["zero"]
    alpha = round(real["pass_pct"] - zero["pass_pct"], 1)
    cost = round((real["resets"] * 49.0) + (2 * 49.0), 0)
    print(f"{g[0]:58s} || {real['pass_pct']:6.1f}%   {zero['pass_pct']:6.1f}%   +{alpha:5.1f}% || {real['resets']:4.1f}   ${cost:4.0f} {real['dll_breaches']:3d}")

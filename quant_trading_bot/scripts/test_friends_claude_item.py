"""
Test Friend's Claude Exact 3-Piece Item on Topstep $50K Static Combine ($149 One-Time)
Item: choch ES 6fe8aae66be4 + choch ES 2a56c6c23d02 + nick_momentum NQ n7_8642450689a2161e
"""
import sys, json
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

# 1. Nick Momentum NQ
intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
intra["tout"] = pd.to_datetime(intra.tout_str, utc=True)
intra["tin"] = pd.to_datetime(intra.tin_str, utc=True)
intra["date"] = intra.tout.dt.tz_convert("America/New_York").dt.date
# Nick's momentum sleeve in intra is TRD30_D / TRD60
nick_mom = intra[intra.sleeve == "TRD30_D"].copy()

# 2. ES CHoCH trades
choch = pd.read_parquet(ROOT / "data/processed/es_choch_trades_train.parquet")
choch["tout"] = pd.to_datetime(choch.tout_str, utc=True)
choch["tin"] = pd.to_datetime(choch.tin_str, utc=True)
choch["date"] = choch.tout.dt.tz_convert("America/New_York").dt.date

# Friend's Claude item: choch 6fe8 + choch 2a56 + nick_momentum
friends_trades = pd.concat([choch, nick_mom], ignore_index=True).sort_values("tin").reset_index(drop=True)
friends_trades["r_net"] = friends_trades["net_today"] / friends_trades["risk_today"].clip(lower=1.0)

print(f"Friend's Claude Total Trades: {len(friends_trades)}")
print(f"Breakdown:")
print(f"  CHOCH 6FE8: {(friends_trades.sleeve == 'CHOCH_6FE8').sum()} trades (WinRate: {(friends_trades[friends_trades.sleeve == 'CHOCH_6FE8'].r_net > 0).mean()*100:.1f}%)")
print(f"  CHOCH 2A56: {(friends_trades.sleeve == 'CHOCH_2A56').sum()} trades (WinRate: {(friends_trades[friends_trades.sleeve == 'CHOCH_2A56'].r_net > 0).mean()*100:.1f}%)")
print(f"  Nick Momentum: {(friends_trades.sleeve == 'TRD30_D').sum()} trades (WinRate: {(friends_trades[friends_trades.sleeve == 'TRD30_D'].r_net > 0).mean()*100:.1f}%)")

# RTH sessions
nq_bars = pd.read_parquet(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet", columns=["timestamp_utc"])
all_dates = pd.to_datetime(nq_bars.timestamp_utc, utc=True).dt.tz_convert("America/New_York").dt.date.unique()
all_rth_sessions = [d for d in sorted(all_dates) if d.weekday() < 5]
n_sessions = len(all_rth_sessions)

trades_by_date = defaultdict(list)
for _, row in friends_trades.iterrows():
    trades_by_date[row["date"]].append(row)

TARGET = 4000.0
FLOOR = -2000.0
DLL = -1000.0

# 1. Zero-Reset Bal-3 Sizing on Friend's Item
def test_bal3(horizon):
    total = n_sessions - horizon + 1
    passes, ruins, dll_hits = 0, 0, 0
    days_to_pass = []
    
    for w in range(total):
        bal = 0.0
        passed, ruined = False, False
        for s_idx in range(w, w + horizon):
            dt = all_rth_sessions[s_idx]
            cushion = max(0.0, bal - FLOOR)
            if cushion <= 0:
                ruined = True
                break
            if bal <= 0:
                size_mult = max(0.35, (cushion / 2000.0) ** 1.20)
                day_stop = max(-150.0, -380.0 * size_mult)
            else:
                size_mult = min(1.75, 1.0 + (bal / 4000.0) * 0.75)
                day_stop = -380.0
                
            day_pnl = 0.0
            for tr in trades_by_date.get(dt, []):
                risk = 160.0 * size_mult
                if day_pnl <= day_stop: break
                r = tr["r_net"]
                pnl = r * risk
                if day_pnl + pnl <= DLL:
                    pnl = DLL - day_pnl
                    day_pnl += pnl
                    bal += pnl
                    dll_hits += 1
                    break
                day_pnl += pnl
                bal += pnl
                if bal <= FLOOR:
                    ruined = True
                    break
                if bal >= TARGET:
                    passed = True
                    break
            if passed or ruined:
                elapsed = (s_idx - w) + 1
                if passed:
                    passes += 1
                    days_to_pass.append(elapsed)
                if ruined: ruins += 1
                break
        if bal <= FLOOR and not ruined: ruins += 1
        
    return {
        "horizon": horizon,
        "months": horizon / 21.0,
        "pass_pct": passes / total * 100,
        "ruin_pct": ruins / total * 100,
        "dll_hits": dll_hits,
        "median_days": np.median(days_to_pass) if days_to_pass else 0.0
    }

print("\n=== Friend's Claude Item under Zero-Reset Bal-3 Sizing ===")
print(f"{'Horizon':<10} | {'Months':<8} | {'Pass Rate':<10} | {'Survival':<10} | {'Ruin %':<8} | {'Median Days':<12}")
print("-" * 65)
for h in [21, 30, 42, 60, 90, 120]:
    r = test_bal3(h)
    surv = 100.0 - r['ruin_pct']
    md = f"{r['median_days']:.1f}d" if r['median_days'] > 0 else "N/A"
    print(f"{h:<10} | {r['months']:<8.1f} | {r['pass_pct']:>8.1f}% | {surv:>8.1f}% | {r['ruin_pct']:>6.2f}% | {md:<12}")

# 2. Friend's Claude Sprint ($1,500 Risk)
def test_friend_sprint(max_days):
    total = n_sessions - max_days + 1
    passes, ruins, dll_hits = 0, 0, 0
    for i in range(total):
        bal = 0.0
        passed, ruined = False, False
        for d in range(i, i + max_days):
            dt = all_rth_sessions[d]
            day_pnl = 0.0
            for tr in trades_by_date.get(dt, []):
                risk = 1500.0
                r = tr["r_net"]
                pnl = r * risk
                if pnl < -risk: pnl = -risk
                if day_pnl + pnl <= DLL:
                    pnl = DLL - day_pnl
                    day_pnl += pnl
                    bal += pnl
                    dll_hits += 1
                    break
                day_pnl += pnl
                bal += pnl
                if bal >= TARGET:
                    passed = True
                    break
                if bal <= FLOOR:
                    ruined = True
                    break
                break
            if passed or ruined: break
        if passed: passes += 1
        if ruined or bal <= FLOOR: ruins += 1
    return {
        "days": max_days,
        "pass_pct": passes / total * 100,
        "ruin_pct": ruins / total * 100,
        "dll_pct": dll_hits / total * 100
    }

print("\n=== Friend's Claude Item under $1,500 Sprint ===")
print(f"{'Days':<8} | {'Pass Rate':<12} | {'Ruin Rate':<12} | {'DLL Hits':<10}")
print("-" * 48)
for d in [2, 3, 5, 10]:
    r = test_friend_sprint(d)
    print(f"{d:<8} | {r['pass_pct']:>10.1f}% | {r['ruin_pct']:>10.1f}% | {r['dll_pct']:>8.1f}%")

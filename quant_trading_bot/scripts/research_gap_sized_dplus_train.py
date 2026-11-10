"""Research Script: State-Conditioned Dynamic Sizing for Architecture D+ (Crabel Gap-State Sizing)
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Economic Thesis:
Devin's dplus_4 audit proved that Crabel Open Drive has two distinct positive-expectancy states:
1. Gap Continuation (drive == gap): $21.32/trade, 13/14 positive years (Premium Momentum Regime)
2. Gap Fade (drive != gap): $10.95/trade, 7/14 positive years (Normal Mean-Reverting Chop)

Instead of discarding the $2,540 profit from fade trades, we test state-conditioned dynamic sizing:
- 2 contracts on Gap Continuation ($300 risk budget)
- 1 contract on Gap Fades ($150 risk budget)
- 1 contract on remaining sleeves (MNQ 60m trend and MES 30m idle ballast)

Compare against:
1. Base D+ v2 (1c on everything)
2. Static 2c D+ v2 (2c on everything, $300 budget)
3. Gap-Sized D+ v2 (2c only on continuation, 1c on everything else)
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

print("=" * 80)
print("RESEARCH: GAP-STATE CONDITIONED SIZING (2010-2023 TRAINING ONLY)")
print("=" * 80, flush=True)

# Use Devin's exact dplus_4 infrastructure
src = (ROOT / "scripts/dplus_1_pilot.py").read_text().split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_1_pilot.py")}
exec(src, ns)
ep, run_sl, route, stats, marked, bars_for = ns["ep"], ns["run_sl"], ns["route"], ns["stats"], ns["marked"], ns["bars_for"]

sls = ep.CANDIDATES["ag_arch_d_plus_v2"]["sleeves"]
cr = [s for s in sls if "CRABEL" in s["name"]][0]

b, _, _ = bars_for(cr)
loc = b.timestamp_utc.dt.tz_convert("America/New_York")
m = loc.dt.hour * 60 + loc.dt.minute
day = loc.dt.date

rth = b[(m >= 570) & (m <= 960)]
rl = loc[rth.index]
first_open = rth.groupby(day[rth.index]).open.first()
last_close = rth.groupby(day[rth.index]).close.last()
gap = (first_open - last_close.shift(1)).dropna()
gap.index = pd.to_datetime(pd.Series(gap.index)).dt.date.to_numpy()
gapd = dict(zip(gap.index, gap.to_numpy()))

allt = sum((run_sl(sl, i) for i, sl in enumerate(sls)), [])
base_trades = route(allt)

dkey = next(k for k in ("direction", "side", "dir") if k in base_trades[0])
def is_long(t):
    v = t[dkey]
    return (v > 0) if isinstance(v, (int, float, np.integer, np.floating)) else str(v).lower() in ("long", "buy", "1")

for t in base_trades:
    t["day"] = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York").date()
    t["gap"] = gapd.get(t["day"], np.nan)
    t["crabel"] = t["sleeve"] == cr["name"]
    t["cont"] = bool(t["crabel"] and not np.isnan(t["gap"]) and ((is_long(t) and t["gap"] >= 0) or (not is_long(t) and t["gap"] <= 0)))

def evaluate_sizing_rule(name, scale_func):
    """Evaluate a sizing rule that dynamically scales net and stop_risk per trade."""
    scaled_trades = []
    daily = {}
    ev = []
    
    for t in base_trades:
        scale = scale_func(t)
        t_net = float(t["net"]) * scale
        t_risk = float(t["stop_risk"]) * scale
        
        en = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York")
        ex = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York")
        
        ev.append((en, "worst", -t_risk, 0.0))
        ev.append((ex, "close", 0.0, t_net))
        daily[ex.date()] = daily.get(ex.date(), 0.0) + t_net
        
        t_copy = dict(t)
        t_copy["net"] = t_net
        t_copy["stop_risk"] = t_risk
        t_copy["scale"] = scale
        scaled_trades.append(t_copy)
        
    ev.sort(key=lambda z: z[0])
    closed = hwm = worst = 0.0
    br = {2000: 0, 2500: 0}
    inb = {f: False for f in br}
    
    for ts, kind, unreal, real in ev:
        if kind == "worst": eq = closed + unreal
        else: closed += real; eq = closed; hwm = max(hwm, eq)
        tdd = hwm - eq
        if tdd > worst: worst = tdd
        for f in br:
            if tdd >= f and not inb[f]: br[f] += 1; inb[f] = True
            if tdd < f * 0.5: inb[f] = False
            
    d = pd.Series(daily).sort_index()
    yr = d.groupby(pd.to_datetime(d.index).year).sum()
    st = stats(scaled_trades)
    
    # Block-bootstrap breach probability on daily series
    from sizing_1_pilot import breach
    mc = breach(d)
    
    wr = float(np.mean([t["net"] > 0 for t in scaled_trades]) * 100) if len(scaled_trades) else 0.0
    pre2020 = float(sum(t["net"] for t in scaled_trades if pd.Timestamp(t["exit_ts"]).year < 2020))
    
    print(f"\n--- {name} ---")
    print(f"Trades: {len(scaled_trades)} | Net P&L: +${st['net']:,.2f} | Exp: +${st['per']:.2f}/tr | Win: {wr:.1f}%")
    print(f"Realized DD: ${st['closed_dd']:,.2f} | Marked DD: ${worst:,.2f} | $2k Touches: {br[2000]}")
    print(f"Positive Years: {st['pos_years']}/14 ({st['pos_years']/14*100:.1f}%) | 1Y MC Breach: {mc*100:.2f}%")
    print(f"Worst Day: ${float(d.min()):,.2f} | Pre-2020 Net: +${pre2020:,.2f}")
    
    return {
        "name": name,
        "net": round(st["net"], 2),
        "per_trade": round(st["per"], 2),
        "win_rate": round(wr, 1),
        "realized_dd": round(st["closed_dd"], 2),
        "marked_dd": round(worst, 2),
        "touches_2000": br[2000],
        "pos_years": st["pos_years"],
        "mc_breach_pct": round(mc * 100, 2),
        "worst_day": round(float(d.min()), 2),
        "pre2020_net": round(pre2020, 2),
        "by_year": {int(y): round(v, 2) for y, v in yr.items()}
    }

# Rule 1: Baseline D+ v2 (1c on everything)
res_base = evaluate_sizing_rule("1. Baseline D+ v2 (1c on all sleeves)", lambda t: 1.0)

# Rule 2: Static 2c (2c on all sleeves, $300 budget)
res_static_2c = evaluate_sizing_rule("2. Static 2c D+ v2 (2c on all sleeves)", lambda t: 2.0)

# Rule 3: Dynamic Gap-State Sizing (2c only on Crabel Gap Continuation, 1c on everything else)
res_gap_sized = evaluate_sizing_rule(
    "3. Gap-State Sized (2c on Crabel Continuation, 1c on Fades & other sleeves)",
    lambda t: 2.0 if (t["crabel"] and t["cont"]) else 1.0
)

# Rule 4: Gap-State Sizing with SKEW confirmation (2c on Crabel Continuation when SKEW normal)
res_gap_skew = evaluate_sizing_rule(
    "4. Gap-State + Asymmetric 1.5x Sizing",
    lambda t: 1.5 if (t["crabel"] and t["cont"]) else 1.0
)

out_report = {
    "baseline_1c": res_base,
    "static_2c": res_static_2c,
    "gap_state_sized_2c": res_gap_sized,
    "gap_state_sized_1_5c": res_gap_skew
}

out_path = ROOT / "reports/GAP_STATE_SIZING_DPLUS_TRAIN.json"
with open(out_path, "w") as fp:
    json.dump(out_report, fp, indent=2, default=str)
print(f"\n[DONE] Saved Gap-State Sizing audit to {out_path}")

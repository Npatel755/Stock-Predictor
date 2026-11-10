"""Research Script: Synergy of Gap-State Sizing + Volatility Floor Filtering for Architecture D+.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Investigates:
Does combining the proven Gap-State Sizing (2c on Crabel Continuation, 1c on Fades)
with an ex-ante CBOE Volatility Floor (avoiding dead low-vol summer compressions VIX < 11-13):
1. Boost total net profit beyond +$23,142?
2. Cut marked drawdown below $1,000?
3. Improve calendar consistency and Sharpe?
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

print("=" * 80)
print("RESEARCH: GAP-STATE SIZING + VOLATILITY FLOOR SYNERGY (2010-2023 TRAINING)")
print("=" * 80, flush=True)

src = (ROOT / "scripts/dplus_1_pilot.py").read_text().split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_1_pilot.py")}
exec(src, ns)
ep, run_sl, route, stats, marked, bars_for = ns["ep"], ns["run_sl"], ns["route"], ns["stats"], ns["marked"], ns["bars_for"]
from sizing_1_pilot import breach

# Load VIX history
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df['date'] = pd.to_datetime(vix_df['DATE'], format='%m/%d/%Y').dt.date
vix_map = vix_df.set_index('date')['CLOSE'].astype(float).to_dict()
vix_dates = np.array(sorted(list(vix_map.keys())))

def prior_vix(d):
    p = vix_dates.searchsorted(d, side='left') - 1
    if p >= 0:
        return vix_map.get(vix_dates[p], 20.0)
    return 20.0

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
    t["vix"] = prior_vix(t["day"])
    t["crabel"] = t["sleeve"] == cr["name"]
    t["cont"] = bool(t["crabel"] and not np.isnan(t["gap"]) and ((is_long(t) and t["gap"] >= 0) or (not is_long(t) and t["gap"] <= 0)))

def evaluate_combined_policy(vix_floor=0.0):
    scaled_trades = []
    daily = {}
    ev = []
    
    for t in base_trades:
        # Check VIX floor
        if vix_floor > 0.0 and t["vix"] < vix_floor:
            continue  # Stand aside on low-vol chop days
            
        # Sizing rule: 2c on Crabel Continuation, 1c on Fades & other sleeves
        scale = 2.0 if (t["crabel"] and t["cont"]) else 1.0
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
    br = {2000: 0}
    for ts, kind, unreal, real in ev:
        if kind == "worst": eq = closed + unreal
        else: closed += real; eq = closed; hwm = max(hwm, eq)
        tdd = hwm - eq
        if tdd > worst: worst = tdd
        if tdd >= 2000: br[2000] += 1
            
    d = pd.Series(daily).sort_index()
    yr = d.groupby(pd.to_datetime(d.index).year).sum()
    st = stats(scaled_trades)
    mc = breach(d) if len(d) else 0.0
    
    wr = float(np.mean([t["net"] > 0 for t in scaled_trades]) * 100) if len(scaled_trades) else 0.0
    pre2020 = float(sum(t["net"] for t in scaled_trades if pd.Timestamp(t["exit_ts"]).year < 2020))
    net_to_dd = round(st["net"] / worst, 1) if worst > 0 else 0.0
    
    label = f"Gap-Sized + VIX Floor >= {vix_floor:.1f}" if vix_floor > 0 else "Gap-Sized Baseline (No VIX Floor)"
    print(f"\n--- {label} ---")
    print(f"Trades: {len(scaled_trades)} | Net P&L: +${st['net']:,.2f} | Exp: +${st['per']:.2f}/tr | Win: {wr:.1f}%")
    print(f"Realized DD: ${st['closed_dd']:,.2f} | Marked DD: ${worst:,.2f} | Net/DD: {net_to_dd}")
    print(f"Positive Years: {st['pos_years']}/14 ({st['pos_years']/14*100:.1f}%) | 1Y MC Breach: {mc*100:.2f}%")
    print(f"Worst Day: ${float(d.min()):,.2f} | Pre-2020 Net: +${pre2020:,.2f}")
    
    return {
        "vix_floor": vix_floor,
        "trades": len(scaled_trades),
        "net": round(st["net"], 2),
        "per_trade": round(st["per"], 2),
        "win_rate": round(wr, 1),
        "realized_dd": round(st["closed_dd"], 2),
        "marked_dd": round(worst, 2),
        "net_to_dd": net_to_dd,
        "touches_2000": br[2000],
        "pos_years": st["pos_years"],
        "mc_breach_pct": round(mc * 100, 2),
        "worst_day": round(float(d.min()), 2),
        "pre2020_net": round(pre2020, 2),
        "by_year": {int(y): round(v, 2) for y, v in yr.items()}
    }

results = []
for vf in [0.0, 11.0, 12.0, 13.0, 14.0, 15.0]:
    results.append(evaluate_combined_policy(vix_floor=vf))

out_path = ROOT / "reports/GAPSIZE_PLUS_VIX_FLOOR_SWEEP_TRAIN.json"
with open(out_path, "w") as fp:
    json.dump(results, fp, indent=2, default=str)
print(f"\n[DONE] Saved combined synergy results to {out_path}")

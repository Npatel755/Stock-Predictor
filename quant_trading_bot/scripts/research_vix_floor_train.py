"""Research Script: Volatility Floor Conditioning (VIX Regime Filter) for Architecture D+
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Hypothesis:
In low-volatility compression regimes (e.g. VIX < 13-14), intraday range is too narrow to overcome
CME micro bid-ask spreads and commissions, resulting in chop. Filtering out extreme low VIX will
eliminate negative-expectancy trades, reduce portfolio drawdown, and boost overall expectancy.
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

print("=" * 80)
print("VOLATILITY FLOOR REGIME AUDIT (2010-2023 TRAINING ONLY)")
print("=" * 80, flush=True)

os.environ["SIZING_BUDGET"] = "150.0"
srcs = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]
ns1 = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}
exec(srcs, ns1)
ep = ns1["ep"]
bars_for = ns1["bars_for"]
backw_mask = ns1["backw_mask"]
daily = ns1["daily"]
START = ns1["START"]
MULT = ns1["MULT"]

spec = ep.CANDIDATES["ag_arch_d_plus_v2"]

# Load VIX
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

def run_sl_vix_floor(sl, prio, vix_floor=0.0):
    b, mins, atr = bars_for(sl)
    blocked = backw_mask(b) if (spec.get("day_filter") == "no_backwardation" and not sl.get("day_filter_exempt")) else None
    
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    day = et.dt.date.to_numpy()
    
    # Custom VIX floor mask: block entries if prior VIX < vix_floor
    if vix_floor > 0.0:
        vix_series = pd.Series([prior_vix(d) for d in day], index=b.index)
        low_vix_mask = vix_series < vix_floor
        if blocked is not None:
            blocked = blocked | low_vix_mask.to_numpy()
        else:
            blocked = low_vix_mask.to_numpy()
            
    r_sl = ep.run_sleeve(sl, b, START, blocked)
    for t in r_sl["trades"]:
        t["prio"] = prio
        t["sleeve"] = sl["name"]
        t["exit_day"] = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        t["dec"] = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=mins)
        a = float(atr.get(t["dec"], np.nan))
        t["stop_risk"] = round(float(sl["stop_atr"]) * a * MULT[sl["instrument"]] + 1.0 + 3 * 0.25 * MULT[sl["instrument"]], 2)
    return r_sl["trades"]

def route_trades(allt):
    allt = sorted(allt, key=lambda x: (x["dec"], x["prio"]))
    acc = []
    busy_until = None
    for t in allt:
        en = pd.Timestamp(t["entry_ts"])
        ex = pd.Timestamp(t["exit_ts"])
        if busy_until is not None and en < busy_until:
            continue
        acc.append(t)
        busy_until = ex
    return acc

sleeves = spec["sleeves"]

def evaluate_vix_threshold(floor_val):
    all_trades = []
    for i, sl in enumerate(sleeves):
        all_trades.extend(run_sl_vix_floor(sl, i, vix_floor=floor_val))
    routed = route_trades(all_trades)
    
    df = pd.DataFrame(routed)
    df["net"] = df["net"].astype(float)
    df["year"] = [pd.Timestamp(x).year for x in df["exit_ts"]]
    
    cum = df["net"].cumsum()
    hwm = cum.cummax()
    dd = hwm - cum
    max_dd = dd.max() if len(dd) else 0.0
    
    n = len(df)
    net = cum.iloc[-1] if n else 0.0
    exp = net / n if n else 0.0
    wr = (df["net"] > 0).mean() * 100 if n else 0.0
    
    yr = df.groupby("year")["net"].sum()
    pos_years = (yr > 0).sum()
    
    # Marked DD
    ev = []
    daily_pnl = {}
    for t in routed:
        en = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York")
        ex = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York")
        ev.append((en, "worst", -float(t["stop_risk"]), 0.0))
        ev.append((ex, "close", 0.0, float(t["net"])))
        daily_pnl[ex.date()] = daily_pnl.get(ex.date(), 0.0) + float(t["net"])
        
    ev.sort(key=lambda z: z[0])
    closed = hwm_m = worst_m = 0.0
    br2k = 0
    for ts, kind, unreal, real in ev:
        if kind == "worst": eq = closed + unreal
        else: closed += real; eq = closed; hwm_m = max(hwm_m, eq)
        tdd = hwm_m - eq
        if tdd > worst_m: worst_m = tdd
        if tdd >= 2000: br2k += 1
        
    s_daily = pd.Series(daily_pnl).sort_index()
    mc_breach = ns1["breach"](s_daily) if len(s_daily) else 0.0
    
    label = f"VIX Floor >= {floor_val:.1f}" if floor_val > 0 else "Baseline (No VIX Floor)"
    print(f"[{label}]")
    print(f"  Trades: {n} | Net: +${net:,.2f} | Exp: +${exp:.2f}/tr | WR: {wr:.1f}%")
    print(f"  Realized DD: ${max_dd:,.2f} | Marked DD: ${worst_m:,.2f} | $2k Touches: {br2k}")
    print(f"  Pos Years: {pos_years}/14 ({pos_years/14*100:.1f}%) | 1Y MC Ruin: {mc_breach*100:.2f}%")
    return dict(floor=floor_val, trades=n, net=round(net, 2), exp=round(exp, 2), wr=round(wr, 1),
                realized_dd=round(max_dd, 2), marked_dd=round(worst_m, 2), touches=br2k, pos_years=pos_years)

results = []
for f in [0.0, 11.0, 12.0, 13.0, 14.0, 15.0]:
    results.append(evaluate_vix_threshold(f))

out_path = ROOT / "reports/VOLATILITY_FLOOR_SWEEP_TRAIN.json"
with open(out_path, "w") as fp:
    json.dump(results, fp, indent=2, default=str)
print(f"\n[DONE] Saved sweep results to {out_path}")

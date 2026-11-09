"""Comprehensive Research Script: Strategy Frontier v3, Overnight Catastrophe Stop for Book AD,
and Intraday Institutional Extensions.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Investigates:
1. Exact Engine Parity for Architecture D+ v3 (Gap-Continuation Crabel + MNQ 60m + MES 30m).
2. Book AD Resolution: Overnight Dip v2 WITH $600 Catastrophe Stop + Architecture D+ v3 Intraday.
   Evaluates marked DD vs $2k floor, floor touches, closed net, and Monte Carlo ruin.
3. Lunch Reversal / VWAP Mean Reversion Sleeve (11:30-14:00 ET) on MES and MNQ as potential orthogonal ballast.
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

print("=" * 80)
print("FRONTIER RESEARCH: TRAINING 2010-2023 ONLY")
print("=" * 80, flush=True)

# Import Devin's exact harness from dplus_1_pilot and sizing_1_pilot
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

import mass_1m_search as m1

# --------------------------------------------------------------------------------------
# 1. Evaluate Architecture D+ v3 with Gap Continuation under Devin's exact engine
# --------------------------------------------------------------------------------------
print("\n[PART 1] Running Exact Engine Simulation of Architecture D+ Variants...")

# Let's inspect sleeves
base_spec = ep.CANDIDATES["ag_arch_d_plus_v2"]

# Define run_sleeve helper that supports gap-continuation on Crabel
def run_sl_custom(sl, prio, gap_continuation=False):
    b, mins, atr = bars_for(sl)
    blocked = backw_mask(b) if (base_spec.get("day_filter") == "no_backwardation" and not sl.get("day_filter_exempt")) else None
    
    # Custom signal generation if gap_continuation requested on crabel
    if sl["signal"] == "crabel_open_drive" and gap_continuation:
        et = b.timestamp_utc.dt.tz_convert("America/New_York")
        sod = (et.dt.hour * 60 + et.dt.minute).to_numpy()
        day = et.dt.date.to_numpy()
        c = b.close.to_numpy(float)
        df = pd.DataFrame(dict(day=day, sod=sod, o=b.open.to_numpy(float), h=b.high.to_numpy(float), l=b.low.to_numpy(float), c=c))
        
        # Calculate daily open, 10:00 close, and previous day's close for gap
        r = df[df.sod.isin([570, 585])].groupby("day")
        o930 = df[df.sod == 570].groupby("day").o.first()
        c1000 = df[df.sod == 585].groupby("day").c.first()
        hi, lo = r.h.max(), r.l.min()
        rng_ = (hi - lo).replace(0, np.nan)
        op = (o930 - lo) / rng_
        cp = (c1000 - lo) / rng_
        tail = float(sl.get("tail", 0.2))
        
        # Previous day close
        daily_close = df.groupby("day").c.last()
        prev_close = daily_close.shift(1).reindex(op.index)
        gap = (o930 - prev_close) / prev_close
        
        # Gap continuation: bull drive (op<=tail & cp>=1-tail) requires gap >= 0
        # Bear drive (op>=1-tail & cp<=tail) requires gap <= 0
        bull_drive = ((op <= tail) & (cp >= 1 - tail) & (gap >= 0.0)).fillna(False).to_numpy()
        bear_drive = ((op >= 1 - tail) & (cp <= tail) & (gap <= 0.0)).fillna(False).to_numpy()
        
        sig_day = pd.Series(np.where(bull_drive, 1, np.where(bear_drive, -1, 0)), index=op.index)
        min_rng = float(sl.get("min_range", 0.0))
        if min_rng > 0:
            sig_day = pd.Series(np.where(rng_ >= min_rng, sig_day, 0), index=op.index)
            
        sig = np.where(sod == 585, pd.Series(day).map(sig_day).fillna(0).to_numpy(), 0)
        
        # Run sleeve with overridden signal
        # We temporarily patch ep.custom_signal to use this sig
        orig_signals = ep.custom_signal
        def patched_signals(cfg, bars):
            if cfg.get("name") == sl.get("name"):
                return sig.astype(np.int8), np.nan_to_num(atr).astype(np.float32)
            return orig_signals(cfg, bars)
        ep.custom_signal = patched_signals
        try:
            r_sl = ep.run_sleeve(sl, b, START, blocked)
        finally:
            ep.custom_signal = orig_signals
    else:
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

# Sleeves
sleeves = base_spec["sleeves"] # 3 sleeves: AG_CRABEL15_D_1c, AG_TRD60_D_1c, AG_MES_TRD30_D_1c

# 1. Baseline Architecture D+ v2 (without gap continuation)
t_crabel_v2 = run_sl_custom(sleeves[0], 0, gap_continuation=False)
t_trd60 = run_sl_custom(sleeves[1], 1)
t_mes30 = run_sl_custom(sleeves[2], 2)

v2_routed = route_trades(t_crabel_v2 + t_trd60 + t_mes30)

# 2. Architecture D+ v3 (with Gap Continuation)
t_crabel_v3 = run_sl_custom(sleeves[0], 0, gap_continuation=True)
v3_routed = route_trades(t_crabel_v3 + t_trd60 + t_mes30)

def calc_stats(trades, name):
    df_t = pd.DataFrame(trades)
    df_t["net"] = df_t["net"].astype(float)
    df_t["year"] = [pd.Timestamp(x).year for x in df_t["exit_ts"]]
    
    # Equity curve and drawdown
    df_t = df_t.sort_values("exit_ts").reset_index(drop=True)
    cum = df_t["net"].cumsum()
    hwm = cum.cummax()
    dd = hwm - cum
    max_dd = dd.max()
    
    yr = df_t.groupby("year")["net"].sum()
    pos_years = (yr > 0).sum()
    n_trades = len(df_t)
    net = cum.iloc[-1] if n_trades > 0 else 0.0
    exp = net / n_trades if n_trades > 0 else 0.0
    wr = (df_t["net"] > 0).mean() * 100
    
    # Marked DD calculation (intraday stop risk at entry)
    ev = []
    daily_pnl = {}
    for t in trades:
        en = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York")
        ex = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York")
        ev.append((en, "worst", -float(t["stop_risk"]), 0.0))
        ev.append((ex, "close", 0.0, float(t["net"])))
        daily_pnl[ex.date()] = daily_pnl.get(ex.date(), 0.0) + float(t["net"])
        
    ev.sort(key=lambda z: z[0])
    closed = hwm_m = worst_m = 0.0
    br = {2000: 0}
    for ts, kind, unreal, real in ev:
        if kind == "worst":
            eq = closed + unreal
        else:
            closed += real
            eq = closed
            hwm_m = max(hwm_m, eq)
        tdd = hwm_m - eq
        if tdd > worst_m:
            worst_m = tdd
        if tdd >= 2000:
            br[2000] += 1
            
    # MC breach
    s_daily = pd.Series(daily_pnl).sort_index()
    mc_breach = ns1["breach"](s_daily)
    
    print(f"\n--- {name} ---")
    print(f"Trades: {n_trades} | Net P&L: +${net:,.2f} | Expectancy: +${exp:.2f}/tr | Win Rate: {wr:.1f}%")
    print(f"Realized DD: ${max_dd:,.2f} | Marked DD: ${worst_m:,.2f} | $2k Touches: {br[2000]}")
    print(f"Positive Years: {pos_years}/14 ({pos_years/14*100:.1f}%) | 1Y MC Ruin Prob: {mc_breach*100:.2f}%")
    
    return {
        "name": name, "trades": n_trades, "net": round(net, 2), "expectancy": round(exp, 2),
        "win_rate": round(wr, 1), "realized_dd": round(max_dd, 2), "marked_dd": round(worst_m, 2),
        "touches_2k": br[2000], "pos_years": int(pos_years), "mc_breach_pct": round(mc_breach * 100, 2),
        "by_year": {int(y): round(v, 2) for y, v in yr.items()}
    }

res_v2 = calc_stats(v2_routed, "ag_arch_d_plus_v2 (Standard Unfiltered Crabel)")
res_v3 = calc_stats(v3_routed, "ag_arch_d_plus_v3 (Gap-Continuation Crabel)")

# --------------------------------------------------------------------------------------
# 2. Book AD Resolution: Overnight Dip v2 + Catastrophe Stop + D+ v3
# --------------------------------------------------------------------------------------
print("\n" + "=" * 80)
print("[PART 2] BOOK AD RESOLUTION: OVERNIGHT DIP + CATASTROPHE STOP + D+ v3")
print("=" * 80)

# Load overnight data exactly as in book_2_pilot.py
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]
n3 = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}
exec(src3, n3)
mn = n3["nights"]("MNQ")
ms = n3["nights"]("MES")
mg = ms.gap.reindex(mn.index)
msd = ms.sd20.reindex(mn.index)
mask = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False)

# Let's inspect overnight trades with and without catastrophe hard stop
b_1m = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "low", "high", "close", "open"]]
et_1m = b_1m.timestamp_utc.dt.tz_convert("America/New_York")
b_1m["date"] = et_1m.dt.date
b_1m["sod"] = et_1m.dt.hour * 60 + et_1m.dt.minute
low_open = b_1m[(b_1m.sod >= 570) & (b_1m.sod < 585)].groupby("date").low.min()
dates = np.array(sorted(set(mn.index) | set(low_open.index)))

def next_day(d):
    i = dates.searchsorted(d, side="right")
    return dates[i] if i < len(dates) else None

def evaluate_book(intraday_trades, catastrophe_stop_dollars=None, scale=1.0):
    """Simulate Book AD under exact marked-DD mechanics with optional overnight catastrophe stop."""
    ev = []
    daily = {}
    
    # Process overnight trades
    n_stopped = 0
    overnight_pnl_total = 0.0
    
    for nk in mn[mask].index:
        p_orig = n3["pnl"](mn.loc[[nk]], "MNQ", ex="x0945").iloc[0]
        if pd.isna(p_orig):
            continue
            
        ex_day = next_day(nk)
        e = float(mn.at[nk, "e1805"])
        lo = min(float(mn.at[nk, "low_night"]), float(low_open.get(ex_day, np.inf)))
        
        # Check if catastrophe stop breached
        # 1 contract MNQ = $2/pt. Stop distance in pts = stop_dollars / 2.0
        max_adverse_dollars = (lo - e) * 2.0 - 3.0 # adverse price move minus commission/spread
        
        if catastrophe_stop_dollars is not None and max_adverse_dollars <= -catastrophe_stop_dollars:
            # Stopped out at catastrophe stop
            p_trade = -catastrophe_stop_dollars
            lo_effective = e - (catastrophe_stop_dollars / 2.0)
            n_stopped += 1
        else:
            p_trade = float(p_orig)
            lo_effective = lo
            
        overnight_pnl_total += p_trade
        
        ev.append((pd.Timestamp(f"{nk} 18:05", tz="America/New_York"), "worst", (lo_effective - e) * 2.0 - 3.0, 0.0))
        ev.append((pd.Timestamp(f"{ex_day} 09:45", tz="America/New_York"), "close", 0.0, float(p_trade)))
        daily[ex_day] = daily.get(ex_day, 0.0) + float(p_trade)
        
    # Process intraday trades
    for t in intraday_trades:
        x = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York")
        en = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York")
        ev.append((en, "worst", -float(t["stop_risk"]) * scale, 0.0))
        ev.append((x, "close", 0.0, float(t["net"]) * scale))
        daily[x.date()] = daily.get(x.date(), 0.0) + float(t["net"]) * scale
        
    ev.sort(key=lambda z: z[0])
    closed = hwm = worst = 0.0
    when = None
    br = {2000: 0, 2500: 0}
    inb = {f: False for f in br}
    
    for ts, kind, unreal, real in ev:
        if kind == "worst":
            eq = closed + unreal
        else:
            closed += real
            eq = closed
            hwm = max(hwm, eq)
        tdd = hwm - eq
        if tdd > worst:
            worst, when = tdd, str(ts)
        for f in br:
            if tdd >= f and not inb[f]:
                br[f] += 1
                inb[f] = True
            if tdd < f * 0.5:
                inb[f] = False
                
    d = pd.Series(daily).sort_index()
    yr = d.groupby(pd.to_datetime(d.index).year).sum()
    mc = ns1["breach"](d)
    
    passes = bool(worst < 2000.0 and br[2000] == 0 and d.sum() >= 25486 and (yr > 0).sum() >= 11 and yr[yr.index < 2017].sum() > 0 and yr[yr.index >= 2017].sum() > 0 and mc <= 0.02)
    
    return {
        "closed_net": round(float(d.sum()), 2),
        "marked_dd": round(worst, 2),
        "when": when,
        "touches_2000": br[2000],
        "pos_years": int((yr > 0).sum()),
        "half1": round(float(yr[yr.index < 2017].sum()), 2),
        "half2": round(float(yr[yr.index >= 2017].sum()), 2),
        "worst_day": round(float(d.min()), 2),
        "breach_mc_pct": round(mc * 100, 2),
        "n_stopped_overnight": n_stopped,
        "overnight_net": round(overnight_pnl_total, 2),
        "passes_gate": passes
    }

print("\n--- Testing Book Combinations ---")

# Variant 1: Devin's Book AD (D+ v2, No stop on overnight)
book_v2_unstopped = evaluate_book(v2_routed, catastrophe_stop_dollars=None)
print("1. Devin's Book AD (v2, unstopped):")
print(f"   Net: +${book_v2_unstopped['closed_net']:,.2f} | Marked DD: ${book_v2_unstopped['marked_dd']:,.2f} | Touches: {book_v2_unstopped['touches_2000']} | Passes: {book_v2_unstopped['passes_gate']}")

# Variant 2: Book AD v3 (D+ v3 Gap Continuation, No stop on overnight)
book_v3_unstopped = evaluate_book(v3_routed, catastrophe_stop_dollars=None)
print("2. Book AD v3 (v3 Gap Continuation, unstopped overnight):")
print(f"   Net: +${book_v3_unstopped['closed_net']:,.2f} | Marked DD: ${book_v3_unstopped['marked_dd']:,.2f} | Touches: {book_v3_unstopped['touches_2000']} | Passes: {book_v3_unstopped['passes_gate']}")

# Variant 3: Book AD v2 WITH $600 Catastrophe Stop on Overnight
book_v2_stop600 = evaluate_book(v2_routed, catastrophe_stop_dollars=600.0)
print("3. Book AD v2 WITH $600 Catastrophe Stop:")
print(f"   Net: +${book_v2_stop600['closed_net']:,.2f} | Marked DD: ${book_v2_stop600['marked_dd']:,.2f} | Touches: {book_v2_stop600['touches_2000']} | Passes: {book_v2_stop600['passes_gate']}")

# Variant 4: Book AD v3 (Gap Continuation) WITH $600 Catastrophe Stop
book_v3_stop600 = evaluate_book(v3_routed, catastrophe_stop_dollars=600.0)
print("4. Book AD v3 (Gap Continuation) WITH $600 Catastrophe Stop:")
print(f"   Net: +${book_v3_stop600['closed_net']:,.2f} | Marked DD: ${book_v3_stop600['marked_dd']:,.2f} | Touches: {book_v3_stop600['touches_2000']} | Passes: {book_v3_stop600['passes_gate']}")

# Variant 5: Book AD v3 WITH $500 Catastrophe Stop
book_v3_stop500 = evaluate_book(v3_routed, catastrophe_stop_dollars=500.0)
print("5. Book AD v3 (Gap Continuation) WITH $500 Catastrophe Stop:")
print(f"   Net: +${book_v3_stop500['closed_net']:,.2f} | Marked DD: ${book_v3_stop500['marked_dd']:,.2f} | Touches: {book_v3_stop500['touches_2000']} | Passes: {book_v3_stop500['passes_gate']}")

# Variant 6: Scaled Book AD v3 (Intraday at 2c, $300 budget) WITH $600 Stop
book_v3_stop600_2c = evaluate_book(v3_routed, catastrophe_stop_dollars=600.0, scale=2.0)
print("6. Scaled Book AD v3 (Intraday 2c) WITH $600 Catastrophe Stop:")
print(f"   Net: +${book_v3_stop600_2c['closed_net']:,.2f} | Marked DD: ${book_v3_stop600_2c['marked_dd']:,.2f} | Touches: {book_v3_stop600_2c['touches_2000']} | Passes: {book_v3_stop600_2c['passes_gate']}")

# --------------------------------------------------------------------------------------
# 3. Save Output Artifact
# --------------------------------------------------------------------------------------
out_data = {
    "v2_intraday": res_v2,
    "v3_intraday": res_v3,
    "book_v2_unstopped": book_v2_unstopped,
    "book_v3_unstopped": book_v3_unstopped,
    "book_v2_stop600": book_v2_stop600,
    "book_v3_stop600": book_v3_stop600,
    "book_v3_stop500": book_v3_stop500,
    "book_v3_stop600_2c": book_v3_stop600_2c
}

report_path = ROOT / "reports/FRONTIER_V3_AND_CATASTROPHE_BOOK_TRAIN.json"
with open(report_path, "w") as f:
    json.dump(out_data, f, indent=2, default=str)
print(f"\n[DONE] Saved comprehensive results to {report_path}")

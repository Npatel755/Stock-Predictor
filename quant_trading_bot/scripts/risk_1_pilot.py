"""risk_1: pause rules for Book A's overnight leg, scored with book_1's intraday-trailing marks; training 2010-23 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
src = (ROOT / "scripts/book_1_pilot.py").read_text().split("\nev.sort(")[0]
ns = {"__file__": str(ROOT / "scripts/book_1_pilot.py")}; exec(src, ns); ev = ns["ev"]
# tag events: overnight events were appended first (night loop) -> mark by order: find split via the first intraday event's structure
# book_1 appends (t_in,"worst",...),(t_out,"close",...) per night, then per intraday trade. We re-derive leg by checking membership in the night times.
night_times = set(); src_n = src
for key in ns["mn"].index if "mn" in ns else []: pass
# simpler: rebuild leg tags from the night loop variables kept in ns
ov_pairs = ns.get("ov_pairs")
if ov_pairs is None:
    # reconstruct: nights in ns["mn"] with the v2 mask produce entry at 18:05 ET of nk and exit next day 09:45 -> tag events whose time is 18:05 ET
    pass
def leg_of(t, kind):  # overnight entries are at 18:05 ET exactly, exits at 09:45 ET exactly
    hm = (t.hour, t.minute); return "ov" if hm in ((18, 5), (9, 45)) else "in"
events = sorted([(t, k, w, r, leg_of(t, k)) for (t, k, w, r) in ev], key=lambda x: x[0])
def week_key(t):  # Sunday 18:00 belongs to the following Mon-Fri week
    d = (t + pd.Timedelta(hours=6)).date(); iso = pd.Timestamp(d).isocalendar(); return (iso[0], iso[1])
def run(rule, thr=None):
    closed = 0.0; hwm = 0.0; worst_tdd = 0.0; when = None; br = {2000: 0, 2500: 0}; inb = {2000: False, 2500: False}
    week = None; wk_pnl = 0.0; paused = False; skip_open = set(); streak = 0; skipped = 0; skip_next = False; nights = 0
    i = 0
    while i < len(events):
        t, k, w, r, leg = events[i]
        wk = week_key(t)
        if wk != week: week, wk_pnl, paused = wk, 0.0, False
        if leg == "ov" and k == "worst":  # a night entry: decide skip
            nights += 1
            skip = (rule in ("R1", "R2") and paused) or (rule == "R3" and skip_next)
            if skip:
                skipped += 1; skip_open.add(i)
                if rule == "R3": skip_next = False; streak = 0
                # also skip the matching close (next ov close event)
                j = i + 1
                while j < len(events) and not (events[j][4] == "ov" and events[j][1] == "close"): j += 1
                skip_open.add(j); i += 1; continue
        if i in skip_open: i += 1; continue
        eq = closed + w if k == "worst" else closed + r
        if k == "close":
            closed += r; wk_pnl += r
            if leg == "ov":
                streak = streak + 1 if r < 0 else 0
                if rule == "R3" and streak >= 3: skip_next = True
            if rule in ("R1", "R2") and wk_pnl <= -thr: paused = True
        hwm = max(hwm, eq); tdd = hwm - eq
        if tdd > worst_tdd: worst_tdd, when = tdd, str(t)
        for f in br:
            if tdd >= f and not inb[f]: br[f] += 1; inb[f] = True
            if tdd < f * 0.5: inb[f] = False
        i += 1
    return dict(closed_net=round(closed, 2), marked_dd=round(worst_tdd, 2), when=when, breaches=br, nights=nights, skipped=skipped)
out = {"book_a": run("base")}; print("book_a", out["book_a"], flush=True)
for rule, thr in (("R1", 750.0), ("R2", 1000.0), ("R3", None)):
    r = run(rule, thr); r["retained"] = round(r["closed_net"] / out["book_a"]["closed_net"], 3); r["pass"] = bool(r["marked_dd"] < 2000 and r["retained"] >= 0.9)
    out[rule] = r; print(rule, r, flush=True)
Path(ROOT / "reports/RISK_1_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

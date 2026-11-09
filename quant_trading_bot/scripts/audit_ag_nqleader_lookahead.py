"""Forensic check of Antigravity's NQ-leader sleeve (audit_unified_5sleeve_portfolio.py): their z uses the close of the bar timestamped 10:00
(= 10:15 close, bars are open-stamped) while the signal is placed on the 09:45 bar and filled at the 10:00 open -> one-bar look-ahead.
Runs both conventions on the fixed engine, MNQ costs, 2010-23, two-sided z >= 1.0 (their script's threshold), stop 2 ATR, 4R, hold 12."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/composite_1_pilot.py").read_text().split("def variants(S):")[0]
ns = {"__file__": str(ROOT / "scripts/composite_1_pilot.py")}; exec(src, ns); m1, run, total = ns["m1"], ns["run"], ns["total"]; ns["P"].update(stop_atr=2.0, target_r=4.0, hold_bars=12)
nq = m1.load_bars("MNQ", 15, "2009-11-01", "2024-01-01", "train").reset_index(drop=True); es = m1.load_bars("MES", 15, "2009-11-01", "2024-01-01", "train").reset_index(drop=True)
def daily(b, close_sod):
    et = b.timestamp_utc.dt.tz_convert("America/New_York"); sod = (et.dt.hour * 60 + et.dt.minute).to_numpy(); day = et.dt.date
    g = pd.DataFrame(dict(day=day, sod=sod, o=b.open.astype(float), c=b.close.astype(float)))
    return pd.DataFrame(dict(o=g[g.sod == 570].groupby("day").o.first(), c=g[g.sod == close_sod].groupby("day").c.last())).dropna(), sod, day
et = nq.timestamp_utc.dt.tz_convert("America/New_York"); sod = (et.dt.hour * 60 + et.dt.minute).to_numpy(); day = et.dt.date
h, l, c = nq.high.astype(float), nq.low.astype(float), nq.close.astype(float); prev = c.shift(1)
ATR = np.nan_to_num(pd.concat((h - l, (h - prev).abs(), (l - prev).abs()), axis=1).max(axis=1).rolling(14, min_periods=14).mean().to_numpy()).astype(np.float32)
out = {}
for label, close_sod in (("correct_close_1000", 585), ("lookahead_close_1015", 600)):
    Dn, _, _ = daily(nq, close_sod); De, _, _ = daily(es, close_sod)
    spread = ((Dn.c / Dn.o) - (De.c / De.o)).dropna(); z = spread / spread.rolling(20, min_periods=20).std().shift(1)
    dirs = pd.Series(np.where(z >= 1.0, 1, np.where(z <= -1.0, -1, 0)), index=z.index)
    sig = np.where(sod == 585, pd.Series(day).map(dirs).fillna(0).to_numpy(), 0).astype(np.int8)
    o = run(nq, sig, ATR, 2010); t = total(o); tr = sum(v["trades"] for v in o.values())
    out[label] = dict(total=t, trades=tr, per_trade=round(t / tr, 2), pos_years=int(sum(v["net"] > 0 for v in o.values())), pre2020=round(sum(v["net"] for y, v in o.items() if y < 2020), 2), by_year={y: v["net"] for y, v in o.items()})
    print(label, {k: v for k, v in out[label].items() if k != "by_year"}, flush=True)
json.dump(out, open(ROOT / "reports/AG_NQLEADER_LOOKAHEAD_AUDIT.json", "w"), indent=1); print("DONE")

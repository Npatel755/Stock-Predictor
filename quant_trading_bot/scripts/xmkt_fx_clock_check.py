"""xmkt_fx_clock_check (Claude fork A, 2026-11-11): verify HistData's FX wall clock before any strategy result is used. TRAINING years only.
No CME FX futures data is on hand, so the clock is checked against known US event times instead:
  (1) on first Fridays of the month (NFP is almost always one of them) the largest mean |1-min log return| between 06:00 and 11:00 wall time
      must sit at 08:30 (the bar starting 08:30) if the clock is New York time; a fixed-EST clock would show 07:30 in summer;
  (2) the Sunday reopen should appear at 17:00 New York time.
Checked per year x regime (winter / summer / spring gap = US already on DST, EU not yet / fall gap). Any year-regime where the spike is not at
08:30 is flagged and its weeks are DROPPED by the strategy script (rule fixed here, before results). Run with `python -P`.
AMENDMENT (after the first EUR/USD run, before any strategy result): a peak at 08:29-08:31 counts as aligned (the release spike spills into
the next 1-minute bar; an hour shift shows as 07:30 / 09:30 with a 16:00 Sunday open). EUR/USD summer/winter: all within 08:30-08:31 with a
17:00 Sunday open; fall-gap weeks 2019, 2021-23 are an hour off (07:30 / 09:00, Sunday 16:00). Rule used by xmkt_fx_train.py: drop EVERY
year's spring-gap and fall-gap weeks (as gold_1 did) plus any summer/winter year-regime that fails the +-1 minute check.
"""
import json, sys
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; SRC = ROOT / "data/external/xmkt_histdata"


def regime_of(dates):
    out = {}
    for d in sorted(set(dates)):
        y = d.year; mar = pd.date_range(f"{y}-03-01", f"{y}-03-31", freq="W-SUN"); octo = pd.date_range(f"{y}-10-01", f"{y}-10-31", freq="W-SUN")
        us_s, eu_s, eu_e = mar[1].date(), mar[-1].date(), octo[-1].date(); us_e = pd.date_range(f"{y}-11-01", f"{y}-11-30", freq="W-SUN")[0].date()
        out[d] = "spring_gap" if us_s <= d < eu_s else "fall_gap" if eu_e <= d < us_e else ("summer" if us_s <= d < us_e else "winter")
    return out


def check(p):
    df = pd.read_parquet(SRC / f"{p}_1m_2010_2023.parquet").sort_values("wall").reset_index(drop=True)
    assert df.wall.max() < pd.Timestamp("2024-01-01")
    df["r"] = np.log(df.close).diff().abs(); df["d"] = df.wall.dt.date; df["mod"] = df.wall.dt.hour * 60 + df.wall.dt.minute
    REG = regime_of(df.d); df["reg"] = df.d.map(REG); dow = pd.to_datetime(df.d).dt.dayofweek; dom = pd.to_datetime(df.d).dt.day
    ff = df[(dow == 4) & (dom <= 7) & (df["mod"] >= 360) & (df["mod"] < 660)]
    sun = df[dow == 6].groupby("d").wall.min()
    rows = []
    for (y, reg), g in ff.groupby([pd.to_datetime(ff.d).dt.year, "reg"]):
        m = g.groupby("mod").r.mean(); top = int(m.idxmax())
        s = sun[[REG[d] == reg and d.year == y for d in sun.index]]
        rows.append(dict(year=int(y), regime=reg, peak=f"{top // 60:02d}:{top % 60:02d}", peak_over_median=round(float(m.max() / m.median()), 1),
                         sunday_open=s.dt.strftime("%H:%M").mode().iloc[0] if len(s) else None, first_fridays=int(g.d.nunique())))
    t = pd.DataFrame(rows); t["ok"] = t.peak.isin(["08:29", "08:30", "08:31"])
    return t


if __name__ == "__main__":
    res = {}
    for p in sys.argv[1:] or ["eurusd"]:
        t = check(p); res[p] = t.to_dict("records"); print(p); print(t.to_string(index=False), flush=True)
    f = ROOT / "reports/xmkt_fx_clock_check.json"; old = json.loads(f.read_text()) if f.exists() else {}; old.update(res)
    f.write_text(json.dumps(old, indent=1, default=str))

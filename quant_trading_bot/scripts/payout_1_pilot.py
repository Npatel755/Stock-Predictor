"""payout_1: sizes at which the typical winning trade / day clears $150, and what it costs (research/payout_1/PROTOCOL.md)."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
S2 = (ROOT / "scripts/staging_2_pilot.py").read_text().split('ns["trades"] = trades')[0]; n2 = {"__file__": str(ROOT / "scripts/staging_2_pilot.py")}; exec(S2, n2)
trades, NY = n2["trades"], n2["NY"]
F = (ROOT / "scripts/funded_1_pilot.py").read_text(); nf = {"np": np, "pd": pd}; exec(F[F.index("def sim("):F.index("starts = ")], nf); sim = nf["sim"]
CONF = {"overnight_v2": lambda t: 1 if t["leg"] == "L1" else 0, "allweather_1c": lambda t: 1 if t["leg"] == "L2" else 0,
        "dplus_v2": lambda t: 1 if t["leg"] == "L3" else 0, "dplus_gapsized": lambda t: (2 if t["gap2"] else 1) if t["leg"] == "L3" else 0,
        "bookA": lambda t: 1 if t["leg"] in ("L1", "L2") else 0, "bookA_skew": lambda t: (2 if t["skew"] else 1) if t["leg"] in ("L1", "L2") else 0}
starts = pd.date_range("2010-01-01", "2023-01-01", freq="MS", tz=NY); out = {}
for cname, mult in CONF.items():
    out[cname] = {}
    for k in range(1, 7):
        tr = [dict(t, m=mult(t) * k) for t in trades if mult(t)]
        nets = np.array([t["net"] * t["m"] for t in tr]); wins = nets[nets > 0]
        day = pd.Series(nets, index=[t["t_out"].date() for t in tr]).groupby(level=0).sum(); wd = day[day > 0]
        yrs = pd.Series(day.values, index=pd.to_datetime(day.index)); d150 = yrs[yrs >= 150].groupby(yrs[yrs >= 150].index.year).size()
        ev = []
        for t in tr: ev.append((t["t_in"], 0, t["worst"] * t["m"], 0.0, t["t_out"].date())); ev.append((t["t_out"], 1, 0.0, t["net"] * t["m"], t["t_out"].date()))
        ev.sort(key=lambda x: (x[0], x[1]))
        res = [sim([x for x in ev if s0 <= x[0] < s0 + pd.DateOffset(months=12)], "STATIC", 1000.0, horizon_end=s0 + pd.DateOffset(months=12)) for s0 in starts]
        oc = pd.Series([r["outcome"] for r in res]); ok = [r["closed"] for r in res if r["outcome"] == "open"]
        eq = day.cumsum(); mk = []  # marked DD from event path
        closed = hwm = 0.0; mdd = 0.0
        for ts, kind, unreal, real, d in ev:
            if kind == 0: mdd = max(mdd, hwm - (closed + unreal))
            else: closed += real; hwm = max(hwm, closed); mdd = max(mdd, hwm - closed)
        out[cname][k] = dict(trades=len(tr), net=round(float(nets.sum()), 2), median_win_trade=round(float(np.median(wins)), 2), share_win_trades_ge150=round(float((wins >= 150).mean()), 3),
                             median_win_day=round(float(np.median(wd)), 2), share_win_days_ge150=round(float((wd >= 150).mean()), 3), days150_per_year=round(float(d150.reindex(range(2010, 2024), fill_value=0).mean()), 1),
                             marked_dd=round(mdd, 2), worst_day=round(float(day.min()), 2), p_breach_static=round(float((oc == "fail_floor").mean()), 3), p_dll=round(float((oc == "fail_dll").mean()), 3),
                             median_net_12m=round(float(np.median(ok)), 2) if ok else None)
    ks = [k for k in range(1, 7) if out[cname][k]["median_win_trade"] >= 150 and out[cname][k]["median_win_day"] >= 150]
    out[cname]["k_star"] = ks[0] if ks else None
    print(cname, "k*", out[cname]["k_star"], {k: (v["median_win_trade"], v["median_win_day"], v["marked_dd"], v["p_breach_static"], v["p_dll"], v["days150_per_year"]) for k, v in out[cname].items() if k != "k_star"}, flush=True)
json.dump(out, open(ROOT / "reports/PAYOUT_1_TRAINING.json", "w"), indent=1, default=str); print("DONE", flush=True)

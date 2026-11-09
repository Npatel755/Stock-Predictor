"""Descriptive edge attribution (training years only, nothing tuned): is the 2020-23 profit of the surviving 15-min trend/breakout
sleeves a realized-volatility effect? Cuts each sleeve's trade ledger by prior-20-session realized-vol tercile (terciles fixed on
all 2010-23 sessions), decade, side and exit reason; reports concentration. Costs: $0.61/side, MNQ spread 1.75 ticks."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
from quant_futures.session_calendar import apply_early_close
eng = ep.engine()
REASON = {1: "flat_session_end", 2: "hold_timeout", 3: "stop", 4: "target", 5: "data_gap"}
SLEEVES = {s["name"]: s for s in ep.CANDIDATES["portfolio_e"]["sleeves"]}
SLEEVES["MNQ_TRD8_1c"] = dict(instrument="MNQ", family="trend", lookback=8, threshold=1.0, stop_atr=2.0, target_r=2.0, hold_bars=12, session_start=600, session_end=720, max_contracts=1, trailing_atr=0.0)
SLEEVES["AG_MNQ_Trend_1c"] = dict(instrument="MNQ", family="trend", lookback=6, threshold=1.0, stop_atr=1.75, target_r=2.25, hold_bars=6, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)
SLEEVES["AG_MNQ_MornBrk_1c"] = dict(instrument="MNQ", family="breakout", lookback=20, threshold=1.25, stop_atr=1.5, target_r=2.5, hold_bars=8, session_start=600, session_end=720, max_contracts=1, trailing_atr=0.0)
SLEEVES["AG_MES_Mom_1c"] = dict(instrument="MES", family="momentum", lookback=6, threshold=2.0, stop_atr=1.5, target_r=2.25, hold_bars=20, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)
BARS = {i: m1.load_bars(i, 15, "2009-12-01", "2024-01-01", "train").reset_index(drop=True) for i in ("MES", "MNQ")}
for b in BARS.values():
    assert b.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")

def session_vol(bars):
    loc = bars.timestamp_utc.dt.tz_convert("America/New_York")
    rth = bars[(loc.dt.hour * 60 + loc.dt.minute >= 570) & (loc.dt.hour * 60 + loc.dt.minute < 960)]
    close = rth.groupby(loc.loc[rth.index].dt.date).close.last()
    r = np.log(close).diff()
    vol = (r.rolling(20).std() * np.sqrt(252)).shift(1)  # known at the session open
    q = vol.quantile([1 / 3, 2 / 3]).to_numpy()
    terc = pd.cut(vol, [-np.inf, q[0], q[1], np.inf], labels=["low", "mid", "high"])
    return pd.DataFrame(dict(vol=vol, terc=terc.astype(str))), q

def trades(cfg, bars):
    data = apply_early_close(eng["arrays"](bars), bars); f = eng["features"](bars, int(cfg["lookback"])); raw = eng["signal_for"](cfg, f).astype(np.int8)
    loc = bars.timestamp_utc.dt.tz_convert("America/New_York"); dec = (loc.dt.hour * 60 + loc.dt.minute + 15).to_numpy()
    sig = np.where((dec >= cfg["session_start"]) & (dec < cfg["session_end"]) & (loc.dt.day_of_week.to_numpy() < 5), raw, 0).astype(np.int8)
    ecfg = eng["execution_cfg"](cfg); ecfg["commission_per_side"] = 0.61; ecfg["spread_ticks"] = 1.75 if cfg["instrument"] == "MNQ" else 1.0
    out = []
    for y in range(2010, 2024):
        idx = np.flatnonzero(data["year"] == y); a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
        d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(f["atr"][a:b]), ecfg)
        n = len(r["trade_net"])
        if n:
            et = pd.to_datetime(d["timestamp"][r["trade_entry"][:n]], unit="ns", utc=True).tz_convert("America/New_York")
            out.append(pd.DataFrame(dict(date=et.date, year=y, side=r["trade_side"][:n], net=r["trade_net"][:n], fees=r["trade_fees"][:n], reason=[REASON.get(int(x), str(x)) for x in r["trade_reason"][:n]])))
    return pd.concat(out, ignore_index=True)

def cuts(t, vol):
    t = t.merge(vol, left_on="date", right_index=True, how="left"); t["decade"] = np.where(t.year < 2020, "2010-19", "2020-23")
    def agg(g): return dict(net=round(float(g.net.sum())), trades=int(len(g)), per_trade=round(float(g.net.mean()), 1), win=round(float((g.net > 0).mean()), 2))
    res = dict(total=agg(t), by_decade_terc={f"{d}|{v}": agg(g) for (d, v), g in t.groupby(["decade", "terc"])}, by_terc={v: agg(g) for v, g in t.groupby("terc")},
               by_side={str(s): agg(g) for s, g in t.groupby("side")}, by_reason={s: agg(g) for s, g in t.groupby("reason")}, by_year={int(y): round(float(g.net.sum())) for y, g in t.groupby("year")})
    pos = t[t.net > 0].net.sum(); sess = t.groupby("date").net.sum().sort_values(ascending=False)
    res["concentration"] = dict(top5_sessions_share_of_gross_wins=round(float(sess.head(5).sum() / pos), 3), top5pct_trades_share_of_net=round(float(t.net.nlargest(max(1, len(t) // 20)).sum() / t.net.sum()), 2) if t.net.sum() > 0 else None,
                                gross_wins=round(float(pos)), gross_losses=round(float(t[t.net <= 0].net.sum())), fees=round(float(t.fees.sum())))
    return res

VOL = {i: session_vol(BARS[i]) for i in BARS}
report = {"vol_terciles": {i: dict(cut_points=[round(float(x), 3) for x in VOL[i][1]], sessions_by_decade_and_terc={f"{'2010-19' if d < 2020 else '2020-23'}|{v}": int(n) for (d, v), n in VOL[i][0].assign(dec=pd.to_datetime(VOL[i][0].index).year).groupby(["dec", "terc"]).size().items()}) for i in VOL}}
# collapse decade counts
for i in VOL:
    c = {}
    for k, n in report["vol_terciles"][i]["sessions_by_decade_and_terc"].items():
        c[k] = c.get(k, 0) + n
    report["vol_terciles"][i]["sessions_by_decade_and_terc"] = c
for name, cfg in SLEEVES.items():
    t = trades(cfg, BARS[cfg["instrument"]]); report[name] = cuts(t, VOL[cfg["instrument"]][0])
    print(name, report[name]["total"], report[name]["by_decade_terc"], flush=True)
(ROOT / "reports" / "EDGE_ATTRIBUTION_VOL.json").write_text(json.dumps(report, indent=1, default=str))

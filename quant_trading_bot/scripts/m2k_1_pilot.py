"""m2k_1 (research/m2k_1/PROTOCOL.md): frozen overnight-dip and All-Weather rules transferred to Russell (M2K) and Dow (MYM) micros.
Training only: bars >= 2024-01-01 are never read. RTY/YM full-size bars stand in for the micros (micro economics applied)."""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import training_5m_v2_policy as policy
policy.SPECS["M2K"] = {"tick": 0.1, "multiplier": 5.0}; policy.SPECS["MYM"] = {"tick": 1.0, "multiplier": 0.5}
os.environ["SIZING_BUDGET"] = "1e9"
s1 = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]
ns1 = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}; exec(s1, ns1); ep, backw_mask, breach = ns1["ep"], ns1["backw_mask"], ns1["breach"]
src = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("\nif __name__")[0].split("\nN = ")[0]
ns = {"__name__": "ov3", "__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src, ns)
SPEC = ns["SPEC"]; SPEC["M2K"] = dict(tick=0.1, tv=0.5, spread=2.0); SPEC["MYM"] = dict(tick=1.0, tv=0.5, spread=2.0)
ECON = {"M2K": ("RTY_c_0", 5.0), "MYM": ("YM_c_0", 0.5)}

def load_1m(inst):
    f = ROOT / f"data/market/crossasset/{ECON[inst][0]}_ohlcv1m_2010_2025.parquet"
    d = pd.read_parquet(f, columns=["open", "high", "low", "close", "volume"]); d = d[d.index < pd.Timestamp("2024-01-01", tz="UTC")]
    b = d.reset_index().rename(columns={"ts_event": "timestamp_utc"}); b = b[b.timestamp_utc >= pd.Timestamp("2010-01-01", tz="UTC")].reset_index(drop=True)
    assert b.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
    return b

def nights_from_bars(b):  # same construction as overnight_3 nights(), from an in-memory 1-min frame
    b = b[["timestamp_utc", "open", "high", "low", "close"]].copy()
    et = pd.to_datetime(b.timestamp_utc, utc=True).dt.tz_convert("America/New_York"); b["sod"] = (et.dt.hour * 60 + et.dt.minute).to_numpy(); b["date"] = et.dt.date.to_numpy()
    dates = sorted(set(b.date)); prev = {d: p for p, d in zip(dates[:-1], dates[1:])}
    b["nk"] = np.where(b.sod >= 1080, b.date, np.where(b.sod <= 600, pd.Series(b.date).map(prev).to_numpy(), None))
    day = b.groupby("date"); g = b[b.nk.notna()].groupby("nk")
    def at(sod, col, grp=g): s = b[b.sod == sod]; return s.groupby("nk" if grp is g else "date")[col].first()
    n = pd.DataFrame(dict(rth_open=at(570, "open", day), rth_close=b[(b.sod >= 955) & (b.sod < 960)].groupby("date").close.last(), o1800=at(1080, "open", day)))
    ent = pd.DataFrame(dict(e1805=at(1085, "open"), x0945=at(585, "open")))
    pre = b[(b.nk.notna()) & ((b.sod >= 1086) | (b.sod < 570))].groupby("nk"); ent["low_night"] = pre.low.min()
    n["ref_close"] = n.rth_close.ffill(); n = n.join(ent, how="inner").dropna(subset=["e1805", "x0945", "ref_close"]); n["year"] = [pd.Timestamp(d).year for d in n.index]
    n["gap"] = n.o1800 / n.ref_close - 1; n["sd20"] = n.gap.rolling(20, min_periods=15).std().shift(1)
    return n

def gate_ov(r, years):
    need = 11 if years >= 14 else int(np.ceil(0.78 * years))
    return bool(r["net"] > 0 and r["nights"] >= (100 if years >= 14 else 50) and r["pos_years"] >= need and (r["max_year_share"] or 1) <= 0.4 and r["max_dd"] < 2000 and r["beat"] >= 190)

me = ns["nights"]("MES"); mn = ns["nights"]("MNQ")
mes_dip = (me.gap <= -0.5 * me.sd20)
out = {}
for inst in ("M2K", "MYM"):
    b = load_1m(inst); n = nights_from_bars(b); years = int(n.year.nunique()); out[inst] = dict(first=str(b.timestamp_utc.min())[:10], years=years, nights_total=int(len(n)))
    print(inst, "bars", len(b), "from", out[inst]["first"], "nights", len(n), "years", years, flush=True)
    p = ns["pnl"](n, inst, ent="e1805", ex="x0945")
    own = (n.gap <= -0.5 * n.sd20).fillna(False); co = own & mes_dip.reindex(n.index).fillna(False)
    for tag, mask in (("T1_own_dip", own), ("T2_co_dip_MES", co)):
        r = ns["evaluate"](n, p, mask, n_plc=200); r.pop("by_year", None); r["pass"] = gate_ov(r, years); out[inst][tag] = r; print(inst, tag, r, flush=True)
    # T3 All-Weather v2 1c sleeves, micro economics, lenient N-minute bars
    def lenient(mins):
        bucket = b.timestamp_utc.dt.floor(f"{mins}min"); grp = b.groupby(bucket)
        f = grp.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum")).reset_index()
        return ep.canonical_bars(f, inst, inst)
    trades = []
    for sl in ep.CANDIDATES["ag_all_weather_v2_1c"]["sleeves"]:
        cfg = dict(sl, instrument=inst); bars = lenient(int(sl["bar_minutes"])); r = ep.run_sleeve(cfg, bars, "2010-01-01T00:00:00Z", backw_mask(bars))
        for t in r["trades"]: t["exit_day"] = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        trades += r["trades"]
    d = ns1["daily"](trades); d.index = pd.to_datetime(d.index); yr = d.groupby(d.index.year).sum(); eq = d.cumsum()
    t3 = dict(net=round(float(d.sum()), 2), trades=len(trades), per=round(float(d.sum() / max(len(trades), 1)), 2), pos_years=int((yr > 0).sum()), years=int(len(yr)),
              max_year_share=round(float(yr.max() / d.sum()), 3) if d.sum() > 0 else None, dd=round(float((eq.cummax() - eq).max()), 2), pre2020=round(float(yr[yr.index < 2020].sum()), 2))
    t3["pass"] = bool(t3["net"] > 0 and t3["pos_years"] >= int(np.ceil(0.64 * t3["years"])) and (t3["max_year_share"] or 1) <= 0.4 and t3["dd"] < 2000 and (t3["pre2020"] > 0 if years >= 14 else True))
    out[inst]["T3_allweather_1c"] = t3; print(inst, "T3", t3, flush=True)
    out[inst]["_t2_daily"] = p[co & p.notna()]
# T4 books: MNQ overnight v2 + each T2 passer
p_mnq = ns["pnl"](mn, "MNQ", ex="x0945"); v2 = ((mn.gap <= -0.5 * mn.sd20) & mes_dip.reindex(mn.index)).fillna(False); d_mnq = p_mnq[v2 & p_mnq.notna()]
def bookstats(d):
    d = d.sort_index(); eq = d.cumsum(); yr = d.groupby([pd.Timestamp(x).year for x in d.index]).sum()
    return dict(net=round(float(d.sum()), 2), dd=round(float((eq.cummax() - eq).max()), 2), pos_years=int((yr > 0).sum()), breach=breach(d))
out["T4_books"] = {"mnq_v2_alone": bookstats(d_mnq)}
for inst in ("M2K", "MYM"):
    q = out[inst].pop("_t2_daily")
    if out[inst]["T2_co_dip_MES"]["pass"]:
        bk = bookstats(d_mnq.add(q, fill_value=0.0)); bk["pass"] = bool(bk["dd"] < 2000 and bk["breach"] <= 0.02); out["T4_books"][f"mnq_v2+{inst}_T2"] = bk; print("T4", inst, bk, flush=True)
Path(ROOT / "reports/M2K_1_TRAINING.json").write_text(json.dumps(out, indent=1, default=str)); print("done")

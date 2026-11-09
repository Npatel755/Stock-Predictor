"""orderflow_1 pilot: MNQ top-of-book imbalance vs forward returns and an 18-config executable rule (research/orderflow_1/PROTOCOL.md).
Usage: orderflow_1_pilot.py data/market/orderflow/MNQ_c0_bbo-1s_2023.parquet
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
TICK, PV = 0.25, 0.5          # MNQ tick size, $ per tick
COMM = 0.61                   # $/side LucidFlex
SLIP_TICKS = 1.0              # ticks against on each fill (on top of crossing the spread)
RT_COST_TICKS = 2 * SLIP_TICKS + 2 * COMM / PV   # excl. spread, which is paid via bid/ask fills: 2 + 2.44 = 4.44 ticks

def load(path):
    d = pd.read_parquet(path)
    for c in ("bid_sz_00", "ask_sz_00", "bid_px_00", "ask_px_00", "size"):
        d[c] = d[c].astype(float)   # uint32 sizes wrap on subtraction
    ts = pd.to_datetime(d.ts_recv, utc=True)
    et = ts.dt.tz_convert("America/New_York")
    d["date"] = et.dt.date
    d["sod"] = et.dt.hour * 3600 + et.dt.minute * 60 + et.dt.second
    d = d[(d.sod >= 9 * 3600 + 30 * 60) & (d.sod < 16 * 3600)].copy()
    d = d[(d.bid_px_00 > 0) & (d.ask_px_00 > 0) & (d.ask_px_00 > d.bid_px_00)]
    d["mid"] = (d.bid_px_00 + d.ask_px_00) / 2
    d["spread_t"] = (d.ask_px_00 - d.bid_px_00) / TICK
    tot = d.bid_sz_00 + d.ask_sz_00
    d["imb"] = (d.bid_sz_00 - d.ask_sz_00) / tot.where(tot > 0)
    d["micro_t"] = ((d.bid_px_00 * d.ask_sz_00 + d.ask_px_00 * d.bid_sz_00) / tot.where(tot > 0) - d.mid) / TICK
    sd = d.side.map({"B": 1, "A": -1}).fillna(0).astype(float)
    g = d.groupby("date", sort=False)
    for w in (5, 30, 60):
        d[f"imb{w}"] = g["imb"].transform(lambda s: s.rolling(w, min_periods=w).mean())
    d["lt60"] = sd.groupby(d.date).transform(lambda s: s.rolling(60, min_periods=10).sum())
    d["mom60_t"] = (d.mid - g["mid"].shift(60)) / TICK
    for h in (10, 60, 300):
        d[f"fwd{h}_t"] = (g["mid"].shift(-h) - d.mid) / TICK
    d["day_id"] = pd.factorize(d.date)[0]
    return d.reset_index(drop=True)

def day_block_t(x, y, day):
    """slope of y on x with day-clustered SE (dependence-aware)."""
    m = np.isfinite(x) & np.isfinite(y)
    x, y, day = x[m], y[m], day[m]
    xc = x - x.mean(); b = (xc * y).sum() / (xc ** 2).sum(); a = y.mean() - b * x.mean()
    e = y - a - b * x
    df = pd.DataFrame({"s": xc * e, "d": day}).groupby("d")["s"].sum()
    se = np.sqrt((df ** 2).sum()) / (xc ** 2).sum()
    return float(b), float(b / se), int(m.sum())

def test1(d):
    out = {}
    rth = d[(d.sod >= 9 * 3600 + 45 * 60) & (d.sod < 15 * 3600 + 45 * 60)]
    for feat in ("imb", "imb5", "imb30", "imb60", "micro_t", "lt60", "mom60_t"):
        for h in (10, 60, 300):
            x, y = rth[feat].to_numpy(float), rth[f"fwd{h}_t"].to_numpy(float)
            b, t, n = day_block_t(x, y, rth.day_id.to_numpy())
            m = np.isfinite(x) & np.isfinite(y)
            dec = pd.qcut(pd.Series(x[m]).rank(method="first"), 10, labels=False)
            means = pd.Series(y[m]).groupby(dec.values).mean()
            out[f"{feat}_h{h}"] = dict(slope=round(b, 4), t_dayblock=round(t, 2), n=n, decile_means_ticks=[round(v, 3) for v in means],
                                       top_minus_bottom_ticks=round(float(means.iloc[-1] - means.iloc[0]), 3), rt_cost_ticks=round(RT_COST_TICKS + 1, 2))
    # time-of-day baseline: R^2 of minute-of-day means
    for h in (10, 60, 300):
        y = rth[f"fwd{h}_t"]; tod = (rth.sod // 60)
        fit = y.groupby(tod).transform("mean")
        out[f"tod_baseline_h{h}_r2"] = round(float(1 - ((y - fit) ** 2).sum() / ((y - y.mean()) ** 2).sum()), 5)
    return out

@njit(cache=True)
def sim(bid, ask, sig, day, sod, hold_s, stop_ticks, s_start, s_end, flat_by):
    n = len(bid); pnl = np.zeros(n); pos = 0; ep = 0.0; em = 0.0; et = 0; eday = -1; trades = 0
    for i in range(n):
        if pos != 0:
            exit_ = False
            if day[i] != eday: exit_ = True              # should not happen (flat_by) but guard
            elif sod[i] >= flat_by: exit_ = True
            elif i - et >= hold_s: exit_ = True
            elif pos > 0 and (em - 0.5 * (bid[i] + ask[i])) / TICK >= stop_ticks: exit_ = True   # adverse mid move from entry mid
            elif pos < 0 and (0.5 * (bid[i] + ask[i]) - em) / TICK >= stop_ticks: exit_ = True
            if exit_:
                px = bid[i] - SLIP_TICKS * TICK if pos > 0 else ask[i] + SLIP_TICKS * TICK
                pnl[i] += pos * (px - ep) / TICK * PV - 2 * COMM
                pos = 0; trades += 1
        if pos == 0 and sig[i] != 0 and sod[i] >= s_start and sod[i] < s_end and i + 1 < n and day[i + 1] == day[i]:
            pos = sig[i]
            ep = ask[i + 1] + SLIP_TICKS * TICK if pos > 0 else bid[i + 1] - SLIP_TICKS * TICK   # fill next second, marketable
            em = 0.5 * (bid[i + 1] + ask[i + 1]); et = i + 1; eday = day[i]
    return pnl, trades

def test2(d, rng, contra=False):
    bid, ask = d.bid_px_00.to_numpy(float), d.ask_px_00.to_numpy(float)
    day, sod = d.day_id.to_numpy(np.int64), d.sod.to_numpy(np.int64)
    months = pd.to_datetime(d.date.astype(str)).dt.month.to_numpy()
    s_start, s_end, flat_by = 9 * 3600 + 45 * 60, 15 * 3600 + 45 * 60, 15 * 3600 + 55 * 60
    imb30 = d.imb30.to_numpy(float)
    res = []
    for q in (0.3, 0.5, 0.7):
        base = np.where(imb30 >= q, 1, np.where(imb30 <= -q, -1, 0)).astype(np.int8)
        if contra: base = -base
        for hold in (60, 180, 300):
            for stop in (2.0, 4.0):
                pnl, tr = sim(bid, ask, base, day, sod, hold, stop, s_start, s_end, flat_by)
                net = float(pnl.sum()); mon = pd.Series(pnl).groupby(months).sum()
                plc = []
                elig = (sod >= s_start) & (sod < s_end)
                for _ in range(20):
                    ps = np.zeros_like(base)
                    for dd in np.unique(day):
                        m = (day == dd)
                        k = int((base[m] != 0).sum())
                        idx = np.flatnonzero(m & elig)
                        if k and len(idx) >= k:
                            pick = rng.choice(idx, size=k, replace=False)
                            ps[pick] = rng.choice(np.array([1, -1], dtype=np.int8), size=k)
                    pp, _ = sim(bid, ask, ps, day, sod, hold, stop, s_start, s_end, flat_by)
                    plc.append(float(pp.sum()))
                plc = np.array(plc)
                res.append(dict(q=q, hold_s=hold, stop_ticks=stop, contra=contra, net=round(net, 2), trades=int(tr),
                                per_trade=round(net / tr, 3) if tr else None, months_pos=int((mon > 0).sum()),
                                monthly=[round(v, 1) for v in mon], placebo_mean=round(plc.mean(), 1), placebo_sd=round(plc.std(), 1),
                                placebo_p=round(float((plc >= net).mean()), 3)))
                print(res[-1]["q"], hold, stop, contra, "net", res[-1]["net"], "tr", tr, "mp", res[-1]["months_pos"], "plc_p", res[-1]["placebo_p"], flush=True)
    return res

if __name__ == "__main__":
    d = load(sys.argv[1])
    info = dict(rows=len(d), days=int(d.day_id.nunique()), spread_1tick_share=round(float((d.spread_t == 1).mean()), 4),
                spread_mean_ticks=round(float(d.spread_t.mean()), 3), bid_sz_med=float(d.bid_sz_00.median()), ask_sz_med=float(d.ask_sz_00.median()),
                side_counts=d.side.value_counts().to_dict())
    print(info, flush=True)
    t1 = test1(d); print(json.dumps({k: v for k, v in t1.items() if "imb30" in k or "tod" in k}, indent=0), flush=True)
    rng = np.random.default_rng(7)
    t2 = test2(d, rng); t3 = test2(d, rng, contra=True)
    out = dict(data=info, test1=t1, test2_with_imbalance=t2, test3_against_imbalance=t3)
    (ROOT / "reports" / "ORDERFLOW_1_PILOT.json").write_text(json.dumps(out, indent=1, default=str))
    print("written reports/ORDERFLOW_1_PILOT.json")

"""orderflow_2 pilot (research/orderflow_2/PROTOCOL.md): signed-volume imbalance from MNQ trades (Apr-Dec 2023) joined to the
BBO-1s quotes; predictive decile test + 58-config executable grid with placebos. Reuses orderflow_1_pilot's loader and simulator."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import orderflow_1_pilot as of1
TICK = of1.TICK; rng = np.random.default_rng(20261109); DELAY = 10; N_PLACEBO = 20
S_START, S_END, FLAT = 9 * 3600 + 45 * 60, 15 * 3600 + 30 * 60, 15 * 3600 + 45 * 60

q = of1.load(str(ROOT / "data/market/orderflow/MNQ_c0_bbo-1s_2023.parquet"))
tr = pd.read_parquet(ROOT / "data/market/orderflow/MNQ_c0_trades_2023-04_2023-12.sec.parquet")
tcol = "ts_recv" if "ts_recv" in q.columns else "ts_event"
q["sec"] = pd.to_datetime(q[tcol], utc=True).dt.floor("1s"); tr["sec"] = tr.ts.dt.floor("1s")
d = q.merge(tr[["sec", "buy_vol", "sell_vol", "none_vol", "big_buy", "big_sell", "n"]], on="sec", how="left").fillna({"buy_vol": 0, "sell_vol": 0, "none_vol": 0, "big_buy": 0, "big_sell": 0, "n": 0})
d = d[d.sec >= pd.Timestamp("2023-04-01", tz="UTC")].reset_index(drop=True)
g = d.groupby("day_id", sort=False)
def rsum(col, w): return g[col].transform(lambda s: s.rolling(w, min_periods=w).sum()).shift(1)  # past-only (ends at previous second)
feats = {}
for w in (60, 300, 900):
    b, s = rsum("buy_vol", w), rsum("sell_vol", w); feats[f"svi{w}"] = ((b - s) / (b + s).where((b + s) > 0)).to_numpy()
b, s = rsum("big_buy", 300), rsum("big_sell", 300); feats["bigimb300"] = ((b - s) / (b + s).where((b + s) > 0)).to_numpy()
cum = (d.buy_vol - d.sell_vol); delta900 = g[cum.name if cum.name else "buy_vol"].transform(lambda s: s) if False else cum.groupby(d.day_id).transform(lambda s: s.rolling(900, min_periods=900).sum()).shift(1)
hi900 = g["mid"].transform(lambda s: s.rolling(900, min_periods=900).max()).shift(1); lo900 = g["mid"].transform(lambda s: s.rolling(900, min_periods=900).min()).shift(1)
div = np.where((d.mid > hi900) & (delta900 <= 0), -1, np.where((d.mid < lo900) & (delta900 >= 0), 1, 0))
d["minute"] = d.sod // 60; bv300 = rsum("buy_vol", 300); sv300 = rsum("sell_vol", 300)
mstat = pd.DataFrame(dict(day=d.day_id, minute=d.minute, bv=bv300, sv=sv300)).groupby(["day", "minute"]).last().reset_index()
for c in ("bv", "sv"):
    piv = mstat.pivot(index="day", columns="minute", values=c); mu = piv.rolling(20, min_periods=20).mean().shift(1); sd = piv.rolling(20, min_periods=20).std().shift(1)
    z = ((piv - mu) / sd).stack().rename(f"z{c}").reset_index(); mstat = mstat.merge(z, on=["day", "minute"], how="left")
d = d.merge(mstat[["day", "minute", "zbv", "zsv"]], left_on=["day_id", "minute"], right_on=["day", "minute"], how="left")
exh = np.where((d.zbv > 2) & (d.mid <= hi900), -1, np.where((d.zsv > 2) & (d.mid >= lo900), 1, 0))
day, sod = d.day_id.to_numpy(np.int64), d.sod.to_numpy(np.int64); bid, ask = d.bid_px_00.to_numpy(float), d.ask_px_00.to_numpy(float)
month = pd.to_datetime(d.sec).dt.month.to_numpy()

out = dict(rows=int(len(d)), sessions=int(d.day_id.nunique()), side_none_share=float(d.none_vol.sum() / max(d[["buy_vol", "sell_vol", "none_vol"]].sum().sum(), 1)), predictive={}, executable=[])
rth = (sod >= S_START) & (sod < S_END)
for name, x in {**feats}.items():
    out["predictive"][name] = {}
    for h in (10, 60, 300):
        y = d[f"fwd{h}_t"].to_numpy(); m = rth & np.isfinite(x) & np.isfinite(y)
        dec = pd.qcut(pd.Series(x[m]), 10, labels=False, duplicates="drop"); means = pd.Series(y[m]).groupby(dec.to_numpy()).mean()
        spread, t, n = of1.day_block_t((dec.to_numpy() == dec.max()).astype(float) - (dec.to_numpy() == 0).astype(float), y[m], day[m])
        rho = float(pd.Series(means.index).corr(pd.Series(means.to_numpy()), method="spearman"))
        out["predictive"][name][f"fwd{h}"] = dict(decile_means_ticks=[round(float(v), 3) for v in means], top_minus_bottom_ticks=round(float(means.iloc[-1] - means.iloc[0]), 3), t=round(t, 2), monotone_rho=round(rho, 2), n=n)
        print(name, h, out["predictive"][name][f"fwd{h}"]["top_minus_bottom_ticks"], "t", round(t, 2), "rho", round(rho, 2), flush=True)

def delayed(sig):
    s = np.zeros_like(sig); s[DELAY:] = sig[:-DELAY]; s[day != np.r_[day[:DELAY], day[:-DELAY]]] = 0; return s
def run(sig, hold, stop=4):
    pnl, ntr = of1.sim(bid, ask, delayed(sig), day, sod, hold, stop, S_START, S_END, FLAT)
    mp = pd.Series(pnl).groupby(month).sum(); return float(pnl.sum()), ntr, {int(k): round(float(v), 2) for k, v in mp.items()}
elig = np.flatnonzero(rth)
def placebo(sig, hold):
    n = int((sig != 0).sum()); p = np.zeros_like(sig); pick = rng.choice(elig, size=min(n, len(elig)), replace=False); p[pick] = rng.choice([-1, 1], size=len(pick)); return run(p, hold)[0]
configs = [(f"svi{w}", qq, mode, hold) for w in (60, 300, 900) for qq in (0.3, 0.5, 0.7) for mode in ("cont", "rev") for hold in (120, 300, 900)]
configs += [("divergence", None, "rev", h) for h in (300, 900)] + [("exhaustion", None, "rev", h) for h in (300, 900)]
for name, qq, mode, hold in configs:
    if name == "divergence": sig = div.astype(np.int8)
    elif name == "exhaustion": sig = exh.astype(np.int8)
    else:
        x = np.nan_to_num(feats[name]); sig = np.where(x >= qq, 1, np.where(x <= -qq, -1, 0)).astype(np.int8)
        if mode == "rev": sig = -sig
    net, ntr, mp = run(sig, hold)
    pl = [placebo(sig, hold) for _ in range(N_PLACEBO)] if ntr >= 50 else []
    rec = dict(feature=name, q=qq, mode=mode, hold_s=hold, net=round(net, 2), trades=ntr, per_trade=round(net / ntr, 2) if ntr else None, months_pos=int(sum(v > 0 for v in mp.values())), monthly=mp,
               placebo_pct=float(np.mean(np.array(pl) < net)) if pl else None, placebo_mean=round(float(np.mean(pl)), 2) if pl else None)
    out["executable"].append(rec); print(rec["feature"], qq, mode, hold, "net", rec["net"], "trades", ntr, "months+", rec["months_pos"], "plc", rec["placebo_pct"], flush=True)
json.dump(out, open(ROOT / "reports/ORDERFLOW_2_PILOT.json", "w"), indent=1)
print("DONE", flush=True)

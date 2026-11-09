"""Replicate Antigravity's 'Architecture C' (Crabel open-drive 10:00 + MNQ 30m morning trend lb16/th0.75 + MNQ 60m trend lb12/th0.75, strict 1c
router Crabel > S2 > S3) on the fixed engine, TRAINING 2010-2023 only (2024-26 already scored by the sender; not loaded here). Micro costs.
Router applied at trade level: a trade is rejected if its decision bar falls while an accepted higher/earlier trade is open."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
START = "2010-01-01T00:00:00Z"
def crabel_signal(cfg, bars):
    et = bars.timestamp_utc.dt.tz_convert("America/New_York"); sod = (et.dt.hour * 60 + et.dt.minute).to_numpy(); day = et.dt.date.to_numpy()
    o, h, l, c = (bars[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close")); prev = np.roll(c, 1); prev[0] = c[0]
    atr = pd.Series(np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))).rolling(14, min_periods=14).mean().bfill().to_numpy()
    df = pd.DataFrame(dict(day=day, sod=sod, o=o, h=h, l=l, c=c)); r = df[df.sod.isin([570, 585])].groupby("day")
    o930 = df[df.sod == 570].groupby("day").o.first(); c1000 = df[df.sod == 585].groupby("day").c.first(); hi, lo = r.h.max(), r.l.min()
    rng_ = (hi - lo).replace(0, np.nan); op = (o930 - lo) / rng_; cp = (c1000 - lo) / rng_
    sig_day = pd.Series(np.where((op <= 0.2) & (cp >= 0.8), 1, np.where((op >= 0.8) & (cp <= 0.2), -1, 0)), index=op.index)
    sig = np.where(sod == 585, pd.Series(day).map(sig_day).fillna(0).to_numpy(), 0).astype(np.int8)  # placed on the 09:45 bar (close = 10:00) -> fill at the 10:00 open
    return sig, atr.astype(np.float32)
def trend_signal(cfg, bars):
    c, h, l = bars.close.astype(float), bars.high.to_numpy(float), bars.low.to_numpy(float); prev = np.r_[c.to_numpy()[0], c.to_numpy()[:-1]]
    atr = pd.Series(np.maximum(h - l, np.maximum(abs(h - prev), abs(l - prev)))).rolling(14, min_periods=14).mean().to_numpy()
    lb = int(cfg["lookback"]); z = ((c.ewm(span=lb // 2, adjust=False).mean() - c.ewm(span=lb, adjust=False).mean()).to_numpy() / atr)
    sig = np.where(np.abs(z) >= cfg["threshold"], np.sign(z), 0); return np.nan_to_num(sig).astype(np.int8), np.nan_to_num(atr).astype(np.float32)
def dispatch(cfg, bars): return crabel_signal(cfg, bars) if cfg["signal"] == "crabel" else trend_signal(cfg, bars)
ep.custom_signal = dispatch
B15 = m1.load_bars("MNQ", 15, "2009-11-01", "2024-01-01", "train").reset_index(drop=True); assert B15.timestamp_utc.max() < pd.Timestamp("2024-01-02", tz="UTC")
B30 = m1.load_bars("MNQ", 30, "2009-11-01", "2024-01-01", "train").reset_index(drop=True); B60 = m1.load_bars("MNQ", 60, "2009-11-01", "2024-01-01", "train").reset_index(drop=True)
S = {
 "S1_crabel": (dict(name="S1_crabel", instrument="MNQ", family="trend", lookback=8, threshold=0.0, stop_atr=2.0, target_r=4.0, hold_bars=12, trailing_atr=0.0, max_contracts=1,
                    session_start=600, session_end=945, signal="crabel", entry_start=585, entry_end=585, max_gap_minutes=20), B15, 15),
 "S2_trend30": (dict(name="S2_trend30", instrument="MNQ", family="trend", lookback=16, threshold=0.75, stop_atr=1.5, target_r=3.5, hold_bars=8, trailing_atr=0.0, max_contracts=1,
                     session_start=585, session_end=720, signal="trend", entry_start=555, entry_end=690, max_gap_minutes=60), B30, 30),
 "S3_trend60": (dict(name="S3_trend60", instrument="MNQ", family="trend", lookback=12, threshold=0.75, stop_atr=1.25, target_r=4.0, hold_bars=8, trailing_atr=0.0, max_contracts=1,
                     session_start=600, session_end=720, signal="trend", entry_start=540, entry_end=660, max_gap_minutes=90), B60, 60),
}
def yearly(trades):
    if not trades: return {}
    t = pd.DataFrame(trades); t["year"] = pd.to_datetime(t.entry_ts).dt.year; return {int(y): round(float(v), 2) for y, v in t.groupby("year").net.sum().items()}
def summary(trades):
    yr = yearly(trades); net = sum(yr.values()); t = pd.DataFrame(trades) if trades else pd.DataFrame(columns=["net", "entry_ts"])
    eq = t.sort_values("entry_ts").net.cumsum() if len(t) else pd.Series(dtype=float); dd = float((eq.cummax() - eq).max()) if len(eq) else 0.0
    return dict(net=round(net, 2), trades=len(trades), per_trade=round(net / max(1, len(trades)), 2), pos_years=int(sum(v > 0 for v in yr.values())), pre2020=round(sum(v for y, v in yr.items() if y < 2020), 2),
                max_year_share=round(max(yr.values()) / net, 3) if net > 0 else None, closed_dd=round(dd, 2), by_year=yr)
out = {}; all_tr = []
for name, (cfg, bars, mins) in S.items():
    r = ep.run_sleeve(cfg, bars, START); tr = r["trades"]
    for x in tr: x["sleeve"] = name; x["prio"] = list(S).index(name); x["dec"] = pd.Timestamp(x["entry_ts"]) - pd.Timedelta(minutes=mins)
    out[name] = summary(tr); print(name, {k: v for k, v in out[name].items() if k != "by_year"}, flush=True); all_tr += tr
all_tr.sort(key=lambda x: (x["dec"], x["prio"])); acc = []
for x in all_tr:
    if any(pd.Timestamp(a["entry_ts"]) <= x["dec"] < pd.Timestamp(a["exit_ts"]) for a in acc[-5:]): continue
    acc.append(x)
out["ARCH_C_routed"] = summary(acc); print("ARCH_C_routed", out["ARCH_C_routed"], flush=True)
out["sender_claim_2010_23"] = dict(net=14396.72, trades=1524, pre2020=3691.72, pos_years_2010_19=6, note="from reports/ARCHITECTURE_C_ALL_SPLITS.json (net_pre + net_post); 2024-26 also scored by sender")
for x in acc: x.pop("dec", None)
json.dump(out, open(ROOT / "reports/ANTIGRAVITY_ARCH_C_REPLICATION.json", "w"), indent=1, default=str); print("DONE")

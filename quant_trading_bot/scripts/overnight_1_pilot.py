"""overnight_1 (research/overnight_1/PROTOCOL.md): Globex overnight hold 18:05 ET open -> next 09:30 ET open, training 2010-2023. 1-min bars."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1
SPEC = dict(MNQ=dict(tick=0.25, tv=0.5, spread=1.75), MES=dict(tick=0.25, tv=1.25, spread=1.0)); COMM, SLIP = 0.61, 1
def cboe(n):
    d = pd.read_csv(ROOT / f"data/external/{n}_History.csv"); d["date"] = pd.to_datetime(d.DATE, format="%m/%d/%Y").dt.date; return d.set_index("date").CLOSE.astype(float)
ratio = (cboe("VIX") / cboe("VIX3M")).dropna()
def nights(prod):
    b = m1.load_bars(prod, 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "close", "high", "low"]]
    et = pd.to_datetime(b.timestamp_utc, utc=True).dt.tz_convert("America/New_York"); b["sod"] = et.dt.hour * 60 + et.dt.minute; b["date"] = et.dt.date; b["dow"] = et.dt.dayofweek
    rth_close = b[b.sod == 959].groupby("date").close.last(); rth_open = b[b.sod == 570].groupby("date").open.first()
    ent = b[b.sod == 1085].groupby("date").open.first()           # 18:05 ET bar open (first completed bar after 18:00 reopen)
    nxt_open = rth_open.shift(-1); nxt_c0935 = b[b.sod == 935 + 0].groupby("date").close.last().shift(-1)  # placeholder, replaced below
    c0935 = b[b.sod == 575].groupby("date").close.last().shift(-1)  # 09:35 ET close next day
    night = pd.DataFrame(dict(ent=ent, exit_open=nxt_open, exit_0935=c0935, rth_close=rth_close, rth_open=rth_open, dow=b.groupby("date").dow.first())).dropna(subset=["ent", "exit_open"])
    # overnight low for the stop variant: min low between 18:05 and 09:30 next day
    b["night_key"] = np.where(b.sod >= 1080, b.date, pd.Series(b.date).shift(1).where(False, b.date))  # simple: minutes >= 18:00 belong to that date's night; early minutes (< 9:30) belong to previous date
    prev_date = pd.Series(b.date).shift(1); key = pd.Series(b.date.values, index=b.index).where(b.sod >= 1080, np.nan)
    dates_sorted = sorted(set(b.date)); d2prev = {d: p for p, d in zip(dates_sorted[:-1], dates_sorted[1:])}
    key = key.where(key.notna(), pd.Series(b.date).map(d2prev).where(b.sod < 570, np.nan)); b["nk"] = key
    low_night = b.dropna(subset=["nk"]).groupby("nk").low.min(); night["low_night"] = low_night.reindex(night.index)
    night["idx_dates"] = night.index; night["year"] = pd.to_datetime(pd.Series(night.index, index=night.index)).dt.year
    night["rth_ret"] = night.rth_close / night.rth_open - 1; night["reopen_gap"] = night.ent / night.rth_close - 1
    night["ratio_prev"] = pd.Series(night.index, index=night.index).map(ratio)   # prior close (same date) VIX/VIX3M known at 18:00
    return night
def pnl(night, prod, side=1, exit_col="exit_open", stop=False):
    s = SPEC[prod]; move = side * (night[exit_col] - night.ent)
    if stop:
        sd = (night.exit_open - night.ent).rolling(20, min_periods=15).std().shift(1); hit = (night.ent - night.low_night) > 2 * sd
        move = np.where(hit & (side == 1), -2 * sd, move)
    cost = (s["spread"] + 2 * SLIP) * s["tv"] + 2 * COMM
    return pd.Series(np.asarray(move) / s["tick"] * s["tv"] - cost, index=night.index)
def gate(p, years, n_plc_beat=None, n_plc=None):
    yr = p.groupby(years).sum(); t = float(p.sum()); rec = dict(net=round(t, 2), nights=int(len(p)), per_night=round(t / len(p), 2) if len(p) else None, pos_years=int((yr > 0).sum()), years=int(len(yr)),
        pre2020=round(float(yr[yr.index < 2020].sum()), 2), max_year_share=round(float(yr.max() / t), 3) if t > 0 else None, by_year={int(y): round(float(v), 2) for y, v in yr.items()})
    if n_plc is not None: rec.update(beat=n_plc_beat, n_plc=n_plc)
    rec["pass"] = bool(t > 0 and rec["pos_years"] >= 10 and len(p) >= 100 and (rec["max_year_share"] or 1) <= 0.4 and (n_plc is None or n_plc_beat >= 0.95 * n_plc)); return rec
rng = np.random.default_rng(31); out = {}
N = {p: nights(p) for p in ("MNQ", "MES")}
def filtered(name, prod, mask, side=1):
    n = N[prod]; p = pnl(n, prod, side)[mask]; yrs = n.year[mask]
    cnt = yrs.groupby(yrs).size(); plc = []
    for _ in range(200):
        pick = np.concatenate([rng.choice(n.index[n.year == y], size=min(int(c), int((n.year == y).sum())), replace=False) for y, c in cnt.items()])
        plc.append(float(pnl(n, prod, side).loc[pick].sum()))
    rec = gate(p, yrs, int(sum(p.sum() > x for x in plc)), 200); rec["placebo_mean"] = round(float(np.mean(plc)), 2); out[name] = rec; print(name, {k: v for k, v in rec.items() if k != "by_year"}, flush=True)
for prod in ("MNQ", "MES"):
    n = N[prod]; allm = pd.Series(True, index=n.index)
    out[f"V1_long_all_{prod}"] = gate(pnl(n, prod), n.year); print(f"V1_long_all_{prod}", {k: v for k, v in out[f"V1_long_all_{prod}"].items() if k != "by_year"}, flush=True)
    gross = (n.exit_open - n.ent) / SPEC[prod]["tick"] * SPEC[prod]["tv"]; out[f"V1_gross_{prod}"] = dict(gross_total=round(float(gross.sum()), 2), per_night_ticks=round(float(((n.exit_open - n.ent) / SPEC[prod]["tick"]).mean()), 2), t=round(float(gross.mean() / gross.std() * np.sqrt(len(gross))), 2))
    print(f"V1_gross_{prod}", out[f"V1_gross_{prod}"], flush=True)
    out[f"V13_short_all_{prod}"] = gate(pnl(n, prod, -1), n.year)
    out[f"V12_exit0935_{prod}"] = gate(pnl(n, prod, 1, "exit_0935"), n.year)
    out[f"V11_stop_{prod}"] = gate(pnl(n, prod, 1, "exit_open", True), n.year)
    filtered(f"V3_sunday_{prod}", prod, n.dow == 6); filtered(f"V4_mon_thu_{prod}", prod, n.dow <= 3)
    filtered(f"V5_after_down_day_{prod}", prod, n.rth_ret < 0); filtered(f"V6_after_up_day_{prod}", prod, n.rth_ret > 0)
    filtered(f"V7_contango_{prod}", prod, n.ratio_prev < 1); filtered(f"V8_backwardation_{prod}", prod, n.ratio_prev > 1)
    filtered(f"V9_reopen_dip_{prod}", prod, n.reopen_gap < 0); filtered(f"V14_stress_day_{prod}", prod, n.rth_ret < -0.01)
json.dump(out, open(ROOT / "reports/OVERNIGHT_1_TRAINING.json", "w"), indent=1, default=float); print("PASSERS", [k for k, v in out.items() if isinstance(v, dict) and v.get("pass")]); print("DONE")

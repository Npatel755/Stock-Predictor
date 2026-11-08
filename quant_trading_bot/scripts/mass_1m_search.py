"""mass_1m: 1-minute counter-trend search (research/mass_1m/PROTOCOL.md). Reuses the mass_v2 pipeline
(engine, gates, placebo, deflation, freeze) with 1/3/5-minute bars and six fade families."""
import itertools, json, os, sys, hashlib
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_v2_search as m  # noqa: E402
import unseen_years_replication as uy  # noqa: E402
from quant_futures import ensemble_paper as ep  # noqa: E402
from quant_futures.data import canonical  # noqa: E402
from quant_futures.session_calendar import apply_early_close  # noqa: E402

RUN = ROOT / "runs" / "mass_1m"; RUN.mkdir(parents=True, exist_ok=True)
m.RUN, m.SUFFIX = RUN, "_1m"
m.DB = RUN / "results_1m.sqlite"; m.FROZEN = RUN / "frozen_survivors_1m.json"
m.YEARS = list(range(2010, 2024))
PRODUCTS = ("MES", "MNQ"); MINI_OF = {"MES": "ES", "MNQ": "NQ"}
RES = (1, 3, 5)
FAMILIES = ("vwap_snapback", "volume_exhaustion", "orb_fade", "rsi_extreme", "keltner_fade", "stretch_fade")
LOOKBACKS = (10, 20, 30, 60); ORB_MINUTES = (15, 30, 60)
THRESHOLDS = (1.0, 1.5, 2.0, 3.0)
SESSIONS = ((585, 690), (600, 720), (720, 870), (840, 945), (585, 945))
STOP_ATR = (1.0, 2.0, 3.0); TARGET_R = (0.5, 1.0, 2.0); HOLD_MIN = (15, 30, 60, 120); TRAIL = (0.0, 2.0)
m.EXITS = list(itertools.product(STOP_ATR, TARGET_R, HOLD_MIN, TRAIL))
for p in PRODUCTS:
    for r in RES:
        m.MICRO[f"{p}@{r}"] = p
m.N_TRIALS = len(PRODUCTS) * len(RES) * ((len(FAMILIES) - 1) * len(LOOKBACKS) + len(ORB_MINUTES)) * len(THRESHOLDS) * len(SESSIONS) * len(m.EXITS)
CAT = json.load(open(uy.CATALOG))["instruments"]


def units():
    for p in PRODUCTS:
        for r in RES:
            for fam in FAMILIES:
                lbs = ORB_MINUTES if fam == "orb_fade" else LOOKBACKS
                for lb in lbs:
                    for th in THRESHOLDS:
                        for s0, s1 in SESSIONS:
                            yield (f"{p}@{r}", f"{fam}_r{r}", lb, th, s0, s1)


def unit_key(u):
    return "|".join(str(x) for x in u)


def load_bars(product, res, start, end, split):
    """1-minute Databento bars aggregated to `res` minutes (lenient), canonicalised."""
    frames = []
    for sym, lo, hi in ((MINI_OF[product], start, min(end, "2019-01-01")), (product, max(start, "2019-01-01"), end)) if split == "train" else ((product, start, end),):
        if lo >= hi:
            continue
        path = str(CAT[sym]["splits"][split]["path"])
        con = duckdb.connect()
        q = f"""SELECT time_bucket(INTERVAL '{res} minutes', timestamp_utc::TIMESTAMPTZ) AS timestamp_utc,
                 arg_min(open, timestamp_utc) AS open, max(high) AS high, min(low) AS low, arg_max(close, timestamp_utc) AS close,
                 sum(volume) AS volume, arg_min(contract, timestamp_utc) AS contract, arg_min(session_id, timestamp_utc) AS session_id
                 FROM read_parquet('{path}') WHERE timestamp_utc >= '{lo}' AND timestamp_utc < '{hi}' GROUP BY 1 ORDER BY 1"""
        f = con.execute(q).fetch_df(); con.close()
        f["instrument"] = product
        frames.append(f)
    f = pd.concat(frames, ignore_index=True)
    f = f[f.timestamp_utc.notna()].copy()
    f["timestamp_utc"] = pd.to_datetime(f.timestamp_utc, utc=True)
    for c in ("open", "high", "low", "close"):
        f[c] = f[c].astype(float)
    f["high"] = f[["open", "high", "low", "close"]].max(axis=1); f["low"] = f[["open", "high", "low", "close"]].min(axis=1)
    f["volume"] = f.volume.astype(float).round()
    return canonical(f)


def base_features(bars, res):
    """Resolution-level features: 30-minute ATR, RTH VWAP, opening ranges, ET minute."""
    c, h, l, o, v = (bars[k].to_numpy(float) for k in ("close", "high", "low", "open", "volume"))
    prev = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - prev), abs(l - prev)))
    n = max(2, 30 // res)
    atr = pd.Series(tr).rolling(n, min_periods=n).mean().to_numpy(np.float32)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    minute = (local.dt.hour * 60 + local.dt.minute).to_numpy()
    sess = pd.factorize(bars.session_id.astype(str), sort=False)[0]
    rth = minute >= 570
    tp = (h + l + c) / 3.0
    df = pd.DataFrame(dict(s=sess, pv=np.where(rth, tp * v, 0.0), vv=np.where(rth, v, 0.0), h=np.where(rth, h, np.nan), l=np.where(rth, l, np.nan), minute=minute))
    g = df.groupby("s", sort=False)
    cpv, cvv = g.pv.cumsum().to_numpy(), g.vv.cumsum().to_numpy()
    vwap = np.where(rth & (cvv > 0), cpv / np.where(cvv > 0, cvv, 1.0), np.nan).astype(np.float32)
    orb = {}
    for mins in ORB_MINUTES:
        inrange = rth & (minute < 570 + mins)
        hh = pd.Series(np.where(inrange, h, -np.inf)).groupby(sess).cummax().to_numpy()
        ll = pd.Series(np.where(inrange, l, np.inf)).groupby(sess).cummin().to_numpy()
        formed = rth & (minute >= 570 + mins) & np.isfinite(hh) & np.isfinite(ll)
        orb[mins] = (np.where(formed, hh, np.nan).astype(np.float32), np.where(formed, ll, np.nan).astype(np.float32))
    return dict(atr=atr, vwap=vwap, orb=orb, minute=minute, c=c.astype(np.float32), o=o.astype(np.float32), h=h.astype(np.float32),
                l=l.astype(np.float32), v=v.astype(np.float32))


def lb_features(bf, lb):
    c, v = pd.Series(bf["c"].astype(float)), pd.Series(bf["v"].astype(float))
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1 / lb, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / lb, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy(np.float32)
    return dict(atr=bf["atr"], ema=c.ewm(span=lb, adjust=False).mean().to_numpy(np.float32), rsi=rsi,
                volmed=v.rolling(lb, min_periods=lb).median().to_numpy(np.float32), move=(c - c.shift(lb)).to_numpy(np.float32))


def signal(fam, bf, f, th):
    c, o, h, l, v, atr = bf["c"], bf["o"], bf["h"], bf["l"], bf["v"], bf["atr"]
    prevc = np.r_[c[0], c[:-1]]
    up_bar, dn_bar = c > o, c < o
    if fam == "vwap_snapback":
        st = (c - bf["vwap"]) / atr
        lng, sht = (st <= -th) & up_bar, (st >= th) & dn_bar
    elif fam == "volume_exhaustion":
        climax = v >= th * f["volmed"]; mv = f["move"] / atr; rng = np.where(h > l, h - l, np.nan); pos = (c - l) / rng
        sht = climax & (mv >= 1.0) & (pos >= 0.75); lng = climax & (mv <= -1.0) & (pos <= 0.25)
    elif fam == "orb_fade":
        hi, lo = bf["orb"][f["lb"]]; prevhi, prevlo = np.r_[np.nan, hi[:-1]], np.r_[np.nan, lo[:-1]]
        sht = (prevc > prevhi + th * 0.5 * atr) & (c <= hi); lng = (prevc < prevlo - th * 0.5 * atr) & (c >= lo)
    elif fam == "rsi_extreme":
        lng, sht = f["rsi"] <= 50 - 10 * th, f["rsi"] >= 50 + 10 * th
    elif fam == "keltner_fade":
        upb, lob = f["ema"] + th * atr, f["ema"] - th * atr; pu, pl = np.r_[np.nan, upb[:-1]], np.r_[np.nan, lob[:-1]]
        sht = (prevc > pu) & (c <= upb); lng = (prevc < pl) & (c >= lob)
    elif fam == "stretch_fade":
        mv = f["move"] / atr
        sht, lng = (mv >= th) & dn_bar, (mv <= -th) & up_bar
    else:
        raise ValueError(fam)
    out = np.zeros(len(c), dtype=np.int8); out[np.nan_to_num(lng)] = 1; out[np.nan_to_num(sht)] = -1
    return out


def build_state(product, res, bars):
    eng = ep.engine()
    data = apply_early_close(eng["arrays"](bars), bars)
    bf = base_features(bars, res)
    feats = {lb: dict(lb_features(bf, lb), lb=lb) for lb in LOOKBACKS}
    for mins in ORB_MINUTES:
        feats.setdefault(mins, dict(atr=bf["atr"], lb=mins))
        feats[mins]["lb"] = mins if mins in ORB_MINUTES else feats[mins]["lb"]
    decision = bf["minute"] + res
    weekday = bars.timestamp_utc.dt.tz_convert("America/New_York").dt.day_of_week.to_numpy() < 5
    slices = {}
    for y in range(2010, 2027):
        idx = np.flatnonzero(data["year"] == y)
        if len(idx):
            slices[y] = (int(idx[0]), int(idx[-1]) + 1)
    return dict(bars=bars, data=data, bf=bf, feats=feats, decision=decision, weekday=weekday, slices=slices, eng=eng)


def load_training():
    for p in PRODUCTS:
        for r in RES:
            bars = load_bars(p, r, "2009-12-01", "2024-01-01", "train")
            m.STATE[f"{p}@{r}"] = build_state(p, r, bars)
            print(f"{p}@{r} loaded {len(bars)} bars, years {sorted(m.STATE[f'{p}@{r}']['slices'])[0]}-{sorted(m.STATE[f'{p}@{r}']['slices'])[-1]}", flush=True)


def masked(mini, fam, lb, th, s0, s1):
    st = m.STATE[mini]
    base = fam.rsplit("_r", 1)[0]
    f = st["feats"][lb]
    raw = signal(base, st["bf"], f, th)
    valid = (st["decision"] >= s0) & (st["decision"] < s1) & st["weekday"]
    return np.where(valid, raw, 0).astype(np.int8), valid


def work_unit(u):
    mini, fam, lb, th, s0, s1 = u
    res = int(mini.split("@")[1])
    sig, _ = masked(mini, fam, lb, th, s0, s1)
    atr = m.STATE[mini]["feats"][lb]["atr"].astype(np.float64)
    rows = []
    for stop, tr, hold_min, trail in m.EXITS:
        p = dict(instrument=m.MICRO[mini], family=fam, lookback=lb, threshold=th, stop_atr=stop, target_r=tr, hold_bars=max(1, hold_min // res),
                 session_start=s0, session_end=s1, max_contracts=1, trailing_atr=trail)
        mm = m.run_config(mini, sig, atr, p)
        rows.append((m.config_id(p), m.MICRO[mini], fam, lb, th, s0, s1, stop, tr, p["hold_bars"], trail, mm["net"], mm["years_pos"], mm["worst_dd"],
                     mm["trades"], mm["per_trade"], mm["top_year_share"], json.dumps(mm["annual"]), json.dumps(mm["annual_dd"]), mm["fp"], int(m.gate123(mm))))
    return unit_key(u), rows


def mini_of_row(r):
    return f"{r['instrument']}@{r['family'].rsplit('_r', 1)[1]}"


def phase_placebo():
    con = m.db()
    surv = pd.read_sql("SELECT * FROM results WHERE g123=1", con)
    print(f"{con.execute('SELECT COUNT(*) FROM results').fetchone()[0]} configs scored, {len(surv)} pass G1-G3", flush=True)
    sharpes = pd.read_sql("SELECT annual FROM results", con).annual.map(lambda s: m._ann_sharpe(json.loads(s))).to_numpy()
    load_training()
    rng = np.random.default_rng(20261109); out = []
    for _, r in surv.iterrows():
        mini = mini_of_row(r); p = m.row_params(r)
        sig, valid = masked(mini, p["family"], p["lookback"], p["threshold"], p["session_start"], p["session_end"])
        atr = m.STATE[mini]["feats"][p["lookback"]]["atr"].astype(np.float64)
        perms = [m.run_config(mini, m.permuted_signal(sig, valid, mini, rng), atr, p)["per_trade"] for _ in range(m.PLACEBO_PERMS)]
        gross = m.run_config(mini, sig, atr, p, gross=True)
        dsr, sr = m.deflated_sharpe(json.loads(r["annual"]), sharpes)
        p95 = float(np.percentile(perms, 95))
        payload = dict(params=p, per_trade=r["per_trade"], placebo_p95=p95, placebo_mean=float(np.mean(perms)), g4=bool(r["per_trade"] > p95),
                       gross_net=gross["net"], gross_years_pos=gross["years_pos"], dsr=dsr, annual_sharpe=sr, g5=bool(dsr is not None and dsr > 0.95),
                       net=r["net"], years_pos=int(r["years_pos"]), worst_dd=r["worst_dd"], trades=int(r["trades"]), fp=r["fp"], annual=json.loads(r["annual"]))
        con.execute("INSERT OR REPLACE INTO placebo VALUES (?,?)", (r["config_id"], json.dumps(payload))); con.commit()
        out.append((r["config_id"], payload))
        print(r["config_id"], p["instrument"], p["family"], "g4", payload["g4"], "dsr", None if dsr is None else round(dsr, 3), flush=True)
    m.freeze(out); con.close()


def phase_validate():
    frozen = json.loads(m.FROZEN.read_text())["frozen"]
    guard = RUN / "validation_done_1m.json"
    if guard.exists():
        raise SystemExit("validation already run once; refusing to re-run (protocol)")
    out, cache = [], {}
    for fz in frozen:
        p = fz["params"]; res = int(p["family"].rsplit("_r", 1)[1]); key = (p["instrument"], res)
        if key not in cache:
            bars = load_bars(p["instrument"], res, "2023-12-01", "2026-01-01", "validation")
            assert bars.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC")
            cache[key] = build_state(p["instrument"], res, bars)
        st = cache[key]; m.STATE[f"val@{key}"] = st
        sig, _ = masked(f"val@{key}", p["family"], p["lookback"], p["threshold"], p["session_start"], p["session_end"])
        atr = st["feats"][p["lookback"]]["atr"].astype(np.float64); r_ = {}
        for y in (2024, 2025):
            a, b = st["slices"][y]
            d = {k: np.ascontiguousarray(v[a:b]) for k, v in st["data"].items()}
            d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
            r = st["eng"]["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(atr[a:b]), st["eng"]["execution_cfg"](p))
            peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
            r_[y] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), dd=round(float(np.max(peaks - r["worst"])), 2), trades=int(len(r["trade_net"])), breach=bool(r["funded_failed"]))
        vnet = r_[2024]["net"] + r_[2025]["net"]; vtr = r_[2024]["trades"] + r_[2025]["trades"]
        holds = (vnet > 0 and r_[2024]["net"] >= -300 and r_[2025]["net"] >= -300 and not (r_[2024]["breach"] or r_[2025]["breach"]) and vtr > 0 and vnet / vtr >= 0.5 * fz["per_trade"])
        out.append(dict(config_id=fz["config_id"], params=p, train_net=fz["net"], train_per_trade=fz["per_trade"], validation=r_, val_net=round(vnet, 2), val_trades=vtr, holds=bool(holds)))
        print(fz["config_id"], p["instrument"], p["family"], r_, "HOLDS" if holds else "fails", flush=True)
    guard.write_text(json.dumps(dict(run_at=pd.Timestamp.now('UTC').isoformat(), results=out), indent=1))
    lines = ["# mass_1m validation (MES/MNQ 2024-2025, run once on the frozen list)\n", "| id | rule | train net 14y | 2024 net / DD | 2025 net / DD | val trades | holds |", "|---|---|---:|---:|---:|---:|---|"]
    for o in out:
        p = o["params"]; v = o["validation"]
        rule = f"{p['instrument']} {p['family']} lb{p['lookback']} th{p['threshold']} {p['session_start']}-{p['session_end']} stop{p['stop_atr']} tgt{p['target_r']} hold{p['hold_bars']} trail{p['trailing_atr']}"
        lines.append(f"| {o['config_id']} | {rule} | {o['train_net']:,.0f} | {v[2024]['net']:,.0f} / {v[2024]['dd']:,.0f} | {v[2025]['net']:,.0f} / {v[2025]['dd']:,.0f} | {o['val_trades']} | {'yes' if o['holds'] else 'no'} |")
    lines.append(f"\n{sum(o['holds'] for o in out)} of {len(out)} frozen survivors hold on validation.")
    (ROOT / "reports" / "MASS_1M_VALIDATION.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))


m.units, m.unit_key, m.load_training, m.masked, m.work_unit = units, unit_key, load_training, masked, work_unit

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("phase", choices=("search", "placebo", "report", "validate"))
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() - 1)); ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.phase == "search":
        m.phase_search(a.workers, a.limit)
    elif a.phase == "placebo":
        phase_placebo()
    elif a.phase == "report":
        m.phase_report()
    else:
        phase_validate()

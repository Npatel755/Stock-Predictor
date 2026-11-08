"""mass_v2: exhaustive 1.2M-configuration search on ES/NQ 2010-2023 (TRAIN partition only) under MES/MNQ economics.

Protocol: research/mass_v2/PROTOCOL.md (registered 2026-11-08 before any run). Phases:
  search    enumerate the full grid, 1 contract, annual $50k accounts 2010..2023, checkpointed in runs/mass_v2/results.sqlite
  placebo   G4 signal-time permutations + restated-friction variant for G1-G3 survivors, behavioural dedup, DSR, freeze list
  report    reports/MASS_V2_TRAINING.{json,md}
  validate  frozen survivors once on MES/MNQ 2024-2025 (validation partition); 2026 is never loaded
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import sqlite3
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import unseen_years_replication as uy  # noqa: E402  (strict loader from the TRAIN partition, mini->micro relabel)
from quant_futures import ensemble_paper as ep  # noqa: E402
from quant_futures.session_calendar import apply_early_close  # noqa: E402  (amendment A2)

RUN = ROOT / "runs" / "mass_v2"
RUN.mkdir(parents=True, exist_ok=True)
BAR_RULE = os.environ.get("MASS_V2_BARS", "strict")  # strict = all 15 source minutes; lenient = >= 1 (amendment A1)
SUFFIX = ("" if BAR_RULE == "strict" else "_" + BAR_RULE) + os.environ.get("MASS_V2_TAG", "")  # A2 runs use MASS_V2_TAG=_a2
DB = RUN / f"results{SUFFIX}.sqlite"
FROZEN = RUN / f"frozen_survivors{SUFFIX}.json"
YEARS = list(range(2010, 2024))
MINIS = ("ES", "NQ")
MICRO = {"ES": "MES", "NQ": "MNQ"}
FAMILIES = ("trend", "momentum", "mean_reversion", "breakout", "vwap", "opening_range", "regime", "volatility", "volume", "hybrid")
LOOKBACKS = (8, 12, 16, 24, 32, 48, 64, 96)
OPENING_LOOKBACKS = (15, 30, 45, 60, 75, 90, 105, 120)
THRESHOLDS = {
    "trend": (0.1, 0.25, 0.5, 0.75, 1.0), "momentum": (0.25, 0.5, 0.75, 1.0, 1.5), "mean_reversion": (0.5, 1.0, 1.5, 2.0, 2.5),
    "breakout": (0.0, 0.1, 0.25, 0.5, 0.75), "vwap": (0.5, 1.0, 1.5, 2.0, 2.5), "opening_range": (0.1, 0.25, 0.5, 0.75, 1.0),
    "regime": (0.25, 0.5, 0.75, 1.0, 1.5), "volatility": (0.5, 1.0, 1.5, 2.0, 2.5), "volume": (1.0, 1.25, 1.5, 1.75, 2.0),
    "hybrid": (0.25, 0.5, 0.75, 1.0, 1.5)}
SESSIONS = ((585, 690), (600, 720), (720, 870), (840, 945), (585, 945))
STOP_ATR = (1.0, 1.5, 2.0, 3.0)
TARGET_R = (1.0, 1.5, 2.0, 3.0, 4.0)
HOLD_BARS = (2, 4, 8, 12, 16)
TRAILING_ATR = (0.0, 1.0, 2.0)
EXITS = list(itertools.product(STOP_ATR, TARGET_R, HOLD_BARS, TRAILING_ATR))
N_TRIALS = 2 * 10 * 8 * 5 * 5 * len(EXITS)
PLACEBO_PERMS = 20
MAX_FROZEN = 20

STATE: dict = {}


def config_id(p):
    key = json.dumps({k: p[k] for k in sorted(p)}, sort_keys=True)
    return "v2_" + hashlib.sha1(key.encode()).hexdigest()[:16]


def units():
    for mini in MINIS:
        for fam in FAMILIES:
            for lb in (OPENING_LOOKBACKS if fam == "opening_range" else LOOKBACKS):
                for th in THRESHOLDS[fam]:
                    for s in SESSIONS:
                        yield (mini, fam, lb, th, s[0], s[1])


def unit_key(u):
    return "|".join(str(x) for x in u)


def load_training():
    eng = ep.engine()
    for mini in MINIS:
        bars = uy.load(mini, "2009-12-01", "2024-01-01", BAR_RULE)
        data = apply_early_close(eng["arrays"](bars), bars)
        feats = {lb: eng["features"](bars, lb) for lb in set(LOOKBACKS) | set(OPENING_LOOKBACKS)}
        local = bars.timestamp_utc.dt.tz_convert("America/New_York")
        decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
        weekday = local.dt.day_of_week.to_numpy() < 5
        year = data["year"]
        slices = {}
        for y in YEARS:
            idx = np.flatnonzero(year == y)
            if len(idx):
                slices[y] = (int(idx[0]), int(idx[-1]) + 1)
        STATE[mini] = dict(bars=bars, data=data, feats=feats, decision=decision, weekday=weekday, slices=slices, eng=eng)
        print(mini, "loaded", len(bars), "bars,", len(slices), "years", flush=True)


def masked(mini, fam, lb, th, s0, s1):
    st = STATE[mini]
    cfg = dict(instrument=MICRO[mini], family=fam, lookback=lb, threshold=th)
    raw = st["eng"]["signal_for"](cfg, st["feats"][lb]).astype(np.int8)
    valid = (st["decision"] >= s0) & (st["decision"] < s1) & st["weekday"]
    return np.where(valid, raw, 0).astype(np.int8), valid


def year_slice(mini, y):
    st = STATE[mini]
    a, b = st["slices"][y]
    d = {k: np.ascontiguousarray(v[a:b]) for k, v in st["data"].items()}
    d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64)
    d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
    return d, a, b


_YEAR_CACHE: dict = {}


def run_config(mini, signal, atr, p, factor=1.0, gross=False):
    st = STATE[mini]
    ecfg = st["eng"]["execution_cfg"](p)
    if gross:
        ecfg.update(commission_per_side=0.0, slippage_ticks=0.0, spread_ticks=0.0, impact_ticks=0.0)
    ecfg["factor"] = float(factor)
    annual, dds, trades, entries = [], [], 0, []
    for y in YEARS:
        if y not in st["slices"]:
            continue
        if (mini, y) not in _YEAR_CACHE:
            _YEAR_CACHE[(mini, y)] = year_slice(mini, y)
        d, a, b = _YEAR_CACHE[(mini, y)]
        r = st["eng"]["execute"](d, np.ascontiguousarray(signal[a:b]), np.ascontiguousarray(atr[a:b]), ecfg)
        eq, worst = r["equity"], r["worst"]
        annual.append(float(r["cash"][-1] - 50000.0))
        peaks = np.maximum.accumulate(np.r_[50000.0, eq])[1:]
        dds.append(float(np.max(peaks - worst)) if len(eq) else 0.0)
        trades += int(len(r["trade_net"]))
        entries.append(np.asarray(r["trade_entry"], dtype=np.int64) + a)
    ent = np.concatenate(entries) if entries else np.empty(0, dtype=np.int64)
    annual = np.asarray(annual)
    total = float(annual.sum())
    return dict(net=round(total, 2), years_pos=int((annual > 0).sum()), n_years=len(annual), worst_dd=round(max(dds), 2) if dds else 0.0,
                trades=trades, per_trade=round(total / trades, 3) if trades else 0.0,
                top_year_share=round(float(annual.max() / total), 3) if total > 0 else None,
                annual=[round(x, 2) for x in annual], annual_dd=[round(x, 2) for x in dds],
                fp=hashlib.sha1(ent.tobytes()).hexdigest()[:16], n_entries=int(len(ent)))


def gate123(m):
    return (m["net"] > 0 and m["years_pos"] >= 10 and m["worst_dd"] < 1000 and m["trades"] >= 140
            and m["top_year_share"] is not None and m["top_year_share"] <= 0.40)


def work_unit(u):
    mini, fam, lb, th, s0, s1 = u
    signal, _ = masked(mini, fam, lb, th, s0, s1)
    atr = STATE[mini]["feats"][lb]["atr"]
    rows = []
    for stop, tr, hold, trail in EXITS:
        p = dict(instrument=MICRO[mini], family=fam, lookback=lb, threshold=th, stop_atr=stop, target_r=tr, hold_bars=hold,
                 session_start=s0, session_end=s1, max_contracts=1, trailing_atr=trail)
        m = run_config(mini, signal, atr, p)
        rows.append((config_id(p), MICRO[mini], fam, lb, th, s0, s1, stop, tr, hold, trail, m["net"], m["years_pos"], m["worst_dd"],
                     m["trades"], m["per_trade"], m["top_year_share"], json.dumps(m["annual"]), json.dumps(m["annual_dd"]), m["fp"],
                     int(gate123(m))))
    return unit_key(u), rows


def db():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("""CREATE TABLE IF NOT EXISTS results(config_id TEXT PRIMARY KEY, instrument TEXT, family TEXT, lookback INT, threshold REAL,
        session_start INT, session_end INT, stop_atr REAL, target_r REAL, hold_bars INT, trailing_atr REAL, net REAL, years_pos INT,
        worst_dd REAL, trades INT, per_trade REAL, top_year_share REAL, annual TEXT, annual_dd TEXT, fp TEXT, g123 INT)""")
    con.execute("CREATE TABLE IF NOT EXISTS done(unit TEXT PRIMARY KEY, finished TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS placebo(config_id TEXT PRIMARY KEY, payload TEXT)")
    return con


def phase_search(workers, limit=None):
    con = db()
    done = {r[0] for r in con.execute("SELECT unit FROM done")}
    todo = [u for u in units() if unit_key(u) not in done]
    if limit:
        todo = todo[:limit]
    print(f"units total {sum(1 for _ in units())}, done {len(done)}, todo {len(todo)}, exits/unit {len(EXITS)}", flush=True)
    load_training()
    t0, n = time.time(), 0
    with Pool(workers) as pool:
        for key, rows in pool.imap_unordered(work_unit, todo, chunksize=1):
            con.executemany("INSERT OR REPLACE INTO results VALUES (" + ",".join("?" * 21) + ")", rows)
            con.execute("INSERT OR REPLACE INTO done VALUES (?,?)", (key, pd.Timestamp.now('UTC').isoformat()))
            con.commit()
            n += 1
            if n % 20 == 0:
                el = time.time() - t0
                print(f"{n}/{len(todo)} units, {n * len(EXITS) / el:.0f} cfg/s, eta {(len(todo) - n) * el / n / 3600:.1f} h", flush=True)
    con.close()


def permuted_signal(signal, valid, mini, rng):
    """Same number of long and short signals per year, placed on random eligible bars of that year."""
    st = STATE[mini]
    out = np.zeros_like(signal)
    for y, (a, b) in st["slices"].items():
        seg = signal[a:b]
        elig = np.flatnonzero(valid[a:b])
        k_long, k_short = int((seg > 0).sum()), int((seg < 0).sum())
        if k_long + k_short == 0 or len(elig) < k_long + k_short:
            continue
        pick = rng.choice(elig, size=k_long + k_short, replace=False)
        out[a + pick[:k_long]] = 1
        out[a + pick[k_long:]] = -1
    return out


def row_params(r):
    return dict(instrument=r["instrument"], family=r["family"], lookback=int(r["lookback"]), threshold=float(r["threshold"]),
                stop_atr=float(r["stop_atr"]), target_r=float(r["target_r"]), hold_bars=int(r["hold_bars"]),
                session_start=int(r["session_start"]), session_end=int(r["session_end"]), max_contracts=1, trailing_atr=float(r["trailing_atr"]))


def deflated_sharpe(annual, all_sharpes):
    """Bailey & Lopez de Prado DSR on the annual return series, N_TRIALS trials, variance of trial Sharpes from the run."""
    r = np.asarray(annual) / 50000.0
    t = len(r)
    sd = r.std(ddof=1)
    if t < 3 or sd == 0:
        return None, None
    sr = r.mean() / sd
    var_sr = float(np.nanvar(all_sharpes)) if len(all_sharpes) > 1 else 1.0 / t
    g = 0.5772156649
    from scipy.stats import norm, skew, kurtosis
    sr0 = math.sqrt(var_sr) * ((1 - g) * norm.ppf(1 - 1 / N_TRIALS) + g * norm.ppf(1 - 1 / (N_TRIALS * math.e)))
    sk, ku = float(skew(r)), float(kurtosis(r, fisher=False))
    denom = math.sqrt(max(1e-12, 1 - sk * sr + (ku - 1) / 4 * sr * sr))
    return float(norm.cdf((sr - sr0) * math.sqrt(t - 1) / denom)), float(sr)


def phase_placebo(workers):
    con = db()
    surv = pd.read_sql("SELECT * FROM results WHERE g123=1", con)
    total = con.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    print(f"{total} configs scored, {len(surv)} pass G1-G3", flush=True)
    sharpes = pd.read_sql("SELECT annual FROM results", con).annual.map(lambda s: _ann_sharpe(json.loads(s))).to_numpy()
    load_training()
    rng = np.random.default_rng(20261108)
    out = []
    for _, r in surv.iterrows():
        mini = {"MES": "ES", "MNQ": "NQ"}[r["instrument"]]
        p = row_params(r)
        signal, valid = masked(mini, p["family"], p["lookback"], p["threshold"], p["session_start"], p["session_end"])
        atr = STATE[mini]["feats"][p["lookback"]]["atr"]
        perms = [run_config(mini, permuted_signal(signal, valid, mini, rng), atr, p)["per_trade"] for _ in range(PLACEBO_PERMS)]
        rest = run_config(mini, signal, atr, p, factor=_restated_factor(mini))
        gross = run_config(mini, signal, atr, p, gross=True)
        dsr, sr = deflated_sharpe(json.loads(r["annual"]), sharpes)
        p95 = float(np.percentile(perms, 95))
        payload = dict(params=p, per_trade=r["per_trade"], placebo_p95=p95, placebo_mean=float(np.mean(perms)), g4=bool(r["per_trade"] > p95),
                       restated_net=rest["net"], restated_years_pos=rest["years_pos"], gross_net=gross["net"], gross_years_pos=gross["years_pos"],
                       dsr=dsr, annual_sharpe=sr, g5=bool(dsr is not None and dsr > 0.95), net=r["net"], years_pos=int(r["years_pos"]),
                       worst_dd=r["worst_dd"], trades=int(r["trades"]), fp=r["fp"], annual=json.loads(r["annual"]))
        con.execute("INSERT OR REPLACE INTO placebo VALUES (?,?)", (r["config_id"], json.dumps(payload)))
        con.commit()
        out.append((r["config_id"], payload))
        print(r["config_id"], p["instrument"], p["family"], "g4", payload["g4"], "dsr", None if dsr is None else round(dsr, 3), flush=True)
    freeze(out)
    con.close()


def _ann_sharpe(annual):
    r = np.asarray(annual) / 50000.0
    sd = r.std(ddof=1) if len(r) > 1 else 0
    return r.mean() / sd if sd > 0 else np.nan


_FACTORS: dict = {}


def _restated_factor(mini):
    """Average cost factor (median close of each year / median close 2020) applied as one engine factor; conservative mean."""
    if mini not in _FACTORS:
        bars = STATE[mini]["bars"]
        ref = float(bars.close[bars.timestamp_utc.dt.year == 2020].median())
        fs = [float(bars.close[bars.timestamp_utc.dt.year == y].median()) / ref for y in YEARS if (bars.timestamp_utc.dt.year == y).any()]
        _FACTORS[mini] = float(np.mean(fs))
    return _FACTORS[mini]


def freeze(out):
    """Behavioural dedup (identical entry fingerprint -> keep smallest worst DD), rank by worst-year net then DSR, cap MAX_FROZEN."""
    cands = [(cid, pl) for cid, pl in out if pl["g4"]]
    best: dict = {}
    for cid, pl in cands:
        key = pl["fp"]
        if key not in best or pl["worst_dd"] < best[key][1]["worst_dd"]:
            best[key] = (cid, pl)
    ranked = sorted(best.values(), key=lambda x: (-min(x[1]["annual"]), -(x[1]["dsr"] or 0)))[:MAX_FROZEN]
    frozen = [dict(config_id=cid, **pl) for cid, pl in ranked]
    FROZEN.write_text(json.dumps(dict(frozen_at=pd.Timestamp.now('UTC').isoformat(), n_g4=len(cands),
                                                              n_unique=len(best), frozen=frozen), indent=1))
    print(f"frozen {len(frozen)} of {len(best)} unique G4 survivors ({len(cands)} incl. duplicates)", flush=True)


def phase_report():
    con = db()
    total = con.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    g123 = con.execute("SELECT COUNT(*) FROM results WHERE g123=1").fetchone()[0]
    by_fam = pd.read_sql("SELECT instrument, family, COUNT(*) n, SUM(g123) passed, AVG(net) avg_net, AVG(years_pos) avg_years_pos, MAX(net) max_net FROM results GROUP BY 1,2", con)
    plc = pd.read_sql("SELECT * FROM placebo", con)
    pl = [json.loads(x) for x in plc.payload] if len(plc) else []
    frozen = json.loads(FROZEN.read_text()) if FROZEN.exists() else {}
    rep = dict(protocol="research/mass_v2/PROTOCOL.md", scored=total, trials_planned=N_TRIALS, g123=g123, g4=sum(p["g4"] for p in pl),
               g5=sum(p["g5"] for p in pl), by_family=by_fam.to_dict(orient="records"), frozen=frozen)
    (ROOT / "reports" / f"MASS_V2_TRAINING{SUFFIX.upper()}.json").write_text(json.dumps(rep, indent=1, default=float))
    lines = [f"# mass_v2 training results (ES/NQ 2010-2023 as MES/MNQ, 1 contract, today's costs)\n",
             f"Configurations scored: {total:,} of {N_TRIALS:,} planned. G1-G3 passers: {g123:,}. G4 (beat placebo p95): {rep['g4']}. "
             f"G5 (DSR > 0.95, N = {N_TRIALS:,}): {rep['g5']}. Frozen for validation: {len(frozen.get('frozen', []))}.\n",
             "| instrument | family | configs | G1-G3 | mean net | mean +years/14 | best net |", "|---|---|---:|---:|---:|---:|---:|"]
    for r in by_fam.itertuples():
        lines.append(f"| {r.instrument} | {r.family} | {r.n:,} | {int(r.passed or 0)} | {r.avg_net:,.0f} | {r.avg_years_pos:.1f} | {r.max_net:,.0f} |")
    if frozen.get("frozen"):
        lines += ["\n| id | rule | net 14y | +yrs | worst DD | trades | placebo p95/trade | per trade | gross net | restated net | DSR |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for f in frozen["frozen"]:
            p = f["params"]
            rule = f"{p['instrument']} {p['family']} lb{p['lookback']} th{p['threshold']} {p['session_start']}-{p['session_end']} stop{p['stop_atr']} tgt{p['target_r']} hold{p['hold_bars']} trail{p['trailing_atr']}"
            lines.append(f"| {f['config_id']} | {rule} | {f['net']:,.0f} | {f['years_pos']} | {f['worst_dd']:,.0f} | {f['trades']} | {f['placebo_p95']:.1f} | {f['per_trade']:.1f} | {f['gross_net']:,.0f} | {f['restated_net']:,.0f} | {'-' if f['dsr'] is None else f'{f['dsr']:.2f}'} |")
    (ROOT / "reports" / f"MASS_V2_TRAINING{SUFFIX.upper()}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    con.close()


def phase_validate():
    """Run the frozen list once on MES/MNQ 2024-2025 from the validation partition. Never loads 2026."""
    frozen = json.loads(FROZEN.read_text())["frozen"]
    if (RUN / f"validation_done{SUFFIX}.json").exists():
        raise SystemExit("validation already run once; refusing to re-run (protocol)")
    import duckdb
    eng = ep.engine()
    cat = json.load(open(uy.CATALOG))["instruments"]
    out = []
    for f in frozen:
        p = f["params"]
        inst = p["instrument"]
        path = cat[inst]["splits"]["validation"]["path"]
        con = duckdb.connect()
        frame = con.execute(uy.STRICT, [str(path), "2023-12-01", "2026-01-01"]).fetch_df()
        con.close()
        frame = frame[frame.timestamp_utc.notna()].copy()
        frame["high"] = frame[["open", "high", "low", "close"]].max(axis=1)
        frame["low"] = frame[["open", "high", "low", "close"]].min(axis=1)
        frame["volume"] = frame.volume.round()
        from quant_futures.data import canonical
        bars = canonical(frame)
        assert bars.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC")
        data = apply_early_close(eng["arrays"](bars), bars)
        feats = eng["features"](bars, p["lookback"])
        raw = eng["signal_for"](p, feats).astype(np.int8)
        local = bars.timestamp_utc.dt.tz_convert("America/New_York")
        decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
        valid = (decision >= p["session_start"]) & (decision < p["session_end"]) & (local.dt.day_of_week.to_numpy() < 5)
        signal = np.where(valid, raw, 0).astype(np.int8)
        res = {}
        for y in (2024, 2025):
            idx = np.flatnonzero(data["year"] == y)
            a, b = int(idx[0]), int(idx[-1]) + 1
            d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
            d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64)
            d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
            r = eng["execute"](d, np.ascontiguousarray(signal[a:b]), np.ascontiguousarray(feats["atr"][a:b]), eng["execution_cfg"](p))
            peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
            res[y] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), dd=round(float(np.max(peaks - r["worst"])), 2),
                          trades=int(len(r["trade_net"])), breach=bool(r["funded_failed"]))
        vnet = res[2024]["net"] + res[2025]["net"]
        vtr = res[2024]["trades"] + res[2025]["trades"]
        holds = (vnet > 0 and res[2024]["net"] >= -300 and res[2025]["net"] >= -300 and not (res[2024]["breach"] or res[2025]["breach"])
                 and vtr > 0 and vnet / vtr >= 0.5 * f["per_trade"])
        out.append(dict(config_id=f["config_id"], params=p, train_net=f["net"], train_per_trade=f["per_trade"], validation=res,
                        val_net=round(vnet, 2), val_trades=vtr, holds=bool(holds)))
        print(f["config_id"], inst, p["family"], res, "HOLDS" if holds else "fails", flush=True)
    (RUN / f"validation_done{SUFFIX}.json").write_text(json.dumps(dict(run_at=pd.Timestamp.now('UTC').isoformat(), results=out), indent=1))
    lines = ["# mass_v2 validation (MES/MNQ 2024-2025, run once on the frozen list)\n",
             "| id | rule | train net 14y | 2024 net / DD | 2025 net / DD | val trades | holds |", "|---|---|---:|---:|---:|---:|---|"]
    for o in out:
        p = o["params"]
        rule = f"{p['instrument']} {p['family']} lb{p['lookback']} th{p['threshold']} {p['session_start']}-{p['session_end']} stop{p['stop_atr']} tgt{p['target_r']} hold{p['hold_bars']} trail{p['trailing_atr']}"
        v = o["validation"]
        lines.append(f"| {o['config_id']} | {rule} | {o['train_net']:,.0f} | {v[2024]['net']:,.0f} / {v[2024]['dd']:,.0f} | {v[2025]['net']:,.0f} / {v[2025]['dd']:,.0f} | {o['val_trades']} | {'yes' if o['holds'] else 'no'} |")
    lines.append(f"\n{sum(o['holds'] for o in out)} of {len(out)} frozen survivors hold on validation.")
    (ROOT / "reports" / f"MASS_V2_VALIDATION{SUFFIX.upper()}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("search", "placebo", "report", "validate"))
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() - 1))
    ap.add_argument("--limit", type=int, default=None, help="search: only this many units (smoke test)")
    a = ap.parse_args()
    if a.phase == "search":
        phase_search(a.workers, a.limit)
    elif a.phase == "placebo":
        phase_placebo(a.workers)
    elif a.phase == "report":
        phase_report()
    else:
        phase_validate()

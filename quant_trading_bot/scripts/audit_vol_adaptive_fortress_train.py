"""Claude audit of Antigravity's 'Enhanced Vol-Adaptive Duo Fortress' (2026-11-10). TRAINING 2010-23 ONLY.

Reuses the functions of audit_vol_adaptive_frozen_all_splits.py (its holdout loop is NOT run; only train.parquet is read).

PRE-DECLARED checks (written before any result of this script was seen):
 A  reproduce the published training result (362 passed / 0 ruined / 3022 timeouts, continuous +$48,827). If it does not
    reproduce, stop and report.
 B  honest pass rate: passed / ALL windows (the published pass_pct divides by passed + ruined and drops the timeouts).
 C  no look-ahead VIX: the published code filters (VIX < 15 = no trade) and sizes (VIX >= 16 = bigger) with the SAME day's VIX
    close, which prints at 16:15 ET, after the 09:45-15:55 trade. Use the prior session's close.
 D  pessimistic 1-minute fills: when stop and target are both inside one bar, stop first (published code takes the target
    first); check the stop on the entry bar too (published code skips it); runner target only on a bar that reaches it; entry on
    a bar that opens beyond the 15-minute level fills at the open (published code fills at the level).
 E  C + D together.
 F  what makes 0% ruin: rerun A and E without the 'defensive floor' (1 micro once equity <= -$200).
 G  12-month horizon (252 sessions) from every session start, with the end state of the windows that neither pass nor fail.
Report the share of trades with an ambiguous bar (the cases 1-second data would settle) and 1-micro P&L by year.
"""
import bisect, json
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "scripts/audit_vol_adaptive_frozen_all_splits.py").read_text(encoding="utf-8")
ns = {"__name__": "ag_fortress"}
exec(SRC.split('\nprint("="*95)\nprint("PROSPECTIVE AUDIT')[0], ns)          # functions + constants only, no split is loaded
P_TRAIN = ns["p_train"]; assert P_TRAIN.name == "train.parquet"
FR, PTV = ns["FRICTION_PTS"], ns["PT_VAL"]
vix_dict, cboe = ns["vix_dict"], ns["cboe_dates"]
same_day_vix = ns["get_vix"]


def prior_day_vix(d):
    dt = pd.to_datetime(d).date(); i = bisect.bisect_left(cboe, dt) - 1
    return vix_dict[cboe[max(i, 0)]]


def load_train():
    con = duckdb.connect(); con.execute("PRAGMA memory_limit='2GB'")
    q = f"""SELECT (timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))::DATE AS date,
      (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 +
       date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ)))::INT AS sod,
      open::DOUBLE AS open, high::DOUBLE AS high, low::DOUBLE AS low, close::DOUBLE AS close
    FROM read_parquet('{P_TRAIN}')
    WHERE (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 +
           date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))) BETWEEN 570 AND 960
    ORDER BY date, sod"""
    rth = con.execute(q).fetch_df(); con.close()
    dates = sorted(rth["date"].unique())
    eod = rth[rth.sod == 960].groupby("date")["close"].last(); sod0 = rth[rth.sod == 570].groupby("date")["open"].first()
    gap = (sod0 - eod.shift(1)).dropna().to_dict()
    G = {d: {k: g[k].to_numpy() for k in ("sod", "open", "high", "low", "close")} for d, g in rth.groupby("date")}
    return dates, gap, G


def sim(dates, gap_dict, G, vixf, pess=False, stop=16.0, t1=28.0, rtp=120.0):
    """Mirror of simulate_crabel_trades; pess=True applies check D. Returns (daily dict, ambiguous-trade count, trade count)."""
    res, amb_trades, n_tr = {}, 0, 0
    flat = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
    for d in dates:
        if vixf(d) < 15.0 or d not in G: res[str(d)] = dict(flat); continue
        gap = gap_dict.get(d, 0.0); b = G[d]
        sod, O, H, L, C = b["sod"], b["open"], b["high"], b["low"], b["close"]
        m = sod < 585
        if not m.any(): res[str(d)] = dict(flat); continue
        h15, l15 = H[m].max(), L[m].min()
        if h15 - l15 < 15.0: res[str(d)] = dict(flat); continue
        it = np.where((sod >= 585) & (sod <= 955))[0]
        if not len(it): res[str(d)] = dict(flat); continue
        inpos, s, e, net, mae, mfav, leg1, amb = False, 0, 0.0, 0.0, 0.0, 0.0, False, False
        sl1 = sl2 = tp1 = 0.0; done = False
        for idx in it:
            hi, lo, op = H[idx], L[idx], O[idx]
            if not inpos:
                if gap >= 0.0 and hi > h15: s = 1; e = max(op, h15) if pess else h15
                elif gap <= 0.0 and lo < l15: s = -1; e = min(op, l15) if pess else l15
                else: continue
                inpos = True; sl1 = sl2 = e - s * stop; tp1 = e + s * t1
                if pess and (lo <= sl1 if s == 1 else hi >= sl1):      # stop inside the entry bar: assume it was hit
                    amb = True; net += -stop - FR; mae = -stop; inpos = False; done = True; break
                continue
            fav = (hi - e) if s == 1 else (e - lo); adv = max(((lo - e) if s == 1 else (e - hi)), -stop)
            if not leg1 and adv < mae: mae = adv
            if fav > mfav: mfav = fav
            hit_sl1 = (lo <= sl1) if s == 1 else (hi >= sl1); hit_tp1 = (hi >= tp1) if s == 1 else (lo <= tp1)
            hit_sl2 = (lo <= sl2) if s == 1 else (hi >= sl2)
            if not leg1:
                if hit_sl1 and hit_tp1: amb = True
                if pess and hit_sl1: net += -stop - FR; inpos = False; break
                if hit_tp1:
                    net += (t1 - FR) * 0.5; leg1 = True; sl2 = e + s * 1.0
                    if pess and ((lo <= sl2) if s == 1 else (hi >= sl2)):   # runner stop in the same bar
                        amb = True; net += (1.0 - FR) * 0.5; inpos = False; break
                elif hit_sl1: net += -stop - FR; inpos = False; break
            else:
                hit_rtp = (fav >= rtp) if pess else (mfav >= rtp)
                if hit_rtp and hit_sl2: amb = True
                if pess and hit_sl2: net += (1.0 - FR) * 0.5; inpos = False; break
                if hit_rtp: net += (rtp - FR) * 0.5; inpos = False; break
                if hit_sl2: net += (1.0 - FR) * 0.5; inpos = False; break
        if inpos:
            lc = C[it[-1]]; net += (((lc - e) if s == 1 else (e - lc)) - FR) * (0.5 if leg1 else 1.0)
        traded = bool(inpos or net != 0.0 or done)
        if traded: n_tr += 1; amb_trades += amb
        res[str(d)] = {"net_1c": float(net * PTV), "mae_1c": float(mae * PTV), "traded": traded, "amb": bool(amb)}
    return res, amb_trades, n_tr


def evaluate(dates, daily, vixf, horizon=100, def_thr=-200.0):
    """Same ladder as run_vol_adaptive_trials; also returns end states of open windows. Steps every session."""
    ds = [str(d) for d in dates]; out = []
    for i in range(len(ds) - horizon):
        cum = 0.0; state = "open"; td = 0
        for step in range(horizon):
            tr = daily.get(ds[i + step])
            if not tr or not tr["traded"]: continue
            td += 1; hv = vixf(ds[i + step]) >= 16.0
            sz = 1 if cum <= def_thr else (14 if hv else 12) if cum >= 2400 else (12 if hv else 10) if cum >= 1200 else (10 if hv else 8)
            pnl, mae = tr["net_1c"] * sz, tr["mae_1c"] * sz
            if pnl <= -1000 or mae <= -1000 or cum + mae <= -2000: state = "fail"; break
            cum += min(pnl, 1500.0)
            if cum <= -2000: state = "fail"; break
            if cum >= 4000: state = "pass"; break
        out.append((state, td, step + 1, cum))
    r = pd.DataFrame(out, columns=["state", "trade_days", "sessions", "end"]); p = r[r.state == "pass"]; o = r[r.state == "open"]
    return dict(windows=len(r), pass_pct_of_all=round(100 * (r.state == "pass").mean(), 1), fail_pct=round(100 * (r.state == "fail").mean(), 1),
                open_pct=round(100 * (r.state == "open").mean(), 1), published_style_pass_pct=round(100 * len(p) / max(1, len(p) + (r.state == "fail").sum()), 1),
                median_sessions_to_pass=float(p.sessions.median()) if len(p) else None, median_trade_days_to_pass=float(p.trade_days.median()) if len(p) else None,
                open_windows_end_median=round(float(o.end.median()), 0) if len(o) else None,
                open_windows_stuck_in_1_micro_pct=round(100 * float((o.end <= def_thr).mean()), 1) if len(o) else None)


def by_year(daily):
    s = pd.Series({k: v["net_1c"] for k, v in daily.items() if v["traded"]}); s.index = pd.to_datetime(s.index)
    g = s.groupby(s.index.year)
    return {int(y): dict(trades=int(len(v)), net_1c=round(float(v.sum()), 0),
                         pf=round(float(v[v > 0].sum() / max(1e-9, -v[v < 0].sum())), 2)) for y, v in g}


if __name__ == "__main__":
    dates, gap, G = load_train()
    out = {}
    # A: published, via Antigravity's own functions
    ns["get_vix"] = same_day_vix
    ag_daily = ns["simulate_crabel_trades"](dates, gap, {d: {k: G[d][k] for k in ("sod", "high", "low", "close")} for d in G})
    A = ns["run_vol_adaptive_trials"]("Training A (published)", dates, ag_daily)
    mine_A, ambA, nA = sim(dates, gap, G, same_day_vix, pess=False)
    mism = sum(abs(mine_A[k]["net_1c"] - ag_daily[k]["net_1c"]) > 1e-6 or mine_A[k]["traded"] != ag_daily[k]["traded"] for k in ag_daily)
    out["A_reproduce"] = dict(published_eval=A["evaluation"], published_continuous=A["continuous"], mirror_mismatch_days=int(mism),
                              reproduces=bool(A["evaluation"]["passed"] == 362 and A["evaluation"]["timeouts"] == 3022 and abs(A["continuous"]["net_profit"] - 48827.0) < 1 and mism == 0))
    print("A reproduces:", out["A_reproduce"]["reproduces"], "mirror mismatches:", mism, flush=True)
    if not out["A_reproduce"]["reproduces"]:
        (ROOT / "reports/AUDIT_VOL_ADAPTIVE_FORTRESS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str)); raise SystemExit("A did not reproduce")
    C, ambC, nC = sim(dates, gap, G, prior_day_vix, pess=False)
    D, ambD, nD = sim(dates, gap, G, same_day_vix, pess=True)
    E, ambE, nE = sim(dates, gap, G, prior_day_vix, pess=True)
    vf = {"A": same_day_vix, "C": prior_day_vix, "D": same_day_vix, "E": prior_day_vix}
    runs = {"A": mine_A, "C": C, "D": D, "E": E}
    out["ambiguous_trades"] = dict(published_fills=f"{ambA}/{nA}", pessimistic_fills=f"{ambD}/{nD}")
    for k, dd in runs.items():
        n1 = [v["net_1c"] for v in dd.values() if v["traded"]]
        out[k] = dict(trades=len(n1), net_1c_total=round(float(sum(n1)), 0), avg_per_trade_1c=round(float(np.mean(n1)), 2),
                      pf_1c=round(float(sum(x for x in n1 if x > 0) / -sum(x for x in n1 if x < 0)), 3),
                      eval_100_sessions=evaluate(dates, dd, vf[k], 100), eval_252_sessions=evaluate(dates, dd, vf[k], 252))
        print(k, {kk: vv for kk, vv in out[k].items()}, flush=True)
    out["F_no_defensive_floor"] = {k: evaluate(dates, runs[k], vf[k], 100, def_thr=-1e9) for k in ("A", "E")}
    print("F", out["F_no_defensive_floor"], flush=True)
    out["by_year_1c"] = {"A_published": by_year(mine_A), "E_prior_vix_pessimistic": by_year(E)}
    (ROOT / "reports/AUDIT_VOL_ADAPTIVE_FORTRESS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
    print("saved")

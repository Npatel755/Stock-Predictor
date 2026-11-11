"""Honest re-count of Antigravity's Hyper-Velocity Fast-Track Fortress for its real job: passing the $4,000 evaluation fast.
TRAINING 2010-23 ONLY (Claude, 2026-11-10). Antigravity's rules are exec'd unchanged from audit_hyper_velocity_all_splits.py (the
part before its split loop, so validation/test are never loaded).

PRE-DECLARED (before running):
- Fills: (a) Antigravity's published sim, (b) 1-second resolved (the 221 ambiguous training days from RESOLVE_CRABEL_1S_TRAINING
  re-simulated on 1-second bars, worst case = published elsewhere). First check that audit_vol_adaptive_fortress_train.sim gives the
  same day P&L as Antigravity's simulate_trades, otherwise (b) is skipped.
- Per attempt, over ALL 100-session windows (their horizon, every session a start): passed / failed (-$2,000 or DLL) / fell to
  -$400 (where their ladder drops to 1 micro) / still open. Policies, ladder otherwise unchanged:
    P1 published: 1 micro at or below -$400 (stall);  P2 reset: an account at or below -$400 at a day's close is reset;
    P3 no floor: keep the ladder, fail only at -$2,000 / DLL.
- Time to a funded account, the number that matters for a fast pass: from every training session, run attempts back to back
  (a reset or failure starts a new attempt the next session) until one passes; cap 252 sessions. Report P(funded) within 21 / 63 /
  126 / 252 sessions, median sessions to funded, and mean number of resets/fails paid for before passing.
- By start year: share of attempts passing within 100 sessions (P2), to see whether the result depends on 2019-21.
- Recommendation rule for Nick's evaluation: recommend the best policy only if, on 1-second resolved fills, P(funded within 63
  sessions) >= 50% in BOTH halves of the starts (2010-16 and 2017-23) and >= 35% for starts in 2022-23.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

SRC = (ROOT / "scripts/audit_hyper_velocity_all_splits.py").read_text(encoding="utf-8").split('\nprint("="*95)\nprint("PROSPECTIVE AUDIT')[0]
assert "splits = [" not in SRC and "p_val)" not in SRC
HV = {"__name__": "hv"}; exec(SRC, HV)
_VIX = {}


def pvix(d):
    if d not in _VIX: _VIX[d] = HV["get_prior_vix"](d)
    return _VIX[d]


def size(cum, vix):
    b = HV["VOL_BONUS"] if vix >= HV["VIX_THRESHOLD"] else 0
    if cum >= HV["SPRINT_THR"]: return HV["SPRINT_SZ"] + b
    if cum >= HV["ACCEL_THR"]: return HV["ACCEL_SZ"] + b
    return HV["BASE_SZ"] + b


def attempt(ds, daily, i, policy, max_len):
    """Run one evaluation from session i. Returns (outcome, sessions used, hit_400). outcome in pass/fail/reset/open."""
    cum = 0.0; hit = False
    for step in range(min(max_len, len(ds) - i)):
        tr = daily.get(ds[i + step])
        if not tr or not tr["traded"]: continue
        sz = 1 if (policy == "P1" and cum <= HV["DEF_TRIGGER"]) else size(cum, pvix(ds[i + step]))
        pnl, mae = tr["net_1c"] * sz, tr["mae_1c"] * sz
        if pnl <= HV["DLL_LIMIT"] or mae <= HV["DLL_LIMIT"] or cum + mae <= HV["STATIC_FLOOR"]: return "fail", step + 1, hit
        cum += min(pnl, HV["DAILY_LOCK"])
        if cum <= HV["STATIC_FLOOR"]: return "fail", step + 1, hit
        if cum >= 4000.0: return "pass", step + 1, hit
        if cum <= HV["DEF_TRIGGER"]:
            hit = True
            if policy == "P2": return "reset", step + 1, hit
    return "open", min(max_len, len(ds) - i), hit


def per_attempt(ds, daily, policy, horizon=100):
    rows = [attempt(ds, daily, i, policy, horizon) + (ds[i][:4],) for i in range(len(ds) - horizon)]
    r = pd.DataFrame(rows, columns=["out", "sess", "hit400", "year"])
    n = len(r); ps = r[r.out == "pass"].sess
    return dict(windows=n, passed_pct=round(100 * (r.out == "pass").mean(), 1), failed_pct=round(100 * (r.out == "fail").mean(), 1),
                reset_at_400_pct=round(100 * (r.out == "reset").mean(), 1), open_pct=round(100 * (r.out == "open").mean(), 1),
                open_and_below_400_pct=round(100 * ((r.out == "open") & r.hit400).mean(), 1),
                published_style_pass_pct=round(100 * (r.out == "pass").sum() / max(1, ((r.out == "pass") | (r.out == "fail")).sum()), 1),
                pass_sessions_median=float(ps.median()) if len(ps) else None,
                by_start_year_pass_pct={y: round(100 * (g.out == "pass").mean(), 1) for y, g in r.groupby("year")})


def to_funded(ds, daily, policy, cap=252):
    rows = []
    for s in range(len(ds) - cap):
        used = 0; paid = 0; funded = None
        while used < cap:
            out, n, _ = attempt(ds, daily, s + used, policy, cap - used)
            used += n
            if out == "pass": funded = used; break
            if out in ("fail", "reset"): paid += 1
            else: break
        rows.append((ds[s][:4], funded, paid))
    r = pd.DataFrame(rows, columns=["year", "funded", "paid"])
    f = r.funded.fillna(np.inf)

    def share(m, k): return round(100 * float((f[m] <= k).mean()), 1)
    allm = np.ones(len(r), bool); h1 = r.year.astype(int) <= 2016; h2 = ~h1; late = r.year.isin(["2022", "2023"])
    return dict(starts=len(r), funded_within={k: share(allm, k) for k in (21, 63, 126, 252)},
                median_sessions_to_funded=(float(np.median(f)) if np.isfinite(np.median(f)) else "not within 252"),
                mean_failed_or_reset_attempts=round(float(r.paid.mean()), 2),
                funded_63_H1_2010_16=share(h1, 63), funded_63_H2_2017_23=share(h2, 63), funded_63_starts_2022_23=share(late, 63),
                funded_63_by_year={y: share((r.year == y).to_numpy(), 63) for y in sorted(r.year.unique())})


def main():
    dates, gap, grouped = HV["load_split_minute_bars"](HV["p_train"])
    assert pd.Timestamp(max(dates)) < pd.Timestamp("2024-01-01")
    ds = [str(d)[:10] for d in dates]
    pub = HV["simulate_trades"](dates, gap, grouped)
    out = {"fills": {}}
    fills = {"published": pub}

    import audit_vol_adaptive_fortress_train as au
    import resolve_crabel_1s_train as rs
    d2, gap2, G = au.load_train()
    mine, _, _ = au.sim(d2, gap2, G, au.prior_day_vix, pess=False); mine = {k[:10]: v for k, v in mine.items()}
    same = all(abs(mine.get(str(k)[:10], {"net_1c": 0})["net_1c"] - v["net_1c"]) < 1e-6 for k, v in pub.items())
    out["au_sim_matches_hyper_sim"] = bool(same)
    print("au.sim matches hyper simulate_trades:", same, flush=True)
    if same:
        led = json.loads((rs.SEC / "_spend_ledger.json").read_text()); by_date = {str(d)[:10]: d for d in d2}; G1s = {}
        for x in sorted(led["days"]):
            d = by_date[x]; g = G[d]; s = rs.one_sec_day(x); m = g["sod"] < 585
            G1s[d] = {c: np.concatenate([g[c][m], s[c].to_numpy()]) for c in ("open", "high", "low", "close")}
            G1s[d]["sod"] = np.concatenate([g["sod"][m], s.sod.to_numpy()])
        worst, _, _ = au.sim(d2, gap2, G, au.prior_day_vix, pess=True)
        sec, _, _ = au.sim([by_date[x] for x in sorted(led["days"])], gap2, G1s, au.prior_day_vix, pess=True)
        res = dict(worst); res.update(sec)
        fills["resolved_1s"] = {k[:10]: v for k, v in res.items()}
    for fname, daily in fills.items():
        daily = {k[:10]: v for k, v in daily.items()}
        o = out["fills"][fname] = {}
        for pol in ("P1", "P2", "P3"):
            o[pol] = dict(per_attempt_100=per_attempt(ds, daily, pol), time_to_funded=to_funded(ds, daily, pol))
            print(fname, pol, {k: v for k, v in o[pol]["per_attempt_100"].items() if k != "by_start_year_pass_pct"},
                  "| funded", o[pol]["time_to_funded"]["funded_within"], "median", o[pol]["time_to_funded"]["median_sessions_to_funded"],
                  "paid", o[pol]["time_to_funded"]["mean_failed_or_reset_attempts"], flush=True)
    # Negative control ADDED AFTER the first run (not a gate, changes no rule): same trade days, sizes, stops and adverse excursions,
    # with every traded day's P&L shifted so the mean per trade is $0. Shows how much of the passing comes from the edge vs the size.
    base = fills.get("resolved_1s", pub); base = {k[:10]: v for k, v in base.items()}
    mu = float(np.mean([v["net_1c"] for v in base.values() if v["traded"]]))
    zero = {k: (dict(v, net_1c=v["net_1c"] - mu) if v["traded"] else v) for k, v in base.items()}
    out["zero_edge_control"] = {"mean_removed_per_trade_1c": round(mu, 2)}
    for pol in ("P1", "P2", "P3"):
        out["zero_edge_control"][pol] = dict(per_attempt_100=per_attempt(ds, zero, pol), time_to_funded=to_funded(ds, zero, pol))
        z = out["zero_edge_control"][pol]
        print("ZERO-EDGE", pol, {k: v for k, v in z["per_attempt_100"].items() if k != "by_start_year_pass_pct"},
              "| funded", z["time_to_funded"]["funded_within"], "median", z["time_to_funded"]["median_sessions_to_funded"], flush=True)
    f = out["fills"].get("resolved_1s")
    if f:
        rec = {p: bool(f[p]["time_to_funded"]["funded_63_H1_2010_16"] >= 50 and f[p]["time_to_funded"]["funded_63_H2_2017_23"] >= 50
                       and f[p]["time_to_funded"]["funded_63_starts_2022_23"] >= 35) for p in ("P1", "P2", "P3")}
        out["recommend"] = rec
        print("recommend:", rec)
    (ROOT / "reports/AUDIT_HYPER_VELOCITY_HONEST_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()

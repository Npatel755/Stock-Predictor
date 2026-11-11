"""v53 (Claude, 2026-11-10): content changes to the best book (v5.2 + overnight dip), scored on BOTH tracks. TRAINING 2010-23 only.

PRE-DECLARED (before results). Base = v5.2 (CRABEL15_D, TRD60_D, MES_TRD30_D, TRD30PM; 1 micro; 2 on Crabel gap-continuation; skip stop risk
> $300/micro; 1-position research routing) + overnight dip 0.55% stop.
Cells: A drop TRD30PM (weakest sleeve: PF 1.08, $5.1/trade) | B Crabel gap-continuation at 3 micros instead of 2 (strongest piece) |
C skip Crabel trades against the opening gap ("fades") | A+B | A+C.
Track 1 EVALUATION (eval_1 rules: size min(3 x base, floor($900 / risk)), overnight min(3, floor($900 / risk)), account stop $700, 1-minute MAE
floor check, DLL $1,000, 55% consistency, 90 calendar days, every session 2010-06..2023-09 a start): pass share all / 2010-16 / 2017-23.
Track 2 FUNDED (payout_24 adopted rule: 1x below $4,000, 2x from $4,000 with $700 stop and $900 risk cap, overnight while balance >= $500,
daily payouts above $6,000; static -$2,000 until the first payout, then $0): 24-month dollars withdrawn, closure S0 / S3 / S4, S0 near-miss
(lowest balance before the first payout <= -$1,500), both halves (2010-07..2016-06, 2016-07..2022-01).
ADOPT a cell for the funded book if: dollars withdrawn >= base x 1.05 in BOTH halves, closure (S0, S3, S4) <= base + 0.005, S0 near-miss <= base,
AND its evaluation pass share is >= base - 1 point overall and not more than 2 points worse in either half. Among adopted cells, the most
dollars. Separately, a cell is adopted for the EVALUATION book only if its pass share beats base by >= 2 points in BOTH halves.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl
import payout_17_bond_filter_train as p17

base0, N0, sc17, fds = p17.base_intra.copy(), p17.N0, p17.scenario, p17.fast_day_series
NIGHT_RISK = abs(float(p17.stop_loss_level))
P10 = p17.ns["ns"]; ov = P10["ov"]
BARS = {k: (pd.to_datetime(b.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), b.high.to_numpy(float), b.low.to_numpy(float))
        for k, b in (("MNQ", P10["m1"]), ("MES", P10["mes1"]))}


def mae_pct(inst, tin, tout, side, entry):
    ts, H, L = BARS[inst]; i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value))
    if i1 <= i0: return 0.0
    w = L[i0:i1].min() if side > 0 else H[i0:i1].max(); return min(0.0, side * (w - entry) / entry)


base0["mae_per_micro"] = [(mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst] for r in base0.itertuples()]
crab = base0.sleeve.str.contains("CRABEL"); cont = crab & (base0.n_contracts >= 2); fade = crab & (base0.n_contracts < 2)

# overnight nights with MAE (eval_1 derivation; must equal payout_17's N0)
ts, H, L = BARS["MNQ"]; O = P10["m1"].open.to_numpy(float); rows = []
for t in ov:
    e_raw = float(t["entry_price"]) - pl.ADV; x_raw = float(t["exit_price"]) + pl.ADV
    tin, tout = pd.Timestamp(t["entry_ts"]), pd.Timestamp(t["exit_ts"]); stop = e_raw * (1 - 0.0055)
    i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value)); hit = np.nonzero(L[i0:i1] <= stop)[0]
    if len(hit): j = i0 + int(hit[0]); x_raw = min(stop, O[j]) if j > i0 else stop; lowest = x_raw
    else: lowest = L[i0:i1].min() if i1 > i0 else e_raw
    pm = (((x_raw - e_raw) / e_raw) * pl.TODAY["MNQ"] - 2 * pl.ADV) * pl.MULT["MNQ"] - pl.FEE
    rows.append(dict(tin=tin.tz_convert(pl.NY), tout=tout.tz_convert(pl.NY), per_micro=pm, mae_per_micro=min(pm, (min(0.0, (lowest - e_raw) / e_raw) * pl.TODAY["MNQ"] - pl.ADV) * pl.MULT["MNQ"])))
NIGHTS = pd.DataFrame(rows)
assert abs(NIGHTS.per_micro.sum() - N0.net_today.sum()) < 1e-6


def variant(v):
    d = base0.copy()
    if "A" in v: d = d[~d.sleeve.str.contains("TRD30PM")]
    if "B" in v:
        m = cont.reindex(d.index).fillna(False); d.loc[m, "net_today"] *= 1.5; d.loc[m, "n_contracts"] = 3.0
    if "C" in v: d = d[~fade.reindex(d.index).fillna(False)]
    return d


# ---------------- Track 1: evaluation
def eval_track(d):
    r = pl.route(d[d.risk_today <= 300.0]).copy(); r["per_micro"] = r.net_today / r.n_contracts
    a = r.assign(q=np.minimum(3 * r.n_contracts, np.floor(900.0 / r.risk_today)))
    qn = float(min(3, int(900.0 // NIGHT_RISK)))
    t = pd.concat([a[["tin", "tout", "per_micro", "mae_per_micro", "q"]], NIGHTS.assign(q=qn)[["tin", "tout", "per_micro", "mae_per_micro", "q"]]], ignore_index=True)
    t = t[t.q >= 1].assign(net=lambda x: x.per_micro * x.q, mae=lambda x: x.mae_per_micro * x.q, day=lambda x: x.tout.dt.date).sort_values("tin")
    by = {k: g for k, g in t.groupby("day")}; td = sorted(by); tix = pd.to_datetime(pd.Series(td).astype(str)).to_numpy(); res = []
    for s in SESS:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(tix, np.datetime64(pd.Timestamp(s)))); bal = 0.0; best = 0.0; out = "timeout"
        for dd in td[i:]:
            if dd >= end: break
            day = 0.0
            for x in by[dd].itertuples():
                if day <= -700.0 or day <= -1000.0: break
                if bal + day + x.mae <= -2000.0: out = "fail"; break
                if day + x.mae <= -1000.0: day = -1000.0; break
                day += x.net
            if out == "fail": break
            bal += max(day, -1000.0); best = max(best, day)
            if bal <= -2000.0: out = "fail"; break
            if bal >= max(4000.0, best / 0.55): out = "pass"; break
        res.append((s, out))
    rr = pd.DataFrame(res, columns=["s", "o"]); h1 = (rr.s < pd.Timestamp("2017-01-01").date()).to_numpy()
    p = lambda m: round(100 * float((rr.o[m] == "pass").mean()), 1)
    return dict(all=p(np.ones(len(rr), bool)), half1=p(h1), half2=p(~h1), fail=round(100 * float((rr.o == "fail").mean()), 1))


mnq = P10["m1"]
SESS = sorted(set(pd.to_datetime(mnq.timestamp_utc, utc=True).dt.tz_convert(pl.NY).dt.date))
SESS = [d for d in SESS if pd.Timestamp(d).dayofweek < 5 and pd.Timestamp("2010-06-07").date() <= d <= pd.Timestamp("2023-09-29").date()]


# ---------------- Track 2: funded (payout_24 rule)
def stressed(d, kind):
    d = d.copy()
    if kind in ("S1", "S3"): d["net_today"] -= 1.0 * d.inst.map(pl.MULT) * d.n_contracts
    if kind in ("S2", "S3"):
        avg = d.groupby("sleeve").net_today.transform("mean"); d["net_today"] -= 0.25 * avg.clip(lower=0)
    if kind == "S4": d["risk_today"] *= 1.5; d["net_today"] *= 1.5
    return d[d.risk_today <= 300.0]


def funded_track(d):
    SER = {}
    for kind in ("S0", "S3", "S4"):
        e = stressed(d, kind); _, n = sc17(kind, N0)
        for m in (1, 2):
            em = e[e.risk_today * e.n_contracts * m <= (900.0 if m > 1 else 1e9)]
            i = pl.route(em)[["tin", "tout", "net_today"]].assign(net_today=lambda x: x.net_today * m)
            nm = n.assign(net_today=n.net_today * m) if (m == 1 or NIGHT_RISK * (1.5 if kind == "S4" else 1) * m <= 900.0) else n.iloc[0:0]
            stop = 400.0 if m == 1 else 700.0
            SER[(kind, m, False)] = fds(i, stop).to_dict(); SER[(kind, m, True)] = fds(pd.concat([i, nm], ignore_index=True), stop).to_dict()
    def run(kind, start_from="2010-07-01", start_to="2022-01-01"):
        keys = [k for k in SER if k[0] == kind]
        days = sorted(set().union(*[set(SER[k]) for k in keys])); ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
        for s0 in pd.date_range(start_from, start_to, freq="MS"):
            a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
            bal = 0.0; paid = False; since = 0.0; usd = 0.0; closed = False; low = 0.0
            for x in days[a:b]:
                m = 2 if bal >= 4000 else 1
                p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0); bal += p; since += p
                if not paid: low = min(low, bal)
                if bal <= (0.0 if paid else -2000.0): closed = True; break
                if (since > 0 or not paid) and bal - 6000.0 >= 250.0:
                    w = min(1500.0, bal - 6000.0); bal -= w; usd += w; paid = True; since = 0.0
            rows.append((usd, closed, low <= -1500.0))
        r = pd.DataFrame(rows, columns=["usd", "closed", "near"])
        return dict(usd=round(float(r.usd.mean()), 0), closed=round(float(r.closed.mean()), 3), near=round(float(r.near.mean()), 3))
    return dict(S0=run("S0"), S3=run("S3"), S4=run("S4"), half1=run("S0", "2010-07-01", "2016-06-01"), half2=run("S0", "2016-07-01", "2022-01-01"))


out = {}
for v in ("base", "A", "B", "C", "A+B", "A+C"):
    d = variant("" if v == "base" else v)
    out[v] = dict(evaluation=eval_track(d), funded=funded_track(d))
    e, f = out[v]["evaluation"], out[v]["funded"]
    print(f"{v:5s} EVAL pass {e['all']} (H1 {e['half1']} H2 {e['half2']}, fail {e['fail']}) | FUNDED $24m {f['S0']['usd']} closed {f['S0']['closed']} near {f['S0']['near']} "
          f"| S3 $ {f['S3']['usd']} cl {f['S3']['closed']} | S4 $ {f['S4']['usd']} cl {f['S4']['closed']} | halves $ {f['half1']['usd']} / {f['half2']['usd']}", flush=True)
b = out["base"]
for v in ("A", "B", "C", "A+B", "A+C"):
    c = out[v]; f, bf, e, be = c["funded"], b["funded"], c["evaluation"], b["evaluation"]
    c["adopt_funded"] = bool(all(f[h]["usd"] >= 1.05 * bf[h]["usd"] for h in ("half1", "half2")) and all(f[k]["closed"] <= bf[k]["closed"] + 0.005 for k in ("S0", "S3", "S4"))
                             and f["S0"]["near"] <= bf["S0"]["near"] and e["all"] >= be["all"] - 1 and e["half1"] >= be["half1"] - 2 and e["half2"] >= be["half2"] - 2)
    c["adopt_evaluation"] = bool(e["half1"] >= be["half1"] + 2 and e["half2"] >= be["half2"] + 2)
ok = [v for v in ("A", "B", "C", "A+B", "A+C") if out[v]["adopt_funded"]]
out["selected_funded"] = max(ok, key=lambda v: out[v]["funded"]["S0"]["usd"]) if ok else None
out["selected_evaluation"] = [v for v in ("A", "B", "C", "A+B", "A+C") if out[v]["adopt_evaluation"]]
print("adopt funded:", {v: out[v]["adopt_funded"] for v in ("A", "B", "C", "A+B", "A+C")}, "-> selected", out["selected_funded"], "| adopt evaluation:", out["selected_evaluation"])
(pl.ROOT / "reports/V53_IMPROVE_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

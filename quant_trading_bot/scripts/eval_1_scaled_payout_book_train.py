"""eval_1 (Claude, 2026-11-10): can the payout book, scaled up, pass the $50K Static Daily Payouts+ evaluation? TRAINING 2010-23 only.

PRE-DECLARED (before results). Evaluation rules (Topstep Labs): target $4,000; static floor -$2,000 checked on UNREALISED P&L in real time;
DLL $1,000 (the position is flattened when the day reaches -$1,000; not a failure); 55% consistency (the target rises to best day / 0.55 when
that is larger); 90 calendar days; no resets.
Book = base R trades (v5.2 + overnight dip 0.55% stop), re-expressed at today's price. Size per trade = min(k x its base contracts,
floor($900 / stop risk per micro)) for intraday; overnight min(k, floor($900 / its stop risk per micro)); account stop min($400 x k, $700) on
realised same-day P&L. k in {2, 3, 4, 5, 6} x overnight leg on | off = 10 cells.
Intraday floor check: each trade's worst open loss (MAE) is measured on 1-minute bars between its entry and exit (overnight: also capped at its
stop). A trade fails the account if realised balance + its MAE <= -$2,000; the DLL flattens a trade at the price where the day reaches -$1,000.
Every trading session in 2010-06..2023-09 is a start. Report pass / fail / timeout shares within 90 days and median sessions to pass.
SELECTION: the cell with the highest pass share; ADOPT it only if its pass share is >= 40% in BOTH halves of the starts (2010-06..2016-12,
2017-01..2023-09). (Reference: the best earlier evaluation result was ~33% pass over ~13 months, Book D+.)
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl
import payout_17_bond_filter_train as p17

P10 = p17.ns["ns"]                                   # payout_10 namespace: 1-minute bars and the overnight trades
base = p17.base_intra; ov = P10["ov"]
mnq, mes = P10["m1"], P10["mes1"]
BARS = {}
for k, b in (("MNQ", mnq), ("MES", mes)):
    BARS[k] = (pd.to_datetime(b.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), b.open.to_numpy(float), b.high.to_numpy(float), b.low.to_numpy(float))


def mae_pct(inst, tin, tout, side, entry):
    ts, O, H, L = BARS[inst]; i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value))
    if i1 <= i0: return 0.0
    worst = L[i0:i1].min() if side > 0 else H[i0:i1].max()
    return min(0.0, side * (worst - entry) / entry)


# intraday trades of the routed base R book (v5.2 rule: skip stop risk > $300 per micro, then route)
intra = pl.route(base[base.risk_today <= 300.0]).copy()
intra["per_micro"] = intra.net_today / intra.n_contracts
intra["mae_per_micro"] = [(mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst] for r in intra.itertuples()]
# overnight nights (payout_10 nights(0.0055) re-derived with MAE)
ts, O, H, L = BARS["MNQ"]; rows = []
for t in ov:
    e_raw = float(t["entry_price"]) - pl.ADV; x_raw = float(t["exit_price"]) + pl.ADV
    tin, tout = pd.Timestamp(t["entry_ts"]), pd.Timestamp(t["exit_ts"]); stop = e_raw * (1 - 0.0055)
    i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value)); hit = np.nonzero(L[i0:i1] <= stop)[0]
    if len(hit): j = i0 + int(hit[0]); x_raw = min(stop, O[j]) if j > i0 else stop; lowest = x_raw
    else: lowest = L[i0:i1].min() if i1 > i0 else e_raw
    pm = (((x_raw - e_raw) / e_raw) * pl.TODAY["MNQ"] - 2 * pl.ADV) * pl.MULT["MNQ"] - pl.FEE
    mae = (min(0.0, (lowest - e_raw) / e_raw) * pl.TODAY["MNQ"] - pl.ADV) * pl.MULT["MNQ"]
    rows.append(dict(tin=tin.tz_convert(pl.NY), tout=tout.tz_convert(pl.NY), per_micro=pm, mae_per_micro=min(mae, pm), n_contracts=1.0, night=True))
nights = pd.DataFrame(rows)
NIGHT_RISK = abs(float(p17.stop_loss_level))
check = pd.concat([intra[["tin", "tout", "net_today"]], p17.N0[["tin", "tout", "net_today"]]], ignore_index=True)
assert abs(nights.per_micro.sum() - p17.N0.net_today.sum()) < 1e-6, "overnight re-derivation differs from payout_17"


def trades(k, night_on):
    a = intra.assign(q=np.minimum(k * intra.n_contracts, np.floor(900.0 / intra.risk_today)), night=False)
    parts = [a[["tin", "tout", "per_micro", "mae_per_micro", "q", "night", "n_contracts"]]]
    if night_on:
        qn = min(k, int(900.0 // NIGHT_RISK))
        if qn >= 1: parts.append(nights.assign(q=float(qn))[["tin", "tout", "per_micro", "mae_per_micro", "q", "night", "n_contracts"]])
    t = pd.concat(parts, ignore_index=True)
    t = t[t.q >= 1].copy()
    # per_micro of intraday rows is per base contract unit; scale: net = per_micro * q ; mae = mae_per_micro * q
    t["net"] = t.per_micro * t.q; t["mae"] = t.mae_per_micro * t.q
    t["day"] = t.tout.dt.date
    return t.sort_values("tin").reset_index(drop=True)


SESS = sorted(set(pd.to_datetime(mnq.timestamp_utc, utc=True).dt.tz_convert(pl.NY).dt.date))
SESS = [d for d in SESS if pd.Timestamp(d).dayofweek < 5 and pd.Timestamp("2010-06-07").date() <= d <= pd.Timestamp("2023-09-29").date()]


def evaluate(k, night_on):
    t = trades(k, night_on); stop = min(400.0 * k, 700.0)
    by_day = {d: g for d, g in t.groupby("day")}; tdays = sorted(by_day)
    tix = pd.to_datetime(pd.Series(tdays).astype(str)).to_numpy(); out = []
    for s in SESS:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date()
        a = int(np.searchsorted(tix, np.datetime64(pd.Timestamp(s)))); bal = 0.0; best = 0.0; res = "timeout"; when = None
        for d in tdays[a:]:
            if d >= end: break
            day = 0.0
            for r in by_day[d].itertuples():
                if day <= -stop or day <= -1000.0: break
                if bal + day + r.mae <= -2000.0: res = "fail"; break
                if day + r.mae <= -1000.0: day = -1000.0; break          # DLL flattens the trade
                day += r.net
            if res == "fail": break
            bal += max(day, -1000.0); best = max(best, day)
            if bal <= -2000.0: res = "fail"; break
            if bal >= max(4000.0, best / 0.55): res = "pass"; when = d; break
        out.append((s, res, None if when is None else int(np.busday_count(s, when)) + 1))
    r = pd.DataFrame(out, columns=["start", "res", "sess"])
    def sh(m): return {o: round(100 * float((r.res[m] == o).mean()), 1) for o in ("pass", "fail", "timeout")}
    h1 = r.start < pd.Timestamp("2017-01-01").date()
    return dict(all=sh(np.ones(len(r), bool)), half1=sh(h1.to_numpy()), half2=sh((~h1).to_numpy()), starts=len(r),
                median_sessions_to_pass=float(r.sess.dropna().median()) if r.sess.notna().any() else None,
                p25_sessions_to_pass=float(r.sess.dropna().quantile(.25)) if r.sess.notna().any() else None)


out = {}
for k in (2, 3, 4, 5, 6):
    for night_on in (True, False):
        name = f"k{k} | overnight {'on' if night_on else 'off'}"; c = out[name] = evaluate(k, night_on)
        print(f"{name:20s} pass/fail/timeout {c['all']} | half1 {c['half1']['pass']} half2 {c['half2']['pass']} | median sessions {c['median_sessions_to_pass']} p25 {c['p25_sessions_to_pass']}", flush=True)
best = max(out, key=lambda n: out[n]["all"]["pass"])
out["summary"] = dict(best=best, adopt=bool(out[best]["half1"]["pass"] >= 40 and out[best]["half2"]["pass"] >= 40))
print(out["summary"])
(pl.ROOT / "reports/EVAL_1_SCALED_PAYOUT_BOOK_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

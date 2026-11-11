"""eval_harness (Claude, 2026-11-11): shared tools for $50K Static Combine research. TRAINING 2010-23 only.

!! NEW WORK: use pass_rate(..., v2=True) and set os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06" BEFORE importing this module. The default v1
day simulator has a look-ahead and an unstable tie order (eval_28), and the default loader skips Jan 1 - May 5, 2019. Defaults are kept only
so earlier results reproduce (54.5 / 65.6 v1 vs 49.7 / 59.4 corrected).

1) screen(daily) - seconds, no heavy load. The cheap gate learned in eval_13: a new stream can only raise the pass rate if it raises the
   book's DAILY Sharpe. `daily` = pd.Series of $ per micro per session (index = python dates, trades counted on their exit day). Compared
   with the eval_8 book at k3 (reports/EVAL_BOOK_DAILY_TRAINING.csv, written by Harness().save_daily()). Returns own Sharpe, correlation,
   combined Sharpe at 0.25..3 micros, and the lift per half. SCREEN PASS = best lift >= +0.007 (5% of 0.141) on all sessions AND lift > 0
   at that weight in BOTH halves (2010-16, 2017-23).
2) Harness() - ~5 minutes to load. The eval_8 book and the eval_13 overlap simulator (reproduces the incumbent 54.5 / 65.6 exactly).
     H.PRE    pre-route book trades (column `sleeve`), H.NIGHTS overnight leg, H.build_book(pre, nights=True) -> routed book frame
     H.pass_rate(book, extra=None, nsize="F1", rule=None) -> {h1, h2} (pass / fail / timeout %, n starts)
   extra = a concurrent stream (its own position next to the book). Columns: tin, tout (tz-aware America/New_York), per_micro ($ per
   micro after costs at today's prices), mae_per_micro ($ per micro, <= 0, incl. exit costs), risk_today ($ stop risk per micro),
   n_contracts (base size, normally 1). nsize: "F1" / "F2" fixed micros, "K" = the book's multiplier k; always capped at floor($900 / risk).
Protocol for anything adopted: pre-declare cells in the script docstring; 2-fold (pick on 2010-16 starts, report on 2017-23 and vice
versa); adopt only if BOTH out-of-fold halves >= incumbent + 1.0 point. Never load 2024+ data.
"""
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "reports/EVAL_BOOK_DAILY_TRAINING.csv"
H1_END = pd.Timestamp("2017-01-01").date()
WEIGHTS = (0.25, 0.5, 1.0, 2.0, 3.0)


def _sr(x):
    s = float(x.std()); return float(x.mean()) / s if s > 0 else 0.0


def screen(daily, name="candidate"):
    b = pd.read_csv(DAILY, parse_dates=["day"]); b["day"] = b.day.dt.date; book = b.set_index("day").k3
    n = pd.Series(daily, dtype=float); n.index = [pd.Timestamp(i).date() for i in n.index]; n = n.groupby(level=0).sum()
    outside = int((~n.index.isin(book.index)).sum()); n = n.reindex(book.index, fill_value=0.0)
    h1 = np.array([d < H1_END for d in book.index])
    res = dict(name=name, active_days=int((n != 0).sum()), days_outside_book_calendar=outside, mean=round(float(n.mean()), 2),
               sd=round(float(n.std()), 1), sr=round(_sr(n), 4), sr_book=round(_sr(book), 4), rho=round(float(book.corr(n)), 3), halves={})
    comb = {w: _sr(book + w * n) for w in WEIGHTS}; res["comb_sr"] = {w: round(v, 4) for w, v in comb.items()}
    bw = max(comb, key=comb.get); res["best_w"] = bw; res["lift"] = round(comb[bw] - _sr(book), 4)
    for nm, m in (("h1", h1), ("h2", ~h1)):
        bb, nn = book[m], n[m]
        res["halves"][nm] = dict(sr=round(_sr(nn), 4), sr_book=round(_sr(bb), 4), rho=round(float(bb.corr(nn)), 3),
                                 lift_at_best_w=round(_sr(bb + bw * nn) - _sr(bb), 4))
    res["screen_pass"] = bool(res["lift"] >= 0.007 and all(res["halves"][h]["lift_at_best_w"] > 0 for h in ("h1", "h2")))
    return res


class Harness:
    def __init__(self):
        s9 = (ROOT / "scripts/eval_9_optimal_sizing_train.py").read_text(encoding="utf-8").split("\n# ---------------- DP")[0]
        E9 = {"__name__": "harness", "__file__": str(ROOT / "scripts/eval_9_optimal_sizing_train.py")}; exec(s9, E9)
        self.E9 = E9; self.pl = E9["pl"]; self.A, self.B, self.SESS = E9["A"], E9["B"], E9["SESS"]; self.DEF_END = E9["DEF_END"]
        E5 = E9["E"]; self.NIGHTS, self.NIGHT_RISK = E5["NIGHTS"], E5["NIGHT_RISK"]
        self.PRE = pd.concat([E9["variant"]("A")] + E9["SLV"], ignore_index=True)
        self.COLS = ["tin", "tout", "per_micro", "mae_per_micro", "n_contracts", "risk_today"]
        self.BOOK = self.build_book(self.PRE)

    @staticmethod
    def route_strict(df):
        """Live strict_1c rule (ensemble_paper.run_routed): by decision time then priority, skip a trade decided before the latest exit of
        any accepted trade - never two positions at once (eval_30-32: the evaluation improvement of 2026-11-11)."""
        keep = []; until = None
        for r in df.sort_values(["dec", "prio"], kind="stable").itertuples():
            if until is not None and r.dec < until: continue
            until = r.tout if until is None else max(until, r.tout); keep.append(r.Index)
        return df.loc[keep]

    @staticmethod
    def route_strict_causal(df):
        """CAUSAL one-position rule (Claude 2026-11-11, eval_36). route_strict sorts by `dec` = the decision BAR'S START label, but a signal
        is known only at the bar close (= tin), so a 60m trade labelled 10:00 (known 11:00) could block a 15m trade known at 10:15 - a
        look-ahead. Here: process trades by tin (the moment the signal is known and filled), then priority; take a trade only if no accepted
        trade is open at that moment (accepted.tout > tin), and only one trade per entry minute."""
        keep = []; until = None; last_tin = None
        for r in df.sort_values(["tin", "prio"], kind="stable").itertuples():
            if until is not None and (r.tin < until or r.tin == last_tin): continue
            until = r.tout if until is None else max(until, r.tout); last_tin = r.tin; keep.append(r.Index)
        return df.loc[keep]

    def build_book(self, pre, nights=True, strict=False):
        pre = pre[pre.risk_today <= 300.0]
        if strict == "causal": r = self.route_strict_causal(pre).copy()
        else: r = (self.route_strict(pre) if strict else self.pl.route(pre)).copy()
        r["per_micro"] = r.net_today / r.n_contracts
        parts = [r[self.COLS + ["sleeve"]]]
        if nights: parts.append(self.NIGHTS.assign(n_contracts=1.0, risk_today=self.NIGHT_RISK, sleeve="NIGHT")[self.COLS + ["sleeve"]])
        return pd.concat(parts, ignore_index=True).assign(noise=False)

    @staticmethod
    def _per_day(df):
        df = df.copy(); df["day"] = df.tout.dt.date; df = df.sort_values("tin")
        df["a"] = df.tin.map(lambda x: x.value); df["b"] = df.tout.map(lambda x: x.value)
        return {k: (g.a.to_numpy(), g.b.to_numpy(), g.per_micro.to_numpy(float), g.mae_per_micro.to_numpy(float), g.n_contracts.to_numpy(float),
                    g.risk_today.to_numpy(float), g.noise.to_numpy(bool)) for k, g in df.groupby("day")}

    @staticmethod
    def sim_day(x, k, nsize="F1"):
        a, b, per, mae, n, risk, nz = x
        cap = np.floor(900.0 / risk)
        q = np.where(nz, np.minimum({"K": k, "F1": 1.0, "F2": 2.0, "F3": 3.0}[nsize], cap), np.minimum(k * n, cap))
        bk = ~nz; stop = 400.0 if np.all(q[bk] <= n[bk]) else 700.0
        acc = []; w = 0.0; dll = False
        for j in range(len(per)):
            if q[j] < 1: continue
            if not nz[j]:
                realised = sum(per[i] * q[i] for i in acc if not nz[i]) + sum(per[i] * q[i] for i in acc if nz[i] and b[i] <= a[j])
                opn = sum(min(0.0, mae[i] * q[i]) for i in acc if nz[i] and b[i] > a[j])
            else:
                realised = sum(per[i] * q[i] for i in acc if b[i] <= a[j])
                opn = sum(min(0.0, mae[i] * q[i]) for i in acc if b[i] > a[j])
            if realised <= -stop or realised <= -1000.0: break
            worst = realised + mae[j] * q[j] + opn
            w = min(w, worst)
            if worst <= -1000.0: dll = True; break
            acc.append(j)
        p = -1000.0 if dll else max(sum(per[i] * q[i] for i in acc), -1000.0)
        return p, w

    @staticmethod
    def sim_day_v2(x, k, nsize="F1"):
        """Corrected day semantics (Claude 2026-11-11, eval_28). v1 (sim_day) treats book trades as strictly sequential: the daily stop and
        DLL checks before trade j count the FINAL P&L of every earlier accepted trade, even one still open at j's entry (341 such entries in
        the eval_8 book) - a look-ahead - and same-minute ties (269 days) are ordered by an unstable sort, so results move ~3 points with
        the frame's row count. v2: (1) a trade is realised for trade j only if it closed before j's entry (exit < entry, or exit = entry
        with an earlier entry); (2) open trades add their MAE to the DLL / floor worst case (conservative, as v1 did for noise trades);
        (3) MAE is capped at the trade's final P&L (831 trades had MAE better than their final loss, 319 of them stopped inside the
        entry minute). Order-invariant for ties."""
        a, b, per, mae, n, risk, nz = x
        mae = np.minimum(mae, per)
        cap = np.floor(900.0 / risk)
        q = np.where(nz, np.minimum({"K": k, "F1": 1.0, "F2": 2.0, "F3": 3.0}[nsize], cap), np.minimum(k * n, cap))
        bk = ~nz; stop = 400.0 if np.all(q[bk] <= n[bk]) else 700.0
        acc = []; w = 0.0; dll = False
        for j in range(len(per)):
            if q[j] < 1: continue
            done = [i for i in acc if b[i] < a[j] or (b[i] == a[j] and a[i] < a[j])]
            realised = sum(per[i] * q[i] for i in done)
            opn = sum(min(0.0, mae[i] * q[i]) for i in acc if i not in done)
            if realised <= -stop or realised <= -1000.0: break
            worst = realised + mae[j] * q[j] + opn
            w = min(w, worst)
            if worst <= -1000.0: dll = True; break
            acc.append(j)
        p = -1000.0 if dll else max(sum(per[i] * q[i] for i in acc), -1000.0)
        return p, min(w, p)

    def _evaluate(self, DAY, starts, td, tix, rule):
        res = []; days_to_pass = []
        for s in starts:
            end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(tix, np.datetime64(pd.Timestamp(s))))
            bal = 0.0; best = 0.0; out = "timeout"
            for dd in td[i:]:
                if dd >= end: break
                k = rule(bal, (dd - s).days, max(4000.0, best / 0.55), 0); p, w = DAY[k][dd]
                if bal + min(w, p) <= -2000.0: out = "fail"; break
                bal += p; best = max(best, p)
                if bal >= max(4000.0, best / 0.55): out = "pass"; days_to_pass.append((dd - s).days); break
            res.append(out)
        x = pd.Series(res)
        return dict(pass_=round(100 * float((x == "pass").mean()), 1), fail=round(100 * float((x == "fail").mean()), 1),
                    timeout=round(100 * float((x == "timeout").mean()), 1), n=len(x),
                    median_days=float(np.median(days_to_pass)) if days_to_pass else None)

    def pass_rate(self, book=None, extra=None, nsize="F1", rule=None, ks=(1, 2, 3, 5), v2=False):
        """v2=True: corrected day semantics (sim_day_v2) and a stable tie order. Default v1 reproduces the incumbent 54.5 / 65.6."""
        book = self.BOOK if book is None else book; rule = rule or self.DEF_END
        frame = book[self.COLS].assign(noise=False)
        if extra is not None and len(extra):
            e = extra.copy()
            if "n_contracts" not in e: e["n_contracts"] = 1.0
            frame = pd.concat([frame, e[self.COLS].assign(noise=True)], ignore_index=True)
        if v2: frame = frame.sort_values(["tin", "tout", "per_micro"], kind="stable").reset_index(drop=True)
        PD = self._per_day(frame); td = sorted(PD); tix = pd.to_datetime(pd.Series(td).astype(str)).to_numpy()
        sim = self.sim_day_v2 if v2 else self.sim_day
        DAY = {k: {dd: sim(PD[dd], float(k), nsize) for dd in td} for k in ks}
        return dict(h1=self._evaluate(DAY, self.A, td, tix, rule), h2=self._evaluate(DAY, self.B, td, tix, rule))

    def save_daily(self):
        PD = self._per_day(self.BOOK[self.COLS].assign(noise=False))
        k3 = pd.Series({d: self.sim_day(PD[d], 3.0)[0] for d in PD}).reindex(self.SESS, fill_value=0.0)
        k1 = pd.Series({d: self.sim_day(PD[d], 1.0)[0] for d in PD}).reindex(self.SESS, fill_value=0.0)
        pd.DataFrame(dict(day=self.SESS, k3=k3.to_numpy(), k1=k1.to_numpy())).to_csv(DAILY, index=False)
        return k3, k1


if __name__ == "__main__":
    H = Harness(); r = H.pass_rate(); print("incumbent via harness", r, flush=True)
    assert r["h1"]["pass_"] == 54.5 and r["h2"]["pass_"] == 65.6, "harness does not reproduce the incumbent"
    k3, k1 = H.save_daily(); print("saved", DAILY, "k3 SR", round(_sr(k3), 4), "k1 SR", round(_sr(k1), 4), flush=True)
    for m in ("P", "R"):   # sanity: the eval_13 noise ledgers must fail the screen
        t = pd.read_csv(ROOT / f"reports/EVAL_13_NOISE_MNQ_{m}_TRADES_TRAINING.csv")
        d = pd.to_datetime(t.tout, utc=True).dt.tz_convert("America/New_York").dt.date
        print("screen noise", m, screen(t.per_micro.groupby(d).sum(), f"noise_{m}"), flush=True)

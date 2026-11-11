"""eval_7 (Claude, 2026-11-10): two more ways to raise P(pass within 90 days). TRAINING 2010-23 only.

PRE-DECLARED (before results). Simulator and starts as eval_5 (v5.3 book, 1-minute MAE floor check, DLL $1,000, 55% consistency, 90 days).
PART A - PRODUCT: the $50K Daily Payouts+ Combine's other drawdown choice, End-of-Day TRAILING: target $3,000, floor = min($0, best
  end-of-day balance - $2,000), checked against each trade's open loss; consistency 55% of the target. Same v5.3 book at k in {2, 3, 4, 5}.
  Reported beside the Static $4,000 results at the same k. (The funded side of the EOD version is different and is not judged here.)
PART B - MORE SLEEVES (greedy forward selection): candidate pool = replicated paper sleeves not yet tried in the book: MES_MOM_3c,
  MNQ_BRK_E_2c, MNQ_VOL_1c, MNQ_E57_1c, MNQ_HYB_C_1c (Codex), AG_MORN30, AG_TRD30C, AG_TRD60C (Antigravity), each at 1 micro with its own
  candidate's VIX day filter, ranked after v5.3's sleeves in the 1-position router, Static $4,000 at k = 3.
  Step: add the candidate with the highest 2010-16 pass share if it beats the current book's 2010-16 pass share by >= 1 point; repeat up to
  3 additions. CONFIRM the final book on 2017-23: pass share >= v5.3 + 2 points there and overall pass share >= v5.3's.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/eval_5_pass_rate_train.py").read_text(encoding="utf-8").split("\nTAB = {")[0]
E = {"__name__": "e7", "__file__": str(ROOT / "scripts/eval_5_pass_rate_train.py")}; exec(src, E)
pl, variant, table, evaluate, size_k, mae_pct, base0, SESS = (E[k] for k in ("pl", "variant", "table", "evaluate", "size_k", "mae_pct", "base0", "SESS"))
P10 = E["P10"]; ep, bars_for, START = P10["ep"], P10["bars_for"], P10["START"]
H1_END = pd.Timestamp("2017-01-01").date()


def eod_eval(tab, k):
    by, td, tix = tab; f = size_k(k); res = []
    for s in SESS:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(tix, np.datetime64(pd.Timestamp(s))))
        bal = 0.0; peak = 0.0; best = 0.0; out = "timeout"
        for d in td[i:]:
            if d >= end: break
            floor = min(0.0, peak - 2000.0); per, mae, n, risk = by[d]; q = f(n, risk); stop = 400.0 if np.all(q <= n) else 700.0; day = 0.0
            for j in range(len(per)):
                if q[j] < 1: continue
                if day <= -stop or day <= -1000.0: break
                if bal + day + mae[j] * q[j] <= floor: out = "fail"; break
                if day + mae[j] * q[j] <= -1000.0: day = -1000.0; break
                day += per[j] * q[j]
            if out == "fail": break
            bal += max(day, -1000.0); best = max(best, day)
            if bal <= floor: out = "fail"; break
            peak = max(peak, bal)
            if bal >= max(3000.0, best / 0.55): out = "pass"; break
        res.append((s, out))
    r = pd.DataFrame(res, columns=["s", "o"]); h1 = (r.s < H1_END).to_numpy()
    sh = lambda m: round(100 * float((r.o[m] == "pass").mean()), 1)
    return dict(all=sh(np.ones(len(r), bool)), h1=sh(h1), h2=sh(~h1), fail=round(100 * float((r.o == "fail").mean()), 1), timeout=round(100 * float((r.o == "timeout").mean()), 1))


out = {"part_a": {}, "part_b": {}}
T53 = table(variant("A"))
for k in (2, 3, 4, 5):
    st = evaluate(T53, (lambda k: lambda bal, day, tgt: size_k(k))(k)); eo = eod_eval(T53, k)
    out["part_a"][f"k{k}"] = dict(static_4k=st, eod_trailing_3k=eo)
    print(f"A k{k}: STATIC $4k pass {st['all']} (H1 {st['h1']} H2 {st['h2']}, fail {st['fail']}, timeout {st['timeout']}) | EOD $3k pass {eo['all']} (H1 {eo['h1']} H2 {eo['h2']}, fail {eo['fail']}, timeout {eo['timeout']})", flush=True)

# ---------------- PART B
POOL = {"MES_MOM_3c": "portfolio_e", "MNQ_BRK_E_2c": "portfolio_e", "MNQ_VOL_1c": "ensemble_epsilon", "MNQ_E57_1c": "ensemble_epsilon",
        "MNQ_HYB_C_1c": "ensemble_beta", "AG_MORN30_1c": "ag_quad", "AG_TRD30C_1c": "ag_arch_c", "AG_TRD60C_1c": "ag_arch_c"}
SLV = {}
for prio, (name, key) in enumerate(POOL.items(), start=10):
    spec = ep.CANDIDATES[key]; sl = next(s for s in spec["sleeves"] if s["name"] == name)
    flt = bool(spec.get("day_filter")) and not sl.get("day_filter_exempt", False)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl, name=name), prio, flt)); x["n_contracts"] = 1.0
    x["mae_per_micro"] = [(mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst] for r in x.itertuples()]
    SLV[name] = x[base0.columns]
    n = x.net_today.to_numpy(); print(f"sleeve {name}: {len(x)} trades, ${n.mean():.1f}/trade, PF {n[n > 0].sum() / -n[n < 0].sum():.2f}, day filter {flt}", flush=True)
fixed3 = lambda bal, day, tgt: size_k(3)
cur_names, cur = [], variant("A"); cur_res = evaluate(table(cur), fixed3); base_res = cur_res
out["part_b"]["v5.3"] = base_res; steps = []
for step in range(3):
    trial = {}
    for name in POOL:
        if name in cur_names: continue
        trial[name] = evaluate(table(pd.concat([cur, SLV[name]], ignore_index=True)), fixed3)
        print(f"B step {step + 1} + {name}: pass {trial[name]['all']} (H1 {trial[name]['h1']} H2 {trial[name]['h2']})", flush=True)
    best = max(trial, key=lambda n: trial[n]["h1"])
    steps.append(dict(step=step + 1, tried=trial, best=best, added=bool(trial[best]["h1"] >= cur_res["h1"] + 1.0)))
    if not steps[-1]["added"]: break
    cur_names.append(best); cur = pd.concat([cur, SLV[best]], ignore_index=True); cur_res = trial[best]
out["part_b"]["steps"] = steps; out["part_b"]["final_sleeves_added"] = cur_names; out["part_b"]["final"] = cur_res
out["part_b"]["confirmed"] = bool(cur_names and cur_res["h2"] >= base_res["h2"] + 2.0 and cur_res["all"] >= base_res["all"])
print("B final:", cur_names, cur_res, "confirmed:", out["part_b"]["confirmed"], flush=True)
(ROOT / "reports/EVAL_7_PRODUCT_AND_SLEEVES_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

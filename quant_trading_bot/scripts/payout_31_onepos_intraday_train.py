"""payout_31 (Claude, 2026-11-11): one position at a time on the funded account, re-asked on the intraday simulator. TRAINING only.

payout_26 rejected one-position routing for the funded rule (-16% dollars) on the old end-of-day simulator, which cannot see stacked open
losses. payout_30's intraday simulator can (Fortress 4X: 7.6 DLL-liquidated days per 24-month window). ONE cell: F4X with causal
one-position routing (eval_harness.route_strict_causal), everything else exactly as payout_30's F4X.
PRE-DECLARED: same qualification rule as payout_30 vs F4X (S0 withdrawn >= 1.03x in both halves, S0 value >= F4X in both halves, S3 and S4
withdrawn >= F4X, closure <= F4X + 0.005). Qualifies -> recommend the routing change for the funded card; otherwise posthoc stays.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/payout_30_intraday_funded_train.py").read_text(encoding="utf-8").split("STACK = pd.concat")[0]
G = dict(__name__="payout_31", __file__=str(ROOT / "scripts/payout_30_intraday_funded_train.py")); exec(src, G)
pl, fc, tables, base = G["pl"], G["fc"], G["tables"], G["base"]


def onepos(df):
    keep = []; until = None; last = None
    for r in df.sort_values(["tin", "prio"], kind="stable").itertuples():
        if until is not None and (r.tin < until or r.tin == last): continue
        until = r.tout if until is None else max(until, r.tout); last = r.tin; keep.append(r.Index)
    return df.loc[keep]


pl.route = onepos
F4X = dict(ladder=((0, 1), (4000, 2), (4800, 3), (6500, 4)), K=8500.0)
c = {kind: fc.summ(fc.replay({"base": tables(base, kind)}, **F4X)) for kind in ("S0", "S3", "S4")}
F = json.loads((ROOT / "reports/PAYOUT_30_INTRADAY_FUNDED_TRAINING.json").read_text())["cells"]["F4X"]
ok = bool(all(c["S0"][f"usd_{h}"] >= 1.03 * F["S0"][f"usd_{h}"] for h in ("h1", "h2"))
          and all(c["S0"][f"value_{h}"] >= F["S0"][f"value_{h}"] for h in ("h1", "h2"))
          and all(c[s]["usd"] >= F[s]["usd"] for s in ("S3", "S4")) and all(c[s]["closed"] <= F[s]["closed"] + 0.005 for s in ("S0", "S3", "S4")))
s = c["S0"]
print(f"F4X_ONEPOS S0 {s['usd']:.0f} ({s['usd_h1']:.0f}/{s['usd_h2']:.0f}) value {s['value']:.0f} closed {c['S0']['closed']:.3f}/{c['S3']['closed']:.3f}/"
      f"{c['S4']['closed']:.3f} S3 {c['S3']['usd']:.0f} S4 {c['S4']['usd']:.0f} y1 {s['y1_pays']} dll/win {s['dll_days']} | qualifies {ok}", flush=True)
(ROOT / "reports/PAYOUT_31_ONEPOS_INTRADAY_TRAINING.json").write_text(json.dumps(dict(F4X_ONEPOS=c, F4X=F, qualifies=ok, validation_accessed=False,
                                                                                     test_accessed=False), indent=1, default=str))

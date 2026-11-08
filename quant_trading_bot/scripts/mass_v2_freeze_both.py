"""Amendment A1 freeze: keep only configurations that passed G1-G4 under BOTH bar rules (strict and lenient).

Reads runs/mass_v2/results.sqlite + results_lenient.sqlite and their placebo tables, writes
runs/mass_v2/frozen_survivors.json (the file phase_validate reads) after backing up the strict-only list.
Ranking as registered: worst-year net (strict run) desc, then DSR; dedup by strict fingerprint; cap 20.
"""
import json
import shutil
import sqlite3
from pathlib import Path

import os
import pandas as pd

TAG = os.environ.get("MASS_V2_TAG", "")

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs" / "mass_v2"


def g4_ids(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    pl = pd.read_sql("SELECT config_id, payload FROM placebo", con)
    con.close()
    out = {}
    for cid, payload in zip(pl.config_id, pl.payload):
        p = json.loads(payload)
        if p["g4"]:
            out[cid] = p
    return out


strict = g4_ids(RUN / f"results{TAG}.sqlite")
lenient = g4_ids(RUN / f"results_lenient{TAG}.sqlite")
both = sorted(set(strict) & set(lenient))
print(f"G4 survivors: strict {len(strict)}, lenient {len(lenient)}, both {len(both)}")
best = {}
for cid in both:
    s = strict[cid]
    s["lenient"] = {k: lenient[cid][k] for k in ("net", "years_pos", "worst_dd", "trades", "per_trade", "placebo_p95", "annual")}
    key = s["fp"]
    if key not in best or s["worst_dd"] < best[key][1]["worst_dd"]:
        best[key] = (cid, s)
ranked = sorted(best.values(), key=lambda x: (-min(x[1]["annual"]), -(x[1]["dsr"] or 0)))[:20]
if (RUN / f"frozen_survivors{TAG}.json").exists() and not (RUN / f"frozen_survivors_strict{TAG}.json").exists():
    shutil.move(RUN / f"frozen_survivors{TAG}.json", RUN / f"frozen_survivors_strict{TAG}.json")
(RUN / f"frozen_survivors{TAG}.json").write_text(json.dumps(dict(frozen_at=pd.Timestamp.now("UTC").isoformat(), rule="A1: G1-G4 under both bar rules",
                                                        n_both=len(both), n_unique=len(best), frozen=[dict(config_id=c, **p) for c, p in ranked]), indent=1))
for cid, p in ranked:
    q = p["params"]
    print(f"{cid} {q['instrument']} {q['family']} lb{q['lookback']} th{q['threshold']} {q['session_start']}-{q['session_end']} stop{q['stop_atr']} tgt{q['target_r']} hold{q['hold_bars']} trail{q['trailing_atr']} | strict net {p['net']:.0f} +{p['years_pos']} | lenient net {p['lenient']['net']:.0f} +{p['lenient']['years_pos']} dd {p['lenient']['worst_dd']:.0f}")
print(f"frozen {len(ranked)}")

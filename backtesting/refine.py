"""Development-only neighborhood search around the saved v1.2 experiment.

2025 is reused selection data, not independent confirmation. The 2026 audit
never selects parameters. The original v1.2 export is not overwritten here.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
from itertools import product
import json
from pathlib import Path
import random

from .config import StrategyConfig
from . import optimize
from .paths import PARQUET, ROOT


def refinement_configs(parent: StrategyConfig, count=128, seed=1202):
    if parent.mode != "research" or parent.strategy_version != "v1.1":
        raise ValueError("Refinement requires the v1.1-based research derivative")
    candidates, seen = [], set()

    def add(label, cfg):
        serialized = json.dumps(asdict(cfg), sort_keys=True)
        if serialized not in seen:
            seen.add(serialized)
            candidates.append({"id": len(candidates), "label": label, "config": asdict(cfg)})

    add("baseline", optimize.baseline())
    add("saved_v1_2", parent)
    grid = list(product([3., 3.5, 4., 4.5, 5.], [.3, .4, .5, .6, .75], [1.2, 1.5, 1.8, 2.1], [5., 10., 15.]))
    random.Random(seed).shuffle(grid)
    for reward, stop, volume, atr in grid:
        if len(candidates) >= count:
            break
        add(f"refine_rr{reward}_stop{stop}_rvol{volume}_atr{atr}",
            replace(parent, reward_r=reward, stop_atr=stop, breakout_rvol=volume, min_atr_bps=atr))
    return candidates


def strict_validation_score(folds):
    # Promotion conditions are eligibility conditions in this preregistered
    # follow-up, rather than a soft score followed by a failed-gate flag.
    if any(optimize.pnl(f) <= 0 for f in folds):
        return -1e9
    return ORIGINAL_VALIDATION_SCORE(folds)


ORIGINAL_VALIDATION_SCORE = optimize.validation_score


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    parent_snapshot = args.output / "parent_config.json"
    if parent_snapshot.exists():
        parent_bytes = parent_snapshot.read_bytes()
    else:
        parent_bytes = args.parent.read_bytes()
        parent_snapshot.write_bytes(parent_bytes)
    parent = StrategyConfig(**json.loads(parent_bytes))
    protocol = {"name": "v1.2 neighborhood follow-up", "parent_config_sha256": hashlib.sha256(parent_bytes).hexdigest(),
                "number_of_prior_completed_searches": 1, "prior_search_candidates": 256,
                "selection_history": "Parent was selected using 2025 validation; this follow-up reuses 2025 and is not independent",
                "training": "2023-2024", "validation_selection": "2025 H1/H2; both halves must be positive before scoring",
                "audit": "previously inspected 2026; cannot select parameters", "v1_2_export_automatically_overwritten": False}
    optimize.write_json(args.output / "refinement_protocol.json", protocol)
    original_fingerprint = optimize.fingerprint
    snapshot_key = parent_snapshot.resolve().relative_to(ROOT.resolve()).as_posix()

    def source_hashes():
        return {**original_fingerprint(), "refine.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                snapshot_key: hashlib.sha256(parent_snapshot.read_bytes()).hexdigest()}

    optimize.fingerprint = source_hashes
    optimize.candidate_configs = lambda count, seed: refinement_configs(parent, count, seed)
    optimize.validation_score = strict_validation_score
    optimize.run(args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, default=ROOT / "configs/dvs_eth_v1_2.json")
    parser.add_argument("--data", type=Path, default=PARQUET)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/optimization/round2_v1_2_neighborhood")
    parser.add_argument("--candidates", type=int, default=128)
    parser.add_argument("--finalists", type=int, default=24)
    parser.add_argument("--seed", type=int, default=1202)
    args = parser.parse_args()
    if args.candidates < 2 or args.finalists < 1:
        parser.error("At least two candidates and one finalist are required")
    run(args)

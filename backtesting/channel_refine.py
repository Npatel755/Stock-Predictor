"""Small frozen follow-up on the independently tested ETH channel family.

2025 selection and 2026 inspection have already occurred; no fresh-validation
claim is permitted. v1.2 and the previous failed experiments are preserved.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from itertools import product
from pathlib import Path
import random

from .alternative_research import run
from .alternative_strategies import SignalRule
from .paths import PARQUET, ROOT


def channel_candidates(count=24, seed=1304):
    rules = [SignalRule('channel_breakout', lookback=55, slow=200, stop_atr=2., reward_r=3., trail_atr=3.)]
    grid = list(product([40, 55, 80], [2., 3.], [2., 3., 4.], [2., 3., 4.]))
    random.Random(seed).shuffle(grid)
    for length, stop, reward, trailing in grid:
        rule = SignalRule('channel_breakout', lookback=length, slow=200, stop_atr=stop, reward_r=reward, trail_atr=trailing)
        if rule not in rules:
            rules.append(rule)
        if len(rules) >= count:
            break
    return [dict(id=i, label=f'channel{r.lookback}_stop{r.stop_atr}_rr{r.reward_r}_trail{r.trail_atr}', rule=asdict(r))
            for i, r in enumerate(rules)]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=PARQUET)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/optimization/round4_v1_3_channel_refinement')
    args = parser.parse_args()
    protocol = dict(name='v1.3 independent ETH channel refinement', finalists=6, prior_search_slots=420,
                    seed=1304, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    parent_experiment='round3_independent_families_verified; selected channel_breakout_7; failed gate',
                    purpose='Test stop, reward and trailing geometry across broad training regimes; retain original historical gate. No sizing increase.',
                    warning='The family was selected using already-inspected data. 2020-2024 and 2025 are reused selection data; 2026 is already inspected. This does not create new independent evidence.')
    run(args, candidate_universe=channel_candidates(), followup_protocol=protocol)

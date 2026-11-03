"""Explicit follow-up to the historical-profit screen; all data is reused."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from itertools import product
from pathlib import Path
import random

from .alternative_strategies import SignalRule
from .exit_research import freeze
from . import net_profit_research
from .paths import ROOT


def candidates(count=64, seed=1306):
    if count != 64:
        raise ValueError('This frozen follow-up contains 64 configurations')
    rng = random.Random(seed)
    rules = [SignalRule('channel_breakout', lookback=64, slow=200, stop_atr=2., reward_r=3., trail_atr=3.),
             SignalRule('channel_breakout', lookback=96, slow=100, stop_atr=1.5, reward_r=5., trail_atr=3.)]
    grids = [list(product([56, 64, 72], [150, 200], [1.75, 2., 2.25], [2.5, 3., 3.5], [2.5, 3., 3.5])),
             list(product([80, 96], [100, 150], [1.5, 1.75, 2.], [4., 4.5, 5.], [2.5, 3., 3.5]))]
    for grid in grids:
        rng.shuffle(grid)
        added = 0
        for length, slow, stop, reward, trailing in grid:
            r = SignalRule('channel_breakout', lookback=length, slow=slow, stop_atr=stop, reward_r=reward, trail_atr=trailing)
            if r not in rules:
                rules.append(r)
                added += 1
            if added == 31:
                break
    return [dict(id=i, label=f'channel{r.lookback}_ema{r.slow}_stop{r.stop_atr}_rr{r.reward_r}_trail{r.trail_atr}', rule=asdict(r))
            for i, r in enumerate(rules)]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/optimization/round6_profit_refinement')
    args = parser.parse_args()
    args.candidates, args.finalists = 64, 8
    args.output.mkdir(parents=True, exist_ok=True)
    protocol = dict(name='Historical-profit follow-up', prior_search_slots=508, candidate_count=64, seed=1306,
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    prior_evidence='Round5 inspected full-period results: channel64/EMA200/2ATR/3R/trail3 made about $5009 at 2.78% drawdown; channel96/EMA100/1.5ATR/5R/trail3 made about $6291 but exceeded the 5% drawdown eligibility limit.',
                    purpose='Small bounded neighborhoods around two observed geometries; same historical-profit gate and dollar risk. Full 2023-2026 data, including 2026, selects parameters.',
                    warning='Additional adaptive historical selection, not independent validation. Earlier experiments and failed checks are retained. This is not a future-profit claim.')
    freeze(args.output/'followup_protocol.json', protocol)
    original_freeze = net_profit_research.freeze

    def freeze_followup(path, plan):
        if path.name == 'manifest.json':
            plan['prior_search_slots'] = protocol['prior_search_slots']
            plan['followup'] = protocol
            plan['source_hashes']['profit_refine.py'] = protocol['source_sha256']
        return original_freeze(path, plan)

    net_profit_research.freeze = freeze_followup
    net_profit_research.candidates = candidates
    net_profit_research.run(args)

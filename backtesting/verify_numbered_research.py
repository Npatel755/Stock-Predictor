"""Independently reproduce a frozen research winner before saving a version."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from .alternative_strategies import SignalRule, simulate
from .config import StrategyConfig
from .entry_neighborhood import eligible
from .exit_research import freeze
from .frozen_inputs import recorded_path
from .independent_visuals import equity_curve
from .market_data import load_history, utc
from .optimize import pnl, subset, write_json
from .paths import ROOT
from .regime_filters import RegimeFilter, apply_filter, prepare_features
from .reporting import safe_value


def exact(actual, expected, label):
    # JSON checkpoints serialize Timestamp values inside endpoint open positions.
    # Compare the same canonical representation without rounding financial values.
    if safe_value(actual) != expected:
        raise ValueError(f'Fresh replay differs from the frozen metrics: {label}')


def preserve_verification(directory,verification):
    path=directory/'verification.json'
    if path.exists():
        original=json.loads(path.read_text(encoding='utf-8'))
        current=safe_value(verification)
        if original==current:return path
        for key in ['selection_sha256','metrics','benchmark']:
            if original.get(key)!=current.get(key):raise ValueError('Fresh recheck differs from the immutable original certificate')
        # Numbered metadata pins the original certificate hash. A verifier-code
        # update must not silently overwrite that historical evidence.
        digest=hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest()
        path=directory/'verification_rechecks'/f'{digest}.json'
        path.parent.mkdir(exist_ok=True)
        freeze(path,current)
    else:write_json(path,verification)
    return path


def verify(directory: Path, root: Path = ROOT):
    plan = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    selected = json.loads((directory/'selection.json').read_text(encoding='utf-8'))
    summary = json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    if not selected['passed_predeclared_validation_gate']:
        raise ValueError('A failed historical gate cannot be verified as a promotable improvement')
    if plan['selection_window'] != ['2023-01-01', '2026-10-28']:
        raise ValueError('Verification requires the unchanged baseline period')
    for section in ['source_hashes', 'protected_profile_hashes']:
        for name, digest in plan[section].items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
                # The selection driver is not executed by this verifier. Keep
                # its frozen provenance when a later safety guard disables it;
                # the actual execution/feature implementations must still match.
                archived=directory/'sources'/name
                if not archived.exists():archived=root/'reference/source_revisions'/digest/name
                guarded_drivers={'campaign_research.py','entry_neighborhood.py','optimize.py','exit_research.py',
                                 'alternative_research.py','channel_period_research.py','numbered_research.py',
                                 'management_research.py','net_profit_research.py','trend_research.py','filter_research.py'}
                # The only accepted difference is the added entry-point guard;
                # helper functions used in this replay must be byte-equivalent.
                guard='    from .generalization_policy import assert_search_allowed\n    assert_search_allowed(ROOT)\n'
                guarded_original=archived.read_text(encoding='utf-8') if archived.exists() else ''
                current=(root/name).read_text(encoding='utf-8')
                guard_only=current.replace(guard,'',1)==guarded_original
                if not (section=='source_hashes' and name in guarded_drivers and archived.exists()
                        and hashlib.sha256(archived.read_bytes()).hexdigest()==digest and guard_only):
                    raise ValueError(f'Frozen {section} input changed: {name}')
    data_paths={name.replace('\\','/'):recorded_path(root,name,value) for name,value in plan['data_hashes'].items()}
    for filename, key in [('parent.json', 'parent_sha256'), ('baseline.json', 'baseline_sha256')]:
        if hashlib.sha256((directory/filename).read_bytes()).hexdigest() != plan[key]:
            raise ValueError(f'Frozen snapshot changed: {filename}')
    parent = json.loads((directory/'parent.json').read_text(encoding='utf-8'))
    cfg = StrategyConfig(**selected['execution_config'])
    if selected['execution_config'] != parent['execution']:
        raise ValueError('Candidate changed the fixed execution configuration')
    parent_rule = SignalRule(**parent['rule'])
    parent_filters = RegimeFilter(**parent['filters'])
    rule = SignalRule(**selected['candidate']['rule'])
    filters = RegimeFilter(**selected['candidate']['filters'])
    bars, _ = load_history(data_paths['data/ethusd/perpetual/candles.parquet'])
    bars = bars[(bars.timestamp >= utc('2023-01-01')) & (bars.timestamp < utc('2026-10-28'))].reset_index(drop=True)
    signals = apply_filter(prepare_features(bars, rule), filters)
    parent_signals = apply_filter(prepare_features(bars, parent_rule), parent_filters)
    benchmark, evaluation = {}, {}
    for key, bps in [('main', 2.), ('stress4', 4.), ('stress8', 8.)]:
        benchmark[key] = simulate(bars, parent_rule, replace(cfg, slippage_bps=bps), signals=parent_signals)[0]
        exact(benchmark[key], summary['benchmark'][key], f'parent_{key}')
    for key, bps in [('full_period', 2.), ('full_4bp', 4.), ('full_8bp', 8.)]:
        metrics, trades, events = simulate(bars, rule, replace(cfg, slippage_bps=bps), signals=signals)
        exact(metrics, summary['evaluation'][key], key)
        evaluation[key] = metrics
        if key == 'full_period':
            curve = equity_curve(bars, events, cfg)
            if abs(curve.equity.iloc[-1]-metrics['final_equity']) > 1e-6:
                raise ValueError('Visual equity does not reconcile with the broker')
            curve.to_parquet(directory/'verified_equity.parquet', index=False)
            trades.to_csv(directory/'verified_trades.csv', index=False)
            events.to_csv(directory/'verified_events.csv', index=False)
        print(f'VERIFIED {key}: ${pnl(metrics):.2f}', flush=True)
    for name, start, end in [('2025_h1', '2025-01-01', '2025-07-01'), ('2025_h2', '2025-07-01', '2026-01-01'),
                             ('2026_h1', '2026-01-01', '2026-07-01'), ('2026_h2', '2026-07-01', '2026-10-28')]:
        b, f = subset(bars, signals, start, end)
        evaluation[name] = simulate(b, rule, cfg, signals=f)[0]
        exact(evaluation[name], summary['evaluation'][name], name)
    weak_bars, weak_signals = subset(bars, signals, '2026-01-01', '2026-07-01')
    evaluation['2026_h1_4bp'] = simulate(weak_bars, rule, replace(cfg, slippage_bps=4.), signals=weak_signals)[0]
    exact(evaluation['2026_h1_4bp'], summary['evaluation']['2026_h1_4bp'], '2026_h1_4bp')
    earlier, _ = load_history(data_paths['data/ethusd/perpetual_2020_2022/candles.parquet'])
    evaluation['earlier_2020_2022'] = simulate(earlier, rule, cfg, signals=apply_filter(prepare_features(earlier, rule), filters))[0]
    exact(evaluation['earlier_2020_2022'], summary['evaluation']['earlier_2020_2022'], 'earlier_2020_2022')
    checks = {k: v for k, v in evaluation.items() if k != 'full_period'}
    passed = eligible(evaluation['full_period'], checks, benchmark, selected['requested_baseline'])
    if not passed or abs(pnl(benchmark['main'])-selected['exact_reference_net']) > 1e-6:
        raise ValueError('Fresh results fail the frozen improvement gate or exact reference')
    weak8 = simulate(weak_bars, rule, replace(cfg, slippage_bps=8.), signals=weak_signals)[0]
    verification = dict(reproduced_exactly=True, metrics=evaluation, benchmark=benchmark,
                        post_selection_2026_h1_8bp=weak8, post_selection_diagnostic_is_selection_gate=False,
                        selection_sha256=hashlib.sha256((directory/'selection.json').read_bytes()).hexdigest(),
                        verifier_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        protected_versions_unchanged=True, passed_frozen_gate=True,
                        forward_validation=False, pine_compiled=False, tradingview_matched=False)
    preserve_verification(directory,verification)
    print(f"VERIFICATION COMPLETE: net=${pnl(evaluation['full_period']):.2f}; weak-half 8bp diagnostic=${pnl(weak8):.2f}", flush=True)
    return verification


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    verify(parser.parse_args().directory)

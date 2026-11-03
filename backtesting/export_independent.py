"""Export a frozen independent strategy as experimental ETH v1.3 Pine."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from .alternative_strategies import SignalRule
from .config import StrategyConfig
from .optimize import write_json
from .paths import ROOT

TEMPLATE = ROOT/'reference/templates/independent_eth.pine'

def render(rule: SignalRule, config: StrategyConfig, version='v1.3'):
    if version not in {'v1.3', 'v1.4'}:
        raise ValueError('Unsupported independent strategy version')
    if (config.mode != 'research' or config.entry_timing != 'next_open'
            or config.margin_ratio != .2 or not config.risk_includes_costs):
        raise ValueError('Independent export requires cost-aware next-open Research and 20% margin')
    from dataclasses import asdict
    payload = dict(rule=asdict(rule), execution=asdict(config))
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    values = {**asdict(rule), **asdict(config), 'stop_atr': rule.stop_atr, 'reward_r': rule.reward_r,
              'trail_atr': rule.trail_atr, 'max_holding_bars': rule.max_holding_bars,
              'config_hash': digest, 'family_title': rule.family.replace('_', ' ').title(),
              'commission_percent': config.commission_bps/100}
    text = TEMPLATE.read_text(encoding='utf-8')
    text = text.replace('ETH v1.3 |', f'ETH {version} |', 1)
    for token in set(re.findall(r'\{\{(\w+)\}\}', text)):
        value = values[token]
        encoded = json.dumps(value) if token == 'family' else str(value)
        text = text.replace('{{'+token+'}}', encoded)
    if '{{' in text:
        raise ValueError('Unresolved Pine template token')
    return text, payload, digest


def export(directory: Path, version='v1.3'):
    selected_path = directory/'selection.json'
    selected = json.loads(selected_path.read_text(encoding='utf-8'))
    rule = SignalRule(**selected['candidate']['rule'])
    cfg = StrategyConfig(**selected['execution_config'])
    text, payload, digest = render(rule, cfg, version=version)
    historical_profit = selected.get('selection_is_historical_profit_optimization', False)
    if historical_profit:
        text = text.replace('//@version=6\n', '//@version=6\n// Selected by historical 2023-2026 net-profit optimization; 2026 is selection data.\n// This export has no independent forward validation.\n', 1)
    suffix = version.replace('.', '_')
    pine = ROOT/f'reference/ETH_Strategy_{suffix}.pine'
    config_path = ROOT/f'configs/eth_strategy_{suffix}.json'
    meta_path = ROOT/f'configs/eth_strategy_{suffix}.metadata.json'
    if pine.exists() and pine.read_text(encoding='utf-8') != text:
        archive = ROOT/'reference/revisions'/hashlib.sha256(pine.read_bytes()).hexdigest()[:16]
        archive.mkdir(parents=True, exist_ok=True)
        for p in [pine, config_path, meta_path]:
            if p.exists():
                (archive/p.name).write_bytes(p.read_bytes())
    pine.parent.mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    pine.write_text(text, encoding='utf-8')
    write_json(config_path, payload)
    write_json(meta_path, dict(strategy_name=f'ETH {version}', family=rule.family, experiment=directory.name,
                              selected_candidate=selected['candidate']['label'], configuration_sha256=digest,
                              pine_sha256=hashlib.sha256(pine.read_bytes()).hexdigest(),
                              selection_sha256=hashlib.sha256(selected_path.read_bytes()).hexdigest(),
                              passed_predeclared_validation_gate=selected['passed_predeclared_validation_gate'],
                              selection_is_historical_profit_optimization=historical_profit,
                              selection_note=('2023-2026, including 2026, participated in historical net-profit selection; not an untouched audit.'
                                              if historical_profit else 'Historical reused-data selection; inspected 2026 retrospective audit.'),
                              ready_for_funded_trading=False, independent_forward_validation=False,
                              tradingview_parity_verified=False, pine_compilation_verified=False,
                              execution_differences=['Pine omits extra basis-point fill slippage and financing',
                                                     'Pine broker path differs from Python stop-first handling',
                                                     'Time-exit recalculation and symbol quantity/tick rounding remain unreconciled']))
    downloads = ROOT/'downloads'
    downloads.mkdir(exist_ok=True)
    (downloads/f'ETH_Strategy_{suffix}.txt').write_bytes(pine.read_bytes())
    print(f'Exported experimental independent {version}: {pine}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--version', choices=['v1.3', 'v1.4'], default='v1.3')
    args = parser.parse_args()
    export(args.directory, version=args.version)

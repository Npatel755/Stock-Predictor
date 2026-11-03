"""Save each qualifying improvement under the next immutable minor version."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

from .alternative_strategies import SignalRule
from .config import StrategyConfig
from .export_volume_candidate import render_volume
from .optimize import write_json
from .paths import ROOT
from .regime_filters import RegimeFilter
from .trend_pine import render_trend


def save(directory: Path, version: str, root: Path = ROOT):
    if not re.fullmatch(r'v1\.(?:[6-9]|[1-9][0-9]+)', version):
        raise ValueError('Expected a new version, v1.6 or later')
    suffix = version.replace('.', '_')
    destinations = [root/f'configs/eth_strategy_{suffix}.json',
                    root/f'configs/eth_strategy_{suffix}.metadata.json',
                    root/f'reference/ETH_Strategy_{suffix}.pine', root/f'{suffix.upper()}.md',
                    root/f'downloads/ETH_Strategy_{suffix}.txt',
                    root/f'downloads/ETH_Strategy_{suffix}_README.txt',
                    root/f'downloads/ETH_Strategy_{suffix}_TradingView.zip']
    if any(p.exists() for p in destinations):
        raise ValueError('Saved versions are immutable; choose the next version')
    previous = sorted(int(p.stem.split('_')[-1]) for p in (root/'configs').glob('eth_strategy_v1_*.json')
                      if not p.name.endswith('.metadata.json'))
    if not previous or int(version.split('.')[1]) != previous[-1]+1:
        raise ValueError('Use the next consecutive version number')
    selection_path = directory/'selection.json'
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    summary = json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    if not selection['passed_predeclared_validation_gate']:
        raise ValueError('The complete frozen historical gate must pass')
    target = json.loads((root/'configs/research_baseline.json').read_text(encoding='utf-8'))
    metrics = summary['evaluation']['full_period']
    net = metrics['final_equity']-metrics['initial_capital']
    if net <= max(target['requested_net_profit_usd'], target['prior_reference_net_profit_usd']):
        raise ValueError('Must beat the exact current baseline and saved reference')
    verification_path = directory/'verification.json'
    if not verification_path.exists():
        raise ValueError('A fresh reproduction verification is required before saving a version')
    verified = json.loads(verification_path.read_text(encoding='utf-8'))
    selection_digest = hashlib.sha256(selection_path.read_bytes()).hexdigest()
    if (not verified.get('reproduced_exactly') or not verified.get('passed_frozen_gate')
            or verified.get('selection_sha256') != selection_digest
            or verified.get('metrics', {}).get('full_period') != metrics):
        raise ValueError('A matching fresh reproduction verification is required')
    cfg = StrategyConfig(**selection['execution_config'])
    if (cfg.risk_usd, cfg.initial_capital, cfg.max_leverage, cfg.commission_bps,
            cfg.slippage_ticks, cfg.slippage_bps, cfg.swap_daily_bps) != (100.,50000.,5.,4.,2,2.,3.3):
        raise ValueError('Keep capital, risk, leverage and costs unchanged')
    rule = SignalRule(**selection['candidate']['rule'])
    filters = RegimeFilter(**selection['candidate']['filters'])
    from .generalization_policy import assert_promotion_allowed
    from dataclasses import asdict
    assert_promotion_allowed(directory,dict(rule=asdict(rule),execution=asdict(cfg),filters=asdict(filters)),root)
    text, payload, digest = (render_trend if filters.min_trend_gap_bps else render_volume)(rule,cfg,filters)
    text = text.replace('ETH Volume Research | Experimental candidate', f'ETH {version} | Channel research', 1)
    text = text.replace('Experimental filtered candidate; saved v1.4 is unchanged.',
                        f'ETH {version}; earlier numbered strategies are preserved.', 1)
    meta = dict(strategy_name=f'ETH {version}', experiment=directory.name,
                selected_candidate=selection['candidate']['label'], configuration_sha256=digest,
                pine_sha256=hashlib.sha256(text.encode()).hexdigest(),
                selection_sha256=selection_digest,
                reproduction_verification_sha256=hashlib.sha256(verification_path.read_bytes()).hexdigest(),
                computational_reproduction_verified=True,
                entry_filters=payload['filters'], same_period_net_usd=net,
                baseline_net_usd=target['requested_net_profit_usd'], baseline_period=['2023-01-01','2026-10-28'],
                baseline_risk_usd=100., exact_reference_at_selection=target['prior_reference_net_profit_usd'],
                passed_predeclared_validation_gate=True, selection_is_historical_profit_optimization=True,
                selection_note='All 2023-2026 data participated in historical selection; no fresh forward-validation claim.',
                independent_forward_validation=False, ready_for_funded_trading=False,
                pine_compilation_verified=False, tradingview_parity_verified=False)
    note = (f'# ETH {version}\n\nModeled same-period net P&L: **${net:,.2f}**, '
            f"versus {target['prior_reference']} at ${target['prior_reference_net_profit_usd']:,.2f}. "
            'January 1, 2023 through October 27, 2026 UTC; $50,000 capital and $100 risk.\n\n'
            f'Experiment: `{directory.name}`. Earlier versions are unchanged.\n\n'
            'Pine compilation and TradingView matching remain unverified. Pine omits Python extra '
            'basis-point fill slippage, financing and stop-first ambiguity handling. Historical '
            'selection is not independent forward validation.\n')
    for path in destinations:
        path.parent.mkdir(parents=True,exist_ok=True)
    # Git's Windows newline conversion must not invalidate the saved Pine hash.
    attributes = root/'reference/.gitattributes'
    existing_attributes = attributes.read_text(encoding='utf-8') if attributes.exists() else ''
    rule_line = f'ETH_Strategy_{suffix}.pine -text'
    if rule_line not in existing_attributes.splitlines():
        attributes.write_text(existing_attributes.rstrip()+'\n'+rule_line+'\n',encoding='utf-8')
    write_json(destinations[0],payload)
    write_json(destinations[1],meta)
    destinations[2].write_bytes(text.encode('utf-8'))
    destinations[3].write_text(note,encoding='utf-8')
    destinations[4].write_bytes(destinations[2].read_bytes())
    destinations[5].write_text(note,encoding='utf-8')
    with zipfile.ZipFile(destinations[6],'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in destinations[2:6]: archive.write(path,path.name)
    target.update(previous_reference_net_profit_usd=target['prior_reference_net_profit_usd'],
                  previous_requested_net_profit_usd=target['requested_net_profit_usd'], requested_net_profit_usd=net,
                  prior_reference=f'ETH {version}', reference_version=version, prior_reference_net_profit_usd=net,
                  versioning_policy=f'Immutable numbered strategies; next qualifying improvement is v1.{int(version.split(".")[1])+1}.')
    write_json(root/'configs/research_baseline.json',target)
    return meta


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('version')
    args=parser.parse_args()
    save(args.directory,args.version)

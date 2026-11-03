"""Save a gated ETH v1.5 candidate against the current user baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .alternative_strategies import SignalRule
from .config import StrategyConfig
from .export_volume_candidate import render_volume
from .optimize import write_json
from .paths import ROOT
from .regime_filters import RegimeFilter
from .trend_pine import render_trend


def save(selection_directory):
    path = selection_directory/'selection.json'
    selection = json.loads(path.read_text(encoding='utf-8'))
    summary = json.loads((selection_directory/'summary.json').read_text(encoding='utf-8'))
    if not selection['passed_predeclared_validation_gate']:
        raise ValueError('v1.5 requires the frozen historical gate to pass')
    metrics = summary['evaluation']['full_period']
    net = metrics['final_equity']-metrics['initial_capital']
    rule = SignalRule(**selection['candidate']['rule'])
    config = StrategyConfig(**selection['execution_config'])
    if (config.risk_usd, config.initial_capital, config.max_leverage, config.commission_bps, config.slippage_bps, config.swap_daily_bps) != (100., 50000., 5., 4., 2., 3.3):
        raise ValueError('v1.5 baseline requires unchanged $100 risk, $50,000 capital, leverage and costs')
    filters = RegimeFilter(**selection['candidate']['filters'])
    text, payload, digest = (render_trend(rule,config,filters) if filters.min_trend_gap_bps else render_volume(rule, config, filters))
    baseline_path=ROOT/'configs/research_baseline.json'
    baseline=json.loads(baseline_path.read_text(encoding='utf-8')) if baseline_path.exists() else {}
    requested=baseline.get('requested_net_profit_usd',6000.)
    reference=baseline.get('prior_reference_net_profit_usd',requested)
    existing_meta=ROOT/'configs/eth_strategy_v1_5.metadata.json'
    prior=json.loads(existing_meta.read_text(encoding='utf-8')) if existing_meta.exists() else {}
    same_selection=(prior.get('selection_sha256')==hashlib.sha256(path.read_bytes()).hexdigest() and prior.get('configuration_sha256')==digest)
    if prior and not same_selection:
        raise ValueError('Saved v1.5 is immutable; use save_numbered with the next version')
    if prior:
        from .numbered_profiles import load_profile
        load_profile(ROOT, version='v1.5')
        print('ETH v1.5 already saved; existing files and historical metadata preserved.')
        return
    if any((ROOT/name).exists() for name in ['configs/eth_strategy_v1_5.json','reference/ETH_Strategy_v1_5.pine']):
        raise ValueError('Existing v1.5 files must be preserved; use the next version')
    if net<=max(requested,reference) and not same_selection:
        raise ValueError('v1.5 must exceed both the current requested baseline and the exact saved reference')
    selection_requested=selection.get('requested_baseline',requested)
    selection_reference=selection.get('exact_reference_net',reference)
    title='ETH v1.5 | Volume + trend research' if filters.min_trend_gap_bps else 'ETH v1.5 | Volume filtered channel research'
    text = text.replace('ETH Volume Research | Experimental candidate', title, 1)
    text = text.replace('Experimental filtered candidate; saved v1.4 is unchanged.', 'ETH v1.5; earlier numbered versions are preserved.', 1)
    text = text.replace('//@version=6\n', f'//@version=6\n// Historical net-profit baseline at selection: ${selection_requested:g} on 2023-01-01 through 2026-10-27 UTC at $100 planned risk.\n', 1)
    pine = ROOT/'reference/ETH_Strategy_v1_5.pine'
    config_path = ROOT/'configs/eth_strategy_v1_5.json'
    meta_path = ROOT/'configs/eth_strategy_v1_5.metadata.json'
    pine.parent.mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    pine.write_text(text, encoding='utf-8')
    write_json(config_path, payload)
    write_json(meta_path, dict(strategy_name='ETH v1.5', experiment=selection_directory.name,
                              selected_candidate=selection['candidate']['label'], configuration_sha256=digest,
                              pine_sha256=hashlib.sha256(pine.read_bytes()).hexdigest(),
                              selection_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), entry_filters=payload['filters'],
                              baseline_net_usd=selection_requested, baseline_period=['2023-01-01', '2026-10-28'], baseline_risk_usd=100.,
                              exact_reference_at_selection=selection_reference,
                              same_period_net_usd=net, improvement_above_requested_baseline=net-selection_requested,
                              passed_predeclared_validation_gate=True, selection_is_historical_profit_optimization=True,
                              selection_note='All 2023-2026 observations including 2026 participated in selection. Additional data tests freeze these rules; they do not reselect them.',
                              independent_forward_validation=False, ready_for_funded_trading=False,
                              pine_compilation_verified=False, tradingview_parity_verified=False,
                              additional_data_reports=['reports/v1_5_additional_data.md', 'reports/v1_5_spot_proxy.md','reports/v1_5_trend_verification.md'],
                              execution_differences=['Pine omits additional basis-point fill slippage, financing and Python stop-first handling',
                                                     'Symbol precision, initialization and broker event ordering remain unreconciled']))
    download = ROOT/'downloads/ETH_Strategy_v1_5.txt'
    download.parent.mkdir(exist_ok=True)
    download.write_bytes(pine.read_bytes())
    print(f'Saved ETH v1.5: net ${net:,.2f}, requested baseline ${requested:,.0f}; earlier profiles preserved. {download}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection_directory', type=Path)
    save(parser.parse_args().selection_directory)

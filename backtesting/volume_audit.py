"""Reproduce the frozen filtered winner and retain post-selection stress tests."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from .alternative_strategies import SignalRule, simulate
from .analyze_experiment import daily_pnl, paired_week_bootstrap
from .config import StrategyConfig
from .exit_research import freeze
from .independent_visuals import equity_curve, performance_chart
from .market_data import load_history, utc
from .optimize import pnl, subset, write_json
from .paths import ROOT, PARQUET
from .regime_filters import RegimeFilter, apply_filter, prepare_features


def audit(directory):
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    selection_path = directory/'selection.json'
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    for name, digest in manifest['source_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Experiment source changed: {name}')
    for name, digest in manifest['data_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Experiment data changed: {name}')
    for name, digest in manifest['protected_profile_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Saved profile changed: {name}')
    rule = SignalRule(**selection['candidate']['rule'])
    config = StrategyConfig(**selection['execution_config'])
    filters = RegimeFilter(**selection['candidate']['filters'])
    if asdict(config) != manifest['execution']:
        raise ValueError('Selected execution differs from frozen cost and risk settings')
    output = directory/'verification'
    output.mkdir(exist_ok=True)
    plan = dict(selection_sha256=hashlib.sha256(selection_path.read_bytes()).hexdigest(),
                audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                full_slippage=[2., 4., 8.], reset_2026_halfyear_checks=True,
                development_rvol_neighbors=[1.8, 2.2], bootstrap_samples=2000, seed=1408,
                policy='Fresh computation on inspected data, not independent market validation. No reselection or saved-version edits. Conditional uncertainty ignores candidate-search bias.')
    freeze(output/'manifest.json', plan)
    bars, _ = load_history(PARQUET)
    bars = bars[(bars.timestamp >= utc('2023-01-01')) & (bars.timestamp < utc('2026-10-28'))].reset_index(drop=True)
    base_features = prepare_features(bars, rule)
    filtered = apply_filter(base_features, filters)
    metrics, trades, events = simulate(bars, rule, config, signals=filtered)
    stored = json.loads((directory/'summary.json').read_text(encoding='utf-8'))['evaluation']['full_period']
    if abs(pnl(metrics)-pnl(stored)) > 1e-7:
        raise ValueError('Fresh replay differs from frozen winner')
    selected_curve = equity_curve(bars, events, config)
    if abs(selected_curve.equity.iloc[-1]-metrics['final_equity']) > 1e-7:
        raise ValueError('Selected visual equity does not match broker equity')
    parent = json.loads((directory/'parent_v1_4.json').read_text(encoding='utf-8'))
    parent_rule, parent_config = SignalRule(**parent['rule']), StrategyConfig(**parent['execution'])
    pm, pt, pe = simulate(bars, parent_rule, parent_config)
    pc = equity_curve(bars, pe, parent_config)
    if abs(pc.equity.iloc[-1]-pm['final_equity']) > 1e-7:
        raise ValueError('Parent visual equity does not match broker equity')
    checks = []
    for bps in plan['full_slippage']:
        m = simulate(bars, rule, replace(config, slippage_bps=bps), signals=filtered)[0]
        checks.append(dict(label=f'full_slippage_{bps}', metrics=m))
        print(f"VOLUME AUDIT full_slippage_{bps} net=${pnl(m):.2f}", flush=True)
    for name, start, end in [('2026_H1', '2026-01-01', '2026-07-01'), ('2026_H2_to_Oct27', '2026-07-01', '2026-10-28')]:
        b, f = subset(bars, filtered, start, end)
        for bps in [2., 4.]:
            m = simulate(b, rule, replace(config, slippage_bps=bps), signals=f)[0]
            checks.append(dict(label=f'{name}_slip{bps}', metrics=m))
            print(f"VOLUME AUDIT {name}_slip{bps} net=${pnl(m):.2f}", flush=True)
    for threshold in plan['development_rvol_neighbors']:
        f = apply_filter(base_features, replace(filters, min_rvol=threshold))
        b, part = subset(bars, f, '2023-01-01', '2026-01-01')
        m = simulate(b, rule, config, signals=part)[0]
        checks.append(dict(label=f'development_RVOL{threshold}', metrics=m))
        print(f"VOLUME AUDIT development_RVOL{threshold} net=${pnl(m):.2f}", flush=True)
    paired = paired_week_bootstrap(daily_pnl(SimpleNamespace(equity=selected_curve, metrics=metrics)),
                                   daily_pnl(SimpleNamespace(equity=pc, metrics=pm)), samples=2000, seed=1408)
    annual = daily_pnl(SimpleNamespace(equity=selected_curve, metrics=metrics)).groupby(lambda t: t.year).sum().to_dict()
    net = trades.net_pnl
    concentration = dict(closed_net=float(net.sum()), largest_three_winners=float(net.clip(lower=0).nlargest(3).sum()),
                         closed_net_without_three_largest_winners=float(net.sum()-net.clip(lower=0).nlargest(3).sum()),
                         note='Diagnostic subtraction, not a replay of a strategy without these trades')
    write_json(output/'summary.json', dict(parent=pm, selected=metrics, checks=checks,
                                          selected_continuous_annual_pnl=annual, paired_conditional_bootstrap=paired,
                                          concentration=concentration, selection_unchanged=True, independent_forward_validation=False))
    selected_curve.to_parquet(output/'selected_equity.parquet', index=False)
    pc.to_parquet(output/'parent_equity.parquet', index=False)
    trades.to_csv(output/'selected_trades.csv', index=False)
    fig = performance_chart(selected_curve, config.initial_capital)
    fig.update_layout(title='Volume research candidate · Equity and drawdown')
    fig.write_html(output/'equity.html', include_plotlyjs=True)
    lines = ['# Filtered-candidate reproduction and stress checks', '', plan['policy'], '',
             f"Fresh same-period replay: saved v1.4 **${pnl(pm):,.2f}**, filtered candidate **${pnl(metrics):,.2f}**; improvement **${pnl(metrics)-pnl(pm):,.2f}**. Event-reconstructed equity matches both broker endpoints.", '',
             '| Post-selection check | Net P&L | Entries | Intrabar drawdown |', '| --- | ---: | ---: | ---: |']
    for row in checks:
        m = row['metrics']
        lines.append(f"| {row['label']} | ${pnl(m):,.2f} | {m['entries']} | {m['max_intrabar_drawdown']:.2%} |")
    lines.extend(['', '| Continuous selected account calendar-year marked P&L | Net P&L |', '| --- | ---: |'])
    for year, value in annual.items():
        lines.append(f'| {year} | ${value:,.2f} |')
    interval = paired['conditional_95pct_interval']
    lines.extend(['', f"Conditional paired seven-day-block interval for net improvement: **${interval[0]:,.2f} to ${interval[1]:,.2f}**. This does not account for searching 638 configuration slots and is not a future-profit probability.", '',
                  f"Closed net after mechanically removing the three largest winning legs: **${concentration['closed_net_without_three_largest_winners']:,.2f}**. This is diagnostic subtraction, not a re-simulated trade-selection strategy.", '',
                  'Half-year checks start independent accounts with causal indicator warm-up and do not sum to continuous P&L. Positive annual totals can hide losing halves. Neighborhood checks use development history and never choose a new rule. All of 2023-2026 has been inspected/used for selection, including 2026. Exact TradingView/Breakout fills, Pine compilation and future paper observations remain absent. Saved v1.4 files and all earlier failures are unchanged.', ''])
    text = '\n'.join(lines)
    (output/'report.md').write_text(text, encoding='utf-8')
    (ROOT/'reports/volume_candidate_verification.md').write_text(text, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    audit(parser.parse_args().directory)

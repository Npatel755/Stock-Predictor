"""One preregistered v1.12 candidate, fixed sizing under unexpected fill costs.

No optimizer, parameter grid, consumed transfer-data selection or version
promotion. Development outcomes remain development evidence.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pandas as pd

from .alternative_strategies import simulate as original_simulate
from .cost_reserve import simulate
from .engine import estimated_round_trip_cost
from .exit_research import freeze
from .frozen_inputs import recorded_path
from .generalization_policy import assert_historical_period, digest, frozen_profile
from .independent_visuals import equity_curve
from .market_data import BAR, clean_candles, load_history, utc
from .optimize import pnl, subset, write_json
from .paths import ROOT
from .post_selection_checks import paired_interval
from .regime_filters import RegimeFilter, apply_filter, prepare_features
from .reporting import safe_value


NAME = 'eth_v1_12'
BUDGETS = {'v1.11_fixed_2bp_budget': 2., 'v1.12_candidate_8bp_budget': 8.}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_directory(root):
    return root/'candidates'/NAME


def artifact_directory(root):
    return root/'artifacts/generalization'/NAME


def register(root=ROOT, now=None):
    """Commit identity and success criteria before calculating any results."""
    directory = candidate_directory(root)
    if (directory/'protocol.json').exists():
        return registered(root)
    p, _, _, _ = frozen_profile(root)
    now = utc(now) if now is not None else pd.Timestamp.now(tz='UTC')
    start = now.floor('D')+pd.Timedelta(days=1)
    directory.mkdir(parents=True, exist_ok=True)
    candidate = dict(version='v1.12 research candidate', parent_version=p['frozen_version'],
                     parent_configuration_sha256=p['frozen_configuration_sha256'],
                     strategy=p['frozen_payload'], sizing_slippage_bps=8.,
                     promoted=False, independent_forward_validation=False)
    freeze(directory/'config.json', candidate)
    from .numbered_profiles import load_profile
    pine = load_profile(root, p['frozen_version'])[3].read_text(encoding='utf-8')
    pine = pine.replace(p['frozen_version'], 'v1.12 candidate')
    # The exported derivative must not retain the parent's configuration hash.
    pine = pine.replace(p['frozen_configuration_sha256'], digest(candidate))
    pine = pine.replace('input.float(2.0, "Extra slippage estimate for sizing only (bp)"',
                        'input.float(8.0, "Fixed slippage budget for sizing only (bp)"')
    if 'Fixed slippage budget for sizing only' not in pine:
        raise ValueError('Parent Pine sizing export format changed')
    pine = pine.replace('Selected using inspected 2023-2026 history, including 2026; no independent forward validation.',
                        'Single cost-reserve hypothesis; development replay is not independent validation.')
    pine = pine.replace('// Full rule/filter/config SHA-256:', '// Candidate payload SHA-256:')
    pine = ('// v1.12 UNPROMOTED research candidate: same signals; fixed 8bp sizing budget.\n'
            '// Planned risk is not a hard loss cap: gaps and financing can exceed it.\n'
            '// Pine fill costs remain two ticks; Python stress fills use separate 2/4/8bp.\n'+pine)
    pine_path = directory/'ETH_Strategy_v1_12_candidate.pine'
    text_path = directory/'ETH_Strategy_v1_12_candidate.txt'
    for path in [pine_path, text_path]:
        if path.exists() and path.read_text(encoding='utf-8') != pine:
            raise ValueError('Candidate Pine already differs')
        path.write_text(pine, encoding='utf-8')
    plan = dict(candidate='v1.12 research candidate', created_at_utc=str(now),
                parent_protocol_sha256=digest(p), candidate_sha256=digest(candidate),
                sizing_budgets_bps=BUDGETS, actual_fill_slippage_bps=[2., 4., 8.],
                change='Only quantity uses a fixed 8bp budget; all signal/stop/target/trailing rules and $100 planned risk stay fixed.',
                rationale='Budget for adverse execution without choosing signal parameters from consumed cross-venue/asset outcomes.',
                source='https://intercom.help/breakoutprop/en/articles/16110234-why-does-my-fill-price-differ-from-the-quoted-price',
                source_note='Breakout describes order-size/liquidity-dependent fills; it does not establish 8bp as a measured normal rate.',
                number_of_candidate_hypotheses=1, optimizer_enabled=False,
                historical_period=['2023-01-01', '2026-10-28'], historical_data_already_inspected=True,
                transfer_data_used_to_choose_thresholds=False,
                development_outcomes_may_change_candidate=False,
                future_period=[str(start), str(start+pd.Timedelta(days=180))],
                final_evaluation_only=True, minimum_closed_trades=30, maximum_drawdown=.05,
                primary_comparison='At 8bp actual fills: lower intrabar drawdown and at least 90% of fixed-2bp-budget baseline net; baseline net must be positive.',
                additional_checks='Candidate positive net at all three fill costs, no margin calls, <=5% drawdown, >=30 closed trades, positive lower seven-day-block interval at 8bp.',
                bootstrap=dict(seed=20261104, draws=10000, block_days=7),
                promotion_automatic=False, ready_for_funded_trading=False,
                source_sha256={name: sha(root/name) for name in list(p['algorithms'])+
                               ['cost_reserve.py', 'cost_reserve_study.py', 'independent_visuals.py',
                                'post_selection_checks.py', 'market_data.py', 'optimize.py',
                                'eth_research/data.py']},
                export_sha256={path.name: sha(path) for path in [pine_path, text_path]})
    freeze(directory/'protocol.json', plan)
    return plan


def registered(root=ROOT):
    p, _, _, _ = frozen_profile(root)
    directory = candidate_directory(root)
    plan = json.loads((directory/'protocol.json').read_text(encoding='utf-8'))
    candidate = json.loads((directory/'config.json').read_text(encoding='utf-8'))
    if plan['parent_protocol_sha256'] != digest(p) or plan['candidate_sha256'] != digest(candidate):
        raise ValueError('Candidate or parent protocol changed')
    for name, expected in plan['source_sha256'].items():
        if sha(root/name) != expected:
            raise ValueError(f'Registered candidate implementation changed: {name}')
    for name, expected in plan['export_sha256'].items():
        if sha(directory/name) != expected:
            raise ValueError('Registered Pine/text export changed')
    return plan


def replay_pairs(bars, signals, rule, cfg, directory):
    """No known-future costs enter sizing; compare both fixed budgets fairly."""
    directory.mkdir(parents=True, exist_ok=True)
    rows, curves = [], {}
    for label, budget in BUDGETS.items():
        for slip in [2., 4., 8.]:
            actual = replace(cfg, slippage_bps=slip)
            metrics, trades, events = simulate(bars, rule, actual, signals,
                                               sizing_slippage_bps=budget)
            curve = equity_curve(bars, events, actual)
            if abs(curve.equity.iloc[-1]-metrics['final_equity']) > 1e-6:
                raise ValueError('Candidate equity does not reconcile with broker')
            name = f'{label}_fill{int(slip)}'
            trades.to_csv(directory/f'{name}_trades.csv', index=False)
            events.to_csv(directory/f'{name}_events.csv', index=False)
            curve.to_parquet(directory/f'{name}_equity.parquet', index=False)
            rows.append(dict(strategy=label, sizing_slippage_bps=budget,
                             actual_fill_slippage_bps=slip, metrics=safe_value(metrics),
                             planned_risk_at_8bp=risk_audit(signals, events, rule, cfg)))
            curves[label, slip] = curve
    return rows, curves


def risk_audit(signals, events, rule, cfg):
    """Initial-stop sizing exposure at signal close, not a realized loss cap."""
    frame = signals.set_index('timestamp')
    values = []
    if len(events):
        for entry in events[events.event == 'entry'].itertuples():
            signal = frame.loc[entry.bar_open-BAR]
            distance = rule.stop_atr*signal.signal_atr
            cost = estimated_round_trip_cost(replace(cfg, slippage_bps=8.), signal.close)
            values.append(float(entry.quantity*(distance+cost)*cfg.point_value))
    return dict(entries=len(values), maximum_estimated_usd=max(values, default=0.),
                mean_estimated_usd=sum(values)/len(values) if values else 0.,
                above_planned_budget=sum(value > cfg.risk_usd+1e-9 for value in values),
                includes_next_open_gap_or_financing=False)


def development(root=ROOT):
    plan = register(root)
    _, rule, cfg, meta = frozen_profile(root)
    origin = root/f"artifacts/optimization/{meta['experiment']}"
    old_plan = json.loads((origin/'manifest.json').read_text(encoding='utf-8'))
    name = 'data/ethusd/perpetual/candles.parquet'
    path = recorded_path(root, name, old_plan['data_hashes'][name])
    bars, _ = load_history(path)
    start, end = map(utc, plan['historical_period'])
    assert_historical_period(end, root)
    bars = bars[(bars.timestamp >= start) & (bars.timestamp < end)].reset_index(drop=True)
    signals = apply_filter(prepare_features(bars, rule), RegimeFilter(**meta['entry_filters']))
    directory = artifact_directory(root)/'development'
    directory.mkdir(parents=True, exist_ok=True)
    freeze(directory/'manifest.json', dict(protocol_sha256=digest(plan),
                                          data_sha256=sha(path), data_path=str(path.relative_to(root))))
    bars.to_parquet(directory/'bars.parquet', index=False)
    windows = [('full', start, end)] + [(str(y), utc(f'{y}-01-01'), min(end, utc(f'{y+1}-01-01')))
                                      for y in range(2023, 2027)]
    results = []
    for label, begin, finish in windows:
        b, f = subset(bars, signals, begin, finish)
        rows, _ = replay_pairs(b, f, rule, cfg, directory/label)
        if label == 'full':
            original = original_simulate(b, rule, cfg, signals=f)[0]
            if safe_value(original) != rows[0]['metrics']:
                raise ValueError('Fixed 2bp budget at 2bp actual fills differs from frozen v1.11')
            if pnl(original) != meta['same_period_net_usd']:
                raise ValueError('Frozen historical benchmark changed')
        results += [dict(period=label, **row) for row in rows]
        print(f'FIXED-BUDGET DEVELOPMENT {label}: '+', '.join(
            f"{r['strategy']} fill={r['actual_fill_slippage_bps']} net={pnl(r['metrics']):.2f}" for r in rows), flush=True)
    result = dict(protocol_sha256=digest(plan), scenarios=results,
                  original_main_reproduced_exactly=True, thresholds_selected_from_results=False,
                  prospective_validation_complete=False, promoted=False,
                  artifacts_sha256={str(path.relative_to(directory)): sha(path)
                                    for path in sorted(directory.rglob('*'))
                                    if path.is_file() and path.suffix in {'.parquet', '.csv'}})
    # A rerun must reproduce every metric, not replace inspected outcomes.
    freeze(directory/'results.json', result)
    report(root, result)
    return result


def verify_development(root=ROOT):
    """Fresh rerun must reproduce immutable metrics and every ledger/curve byte."""
    path = artifact_directory(root)/'development/results.json'
    if not path.exists():
        raise ValueError('Run the predefined development comparison first')
    before = sha(path)
    development(root)
    if sha(path) != before:
        raise ValueError('Fresh development replay changed')
    certificate = dict(results_sha256=before, reproduced_exactly=True,
                       independent_forward_validation=False, promoted=False)
    freeze(path.parent/'verification.json', certificate)
    return certificate


def forward(path, root=ROOT, now=None):
    plan = registered(root)
    now = utc(now) if now is not None else pd.Timestamp.now(tz='UTC')
    start, end = map(utc, plan['future_period'])
    if now < end:
        return dict(status='awaiting_candidate_future_window', earliest_final_evaluation_utc=str(end),
                    passed=False, prices_read=False, promoted=False)
    _, rule, cfg, meta = frozen_profile(root)
    path = Path(path)
    source_hash = sha(path)
    raw = pd.read_parquet(path)
    times = pd.to_datetime(raw.timestamp, utc=True)
    warmup = start-pd.Timedelta(hours=rule.slow*5)
    bars, quality = clean_candles(raw[(times >= warmup) & (times < end)], start=warmup, end=end)
    if quality['missing_bars']:
        raise ValueError('Candidate forward data requires complete coverage including warm-up')
    frame = apply_filter(prepare_features(bars, rule), RegimeFilter(**meta['entry_filters']))
    mask = (bars.timestamp >= start) & (bars.available_at <= end)
    future, signals = bars.loc[mask].reset_index(drop=True), frame.loc[mask].reset_index(drop=True)
    if len(future) != int((end-start)/BAR):
        raise ValueError('Incomplete candidate future period')
    directory = artifact_directory(root)/'forward'
    directory.mkdir(parents=True, exist_ok=True)
    freeze(directory/'data_manifest.json', dict(protocol_sha256=digest(plan), data_sha256=source_hash))
    rows, curves = replay_pairs(future, signals, rule, cfg, directory)
    baseline, candidate = [r['metrics'] for r in rows if r['actual_fill_slippage_bps'] == 8.]
    candidates = [r['metrics'] for r in rows if r['sizing_slippage_bps'] == 8.]
    curve = curves['v1.12_candidate_8bp_budget', 8.]
    # Assign 00:00 closes to the preceding trading day, retaining all 180 days.
    daily = curve.assign(day=(curve.timestamp-pd.Timedelta(nanoseconds=1)).dt.floor('D')).groupby('day').equity.last()
    changes = daily.diff(); changes.iloc[0] = daily.iloc[0]-cfg.initial_capital
    interval = paired_interval(changes.to_numpy(), **plan['bootstrap'])
    checks = dict(positive_net_all_costs=all(pnl(m) > 0 for m in candidates),
                  minimum_closed_trades=all(m['closed_trade_legs'] >= plan['minimum_closed_trades'] for m in candidates),
                  no_margin_calls=all(m['margin_call_events'] == 0 for m in candidates),
                  drawdown_limit=all(m['max_intrabar_drawdown'] <= plan['maximum_drawdown'] for m in candidates),
                  lower_stressed_drawdown=candidate['max_intrabar_drawdown'] < baseline['max_intrabar_drawdown'],
                  retain_90pct_positive_stressed_net=pnl(baseline) > 0 and pnl(candidate) >= .9*pnl(baseline),
                  positive_lower_stressed_block_interval=interval['interval_95'][0] > 0)
    result = dict(protocol_sha256=digest(plan), period=plan['future_period'], scenarios=rows,
                  interval=interval, checks=checks, passed=all(checks.values()),
                  prospective_validation_complete=True, promoted=False, ready_for_funded_trading=False,
                  qualification='Candidate-specific risk comparison. Does not inherit or replace v1.11 validation or certify future profits.')
    freeze(directory/'certificate.json', result)
    return result


def report(root, result):
    rows = result['scenarios']
    lines = ['# ETH v1.12 cost-reserve research candidate', '',
             'One predefined change: fixed 8bp slippage in sizing, versus a fixed 2bp baseline budget. Actual market/stop fills are independently stressed at 2, 4 and 8bp. Both retain two ticks, fees and financing. Signal, stop, target and trail parameters are unchanged.', '',
             '**Not promoted. Future profitability remains unproven.** 2023-2026 observations are consumed development data; no new venue or BTC test was retuned. A separate candidate-specific 180-day prospective protocol was registered before replay. The v1.11 lock is unchanged.', '',
             'The older stress tests raised both fill costs and the sizing estimate together. Their results remain valid for known higher costs. These new tests ask a different question: what if execution is worse than the budget used when sizing? They must not be compared as identical scenarios.', '',
             '| Period | Fixed sizing budget | Actual fill slippage | Net P&L | Entries | Intrabar drawdown | Max estimated initial-stop risk at 8bp |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        m = r['metrics']
        lines.append(f"| {r['period']} | {r['sizing_slippage_bps']}bp | {r['actual_fill_slippage_bps']}bp | ${pnl(m):,.2f} | {m['entries']} | {m['max_intrabar_drawdown']:.2%} | ${r['planned_risk_at_8bp']['maximum_estimated_usd']:.2f} |")
    lines += ['', 'Full-period metrics reproduce the frozen v1.11 main result exactly. Annual tests reset accounts, use causal preceding indicator history, and are not added to the full-period return.', '',
              'Planned stop risk is an estimate. Next-open gaps, stop gaps, financing, spread/depth and costs beyond the assumed reserve can exceed $100. This test does not observe an order book or actual Breakout fills. An 8bp reserve is a fixed stress assumption, not a claimed normal fill rate.', '',
              'The candidate must earn lower stressed drawdown while retaining at least 90% of positive baseline stressed net, plus the separately registered positive-net, drawdown, trade-count and confidence checks. Historical outcomes cannot promote it or revise its protocol.', '',
              '[Breakout execution guidance](https://intercom.help/breakoutprop/en/articles/16110234-why-does-my-fill-price-differ-from-the-quoted-price).', '']
    (root/'reports/v1_12_cost_reserve.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forward-bars', type=Path)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify and args.forward_bars:
        parser.error('Choose development verification or future evaluation')
    outcome = verify_development() if args.verify else forward(args.forward_bars) if args.forward_bars else development()
    print(json.dumps({k: v for k, v in outcome.items() if k != 'scenarios'}, indent=2))

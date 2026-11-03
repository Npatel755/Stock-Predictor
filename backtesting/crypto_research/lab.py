"""Pre-registered multi-coin strategy lab.

Protocol (frozen in manifest.json before any result is written):
  universe   8 Breakout-listed coins (see data.UNIVERSE), ETH excluded by design
  candidates 6 independent signal families x {1h, 4h} x {balanced, patient} exits
             + the frozen ETH v1.11 rule transplanted unchanged = 25 per coin
  train      2021, 2022, 2023 as independently reset annual accounts, 8bp costs
  validation 2024, only the best eligible training candidate per coin
  final      one (coin, candidate) chosen on train+validation evidence only
  test       2025-01-01 .. 2026-10-28, run once for the final choice only
Selection never sees the test window; failing candidates are kept on disk.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json

import numpy as np
import pandas as pd

from .data import DATA, UNIVERSE, clean, load
from ..cost_reserve import simulate
from ..exit_research import freeze
from ..forward_collection import atomic_json
from ..generalization_policy import assert_historical_period, digest, frozen_profile
from ..independent_visuals import equity_curve
from ..market_data import BAR, utc
from ..optimize import subset
from ..paths import ROOT
from ..regime_filters import RegimeFilter, apply_filter, prepare_features
from ..reporting import safe_value
from ..strategy_lab_signals import FAMILIES, LabRule, prepare

NAME = 'crypto_round1'
TRAIN_YEARS = (2021, 2022, 2023)
TRAIN = ['2021-01-01', '2024-01-01']
VALIDATION = ['2024-01-01', '2025-01-01']
TEST = ['2025-01-01', '2026-10-28']
ETH_BASELINE_ID = 'eth_v1_11_transplant'


def candidates():
    rows = [dict(id=f'{family}_{hours}h_{profile}', kind='lab', rule=asdict(LabRule(family, hours, *geometry)))
            for family in FAMILIES for hours in [1, 4]
            for profile, geometry in [('balanced', (2., 3., 3.)), ('patient', (3., 5., 4.))]]
    rows.append(dict(id=ETH_BASELINE_ID, kind='eth_baseline', rule=None))
    return rows


def directory(root):
    return root/'artifacts/crypto_research'/NAME


def plan(root=ROOT, symbols=None, data=DATA):
    assert_historical_period(TEST[1], root)
    symbols = list(symbols or UNIVERSE)
    hashes = {s: load(s, data)[1]['parquet_sha256'] for s in symbols}
    out = directory(root)
    previous = json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else None
    manifest = dict(name=NAME, symbols=symbols, data_hashes=hashes,
        created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        authorization='User asked on 2026-11-03 for a separately versioned new strategy on a non-ETH Breakout coin with a train/validation/test split.',
        candidates=candidates(), candidates_per_symbol=25,
        train_period=TRAIN, train_folds='Three independently reset annual accounts (2021, 2022, 2023).',
        validation_period=VALIDATION, test_period=TEST,
        scoring='CLOSED net at 8bp fill slippage and 8bp sizing budget, $100 risk, $50k account. '
                'score = median(annual closed net) - worst annual loss - 0.5*max(annual intrabar drawdown*$50000).',
        train_gate='>=4 closed legs per year, >=24 total, >=2 of 3 years positive, no margin calls, <=5% drawdown every year, positive score.',
        validation='Best eligible training candidate per coin only; needs positive closed net, >=10 closed legs, <=5% drawdown, no margin calls.',
        final_choice='Among validation-eligible (coin, candidate) pairs choose max(min(median training closed net, validation closed net) - 0.5*validation drawdown*$50000); tie by symbol then id.',
        test_gate='Final choice only, single look: positive closed net at 8bp in 2025 and in 2026, <=5% drawdown at 2/4/8bp, no margin calls. Also reported at 2bp and 4bp.',
        cost_scenarios_bps=[2., 4., 8.], sizing_budget_bps=8., risk_usd=100., initial_capital=50000.,
        test_window_used_for_selection=False, threshold_changes_after_results=False,
        promotion='Passing creates candidates/crypto_v0_1 (unpromoted); live use still requires forward paper evidence.')
    if previous and digest({k: v for k, v in previous.items() if k != 'created_at_utc'}) != digest({k: v for k, v in manifest.items() if k != 'created_at_utc'}):
        raise ValueError('crypto lab manifest changed after registration; use a new NAME')
    out.mkdir(parents=True, exist_ok=True)
    if not (out/'manifest.json').exists():
        freeze(out/'manifest.json', manifest)
    return manifest


def validator(symbol):
    return lambda b: clean(b, symbol, b.timestamp.iloc[0], b.timestamp.iloc[-1]+BAR)


def evaluate(symbol, bars, signals, rule, cfg, sizing=8.):
    metrics, trades, events = simulate(bars, rule, cfg, signals, sizing_slippage_bps=sizing, validator=validator(symbol))
    return dict(metrics=safe_value(metrics), closed_net=float(trades.net_pnl.sum()) if len(trades) else 0.), trades, events


def detailed(symbol, bars, signals, rule, cfg, out, sizing=8.):
    out.mkdir(parents=True, exist_ok=True)
    result, trades, events = evaluate(symbol, bars, signals, rule, cfg, sizing)
    curve = equity_curve(bars, events, cfg)
    if abs(curve.equity.iloc[-1]-result['metrics']['final_equity']) > 1e-6:
        raise ValueError('Equity curve does not reconcile with fills')
    trades.to_csv(out/'trades.csv', index=False)
    events.to_csv(out/'events.csv', index=False)
    curve.to_parquet(out/'equity.parquet', index=False)
    return result


def training_rank(folds):
    profits = [f['closed_net'] for f in folds]
    legs = [f['metrics']['closed_trade_legs'] for f in folds]
    eligible = (len(folds) == len(TRAIN_YEARS) and min(legs) >= 4 and sum(legs) >= 24
                and sum(p > 0 for p in profits) >= 2
                and all(f['metrics']['margin_call_events'] == 0 and f['metrics']['max_intrabar_drawdown'] <= .05 for f in folds))
    score = float(np.median(profits)-max(0., -min(profits))-.5*max(f['metrics']['max_intrabar_drawdown']*50000 for f in folds))
    return dict(score=score, eligible=bool(eligible and score > 0), median_closed_net=float(np.median(profits)))


def validation_rank(training, result):
    m = result['metrics']
    eligible = (training['rank']['eligible'] and result['closed_net'] > 0 and m['closed_trade_legs'] >= 10
                and m['max_intrabar_drawdown'] <= .05 and m['margin_call_events'] == 0)
    score = min(training['rank']['median_closed_net'], result['closed_net'])-.5*m['max_intrabar_drawdown']*50000
    return dict(eligible=bool(eligible), score=float(score))


def choose(rows, key):
    return max(rows, key=lambda r: (r['rank']['eligible'], r['rank']['score'], key(r)))


def geometry(candidate, baseline_rule, meta):
    """(signal builder, execution rule) for a candidate; ETH baseline is transplanted unchanged."""
    if candidate['kind'] == 'eth_baseline':
        return (lambda bars: apply_filter(prepare_features(bars, baseline_rule), RegimeFilter(**meta['entry_filters']))), baseline_rule
    rule = LabRule(**candidate['rule'])
    return (lambda bars: prepare(bars, rule)), rule.execution_rule()


def train_symbol(symbol, bars, manifest, cfg, baseline_rule, meta, out, verify):
    rows = []
    train_bars = bars[bars.timestamp < utc(TRAIN[1])].reset_index(drop=True)
    for candidate in manifest['candidates']:
        path = out/'training'/symbol/f"{candidate['id']}.json"
        if path.exists() and not verify:
            row = json.loads(path.read_text())
            if row['candidate'] != candidate or row['manifest_sha256'] != digest(manifest):
                raise ValueError('Training checkpoint changed identity')
            rows.append(row)
            continue
        build, rule = geometry(candidate, baseline_rule, meta)
        features = build(train_bars)
        folds = []
        for year in TRAIN_YEARS:
            b, f = subset(train_bars, features, f'{year}-01-01', f'{year+1}-01-01')
            result, _, _ = evaluate(symbol, b, f, rule, cfg)
            folds.append(dict(year=year, **result))
        row = dict(symbol=symbol, candidate=candidate, folds=folds, rank=training_rank(folds), manifest_sha256=digest(manifest))
        path.parent.mkdir(parents=True, exist_ok=True)
        freeze(path, row)
        rows.append(row)
        print(f"TRAIN {symbol} {candidate['id']} score={row['rank']['score']:.0f} eligible={row['rank']['eligible']}", flush=True)
        atomic_json(out/'status.json', dict(stage='training', symbol=symbol, complete=len(rows), total=len(manifest['candidates'])))
    return rows


def run(root=ROOT, symbols=None, data=DATA, verify=False, held_out=False):
    manifest = plan(root, symbols, data)
    out = directory(root)
    _, baseline_rule, cfg, meta = frozen_profile(root)
    cfg = replace(cfg, slippage_bps=8.)
    training, validation = {}, []
    for symbol in manifest['symbols']:
        bars, _ = load(symbol, data, manifest['data_hashes'][symbol])
        training[symbol] = train_symbol(symbol, bars, manifest, cfg, baseline_rule, meta, out, verify)
        best = choose(training[symbol], key=lambda r: r['candidate']['id'])
        candidate = best['candidate']
        path = out/'validation'/symbol/f"{candidate['id']}.json"
        if path.exists() and not verify:
            row = json.loads(path.read_text())
        else:
            build, rule = geometry(candidate, baseline_rule, meta)
            preceding = bars[bars.timestamp < utc(VALIDATION[1])].reset_index(drop=True)
            b, f = subset(preceding, build(preceding), *VALIDATION)
            result = detailed(symbol, b, f, rule, cfg, out/'validation'/symbol/candidate['id'])
            row = dict(symbol=symbol, candidate=candidate, result=result, rank=validation_rank(best, result),
                       training_eligible=best['rank']['eligible'], manifest_sha256=digest(manifest))
            freeze(path, row)
        validation.append(row)
        print(f"VALIDATION {symbol} {candidate['id']} closed={row['result']['closed_net']:.0f} eligible={row['rank']['eligible']}", flush=True)
    eligible = [r for r in validation if r['rank']['eligible']]
    selected = max(eligible, key=lambda r: (r['rank']['score'], r['symbol'], r['candidate']['id'])) if eligible else None
    selection = dict(manifest_sha256=digest(manifest),
                     selected=None if selected is None else dict(symbol=selected['symbol'], candidate=selected['candidate']),
                     reason='Passed fixed train/2024 gates' if selected else 'No (coin, candidate) passed both fixed gates',
                     test_window_seen=False, promoted=False)
    if not (out/'selection.json').exists():
        freeze(out/'selection.json', selection)
    summary = dict(manifest_sha256=digest(manifest), training={s: [dict(id=r['candidate']['id'], **r['rank']) for r in rows] for s, rows in training.items()},
                   validation=[dict(symbol=r['symbol'], id=r['candidate']['id'], closed_net=r['result']['closed_net'],
                                    drawdown=r['result']['metrics']['max_intrabar_drawdown'], legs=r['result']['metrics']['closed_trade_legs'], **r['rank']) for r in validation],
                   selection=selection, test=None)
    atomic_json(out/'results.json', summary)
    atomic_json(out/'status.json', dict(stage='selected', selected=selection['selected']))
    if held_out and selected is not None:
        summary['test'] = test(root, data, selection['selected'], baseline_rule, cfg, meta, out)
        atomic_json(out/'results.json', summary)
    report(out, summary)
    return summary


def test(root, data, selected, baseline_rule, cfg, meta, out):
    """Single look at the held-out window for the one selected pair."""
    path = out/'test.json'
    if path.exists():
        return json.loads(path.read_text())
    symbol, candidate = selected['symbol'], selected['candidate']
    bars, _ = load(symbol, data)
    build, rule = geometry(candidate, baseline_rule, meta)
    features = build(bars)
    rows = []
    for label, begin, end in [('test_2025', '2025-01-01', '2026-01-01'), ('test_2026', '2026-01-01', TEST[1]), ('test_full', *TEST)]:
        b, f = subset(bars, features, begin, end)
        for slip in [2., 4., 8.]:
            result = detailed(symbol, b, f, rule, replace(cfg, slippage_bps=slip), out/'test'/label/f'fill{int(slip)}')
            rows.append(dict(period=label, actual_fill_slippage_bps=slip, closed_net=result['closed_net'],
                             drawdown=result['metrics']['max_intrabar_drawdown'], legs=result['metrics']['closed_trade_legs'],
                             margin_calls=result['metrics']['margin_call_events']))
    annual8 = [r for r in rows if r['period'] != 'test_full' and r['actual_fill_slippage_bps'] == 8.]
    passed = (all(r['closed_net'] > 0 for r in annual8) and all(r['drawdown'] <= .05 and r['margin_calls'] == 0 for r in rows))
    outcome = dict(symbol=symbol, candidate=candidate, rows=rows, passed=bool(passed), single_look=True,
                   note='Held-out result is evidence about this one pre-selected pair only; it was not used to choose it.')
    freeze(path, outcome)
    if passed:
        register(root, outcome, cfg)
    return outcome


def register(root, outcome, cfg):
    folder = root/'candidates/crypto_v0_1'
    folder.mkdir(parents=True, exist_ok=True)
    config = dict(version='crypto_v0_1', symbol=outcome['symbol'], breakout=UNIVERSE[outcome['symbol']],
                  candidate=outcome['candidate'], risk_usd=cfg.risk_usd, initial_capital=cfg.initial_capital,
                  slippage_budget_bps=8., commission_bps=cfg.commission_bps, promoted=False,
                  evidence='train 2021-23 / validation 2024 / single-look test 2025-2026-10-28; no forward evidence yet')
    atomic_json(folder/'config.json', config)
    atomic_json(folder/'protocol.json', dict(lab=NAME, manifest_sha256=digest(json.loads((directory(root)/'manifest.json').read_text()))))


def report(out, summary):
    lines = [f'# Crypto research {NAME}', '', 'Pre-registered 8-coin lab; ETH excluded. 25 candidates per coin; selection on 2021-23 train + 2024 validation only.', '',
             '## Validation (best training candidate per coin, 2024, 8bp)', '', '| Coin | Candidate | Train eligible | 2024 closed net | Drawdown | Legs | Eligible |', '|---|---|---|---|---|---|---|']
    for r in summary['validation']:
        tr = next(t for t in summary['training'][r['symbol']] if t['id'] == r['id'])
        lines.append(f"| {r['symbol']} | {r['id']} | {tr['eligible']} | {r['closed_net']:.0f} | {r['drawdown']:.2%} | {r['legs']} | {r['eligible']} |")
    lines += ['', f"## Selection: {summary['selection']['selected']}", '', summary['selection']['reason']]
    if summary['test']:
        t = summary['test']
        lines += ['', f"## Held-out test (single look) — passed: {t['passed']}", '', '| Period | Fill bp | Closed net | Drawdown | Legs |', '|---|---|---|---|---|']
        lines += [f"| {r['period']} | {int(r['actual_fill_slippage_bps'])} | {r['closed_net']:.0f} | {r['drawdown']:.2%} | {r['legs']} |" for r in t['rows']]
    lines += ['', '## Training scores per coin (all candidates retained)', '']
    for s, rows in summary['training'].items():
        lines.append(f"- {s}: " + ', '.join(f"{r['id']}={r['score']:.0f}{'*' if r['eligible'] else ''}" for r in sorted(rows, key=lambda r: -r['score'])[:6]))
    (out/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', nargs='*')
    parser.add_argument('--held-out', action='store_true', help='Run the single-look test for the selected pair')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    run(symbols=args.symbols, verify=args.verify, held_out=args.held_out)

"""Twelve classic channel variants selected chronologically at stressed costs.

No tuned RVOL/trend-distance gates. Test coarse holding periods, not another
whole-history reward/stop search. Original policies and candidates are intact.
"""
from dataclasses import replace
import json

import numpy as np
import pandas as pd

from .alternative_strategies import SignalRule
from .exit_research import freeze
from .forward_collection import collection_lock, atomic_json
from .generalization_policy import digest, frozen_profile, assert_historical_period
from .indicators import resample_complete, rma
from .market_data import BAR, utc
from .optimize import pnl, subset
from .paths import ROOT
from .regime_filters import apply_filter, prepare_features, RegimeFilter
from .strategy_lab import plan as parent_plan, load_development, training_rank, validation_rank, choose_family, detailed, sha


NAME = 'channel_timeframes_round1'


def directory(root):
    return root/'artifacts/strategy_lab'/NAME


def candidates():
    return [dict(id=f'channel_{hours}h_{length}_{profile}', hours=hours, length=length,
                 geometry=dict(stop_atr=geometry[0], reward_r=geometry[1], trail_atr=geometry[2]))
            for hours in [1, 4, 24] for length in [20, 55]
            for profile, geometry in [('balanced', (2., 3., 3.)), ('patient', (3., 5., 4.))]]


def geometry(candidate):
    return SignalRule('channel_breakout', lookback=candidate['length'], slow=200, **candidate['geometry'])


def prepare(bars, candidate):
    hours, length = candidate['hours'], candidate['length']
    frame = resample_complete(bars, f'{hours}h')
    close = frame.close
    trend = close.ewm(span=200, adjust=False).mean()
    upper, lower = frame.high.shift().rolling(length).max(), frame.low.shift().rolling(length).min()
    ready = close.expanding().count() >= 200
    long, short = ready & (close > upper) & (close > trend), ready & (close < lower) & (close < trend)
    tr = pd.concat([frame.high-frame.low, (frame.high-close.shift()).abs(), (frame.low-close.shift()).abs()], axis=1).max(axis=1)
    atr = rma(tr, 14)
    availability = frame.index+pd.Timedelta(hours=hours)-BAR
    signals = pd.DataFrame(dict(signal=np.where(long, 1, np.where(short, -1, 0)), signal_atr=atr.to_numpy()), index=availability)
    mapped = signals.reindex(pd.DatetimeIndex(bars.timestamp))
    result = bars.copy()
    result['signal'] = mapped.signal.fillna(0).to_numpy(dtype=int)
    result['signal_atr'] = mapped.signal_atr.to_numpy()
    result['management_atr'] = pd.Series(atr.to_numpy(), index=availability).reindex(pd.DatetimeIndex(bars.timestamp), method='ffill').to_numpy()
    return result


def register(root=ROOT):
    parent = parent_plan(root)
    assert_historical_period('2026-10-28', root)
    out = directory(root); out.mkdir(parents=True, exist_ok=True)
    path = out/'manifest.json'
    previous = json.loads(path.read_text()) if path.exists() else None
    plan = dict(name=NAME, created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        candidates=candidates(), candidate_count=12, source_sha256={**parent['source_sha256'], 'channel_timeframe_lab.py': sha(root/'channel_timeframe_lab.py')},
        data_hashes=parent['data_hashes'], parent_protocol_sha256=parent['parent_protocol_sha256'],
        train_period=parent['train_period'], validation_period=parent['validation_period'], audit_period=parent['audit_period'],
        selection='Same fixed training gates/score as the six-family lab. Top training candidate per timeframe enters 2024; choose eligible finalist with best fixed validation rank. A daily model with insufficient 2020 trades remains ineligible.',
        source_selection_independent_of_later_audit=True,
        sizing_budget_bps=8., actual_fill_bps=[2., 4., 8.],
        gates=parent['train_gate'], chronological_gap_days=7,
        all_history_consumed=True, future_holdout_access=False, automatic_promotion=False,
        signal='Completed-candle close beyond preceding 20/55-candle high/low with EMA200 direction. No volume or distance threshold.',
        train_warmup='Causal input history only; models require 200 completed own-timeframe candles before any entry.')
    freeze(path, plan)
    return plan


def run(root=ROOT, verify=False):
    with collection_lock(directory(root)/'writer.lock'):
        return _run(root, verify)


def _run(root, verify):
    plan = register(root)
    out = directory(root)
    if (out/'results.json').exists() and not verify:
        return json.loads((out/'results.json').read_text())
    _, baseline_rule, cfg, meta = frozen_profile(root)
    cfg = replace(cfg, slippage_bps=8.)
    bars = load_development(root, plan)
    train = bars[bars.timestamp < utc(plan['train_period'][1])].reset_index(drop=True)
    rows = []
    for candidate in plan['candidates']:
        path = out/'training'/f"{candidate['id']}.json"
        if path.exists() and not verify:
            row = json.loads(path.read_text())
            if row['candidate'] != candidate or row['manifest_sha256'] != digest(plan):
                raise ValueError('Channel checkpoint identity changed')
        else:
            features = prepare(train, candidate)
            folds = []
            for year in [2020, 2021, 2022, 2023]:
                b, f = subset(train, features, f'{year}-01-01', min(utc(f'{year+1}-01-01'), utc(plan['train_period'][1])))
                from .strategy_lab import evaluate
                result, _, _ = evaluate(b, f, geometry(candidate), cfg)
                folds.append(dict(year=year, **result))
            row = dict(candidate=candidate, folds=folds, rank=training_rank(folds), manifest_sha256=digest(plan))
            path.parent.mkdir(parents=True, exist_ok=True)
            freeze(path, row)
        rows.append(row)
        print(f"CHANNEL TRAIN {candidate['id']} score={row['rank']['score']:.2f} eligible={row['rank']['eligible']}", flush=True)
        atomic_json(out/'status.json', dict(stage='training', complete=len(rows), total=12))
    shortlist = [choose_family([r for r in rows if r['candidate']['hours'] == h]) for h in [1, 4, 24]]
    freeze(out/'training_selection.json', dict(candidate_ids=[r['candidate']['id'] for r in shortlist], manifest_sha256=digest(plan)))
    preceding = bars[bars.timestamp < utc(plan['validation_period'][1])].reset_index(drop=True)
    validation = []
    for training in shortlist:
        candidate = training['candidate']
        features = prepare(preceding, candidate)
        b, f = subset(preceding, features, *plan['validation_period'])
        result = detailed(b, f, geometry(candidate), cfg, out/'validation'/candidate['id'])
        row = dict(candidate=candidate, result=result, rank=validation_rank(training, result))
        freeze(out/'validation'/f"{candidate['id']}.json", row)
        validation.append(row)
        print(f"CHANNEL VALIDATION {candidate['id']} closed={result['closed_net']:.2f} eligible={row['rank']['eligible']}", flush=True)
    eligible = [r for r in validation if r['rank']['eligible']]
    selected = max(eligible, key=lambda r: (r['rank']['score'], r['candidate']['id']))['candidate'] if eligible else None
    freeze(out/'selection.json', dict(candidate=selected, manifest_sha256=digest(plan), selected_before_audit=True))
    audit = []
    if selected:
        features = prepare(bars, selected)
        reference = apply_filter(prepare_features(bars, baseline_rule), RegimeFilter(**meta['entry_filters']))
        for label, start, end in [('audit_2025', '2025-01-01', '2026-01-01'), ('audit_2026', '2026-01-01', '2026-10-28'), ('full_development', '2023-01-01', '2026-10-28')]:
            b, f = subset(bars, features, start, end)
            _, base = subset(bars, reference, start, end)
            for slip in [2., 4., 8.]:
                actual = replace(cfg, slippage_bps=slip)
                for name, signals, rule, budget in [('challenger', f, geometry(selected), 8.),
                                                  ('original_2bp_budget', base, baseline_rule, 2.),
                                                  ('baseline_8bp_budget', base, baseline_rule, 8.)]:
                    result = detailed(b, signals, rule, actual, out/'audit'/label/f'{name}_fill{int(slip)}', budget)
                    audit.append(dict(period=label, strategy=name, fill_bps=slip, **result))
            print(f'CHANNEL AUDIT {label} complete', flush=True)
    result = dict(manifest_sha256=digest(plan), training=rows, validation=validation, selected=selected,
                  audit=audit, independent_future_validation=False, promoted=False)
    freeze(out/'results.json', result)
    atomic_json(out/'status.json', dict(stage='complete', candidates=12, selected=selected))
    report(root, result)
    if verify:
        freeze(out/'verification.json', dict(results_sha256=sha(out/'results.json'),
            artifacts_sha256={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.suffix in {'.parquet', '.csv'}},
            all_candidates_replayed=True, reproduced_exactly=True, independent_future_validation=False))
    return result


def report(root, result):
    lines = ['# Coarse channel timeframes', '',
             'Twelve predefined variants: 1h/4h/daily signals, prior 20/55-candle channels, EMA200 direction, two fixed exit profiles. No RVOL or trend-distance threshold. $100 planned risk, fixed 8bp sizing; fees, financing, two ticks and 2/4/8bp actual slippage.', '',
             '**Consumed development history, not independent validation.** Train on 2020-2023 annual closed outcomes at 8bp. Top candidate per timeframe enters 2024; selection freezes before 2025-2026. Training and 2024 end December 25 to leave seven-day gaps. All failed and undersampled candidates remain in the record.', '',
             '| Candidate | Penalized training score | Eligible |', '| --- | ---: | --- |']
    for r in result['training']:
        lines.append(f"| {r['candidate']['id']} | {r['rank']['score']:.2f} | {r['rank']['eligible']} |")
    lines += ['', f"Selected: **{result['selected']['id'] if result['selected'] else 'None: fixed gates failed'}**.", '',
              '| Period | Strategy | Fill cost | Net including open marks | Closed net | Drawdown | Entries |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in result['audit']:
        m = r['metrics']
        lines.append(f"| {r['period']} | {r['strategy']} | {r['fill_bps']}bp | ${pnl(m):,.2f} | ${r['closed_net']:,.2f} | {m['max_intrabar_drawdown']:.2%} | {m['entries']} |")
    lines += ['', 'All comparative replays use causal 2020-2022 indicator warm-up. Annual accounts reset. This does not promote a version, open the future holdout or guarantee future profits.', '']
    (root/'reports/channel_timeframes_round1.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    result = run(verify=parser.parse_args().verify)
    print(json.dumps(dict(selected=result['selected']), indent=2))

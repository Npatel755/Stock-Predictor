"""BNB round 2: pre-registered neighbourhood search around crypto_v0_1 with a plateau gate.

Round 1 picked one (coin, candidate) out of 200 fixed pairs, which is also what
luck would produce. Round 2 asks a different question on the chosen coin only:
does the time-series-momentum rule sit on a broad plateau of settings that all
work, or on an isolated spike? Isolated spikes do not generalize.

Protocol (frozen in manifest.json before any result is written):
  symbol     BNB only (the round-1 choice; BTC/other coins are not re-opened)
  grid       momentum lookback {10,15,20,30,40} bars x trend EMA {100,200,none}
             x volume gate {on,off} x timeframe {4h,8h} x 4 exit sets = 240 rules;
             crypto_v0_1 is the grid point (20, 200, on, 4h, patient)
  train      2021, 2022, 2023 independently reset annual accounts, 8bp costs,
             the same score and gates as round 1
  plateau    a rule is eligible only if it passes the training gate itself,
             at least half of its one-step neighbours pass it too, and the
             median training score over {rule + neighbours} is positive;
             ranking uses that median, not the rule's own score
  validation 2024, the top plateau rule and the crypto_v0_1 grid point only
  decision   crypto_v0_2 is proposed only if the top plateau rule differs
             from crypto_v0_1, passes the validation gate and scores at
             least as well as crypto_v0_1 on validation
  test       2025-01-01 .. 2026-10-28, run once for the proposed rule only.
             crypto_v0_1 has already seen this window (round 1); the
             comparison is reported, never used to pick between them
Selection never sees the test window; every grid point is kept on disk.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import json
import math

import numpy as np
import pandas as pd

from .data import DATA, UNIVERSE, load
from .lab import (TEST, TRAIN, TRAIN_YEARS, VALIDATION, detailed, evaluate, training_rank, validation_rank)
from ..alternative_strategies import SignalRule
from ..exit_research import freeze
from ..forward_collection import atomic_json
from ..generalization_policy import assert_historical_period, digest, frozen_profile
from ..indicators import resample_complete, rma
from ..market_data import BAR, utc
from ..optimize import subset
from ..paths import ROOT

NAME = 'crypto_round2_bnb'
SYMBOL = 'BNB'
LOOKBACKS = (10, 15, 20, 30, 40)
TRENDS = (100, 200, 0)          # 0 = no trend filter
VOLUME_GATES = (True, False)
HOURS = (4, 8)
EXITS = (('tight', (2., 4., 3.)), ('patient', (3., 5., 4.)), ('wide', (3., 8., 4.)), ('loose', (4., 6., 5.)))
BASELINE_ID = 'tsm_l20_t200_von_4h_patient'   # == candidates/crypto_v0_1
WARMUP_BARS = 200


@dataclass(frozen=True)
class MomentumRule:
    lookback: int
    trend: int
    volume_gate: bool
    timeframe_hours: int
    stop_atr: float
    reward_r: float
    trail_atr: float

    def __post_init__(self):
        if self.lookback not in LOOKBACKS or self.trend not in TRENDS or self.timeframe_hours not in HOURS:
            raise ValueError('Setting outside the registered round-2 grid')
        if not all(math.isfinite(x) and x > 0 for x in [self.stop_atr, self.reward_r, self.trail_atr]):
            raise ValueError('Exit settings must be positive and finite')

    def execution_rule(self):
        # Bracket/trailing geometry only; the execution loop receives explicit signals.
        return SignalRule('ema_cross', lookback=20, slow=200, stop_atr=self.stop_atr,
                          reward_r=self.reward_r, trail_atr=self.trail_atr)


def candidate_id(lookback, trend, volume_gate, hours, profile):
    return f"tsm_l{lookback}_t{trend or 'none'}_v{'on' if volume_gate else 'off'}_{hours}h_{profile}"


def candidates():
    rows = []
    for lookback in LOOKBACKS:
        for trend in TRENDS:
            for volume_gate in VOLUME_GATES:
                for hours in HOURS:
                    for profile, geometry in EXITS:
                        rule = MomentumRule(lookback, trend, volume_gate, hours, *geometry)
                        rows.append(dict(id=candidate_id(lookback, trend, volume_gate, hours, profile), kind='momentum_grid',
                                         coordinates=dict(lookback=LOOKBACKS.index(lookback), trend=TRENDS.index(trend),
                                                          volume=VOLUME_GATES.index(volume_gate), hours=HOURS.index(hours),
                                                          exits=[p for p, _ in EXITS].index(profile)),
                                         rule=asdict(rule)))
    assert any(r['id'] == BASELINE_ID for r in rows)
    return rows


def neighbours(candidate, rows):
    """Grid points differing from candidate in exactly one coordinate by one step."""
    mine = candidate['coordinates']
    out = []
    for other in rows:
        if other['id'] == candidate['id']:
            continue
        deltas = [abs(other['coordinates'][k]-mine[k]) for k in mine]
        if sum(deltas) == 1:
            out.append(other)
    return out


def plateau_rank(candidate, rows, scores):
    """scores: id -> training rank dict. Median over the one-step neighbourhood."""
    near = neighbours(candidate, rows)
    own = scores[candidate['id']]
    pool = [own['score']]+[scores[n['id']]['score'] for n in near]
    passing = sum(scores[n['id']]['eligible'] for n in near)
    median = float(np.median(pool))
    eligible = bool(own['eligible'] and 2*passing >= len(near) and median > 0)
    return dict(score=median, eligible=eligible, neighbours=len(near), neighbours_eligible=int(passing))


def directory(root):
    return root/'artifacts/crypto_research'/NAME


def plan(root=ROOT, data=DATA):
    assert_historical_period(TEST[1], root)
    data_hash = load(SYMBOL, data)[1]['parquet_sha256']
    out = directory(root)
    previous = json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else None
    manifest = dict(
        name=NAME, symbol=SYMBOL, data_hash=data_hash,
        created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        authorization='User asked on 2026-11-03 to pick one coin and improve the strategy on it with generalization, not raw fit, as the goal.',
        parent='candidates/crypto_v0_1', baseline_id=BASELINE_ID,
        candidates=candidates(), grid=dict(lookbacks=LOOKBACKS, trends=TRENDS, volume_gates=VOLUME_GATES, hours=HOURS, exits=EXITS),
        train_period=TRAIN, train_folds='Three independently reset annual accounts (2021, 2022, 2023).',
        validation_period=VALIDATION, test_period=TEST,
        scoring='Round-1 training score and gates unchanged (closed net at 8bp fills + 8bp sizing budget, $100 risk, $50k account).',
        plateau_gate='Own training gate passed, >=50% of one-step grid neighbours pass it, median(own+neighbour scores) > 0; rank by that median; tie by id.',
        validation='2024: top plateau rule and the crypto_v0_1 grid point; round-1 validation gate.',
        decision='Propose crypto_v0_2 only if top plateau rule != baseline, passes validation gate, and validation score >= baseline validation score.',
        test_gate='Proposed rule only, single look: positive closed net at 8bp in 2025 and in 2026, <=5% drawdown at 2/4/8bp, no margin calls. '
                  'Baseline held-out numbers (already observed in round 1) are reported alongside but never used for selection.',
        cost_scenarios_bps=[2., 4., 8.], sizing_budget_bps=8., risk_usd=100., initial_capital=50000.,
        test_window_used_for_selection=False, threshold_changes_after_results=False,
        promotion='Passing creates candidates/crypto_v0_2 (unpromoted); crypto_v0_1 and ETH v1.11 are not modified.')
    if previous and digest({k: v for k, v in previous.items() if k != 'created_at_utc'}) != digest({k: v for k, v in manifest.items() if k != 'created_at_utc'}):
        raise ValueError('round-2 manifest changed after registration; use a new NAME')
    out.mkdir(parents=True, exist_ok=True)
    if not (out/'manifest.json').exists():
        freeze(out/'manifest.json', manifest)
    return manifest


class Features:
    """Per-timeframe completed-candle features, computed once and shared by the grid."""

    def __init__(self, bars):
        self.bars = bars
        self.cache = {}

    def base(self, hours_count):
        if hours_count not in self.cache:
            hours = resample_complete(self.bars, f'{hours_count}h')
            c = hours.close
            tr = pd.concat([hours.high-hours.low, (hours.high-c.shift()).abs(), (hours.low-c.shift()).abs()], axis=1).max(axis=1)
            self.cache[hours_count] = dict(
                hours=hours, atr=rma(tr, 14), ready=c.expanding().count() >= WARMUP_BARS,
                volume_ok=hours.volume >= hours.volume.shift().rolling(20).mean(),
                trend={t: c.ewm(span=t, adjust=False).mean() for t in TRENDS if t})
        return self.cache[hours_count]

    def signals(self, rule):
        f = self.base(rule.timeframe_hours)
        hours, c, atr = f['hours'], f['hours'].close, f['atr']
        momentum = c/c.shift(rule.lookback)-1
        above = (c > f['trend'][rule.trend]) if rule.trend else pd.Series(True, index=hours.index)
        below = (c < f['trend'][rule.trend]) if rule.trend else pd.Series(True, index=hours.index)
        long = (momentum > 0) & (momentum.shift() <= 0) & above
        short = (momentum < 0) & (momentum.shift() >= 0) & below
        volume_ok = f['volume_ok'] if rule.volume_gate else pd.Series(True, index=hours.index)
        availability = hours.index+pd.Timedelta(hours=rule.timeframe_hours)-BAR
        hourly = pd.DataFrame(dict(signal=np.where(f['ready'] & volume_ok & long, 1, np.where(f['ready'] & volume_ok & short, -1, 0)),
                                   signal_atr=atr.to_numpy()), index=availability)
        mapped = hourly.reindex(pd.DatetimeIndex(self.bars.timestamp))
        output = self.bars.copy()
        output['signal'] = mapped.signal.fillna(0).to_numpy(dtype=int)
        output['signal_atr'] = mapped.signal_atr.to_numpy()
        output['management_atr'] = pd.Series(atr.to_numpy(), index=availability).reindex(
            pd.DatetimeIndex(self.bars.timestamp), method='ffill').to_numpy()
        return output


def train(bars, manifest, cfg, out, verify):
    rows = []
    train_bars = bars[bars.timestamp < utc(TRAIN[1])].reset_index(drop=True)
    features = Features(train_bars)
    for candidate in manifest['candidates']:
        path = out/'training'/f"{candidate['id']}.json"
        if path.exists() and not verify:
            row = json.loads(path.read_text())
            if row['candidate'] != candidate or row['manifest_sha256'] != digest(manifest):
                raise ValueError('Training checkpoint changed identity')
            rows.append(row)
            continue
        rule = MomentumRule(**candidate['rule'])
        signals = features.signals(rule)
        folds = []
        for year in TRAIN_YEARS:
            b, f = subset(train_bars, signals, f'{year}-01-01', f'{year+1}-01-01')
            result, _, _ = evaluate(SYMBOL, b, f, rule.execution_rule(), cfg)
            folds.append(dict(year=year, **result))
        row = dict(symbol=SYMBOL, candidate=candidate, folds=folds, rank=training_rank(folds), manifest_sha256=digest(manifest))
        path.parent.mkdir(parents=True, exist_ok=True)
        freeze(path, row)
        rows.append(row)
        print(f"TRAIN {candidate['id']} score={row['rank']['score']:.0f} eligible={row['rank']['eligible']}", flush=True)
        atomic_json(out/'status.json', dict(stage='training', complete=len(rows), total=len(manifest['candidates'])))
    return rows


def validate(bars, candidate, training_row, cfg, out, manifest):
    path = out/'validation'/f"{candidate['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    rule = MomentumRule(**candidate['rule'])
    preceding = bars[bars.timestamp < utc(VALIDATION[1])].reset_index(drop=True)
    b, f = subset(preceding, Features(preceding).signals(rule), *VALIDATION)
    result = detailed(SYMBOL, b, f, rule.execution_rule(), cfg, out/'validation'/candidate['id'])
    row = dict(symbol=SYMBOL, candidate=candidate, result=result, rank=validation_rank(training_row, result), manifest_sha256=digest(manifest))
    freeze(path, row)
    return row


def run(root=ROOT, data=DATA, verify=False, held_out=False):
    manifest = plan(root, data)
    out = directory(root)
    _, _, cfg, _ = frozen_profile(root)
    cfg = replace(cfg, slippage_bps=8.)
    bars, _ = load(SYMBOL, data, manifest['data_hash'])
    training = train(bars, manifest, cfg, out, verify)
    by_id = {r['candidate']['id']: r for r in training}
    scores = {k: r['rank'] for k, r in by_id.items()}
    plateau = {c['id']: plateau_rank(c, manifest['candidates'], scores) for c in manifest['candidates']}
    ranked = sorted(manifest['candidates'], key=lambda c: (-plateau[c['id']]['eligible'], -plateau[c['id']]['score'], c['id']))
    top = ranked[0]
    baseline = next(c for c in manifest['candidates'] if c['id'] == BASELINE_ID)
    validation = {}
    for candidate in [top, baseline]:
        if candidate['id'] in validation:
            continue
        validation[candidate['id']] = validate(bars, candidate, by_id[candidate['id']], cfg, out, manifest)
        v = validation[candidate['id']]
        print(f"VALIDATION {candidate['id']} closed={v['result']['closed_net']:.0f} eligible={v['rank']['eligible']}", flush=True)
    top_v, base_v = validation[top['id']], validation[BASELINE_ID]
    proposed = (top['id'] != BASELINE_ID and plateau[top['id']]['eligible'] and top_v['rank']['eligible']
                and top_v['rank']['score'] >= base_v['rank']['score'])
    if top['id'] == BASELINE_ID:
        reason = 'Top plateau rule is crypto_v0_1 itself; nothing to propose'
    elif not plateau[top['id']]['eligible']:
        reason = 'No rule passed the plateau gate'
    elif not top_v['rank']['eligible']:
        reason = 'Top plateau rule failed the 2024 validation gate'
    elif not proposed:
        reason = 'Top plateau rule validated below crypto_v0_1'
    else:
        reason = 'Top plateau rule passed validation at or above crypto_v0_1'
    selection = dict(manifest_sha256=digest(manifest), top_plateau=top['id'], baseline=BASELINE_ID,
                     proposed=dict(symbol=SYMBOL, candidate=top) if proposed else None, reason=reason,
                     test_window_seen=False, promoted=False)
    if not (out/'selection.json').exists():
        freeze(out/'selection.json', selection)
    summary = dict(manifest_sha256=digest(manifest),
                   training=[dict(id=c['id'], **{f'own_{k}': v for k, v in scores[c['id']].items()}, **plateau[c['id']]) for c in ranked],
                   folds={c['id']: [dict(year=f['year'], closed_net=f['closed_net'], drawdown=f['metrics']['max_intrabar_drawdown'],
                                         legs=f['metrics']['closed_trade_legs']) for f in by_id[c['id']]['folds']] for c in ranked},
                   validation={k: dict(closed_net=v['result']['closed_net'], drawdown=v['result']['metrics']['max_intrabar_drawdown'],
                                       legs=v['result']['metrics']['closed_trade_legs'], **v['rank']) for k, v in validation.items()},
                   selection=selection, test=None)
    atomic_json(out/'results.json', summary)
    atomic_json(out/'status.json', dict(stage='selected', proposed=selection['proposed']))
    if held_out and selection['proposed'] is not None:
        summary['test'] = test(root, data, selection['proposed']['candidate'], cfg, out)
        atomic_json(out/'results.json', summary)
    report(out, summary, manifest)
    return summary


def test(root, data, candidate, cfg, out):
    """Single look at the held-out window for the one proposed rule."""
    path = out/'test.json'
    if path.exists():
        return json.loads(path.read_text())
    bars, _ = load(SYMBOL, data)
    rule = MomentumRule(**candidate['rule'])
    signals = Features(bars).signals(rule)
    rows = []
    for label, begin, end in [('test_2025', '2025-01-01', '2026-01-01'), ('test_2026', '2026-01-01', TEST[1]), ('test_full', *TEST)]:
        b, f = subset(bars, signals, begin, end)
        for slip in [2., 4., 8.]:
            result = detailed(SYMBOL, b, f, rule.execution_rule(), replace(cfg, slippage_bps=slip), out/'test'/label/f'fill{int(slip)}')
            rows.append(dict(period=label, actual_fill_slippage_bps=slip, closed_net=result['closed_net'],
                             drawdown=result['metrics']['max_intrabar_drawdown'], legs=result['metrics']['closed_trade_legs'],
                             margin_calls=result['metrics']['margin_call_events']))
    annual8 = [r for r in rows if r['period'] != 'test_full' and r['actual_fill_slippage_bps'] == 8.]
    passed = all(r['closed_net'] > 0 for r in annual8) and all(r['drawdown'] <= .05 and r['margin_calls'] == 0 for r in rows)
    baseline_test = root/'artifacts/crypto_research/crypto_round1/test.json'
    baseline_rows = json.loads(baseline_test.read_text())['rows'] if baseline_test.exists() else None
    outcome = dict(symbol=SYMBOL, candidate=candidate, rows=rows, passed=bool(passed), single_look=True,
                   baseline_rows=baseline_rows,
                   note='Held-out result is evidence about this one pre-selected rule only; it was not used to choose it. '
                        'The crypto_v0_1 rows were observed in round 1 and are shown for context, not selection.')
    freeze(path, outcome)
    if passed:
        register(root, outcome, cfg)
    return outcome


def register(root, outcome, cfg):
    folder = root/'candidates/crypto_v0_2'
    folder.mkdir(parents=True, exist_ok=True)
    config = dict(version='crypto_v0_2', parent='crypto_v0_1', symbol=SYMBOL, breakout=UNIVERSE[SYMBOL],
                  candidate=outcome['candidate'], risk_usd=cfg.risk_usd, initial_capital=cfg.initial_capital,
                  slippage_budget_bps=8., commission_bps=cfg.commission_bps, promoted=False,
                  evidence='train 2021-23 / plateau gate / validation 2024 / single-look test 2025-2026-10-28; no forward evidence yet')
    atomic_json(folder/'config.json', config)
    atomic_json(folder/'protocol.json', dict(lab=NAME, manifest_sha256=digest(json.loads((directory(root)/'manifest.json').read_text()))))


def axis_summary(summary, manifest):
    """Median own training score along each grid axis: a flat axis is a plateau, a spike is not."""
    own = {r['id']: r['own_score'] for r in summary['training']}
    coords = {c['id']: c['coordinates'] for c in manifest['candidates']}
    grid = manifest['grid']
    labels = dict(lookbacks=grid['lookbacks'], trends=[t or 'none' for t in grid['trends']], volume_gates=grid['volume_gates'],
                  hours=grid['hours'], exits=[e[0] for e in grid['exits']])
    keys = dict(lookbacks='lookback', trends='trend', volume_gates='volume', hours='hours', exits='exits')
    lines = []
    for axis, values in labels.items():
        cells = []
        for i, value in enumerate(values):
            pool = [own[k] for k, c in coords.items() if c[keys[axis]] == i]
            cells.append(f"{value}: median {np.median(pool):.0f}, {sum(p > 0 for p in pool)}/{len(pool)} positive")
        lines.append(f"- {axis}: " + '; '.join(cells))
    return lines


def report(out, summary, manifest):
    lines = [f'# Crypto research {NAME}', '', 'Pre-registered BNB-only neighbourhood search around crypto_v0_1 (240 grid rules). '
             'Ranking uses the median training score over each rule and its one-step neighbours (plateau), not the best single fit.', '',
             '## Top 12 by plateau score', '', '| Rule | Plateau | Own | Neighbours passing | Plateau eligible | 2021 / 2022 / 2023 net |', '|---|---|---|---|---|---|']
    for r in summary['training'][:12]:
        folds = summary['folds'][r['id']]
        lines.append(f"| {r['id']} | {r['score']:.0f} | {r['own_score']:.0f} | {r['neighbours_eligible']}/{r['neighbours']} | {r['eligible']} | "
                     + ' / '.join(f"{f['closed_net']:.0f}" for f in folds)+' |')
    base = next(r for r in summary['training'] if r['id'] == BASELINE_ID)
    lines += ['', f"crypto_v0_1 grid point ({BASELINE_ID}): plateau {base['score']:.0f}, own {base['own_score']:.0f}, "
                  f"neighbours passing {base['neighbours_eligible']}/{base['neighbours']}, rank {summary['training'].index(base)+1} of {len(summary['training'])}.",
              '', '## Training score by grid axis (median own score, count positive)', '', *axis_summary(summary, manifest),
              '', '## Validation 2024 (8bp)', '', '| Rule | Closed net | Drawdown | Legs | Eligible | Score |', '|---|---|---|---|---|---|']
    for k, v in summary['validation'].items():
        lines.append(f"| {k} | {v['closed_net']:.0f} | {v['drawdown']:.2%} | {v['legs']} | {v['eligible']} | {v['score']:.0f} |")
    lines += ['', f"## Decision: {summary['selection']['reason']}", '', f"Proposed: {summary['selection']['proposed'] and summary['selection']['proposed']['candidate']['id']}"]
    if summary['test']:
        t = summary['test']
        lines += ['', f"## Held-out test (single look) — passed: {t['passed']}", '', '| Period | Fill bp | Proposed closed net | Drawdown | Legs | crypto_v0_1 closed net | Drawdown |', '|---|---|---|---|---|---|---|']
        for r in t['rows']:
            b = next((x for x in (t['baseline_rows'] or []) if x['period'] == r['period'] and x['actual_fill_slippage_bps'] == r['actual_fill_slippage_bps']), None)
            lines.append(f"| {r['period']} | {int(r['actual_fill_slippage_bps'])} | {r['closed_net']:.0f} | {r['drawdown']:.2%} | {r['legs']} | "
                         + (f"{b['closed_net']:.0f} | {b['drawdown']:.2%} |" if b else 'n/a | n/a |'))
    (out/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--held-out', action='store_true', help='Run the single-look test for the proposed rule')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    run(verify=args.verify, held_out=args.held_out)

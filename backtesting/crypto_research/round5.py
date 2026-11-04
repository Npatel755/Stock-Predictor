"""Round 5: different return sources, not more indicator rules.

Rounds 1-4 searched single-coin indicator rules (one survivor per ~100 tries) and
confirmed that popular indicator recipes lose at realistic costs. Round 5 tests
three mechanics that use information those rules never see:
  xs_momentum       cross-sectional momentum: rank the eight coins by trailing return;
                    long a coin while it is in the top-2 with a positive return and above
                    its EMA50, short while in the bottom-2 with a negative return and below
                    EMA50; exit when it leaves the top/bottom-4 (hysteresis). Daily.
  rel_strength_btc  relative strength vs BTC: the coin/BTC ratio's trailing return turns
                    positive with the coin above its EMA50 (long) or negative below (short);
                    exit when the ratio return flips back. Daily. (BTC itself is skipped.)
  session_breakout  time-of-day: first 1h close after 08:00 UTC beyond the Asia-session
                    (00:00-08:00 UTC) range enters with the stop at the other side of the
                    range, 2R target, 24h time stop; optional EMA200(1h) trend filter.

Protocol (frozen in manifest.json before any result is written):
  coins      BTC SOL XRP BNB DOGE LINK LTC ADA (round-1 universe and data)
  candidates xs_momentum {30, 90}d, rel_strength_btc {30, 60}d, session_breakout {trend, no trend}
             = 6 per coin (4 for BTC), 46 in total; fixed geometry per family, 8bp costs, $100 risk
  train      2021, 2022, 2023 independently reset accounts, round-1 score and gate
  validation 2024 for every training-eligible candidate
  test       2025-01-01 .. 2026-10-28, one look per validation passer
  versions   passers register as candidates/crypto_v0_6, v0_7, ... in universe/candidate order; none promoted
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import json

import numpy as np
import pandas as pd

from .data import DATA, UNIVERSE, load
from .lab import TEST, TRAIN, TRAIN_YEARS, VALIDATION, training_rank, validation_rank
from .round3 import register as register_version
from .round4 import detailed, evaluate, true_range
from ..alternative_strategies import SignalRule
from ..exit_research import freeze
from ..forward_collection import atomic_json
from ..generalization_policy import assert_historical_period, digest, frozen_profile
from ..indicators import resample_complete, rma
from ..market_data import BAR, utc
from ..optimize import subset
from ..paths import ROOT

NAME = 'crypto_round5_sources'
FIRST_VERSION = 6
BIG_TARGET = 100.
DAY, HOUR = pd.Timedelta(days=1), pd.Timedelta(hours=1)
# family -> (parameter values, stop_atr, reward_r, max_holding_bars, description)
RULES = {
    'xs_momentum': ((30, 90), 3., BIG_TARGET, 0,
                    'Daily. Rank the 8 coins by trailing {p}-day return. Long while rank <= 2 with return > 0 and close > EMA50; '
                    'short while rank >= 7 with return < 0 and close < EMA50; entry on the day the condition first holds; '
                    'exit at the close of the day the coin leaves the top-4 (long) / bottom-4 (short). 3 ATR(14) protective stop.'),
    'rel_strength_btc': ((30, 60), 3., BIG_TARGET, 0,
                         'Daily. r = (coin/BTC) trailing {p}-day return. Long when r crosses above 0 with close > EMA50; short when r crosses '
                         'below 0 with close < EMA50; exit when r crosses back through 0. 3 ATR(14) protective stop. Not run on BTC.'),
    'session_breakout': (('trend', 'notrend'), 1., 2., 288,
                         '1h. Asia range = high/low of the 00:00-08:00 UTC hours. First 1h close after 08:00 above the range enters long '
                         '(below: short), at most one entry per day, stop at the other side of the range, 2R target, 24h time stop. '
                         '"trend": close must also be on the EMA200(1h) side of the trade.')
}


@dataclass(frozen=True)
class SourceRule:
    family: str
    parameter: object

    def __post_init__(self):
        if self.family not in RULES or self.parameter not in RULES[self.family][0]:
            raise ValueError('Setting outside the registered round-5 manifest')

    @property
    def spec(self):
        return RULES[self.family]

    def execution_rule(self):
        return SignalRule('ema_cross', lookback=20, slow=200, stop_atr=self.spec[1], reward_r=self.spec[2], trail_atr=0., max_holding_bars=self.spec[3])


def candidates(symbol=None):
    rows = [dict(id=f'{family}_{p}', kind='source', rule=dict(family=family, parameter=p)) for family, spec in RULES.items() for p in spec[0]]
    if symbol == 'BTC':
        rows = [r for r in rows if r['rule']['family'] != 'rel_strength_btc']
    return rows


def directory(root):
    return root/'artifacts/crypto_research'/NAME


def plan(root=ROOT, symbols=None, data=DATA):
    assert_historical_period(TEST[1], root)
    symbols = list(symbols or UNIVERSE)
    hashes = {s: load(s, data)[1]['parquet_sha256'] for s in UNIVERSE}
    out = directory(root)
    previous = json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else None
    manifest = dict(
        name=NAME, symbols=symbols, data_hashes=hashes,
        created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        authorization='User asked on 2026-11-04 to keep finding avenues and add only one or two valuable strategies to the paper server.',
        candidates={s: candidates(s) for s in symbols},
        rules={k: dict(parameters=v[0], stop_atr=v[1], reward_r=v[2], max_holding_bars=v[3], rule=v[4]) for k, v in RULES.items()},
        cross_sectional_universe=list(UNIVERSE), first_version=FIRST_VERSION,
        train_period=TRAIN, train_folds='Three independently reset annual accounts (2021, 2022, 2023).',
        validation_period=VALIDATION, test_period=TEST,
        scoring='Round-1 training score and gates unchanged (closed net at 8bp fills + 8bp sizing budget, $100 risk, $50k account).',
        validation='Every training-eligible candidate is validated on 2024; round-1 validation gate.',
        test_gate='One look per validation passer: positive closed net at 8bp in 2025 and in 2026, <=5% drawdown at 2/4/8bp, no margin calls.',
        cost_scenarios_bps=[2., 4., 8.], sizing_budget_bps=8., risk_usd=100., initial_capital=50000.,
        test_window_used_for_selection=False, threshold_changes_after_results=False,
        promotion='Each passer is registered as candidates/crypto_v0_N (unpromoted) in universe/candidate order; nothing existing is modified.')
    if previous and digest({k: v for k, v in previous.items() if k != 'created_at_utc'}) != digest({k: v for k, v in manifest.items() if k != 'created_at_utc'}):
        raise ValueError('round-5 manifest changed after registration; use a new NAME')
    out.mkdir(parents=True, exist_ok=True)
    if not (out/'manifest.json').exists():
        freeze(out/'manifest.json', manifest)
    return manifest


def daily_closes(frames):
    """Completed-day closes for every coin, aligned on the union of days (no forward fill)."""
    return pd.DataFrame({s: resample_complete(b, '1D').close for s, b in frames.items()}).sort_index()


class Features:
    def __init__(self, bars, symbol, closes):
        self.bars, self.symbol, self.closes = bars, symbol, closes
        self.cache = {}

    def base(self, rule_name):
        if rule_name not in self.cache:
            k = resample_complete(self.bars, rule_name)
            span = DAY if rule_name == '1D' else HOUR
            self.cache[rule_name] = dict(candles=k, atr=rma(true_range(k), 14), availability=k.index+span-BAR)
        return self.cache[rule_name]

    def raw(self, rule):
        p = rule.parameter
        if rule.family == 'session_breakout':
            f = self.base('1h')
            k, c = f['candles'], f['candles'].close
            day = k.index.floor('D')
            asia = (k.index.hour < 8)
            asia_high = k.high.where(asia).groupby(day).transform('max')
            asia_low = k.low.where(asia).groupby(day).transform('min')
            after = pd.Series(k.index.hour >= 8, index=k.index)
            trend = c.ewm(span=200, adjust=False).mean()
            ready = c.expanding().count() >= 200
            up, down = c > asia_high, c < asia_low
            if p == 'trend':
                up, down = up & (c > trend), down & (c < trend)
            # first qualifying hour of each UTC day only, in either direction
            either = (up | down) & after
            first = either & (either.astype(int).groupby(day).cumsum() == 1)
            long, short = first & up & ready, first & down & ready
            basis = pd.Series(np.where(long, c-asia_low, np.where(short, asia_high-c, f['atr'])), index=k.index)
            return long.fillna(False), short.fillna(False), pd.Series(False, index=k.index), pd.Series(False, index=k.index), basis, f
        f = self.base('1D')
        k, c = f['candles'], f['candles'].close
        ema = c.ewm(span=50, adjust=False).mean()
        ready = c.expanding().count() >= 100
        closes = self.closes.reindex(self.closes.index.union(k.index)).loc[k.index]
        if rule.family == 'xs_momentum':
            returns = closes/closes.shift(p)-1
            rank = returns.rank(axis=1, ascending=False)
            own, own_rank = returns[self.symbol], rank[self.symbol]
            in_long, in_short = (own_rank <= 2) & (own > 0) & (c > ema), (own_rank >= 7) & (own < 0) & (c < ema)
            long, short = in_long & ~in_long.shift().fillna(False), in_short & ~in_short.shift().fillna(False)
            exit_long, exit_short = own_rank > 4, own_rank < 5
        else:
            ratio = closes[self.symbol]/closes['BTC']
            r = ratio/ratio.shift(p)-1
            long, short = (r > 0) & (r.shift() <= 0) & (c > ema), (r < 0) & (r.shift() >= 0) & (c < ema)
            exit_long, exit_short = (r < 0) & (r.shift() >= 0), (r > 0) & (r.shift() <= 0)
        return (long & ready).fillna(False), (short & ready).fillna(False), exit_long.fillna(False), exit_short.fillna(False), f['atr'], f

    def signals(self, rule):
        long, short, exit_long, exit_short, basis, f = self.raw(rule)
        table = pd.DataFrame(dict(signal=np.where(long, 1, np.where(short, -1, 0)),
                                  exit_signal=np.where(exit_long, 1, np.where(exit_short, -1, 0)),
                                  signal_atr=basis.to_numpy()), index=f['availability'])
        index = pd.DatetimeIndex(self.bars.timestamp)
        mapped = table.reindex(index)
        output = self.bars.copy()
        output['signal'] = mapped.signal.fillna(0).to_numpy(dtype=int)
        output['exit_signal'] = mapped.exit_signal.fillna(0).to_numpy(dtype=int)
        output['signal_atr'] = mapped.signal_atr.to_numpy()
        output['management_atr'] = pd.Series(f['atr'].to_numpy(), index=f['availability']).reindex(index, method='ffill').to_numpy()
        return output


def features_for(symbol, frames, end):
    cut = {s: b[b.timestamp < utc(end)].reset_index(drop=True) for s, b in frames.items()}
    return Features(cut[symbol], symbol, daily_closes(cut)), cut[symbol]


def train_symbol(symbol, frames, manifest, cfg, out, verify):
    rows = []
    features, train_bars = features_for(symbol, frames, TRAIN[1])
    for candidate in manifest['candidates'][symbol]:
        path = out/'training'/symbol/f"{candidate['id']}.json"
        if path.exists() and not verify:
            row = json.loads(path.read_text())
            if row['candidate'] != candidate or row['manifest_sha256'] != digest(manifest):
                raise ValueError('Training checkpoint changed identity')
            rows.append(row)
            continue
        rule = SourceRule(**candidate['rule'])
        signals = features.signals(rule)
        folds = []
        for year in TRAIN_YEARS:
            b, f = subset(train_bars, signals, f'{year}-01-01', f'{year+1}-01-01')
            result, _, _ = evaluate(symbol, b, f, rule.execution_rule(), cfg)
            folds.append(dict(year=year, **result))
        row = dict(symbol=symbol, candidate=candidate, folds=folds, rank=training_rank(folds), manifest_sha256=digest(manifest))
        path.parent.mkdir(parents=True, exist_ok=True)
        freeze(path, row)
        rows.append(row)
        print(f"TRAIN {symbol} {candidate['id']} score={row['rank']['score']:.0f} eligible={row['rank']['eligible']}", flush=True)
        atomic_json(out/'status.json', dict(stage='training', symbol=symbol, complete=len(rows), total=len(manifest['candidates'][symbol])))
    return rows


def validate(symbol, frames, training_row, cfg, out, manifest):
    candidate = training_row['candidate']
    path = out/'validation'/symbol/f"{candidate['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    rule = SourceRule(**candidate['rule'])
    features, preceding = features_for(symbol, frames, VALIDATION[1])
    b, f = subset(preceding, features.signals(rule), *VALIDATION)
    result = detailed(symbol, b, f, rule.execution_rule(), cfg, out/'validation'/symbol/candidate['id'])
    row = dict(symbol=symbol, candidate=candidate, result=result, rank=validation_rank(training_row, result), manifest_sha256=digest(manifest))
    freeze(path, row)
    return row


def run(root=ROOT, symbols=None, data=DATA, verify=False, held_out=False):
    manifest = plan(root, symbols, data)
    out = directory(root)
    _, _, cfg, _ = frozen_profile(root)
    cfg = replace(cfg, slippage_bps=8.)
    frames = {s: load(s, data, manifest['data_hashes'][s])[0] for s in UNIVERSE}
    training, validation = {}, []
    for symbol in manifest['symbols']:
        rows = train_symbol(symbol, frames, manifest, cfg, out, verify)
        training[symbol] = rows
        for row in rows:
            if row['rank']['eligible']:
                v = validate(symbol, frames, row, cfg, out, manifest)
                validation.append(v)
                print(f"VALIDATION {symbol} {row['candidate']['id']} closed={v['result']['closed_net']:.0f} eligible={v['rank']['eligible']}", flush=True)
    selected = [dict(symbol=r['symbol'], candidate=r['candidate']) for r in validation if r['rank']['eligible']]
    selection = dict(manifest_sha256=digest(manifest), selected=selected,
                     reason=f'{len(selected)} validation passers out of {len(validation)} training-eligible candidates; each gets one held-out look',
                     test_window_seen=False, promoted=False)
    if not (out/'selection.json').exists():
        freeze(out/'selection.json', selection)
    summary = dict(manifest_sha256=digest(manifest),
                   training={s: [dict(id=r['candidate']['id'], **r['rank']) for r in rows] for s, rows in training.items()},
                   validation=[dict(symbol=r['symbol'], id=r['candidate']['id'], closed_net=r['result']['closed_net'],
                                    drawdown=r['result']['metrics']['max_intrabar_drawdown'], legs=r['result']['metrics']['closed_trade_legs'], **r['rank'])
                               for r in validation],
                   selection=selection, test=None)
    atomic_json(out/'results.json', summary)
    atomic_json(out/'status.json', dict(stage='selected', selected=selected))
    if held_out and selected:
        summary['test'] = [test(root, frames, pair, cfg, out, FIRST_VERSION+i) for i, pair in enumerate(selected)]
        atomic_json(out/'results.json', summary)
    report(out, summary)
    return summary


def test(root, frames, pair, cfg, out, version):
    symbol, candidate = pair['symbol'], pair['candidate']
    path = out/'test'/f"{symbol}_{candidate['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    rule = SourceRule(**candidate['rule'])
    features = Features(frames[symbol], symbol, daily_closes(frames)).signals(rule)
    rows = []
    for label, begin, end in [('test_2025', '2025-01-01', '2026-01-01'), ('test_2026', '2026-01-01', TEST[1]), ('test_full', *TEST)]:
        b, f = subset(frames[symbol], features, begin, end)
        for slip in [2., 4., 8.]:
            result = detailed(symbol, b, f, rule.execution_rule(), replace(cfg, slippage_bps=slip), out/'test'/symbol/candidate['id']/label/f'fill{int(slip)}')
            rows.append(dict(period=label, actual_fill_slippage_bps=slip, closed_net=result['closed_net'],
                             drawdown=result['metrics']['max_intrabar_drawdown'], legs=result['metrics']['closed_trade_legs'],
                             margin_calls=result['metrics']['margin_call_events']))
    annual8 = [r for r in rows if r['period'] != 'test_full' and r['actual_fill_slippage_bps'] == 8.]
    passed = all(r['closed_net'] > 0 for r in annual8) and all(r['drawdown'] <= .05 and r['margin_calls'] == 0 for r in rows)
    outcome = dict(symbol=symbol, candidate=candidate, rows=rows, passed=bool(passed), single_look=True,
                   version=f'crypto_v0_{version}' if passed else None,
                   note='Held-out result is evidence about this one pre-selected pair only; it was not used to choose it.')
    freeze(path, outcome)
    if passed:
        register_version(root, outcome, cfg)
    return outcome


def report(out, summary):
    lines = [f'# Crypto research {NAME}', '', 'Cross-sectional momentum, relative strength vs BTC and Asia-session breakout (see manifest.json); '
             'every training-eligible candidate validated on 2024; every validation passer gets one held-out look.', '',
             '## Training (eligible candidates per coin)', '']
    for symbol, rows in summary['training'].items():
        passing = sorted((r for r in rows if r['eligible']), key=lambda r: -r['score'])
        lines.append(f"- {symbol}: {len(passing)}/{len(rows)} eligible" + (': ' + ', '.join(f"{r['id']} ({r['score']:.0f})" for r in passing) if passing else ''))
    lines += ['', '## Validation 2024 (all training-eligible candidates)', '', '| Coin | Candidate | Closed net | Drawdown | Legs | Eligible |', '|---|---|---|---|---|---|']
    lines += [f"| {v['symbol']} | {v['id']} | ${v['closed_net']:,.0f} | {v['drawdown']:.2%} | {v['legs']} | {v['eligible']} |" for v in summary['validation']]
    lines += ['', f"## Selection: {summary['selection']['reason']}", '']
    if summary['test']:
        lines += ['## Held-out 2025-2026 (single look per pair)', '', '| Coin | Candidate | 2025 @8bp | 2026 @8bp | Full @8bp | Worst DD | Passed | Version |', '|---|---|---|---|---|---|---|---|']
        for t in summary['test']:
            at8 = {r['period']: r for r in t['rows'] if r['actual_fill_slippage_bps'] == 8.}
            lines.append(f"| {t['symbol']} | {t['candidate']['id']} | ${at8['test_2025']['closed_net']:,.0f} | ${at8['test_2026']['closed_net']:,.0f} | "
                         f"${at8['test_full']['closed_net']:,.0f} | {max(r['drawdown'] for r in t['rows']):.2%} | {t['passed']} | {t['version'] or '-'} |")
    else:
        lines.append('Held-out window not opened yet.')
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--symbols', nargs='*')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--held-out', action='store_true')
    args = parser.parse_args()
    summary = run(symbols=args.symbols, verify=args.verify, held_out=args.held_out)
    print(json.dumps(summary['selection'], indent=2))


if __name__ == '__main__':
    main()

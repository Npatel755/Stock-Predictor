"""Round 3: eight NEW signal families on all eight Breakout coins, 4h and daily, run in tandem.

Rounds 1-2 exhausted the six original families (one survivor, BNB crypto_v0_1)
and showed that re-tuning a family on the same coin overfits. Round 3 widens
the search sideways instead: different signal mechanics, one more timeframe,
the same frozen exits, costs, gates and chronology. Every coin whose
pre-selected candidate passes 2024 validation gets its own single held-out look,
so several strategies can be paper traded side by side.

Protocol (frozen in manifest.json before any result is written):
  coins      BTC SOL XRP BNB DOGE LINK LTC ADA (round-1 universe, same data)
  families   donchian20, donchian55, keltner, contraction, zscore, macd, efficiency, rsi50
  timeframe  4h (trend EMA200, 200-candle warm-up) and 1D (trend EMA50, 60-day warm-up)
  exits      balanced (2 ATR stop / 3R / 3 ATR trail), patient (3 ATR / 5R / 4 ATR)
             -> 8 x 2 x 2 = 32 candidates per coin, 256 in total; fixed volume gate as round 1
  train      2021, 2022, 2023 independently reset accounts, round-1 score and gate
  validation 2024, the best eligible training candidate per coin only
  test       2025-01-01 .. 2026-10-28, one look per coin whose candidate passed validation,
             plus one pre-registered carry-over: round 1's BTC squeeze_breakout_4h_balanced
             passed 2024 validation but never received its held-out look
  versions   passers register as candidates/crypto_v0_2, v0_3, ... in the fixed order
             carry-over first, then universe order; none is promoted by this script
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import json
import math

import numpy as np
import pandas as pd

from .data import DATA, UNIVERSE, load
from .lab import TEST, TRAIN, TRAIN_YEARS, VALIDATION, detailed, evaluate, training_rank, validation_rank
from ..alternative_strategies import SignalRule
from ..exit_research import freeze
from ..forward_collection import atomic_json
from ..generalization_policy import assert_historical_period, digest, frozen_profile
from ..indicators import resample_complete, rma
from ..market_data import BAR, utc
from ..optimize import subset
from ..paths import ROOT
from ..strategy_lab_signals import LabRule, prepare

NAME = 'crypto_round3_families'
FAMILIES = ('donchian20', 'donchian55', 'keltner', 'contraction', 'zscore', 'macd', 'efficiency', 'rsi50')
TIMEFRAMES = {'4h': dict(rule='4h', span=pd.Timedelta(hours=4), trend=200, warmup=200),
              '1D': dict(rule='1D', span=pd.Timedelta(days=1), trend=50, warmup=60)}
EXITS = (('balanced', (2., 3., 3.)), ('patient', (3., 5., 4.)))
CARRY_OVER = dict(symbol='BTC', id='squeeze_breakout_4h_balanced', rule=dict(family='squeeze_breakout', timeframe_hours=4, stop_atr=2., reward_r=3., trail_atr=3.))
FIRST_VERSION = 2


@dataclass(frozen=True)
class FamilyRule:
    family: str
    timeframe: str
    stop_atr: float
    reward_r: float
    trail_atr: float

    def __post_init__(self):
        if self.family not in FAMILIES or self.timeframe not in TIMEFRAMES:
            raise ValueError('Setting outside the registered round-3 grid')
        if not all(math.isfinite(x) and x > 0 for x in [self.stop_atr, self.reward_r, self.trail_atr]):
            raise ValueError('Exit settings must be positive and finite')

    def execution_rule(self):
        # Bracket/trailing geometry only; the execution loop receives explicit signals.
        return SignalRule('ema_cross', lookback=20, slow=200, stop_atr=self.stop_atr, reward_r=self.reward_r, trail_atr=self.trail_atr)


def candidates():
    return [dict(id=f'{family}_{tf}_{profile}', kind='family_grid', rule=asdict(FamilyRule(family, tf, *geometry)))
            for family in FAMILIES for tf in TIMEFRAMES for profile, geometry in EXITS]


def directory(root):
    return root/'artifacts/crypto_research'/NAME


def plan(root=ROOT, symbols=None, data=DATA):
    assert_historical_period(TEST[1], root)
    symbols = list(symbols or UNIVERSE)
    hashes = {s: load(s, data)[1]['parquet_sha256'] for s in symbols}
    out = directory(root)
    previous = json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else None
    manifest = dict(
        name=NAME, symbols=symbols, data_hashes=hashes,
        created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        authorization='User asked on 2026-11-04 for new novel strategies that can be paper tested in tandem.',
        candidates=candidates(), candidates_per_symbol=len(FAMILIES)*len(TIMEFRAMES)*len(EXITS),
        families=FAMILIES, timeframes={k: dict(trend=v['trend'], warmup=v['warmup']) for k, v in TIMEFRAMES.items()}, exits=EXITS,
        carry_over=CARRY_OVER, first_version=FIRST_VERSION,
        train_period=TRAIN, train_folds='Three independently reset annual accounts (2021, 2022, 2023).',
        validation_period=VALIDATION, test_period=TEST,
        scoring='Round-1 training score and gates unchanged (closed net at 8bp fills + 8bp sizing budget, $100 risk, $50k account).',
        validation='Best eligible training candidate per coin; round-1 validation gate.',
        test_gate='One look per coin whose candidate passed validation, plus the carry-over: positive closed net at 8bp in 2025 and in 2026, '
                  '<=5% drawdown at 2/4/8bp, no margin calls.',
        cost_scenarios_bps=[2., 4., 8.], sizing_budget_bps=8., risk_usd=100., initial_capital=50000.,
        test_window_used_for_selection=False, threshold_changes_after_results=False,
        promotion='Each passer is registered as candidates/crypto_v0_N (unpromoted), N assigned in fixed order; nothing existing is modified.')
    if previous and digest({k: v for k, v in previous.items() if k != 'created_at_utc'}) != digest({k: v for k, v in manifest.items() if k != 'created_at_utc'}):
        raise ValueError('round-3 manifest changed after registration; use a new NAME')
    out.mkdir(parents=True, exist_ok=True)
    if not (out/'manifest.json').exists():
        freeze(out/'manifest.json', manifest)
    return manifest


def efficiency_ratio(c, length):
    change = (c-c.shift(length)).abs()
    path = c.diff().abs().rolling(length).sum()
    return change/path.replace(0., np.nan)


def rsi(close, length):
    change = close.diff()
    gain, loss = rma(change.clip(lower=0), length), rma((-change).clip(lower=0), length)
    value = 100-100/(1+gain/loss.replace(0., np.nan))
    return value.mask(loss.eq(0) & gain.gt(0), 100.).mask(loss.eq(0) & gain.eq(0), 50.)


class Features:
    """Per-timeframe completed-candle features, computed once and shared by all families."""

    def __init__(self, bars):
        self.bars = bars
        self.cache = {}

    def base(self, timeframe):
        if timeframe not in self.cache:
            spec = TIMEFRAMES[timeframe]
            candles = resample_complete(self.bars, spec['rule'])
            c = candles.close
            tr = pd.concat([candles.high-candles.low, (candles.high-c.shift()).abs(), (candles.low-c.shift()).abs()], axis=1).max(axis=1)
            self.cache[timeframe] = dict(
                candles=candles, atr=rma(tr, 14), ready=c.expanding().count() >= spec['warmup'],
                volume_ok=candles.volume >= candles.volume.shift().rolling(20).mean(),
                trend=c.ewm(span=spec['trend'], adjust=False).mean(), availability=candles.index+spec['span']-BAR)
        return self.cache[timeframe]

    def raw_signals(self, rule):
        f = self.base(rule.timeframe)
        k, c, atr, trend = f['candles'], f['candles'].close, f['atr'], f['trend']
        up, down = c > trend, c < trend
        if rule.family in ('donchian20', 'donchian55'):
            n = 20 if rule.family == 'donchian20' else 55
            upper, lower = k.high.shift().rolling(n).max(), k.low.shift().rolling(n).min()
            long, short = (c > upper) & (c.shift() <= upper.shift()) & up, (c < lower) & (c.shift() >= lower.shift()) & down
        elif rule.family == 'keltner':
            middle = c.ewm(span=20, adjust=False).mean()
            upper, lower = middle+2*atr, middle-2*atr
            long, short = (c > upper) & (c.shift() <= upper.shift()) & up, (c < lower) & (c.shift() >= lower.shift()) & down
        elif rule.family == 'contraction':
            quiet = (atr/rma(pd.concat([k.high-k.low, (k.high-c.shift()).abs(), (k.low-c.shift()).abs()], axis=1).max(axis=1), 100)).shift() < .75
            upper, lower = k.high.shift().rolling(10).max(), k.low.shift().rolling(10).min()
            long, short = quiet & (c > upper) & up, quiet & (c < lower) & down
        elif rule.family == 'zscore':
            z = (c-c.rolling(20).mean())/c.rolling(20).std(ddof=0).replace(0., np.nan)
            long, short = (z > -2) & (z.shift() <= -2), (z < 2) & (z.shift() >= 2)
        elif rule.family == 'macd':
            histogram = c.ewm(span=12, adjust=False).mean()-c.ewm(span=26, adjust=False).mean()
            histogram = histogram-histogram.ewm(span=9, adjust=False).mean()
            long, short = (histogram > 0) & (histogram.shift() <= 0) & up, (histogram < 0) & (histogram.shift() >= 0) & down
        elif rule.family == 'efficiency':
            er = efficiency_ratio(c, 10)
            strong = (er > .6) & (er.shift() <= .6)
            long, short = strong & (c > c.shift(10)) & up, strong & (c < c.shift(10)) & down
        else:
            value = rsi(c, 14)
            long, short = (value > 50) & (value.shift() <= 50) & up, (value < 50) & (value.shift() >= 50) & down
        gate = f['ready'] & f['volume_ok']
        return np.where(gate & long.fillna(False), 1, np.where(gate & short.fillna(False), -1, 0))

    def signals(self, rule):
        f = self.base(rule.timeframe)
        availability = f['availability']
        table = pd.DataFrame(dict(signal=self.raw_signals(rule), signal_atr=f['atr'].to_numpy()), index=availability)
        index = pd.DatetimeIndex(self.bars.timestamp)
        mapped = table.reindex(index)
        output = self.bars.copy()
        output['signal'] = mapped.signal.fillna(0).to_numpy(dtype=int)
        output['signal_atr'] = mapped.signal_atr.to_numpy()
        output['management_atr'] = pd.Series(f['atr'].to_numpy(), index=availability).reindex(index, method='ffill').to_numpy()
        return output


def geometry(candidate):
    """(signal builder, execution rule). The carry-over uses round 1's own signal code."""
    if candidate['kind'] == 'carry_over':
        rule = LabRule(**candidate['rule'])
        return (lambda bars: prepare(bars, rule)), rule.execution_rule()
    rule = FamilyRule(**candidate['rule'])
    return (lambda bars: Features(bars).signals(rule)), rule.execution_rule()


def train_symbol(symbol, bars, manifest, cfg, out, verify):
    rows = []
    train_bars = bars[bars.timestamp < utc(TRAIN[1])].reset_index(drop=True)
    features = Features(train_bars)
    for candidate in manifest['candidates']:
        path = out/'training'/symbol/f"{candidate['id']}.json"
        if path.exists() and not verify:
            row = json.loads(path.read_text())
            if row['candidate'] != candidate or row['manifest_sha256'] != digest(manifest):
                raise ValueError('Training checkpoint changed identity')
            rows.append(row)
            continue
        rule = FamilyRule(**candidate['rule'])
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
        atomic_json(out/'status.json', dict(stage='training', symbol=symbol, complete=len(rows), total=len(manifest['candidates'])))
    return rows


def validate(symbol, bars, candidate, training_row, cfg, out, manifest):
    path = out/'validation'/symbol/f"{candidate['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    build, rule = geometry(candidate)
    preceding = bars[bars.timestamp < utc(VALIDATION[1])].reset_index(drop=True)
    b, f = subset(preceding, build(preceding), *VALIDATION)
    result = detailed(symbol, b, f, rule, cfg, out/'validation'/symbol/candidate['id'])
    row = dict(symbol=symbol, candidate=candidate, result=result, rank=validation_rank(training_row, result), manifest_sha256=digest(manifest))
    freeze(path, row)
    return row


def carry_over_candidate():
    return dict(id=CARRY_OVER['id'], kind='carry_over', rule=CARRY_OVER['rule'])


def run(root=ROOT, symbols=None, data=DATA, verify=False, held_out=False):
    manifest = plan(root, symbols, data)
    out = directory(root)
    _, _, cfg, _ = frozen_profile(root)
    cfg = replace(cfg, slippage_bps=8.)
    training, validation = {}, []
    for symbol in manifest['symbols']:
        bars, _ = load(symbol, data, manifest['data_hashes'][symbol])
        rows = train_symbol(symbol, bars, manifest, cfg, out, verify)
        training[symbol] = rows
        best = max(rows, key=lambda r: (r['rank']['eligible'], r['rank']['score'], r['candidate']['id']))
        row = validate(symbol, bars, best['candidate'], best, cfg, out, manifest)
        validation.append(row)
        print(f"VALIDATION {symbol} {best['candidate']['id']} closed={row['result']['closed_net']:.0f} eligible={row['rank']['eligible']}", flush=True)
    selected = [dict(symbol=r['symbol'], candidate=r['candidate']) for r in validation if r['rank']['eligible']]
    if CARRY_OVER['symbol'] in manifest['symbols']:
        selected.insert(0, dict(symbol=CARRY_OVER['symbol'], candidate=carry_over_candidate()))
    selection = dict(manifest_sha256=digest(manifest), selected=selected,
                     reason=f"{len(selected)} pre-selected (coin, candidate) pairs incl. carry-over; each gets one held-out look",
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
        summary['test'] = [test(root, data, pair, cfg, out, FIRST_VERSION+i) for i, pair in enumerate(selected)]
        atomic_json(out/'results.json', summary)
    report(out, summary)
    return summary


def test(root, data, pair, cfg, out, version):
    """Single look at the held-out window for one pre-selected pair."""
    symbol, candidate = pair['symbol'], pair['candidate']
    path = out/'test'/f"{symbol}_{candidate['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    bars, _ = load(symbol, data)
    build, rule = geometry(candidate)
    features = build(bars)
    rows = []
    for label, begin, end in [('test_2025', '2025-01-01', '2026-01-01'), ('test_2026', '2026-01-01', TEST[1]), ('test_full', *TEST)]:
        b, f = subset(bars, features, begin, end)
        for slip in [2., 4., 8.]:
            result = detailed(symbol, b, f, rule, replace(cfg, slippage_bps=slip), out/'test'/symbol/candidate['id']/label/f'fill{int(slip)}')
            rows.append(dict(period=label, actual_fill_slippage_bps=slip, closed_net=result['closed_net'],
                             drawdown=result['metrics']['max_intrabar_drawdown'], legs=result['metrics']['closed_trade_legs'],
                             margin_calls=result['metrics']['margin_call_events']))
    annual8 = [r for r in rows if r['period'] != 'test_full' and r['actual_fill_slippage_bps'] == 8.]
    passed = all(r['closed_net'] > 0 for r in annual8) and all(r['drawdown'] <= .05 and r['margin_calls'] == 0 for r in rows)
    outcome = dict(symbol=symbol, candidate=candidate, rows=rows, passed=bool(passed), single_look=True, version=f'crypto_v0_{version}' if passed else None,
                   note='Held-out result is evidence about this one pre-selected pair only; it was not used to choose it.')
    freeze(path, outcome)
    if passed:
        register(root, outcome, cfg)
    return outcome


def register(root, outcome, cfg):
    folder = root/'candidates'/outcome['version']
    if folder.exists():
        raise ValueError(f"{folder} already exists; versions are never overwritten")
    folder.mkdir(parents=True)
    config = dict(version=outcome['version'], symbol=outcome['symbol'], breakout=UNIVERSE[outcome['symbol']],
                  candidate=outcome['candidate'], risk_usd=cfg.risk_usd, initial_capital=cfg.initial_capital,
                  slippage_budget_bps=8., commission_bps=cfg.commission_bps, promoted=False,
                  evidence='train 2021-23 / validation 2024 / single-look test 2025-2026-10-28 (round 3); no forward evidence yet')
    atomic_json(folder/'config.json', config)
    atomic_json(folder/'protocol.json', dict(lab=NAME, manifest_sha256=digest(json.loads((directory(root)/'manifest.json').read_text()))))


def report(out, summary):
    lines = [f'# Crypto research {NAME}', '', 'Eight new signal families x 4h/1D x 2 exit sets on eight coins; best training candidate per coin '
             'validated on 2024; every validated pair plus the round-1 BTC carry-over gets one held-out look.', '',
             '## Training (eligible candidates per coin)', '']
    for symbol, rows in summary['training'].items():
        passing = sorted((r for r in rows if r['eligible']), key=lambda r: -r['score'])
        lines.append(f"- {symbol}: {len(passing)}/{len(rows)} eligible" + (': ' + ', '.join(f"{r['id']} ({r['score']:.0f})" for r in passing[:5]) if passing else ''))
    lines += ['', '## Validation 2024 (best training candidate per coin)', '', '| Coin | Candidate | Closed net | Drawdown | Legs | Eligible |', '|---|---|---|---|---|---|']
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
    parser.add_argument('--held-out', action='store_true', help='open the held-out window for the pre-selected pairs')
    args = parser.parse_args()
    summary = run(symbols=args.symbols, verify=args.verify, held_out=args.held_out)
    print(json.dumps(summary['selection'], indent=2))


if __name__ == '__main__':
    main()

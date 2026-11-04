"""Round 4: strategies presented on YouTube, encoded literally and run through the same gates.

The user asked whether publicly presented (YouTube) strategies can be tested.
Each rule below is transcribed from a video's stated rules; where a video gives
no stop, timeframe or exit, the manifest records the assumption. Discretionary
systems (supply/demand zones, SMC liquidity models, chart-pattern breakouts,
proprietary paid indicators) cannot be encoded exactly and are listed as
excluded instead of being approximated.

Protocol (frozen in manifest.json before any result is written):
  coins      BTC SOL XRP BNB DOGE LINK LTC ADA (round-1 universe and data)
  rules      see RULES; 13 candidates per coin, 104 in total, exits as the videos state
             (signal exits use the simulator's optional exit_signal column; a wide
             protective stop is added where the video has none)
  train      2021, 2022, 2023 independently reset accounts, round-1 score and gate
  validation 2024 for EVERY training-eligible candidate (external hypotheses, not a tuned grid)
  test       2025-01-01 .. 2026-10-28, one look per validation passer
  versions   passers register as candidates/crypto_v0_6, v0_7, ... in universe/rule order; none promoted
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import json
import math

import numpy as np
import pandas as pd

from .data import DATA, UNIVERSE, load
from .lab import TEST, TRAIN, TRAIN_YEARS, VALIDATION, safe_value, training_rank, validation_rank, validator
from .round3 import register as register_version, rsi
from ..alternative_strategies import SignalRule
from ..cost_reserve import sizing_config
from ..engine import Broker, estimated_round_trip_cost
from ..exit_research import freeze
from ..forward_collection import atomic_json
from ..generalization_policy import assert_historical_period, digest, frozen_profile
from ..independent_visuals import equity_curve
from ..indicators import resample_complete, rma
from ..market_data import BAR, clean_candles, utc
from ..optimize import subset
from ..paths import ROOT

NAME = 'crypto_round4_youtube'
FIRST_VERSION = 6
TIMEFRAMES = {'1h': dict(rule='1h', span=pd.Timedelta(hours=1), warmup=400),
              '4h': dict(rule='4h', span=pd.Timedelta(hours=4), warmup=400),
              '1D': dict(rule='1D', span=pd.Timedelta(days=1), warmup=60)}
BIG_TARGET = 100.
# family -> (timeframes, stop_atr, reward_r, long_only, source, stated rules / assumptions)
RULES = {
    'yt_dema_supertrend': (('1h', '4h'), 1., BIG_TARGET, False, 'youtu.be/g-PLctW8aU0 (611k views)',
                           'DEMA(200) trend filter; enter when Supertrend(ATR 12, x3) flips in the trend direction at candle close; '
                           'stop at the Supertrend line; exit on the opposite flip. Video uses 15m; tested on 1h/4h (15m is uneconomic at 8bp).'),
    'yt_five_ema': (('1h', '4h'), 1., 3., False, 'youtu.be/MArbjQKrN9Y',
                    'Indication candle entirely above (below) EMA(5) whose close breaks the previous candle high (low); '
                    'stop at the indication candle low (high); target 3R. Timeframe not stated; tested on 1h/4h.'),
    'yt_bb_rsi': (('1h', '4h'), 2., BIG_TARGET, False, 'youtu.be/pCmJ8wsAS_w (1.9M views)',
                  'Long when close < lower Bollinger(30, 2) and RSI(13) < 25; short when close > upper band and RSI > 75; '
                  'exit when price returns to the middle band. Video has no stop; 2 ATR(14) protective stop assumed. Timeframe not stated.'),
    'yt_cci14': (('4h', '1D'), 3., BIG_TARGET, False, 'youtu.be/ygl4oEwejJo',
                 'CCI(14) crossing above +100 buys, crossing back below +100 exits; mirror for -100. 3 ATR protective stop assumed.'),
    'yt_cci28': (('4h', '1D'), 3., BIG_TARGET, False, 'youtu.be/ygl4oEwejJo',
                 'Same with the video\'s "improved" CCI(28).'),
    'yt_macd_hist_daily': (('1D',), 5., BIG_TARGET, True, 'youtu.be/cSHNnwcMIO8 (Quantified Strategies)',
                           'Daily MACD(12,26,9) histogram turns positive: buy; turns negative: sell. Long only. 5 ATR protective stop assumed.'),
    'yt_close25_daily': (('1D',), 5., BIG_TARGET, True, 'youtu.be/cSHNnwcMIO8 (Quantified Strategies)',
                         'Buy when close > close 25 days ago; sell when close < close 25 days ago. Long only. 5 ATR protective stop assumed.'),
    'yt_turn_of_month': (('1D',), 5., BIG_TARGET, True, 'youtu.be/cSHNnwcMIO8 (Quantified Strategies)',
                         'Buy at the open of the 5th-last calendar day of the month, sell at the close of the 3rd day of the next month. '
                         'Long only. 5 ATR protective stop assumed.')
}
EXCLUDED = {
    'youtu.be/e-QmGJU1XYc (2.4M views)': 'market-structure + supply/demand zones: zone placement is discretionary',
    'youtu.be/v4qwe618tuw (557k views)': 'SMC 5-rule model: session windows, liquidity sweeps and 1m structure shifts are discretionary',
    'youtu.be/ZudTPpJCbbA (4.5M views)': 'support/resistance breakout with momentum candles: level placement is discretionary',
    'youtu.be/_tMzs9cD-4g': 'Stiff Surge: proprietary indicators (JMA/TDFI/VQ/Stiffness) without public formulas',
    'youtu.be/bEBqThRRWsE': 'Black Flag / Forex Trading Signals 2.0: protected scripts without public formulas',
    'youtu.be/B4ch-Lf8wJc': 'liquidity + discount zone model: discretionary',
    'youtu.be/lRMFcsqhYBU': 'swing structure + fibonacci pullback: discretionary'
}


@dataclass(frozen=True)
class YouTubeRule:
    family: str
    timeframe: str

    def __post_init__(self):
        if self.family not in RULES or self.timeframe not in RULES[self.family][0]:
            raise ValueError('Setting outside the registered round-4 manifest')

    @property
    def spec(self):
        return RULES[self.family]

    def execution_rule(self):
        return SignalRule('ema_cross', lookback=20, slow=200, stop_atr=self.spec[1], reward_r=self.spec[2], trail_atr=0.)


def candidates():
    return [dict(id=f'{family}_{tf}', kind='youtube', rule=asdict(YouTubeRule(family, tf)))
            for family, spec in RULES.items() for tf in spec[0]]


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
        authorization='User asked on 2026-11-04 whether strategies presented on YouTube can be researched.',
        candidates=candidates(), rules={k: dict(timeframes=v[0], stop_atr=v[1], reward_r=v[2], long_only=v[3], source=v[4], rule=v[5]) for k, v in RULES.items()},
        excluded=EXCLUDED, first_version=FIRST_VERSION,
        train_period=TRAIN, train_folds='Three independently reset annual accounts (2021, 2022, 2023).',
        validation_period=VALIDATION, test_period=TEST,
        scoring='Round-1 training score and gates unchanged (closed net at 8bp fills + 8bp sizing budget, $100 risk, $50k account).',
        validation='Every training-eligible candidate is validated on 2024 (external hypotheses, not a tuned grid); round-1 validation gate.',
        test_gate='One look per validation passer: positive closed net at 8bp in 2025 and in 2026, <=5% drawdown at 2/4/8bp, no margin calls.',
        cost_scenarios_bps=[2., 4., 8.], sizing_budget_bps=8., risk_usd=100., initial_capital=50000.,
        test_window_used_for_selection=False, threshold_changes_after_results=False,
        promotion='Each passer is registered as candidates/crypto_v0_N (unpromoted) in universe/rule order; nothing existing is modified.')
    if previous and digest({k: v for k, v in previous.items() if k != 'created_at_utc'}) != digest({k: v for k, v in manifest.items() if k != 'created_at_utc'}):
        raise ValueError('round-4 manifest changed after registration; use a new NAME')
    out.mkdir(parents=True, exist_ok=True)
    if not (out/'manifest.json').exists():
        freeze(out/'manifest.json', manifest)
    return manifest


def simulate(bars, rule, config, signals, *, sizing_slippage_bps=8., validator=None):
    """cost_reserve.simulate plus one branch: an `exit_signal` column equal to the open
    position's direction flattens it at that bar's close ('signal_exit'). The hash-locked
    simulators are not modified; this copy exists only for the signal-exit strategies here."""
    if config.mode != 'research' or config.entry_timing != 'next_open':
        raise ValueError('Independent strategies require next-open Research execution')
    reserve_config = sizing_config(config, sizing_slippage_bps)
    bars, quality = (clean_candles if validator is None else validator)(bars)
    if quality['missing_bars']:
        raise ValueError('Independent strategy research rejects missing candles')
    frame = signals.reset_index(drop=True)
    if len(frame) != len(bars) or not frame.timestamp.equals(bars.timestamp):
        raise ValueError('Signal rows must match candle timestamps')
    broker = Broker(config)
    pending = None
    entries = entries_today = 0
    day, start_equity, locked = None, config.initial_capital, False
    for row in frame.itertuples(index=False):
        broker.bar(row)
        if pending is not None:
            direction, quantity, stop, target = pending
            broker.enter(direction, quantity, row.open, stop, target, row.timestamp, row.timestamp)
            broker.bar(row)
            pending = None
        if broker.position:
            p = broker.position
            held = (row.timestamp+BAR-p.entry_time)/BAR
            if rule.max_holding_bars and held >= rule.max_holding_bars:
                broker.exit(row.close, row.timestamp, 'time_stop', 'research_close')
            elif row.exit_signal == p.direction:
                broker.exit(row.close, row.timestamp, 'signal_exit', 'research_close')
            elif rule.trail_atr and math.isfinite(row.management_atr):
                proposed = row.close-p.direction*rule.trail_atr*row.management_atr
                tighter = proposed > p.stop if p.direction == 1 else proposed < p.stop
                if tighter and p.direction*(row.close-proposed) > config.tick_size:
                    p.stop = proposed
                    broker.events.append(dict(bar_open=row.timestamp, event='stop_update', price=proposed, effective_at=row.timestamp+BAR))
        equity = broker.equity_at(row.close)
        if day != row.timestamp.date():
            day, start_equity, entries_today, locked = row.timestamp.date(), equity, 0, False
        if equity <= start_equity-config.max_daily_loss:
            locked = True
        if row.signal and not broker.position and not locked and entries_today < config.max_trades_day and math.isfinite(row.signal_atr):
            direction = int(row.signal)
            distance = rule.stop_atr*row.signal_atr
            risk_distance = distance+estimated_round_trip_cost(reserve_config, row.close)
            quantity = math.floor(min(config.risk_usd/(risk_distance*config.point_value),
                                      equity*config.max_leverage/(row.close*config.point_value))*1000)/1000
            if distance > config.tick_size and quantity > 0:
                pending = (direction, quantity, row.close-direction*distance, row.close+direction*rule.reward_r*distance)
                entries_today += 1
                entries += 1
        broker.mark(row.close)
    trades = pd.DataFrame(broker.trades)
    net = trades.net_pnl if len(trades) else pd.Series(dtype=float)
    gains, losses = net.clip(lower=0).sum(), -net.clip(upper=0).sum()
    metrics = dict(initial_capital=config.initial_capital, final_equity=broker.equity_at(frame.close.iloc[-1]),
                   entries=entries, closed_trade_legs=len(trades), win_rate=float((net > 0).mean()) if len(net) else None,
                   profit_factor=float(gains/losses) if losses else None,
                   max_intrabar_drawdown=broker.max_drawdown, max_closed_equity_drawdown_usd=broker.closed_equity_drawdown_usd,
                   total_commission=broker.total_commission, total_swap=broker.total_swap, margin_call_events=broker.margin_calls,
                   open_position=asdict(broker.position) if broker.position else None)
    return metrics, trades, pd.DataFrame(broker.events)


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


def true_range(k):
    c = k.close
    return pd.concat([k.high-k.low, (k.high-c.shift()).abs(), (k.low-c.shift()).abs()], axis=1).max(axis=1)


def supertrend(k, period, multiplier):
    """Causal Supertrend: (direction +1/-1, active line) per completed candle."""
    atr = rma(true_range(k), period).to_numpy()
    hl2 = ((k.high+k.low)/2).to_numpy()
    close = k.close.to_numpy()
    upper, lower = hl2+multiplier*atr, hl2-multiplier*atr
    n = len(k)
    direction, line = np.ones(n, dtype=int), np.full(n, np.nan)
    final_upper, final_lower = upper.copy(), lower.copy()
    for i in range(1, n):
        if np.isnan(atr[i]):
            continue
        if np.isnan(final_upper[i-1]):
            line[i] = final_lower[i]
            continue
        final_upper[i] = upper[i] if upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1] else final_upper[i-1]
        final_lower[i] = lower[i] if lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1] else final_lower[i-1]
        if direction[i-1] == 1:
            direction[i] = -1 if close[i] < final_lower[i] else 1
        else:
            direction[i] = 1 if close[i] > final_upper[i] else -1
        line[i] = final_lower[i] if direction[i] == 1 else final_upper[i]
    return pd.Series(direction, index=k.index), pd.Series(line, index=k.index)


def cci(k, length):
    tp = (k.high+k.low+k.close)/3
    mean = tp.rolling(length).mean()
    deviation = (tp-mean).abs().rolling(length).mean()
    return (tp-mean)/(.015*deviation.replace(0., np.nan))


class Features:
    def __init__(self, bars):
        self.bars = bars
        self.cache = {}

    def base(self, timeframe):
        if timeframe not in self.cache:
            spec = TIMEFRAMES[timeframe]
            k = resample_complete(self.bars, spec['rule'])
            self.cache[timeframe] = dict(candles=k, atr=rma(true_range(k), 14), ready=k.close.expanding().count() >= spec['warmup'],
                                         availability=k.index+spec['span']-BAR)
        return self.cache[timeframe]

    def raw(self, rule):
        """(long, short, exit_long, exit_short, stop_basis) boolean/float series on completed candles."""
        f = self.base(rule.timeframe)
        k, c, atr = f['candles'], f['candles'].close, f['atr']
        none = pd.Series(False, index=k.index)
        basis = atr
        if rule.family == 'yt_dema_supertrend':
            e1 = c.ewm(span=200, adjust=False).mean()
            dema = 2*e1-e1.ewm(span=200, adjust=False).mean()
            direction, line = supertrend(k, 12, 3.)
            flip_up, flip_down = (direction == 1) & (direction.shift() == -1), (direction == -1) & (direction.shift() == 1)
            long, short = flip_up & (c > dema), flip_down & (c < dema)
            exit_long, exit_short = flip_down, flip_up
            basis = (c-line).abs()
        elif rule.family == 'yt_five_ema':
            ema = c.ewm(span=5, adjust=False).mean()
            long = (k.low > ema) & (c > k.high.shift())
            short = (k.high < ema) & (c < k.low.shift())
            exit_long, exit_short = none, none
            basis = pd.Series(np.where(long, c-k.low, np.where(short, k.high-c, atr)), index=k.index)
        elif rule.family == 'yt_bb_rsi':
            middle = c.rolling(30).mean()
            deviation = c.rolling(30).std(ddof=0)
            value = rsi(c, 13)
            long, short = (c < middle-2*deviation) & (value < 25), (c > middle+2*deviation) & (value > 75)
            exit_long, exit_short = c >= middle, c <= middle
        elif rule.family in ('yt_cci14', 'yt_cci28'):
            value = cci(k, 14 if rule.family == 'yt_cci14' else 28)
            long, short = (value > 100) & (value.shift() <= 100), (value < -100) & (value.shift() >= -100)
            exit_long, exit_short = (value < 100) & (value.shift() >= 100), (value > -100) & (value.shift() <= -100)
        elif rule.family == 'yt_macd_hist_daily':
            histogram = c.ewm(span=12, adjust=False).mean()-c.ewm(span=26, adjust=False).mean()
            histogram = histogram-histogram.ewm(span=9, adjust=False).mean()
            long, short = (histogram > 0) & (histogram.shift() <= 0), none
            exit_long, exit_short = (histogram < 0) & (histogram.shift() >= 0), none
        elif rule.family == 'yt_close25_daily':
            ref = c.shift(25)
            long, short = (c > ref) & (c.shift() <= ref.shift()), none
            exit_long, exit_short = (c < ref) & (c.shift() >= ref.shift()), none
        else:
            days = pd.Series(k.index.day, index=k.index)
            in_month = pd.Series(k.index.days_in_month, index=k.index)
            long, short = days == in_month-5, none
            exit_long, exit_short = days == 3, none
        if rule.spec[3]:
            short, exit_short = none, none
        return long.fillna(False), short.fillna(False), exit_long.fillna(False), exit_short.fillna(False), basis

    def signals(self, rule):
        f = self.base(rule.timeframe)
        long, short, exit_long, exit_short, basis = self.raw(rule)
        ready = f['ready']
        table = pd.DataFrame(dict(signal=np.where(ready & long, 1, np.where(ready & short, -1, 0)),
                                  exit_signal=np.where(ready & exit_long, 1, np.where(ready & exit_short, -1, 0)),
                                  signal_atr=basis.to_numpy()), index=f['availability'])
        index = pd.DatetimeIndex(self.bars.timestamp)
        mapped = table.reindex(index)
        output = self.bars.copy()
        output['signal'] = mapped.signal.fillna(0).to_numpy(dtype=int)
        output['exit_signal'] = mapped.exit_signal.fillna(0).to_numpy(dtype=int)
        output['signal_atr'] = mapped.signal_atr.to_numpy()
        output['management_atr'] = pd.Series(f['atr'].to_numpy(), index=f['availability']).reindex(index, method='ffill').to_numpy()
        return output


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
        rule = YouTubeRule(**candidate['rule'])
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


def validate(symbol, bars, training_row, cfg, out, manifest):
    candidate = training_row['candidate']
    path = out/'validation'/symbol/f"{candidate['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    rule = YouTubeRule(**candidate['rule'])
    preceding = bars[bars.timestamp < utc(VALIDATION[1])].reset_index(drop=True)
    b, f = subset(preceding, Features(preceding).signals(rule), *VALIDATION)
    result = detailed(symbol, b, f, rule.execution_rule(), cfg, out/'validation'/symbol/candidate['id'])
    row = dict(symbol=symbol, candidate=candidate, result=result, rank=validation_rank(training_row, result), manifest_sha256=digest(manifest))
    freeze(path, row)
    return row


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
        for row in rows:
            if row['rank']['eligible']:
                v = validate(symbol, bars, row, cfg, out, manifest)
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
        summary['test'] = [test(root, data, pair, cfg, out, FIRST_VERSION+i) for i, pair in enumerate(selected)]
        atomic_json(out/'results.json', summary)
    report(out, summary)
    return summary


def test(root, data, pair, cfg, out, version):
    symbol, candidate = pair['symbol'], pair['candidate']
    path = out/'test'/f"{symbol}_{candidate['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    bars, _ = load(symbol, data)
    rule = YouTubeRule(**candidate['rule'])
    features = Features(bars).signals(rule)
    rows = []
    for label, begin, end in [('test_2025', '2025-01-01', '2026-01-01'), ('test_2026', '2026-01-01', TEST[1]), ('test_full', *TEST)]:
        b, f = subset(bars, features, begin, end)
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
    lines = [f'# Crypto research {NAME}', '', 'YouTube-presented rules encoded literally (see manifest.json for sources and assumptions); '
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
    lines += ['', '## Excluded videos (not encodable exactly)', ''] + [f'- {k}: {v}' for k, v in EXCLUDED.items()]
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

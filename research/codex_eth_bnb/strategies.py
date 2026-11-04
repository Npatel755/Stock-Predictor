"""Small, predeclared causal hypothesis library for perpetual-futures research.

All signals are desired exposure after a COMPLETED candle; the execution
engine must delay them until the following candle's open. No fitted threshold
or parameter is estimated outside the supplied chronological input prefix.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


TIMEFRAMES = ('5m', '15m', '1h', '4h')


def library():
    """48 primary settings and 12 separately labeled baseline settings."""
    definitions = [
        ('tsmom', dict(lookback=32, threshold=.35), 'Persistent directional returns may reflect gradual information diffusion.'),
        ('tsmom', dict(lookback=96, threshold=.35), 'A slower return horizon tests persistence outside short-term noise.'),
        ('channel', dict(lookback=20), 'Breaks of previously completed price extremes may initiate persistent trends.'),
        ('channel', dict(lookback=55), 'A slower channel tests whether large structural breakouts persist.'),
        ('zscore', dict(lookback=20, entry=2., exit=.25), 'Range-conditioned stretched prices may revert toward a local mean.'),
        ('zscore', dict(lookback=60, entry=2., exit=.25), 'A slower mean tests range reversion at a different memory scale.'),
        ('trend_pullback', dict(fast=20, slow=80, pullback_atr=.5), 'Pullbacks in an already completed higher-timeframe trend may resume.'),
        ('vol_momentum', dict(lookback=48, threshold=.35, maximum_rv_ratio=1.5), 'Moderate-volatility trends may survive costs better than crisis chasing.'),
        ('vwap_reversion', dict(entry_atr=1.5, exit_atr=.25), 'Range-regime displacement from UTC-session traded-volume value may mean revert.'),
        ('btc_relative', dict(lookback=48), 'Asset returns stronger than BTC may reflect persistent asset-specific demand.'),
        ('cross_relative', dict(lookback=48), 'ETH versus BNB leadership may persist after controlling for the common directional trend.'),
        ('funding_fade', dict(threshold=.0005), 'Extreme already-settled funding may identify crowded positioning vulnerable to reversal.'),
    ]
    result = []
    for timeframe in TIMEFRAMES:
        for family, parameters, mechanism in definitions:
            suffix = '_'.join(f'{key}{value:g}' if isinstance(value, (int, float)) else f'{key}{value}'
                              for key, value in parameters.items())
            result.append(dict(id=f'{family}_{timeframe}_{suffix}', family=family, timeframe=timeframe,
                               parameters=parameters.copy(), mechanism=mechanism, baseline=False,
                               requires_funding=family == 'funding_fade',
                               execution=dict(stop_atr=2., reward_r=3., trail_atr=0., max_hold_bars=48)))
        for family in ('flat', 'buy_hold', 'simple_momentum'):
            result.append(dict(id=f'{family}_{timeframe}', family=family, timeframe=timeframe,
                               parameters=dict(lookback=32) if family == 'simple_momentum' else {},
                               mechanism={'flat': 'Cash benchmark with zero turnover.',
                                          'buy_hold': 'Unlevered long exposure benchmark, including perpetual funding.',
                                          'simple_momentum': 'Unfiltered trailing-return direction benchmark.'}[family],
                               baseline=True, requires_funding=False,
                               execution=dict(stop_atr=0. if family in ('flat', 'buy_hold') else 2.,
                                              reward_r=0. if family in ('flat', 'buy_hold') else 3.,
                                              trail_atr=0., max_hold_bars=0 if family in ('flat', 'buy_hold') else 48)))
    return result


def _duration(frame):
    label = frame.attrs.get('timeframe')
    if label:
        return pd.Timedelta(label.replace('m', 'min') if label.endswith('m') else label)
    times = pd.DatetimeIndex(pd.to_datetime(frame.timestamp, utc=True))
    return times[1]-times[0] if len(times) > 1 else pd.Timedelta(minutes=5)


def _validate(frame):
    out = frame.copy().reset_index(drop=True)
    out['timestamp'] = pd.to_datetime(out.timestamp, utc=True)
    if out.empty or out.timestamp.duplicated().any() or not out.timestamp.is_monotonic_increasing:
        raise ValueError('OHLCV timestamps must be nonempty, unique, and ordered')
    span = _duration(out)
    if span <= pd.Timedelta(0):
        raise ValueError('Candle duration must be positive')
    if len(out) > 1 and not out.timestamp.diff().dropna().eq(span).all():
        raise ValueError('Gaps require explicit segmentation; prices are never forward-filled')
    values = out[['open', 'high', 'low', 'close', 'volume']].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError('OHLCV must be finite, with positive prices and nonnegative volume')
    if (out.high < out[['open', 'close', 'low']].max(axis=1)).any() or (out.low > out[['open', 'close', 'high']].min(axis=1)).any():
        raise ValueError('Inconsistent OHLC ranges')
    return out, span


def _asof_values(decision_times, source_times, values):
    left = pd.DataFrame(dict(available_at=pd.to_datetime(decision_times, utc=True)))
    right = pd.DataFrame(dict(available_at=pd.to_datetime(source_times, utc=True), value=np.asarray(values)))
    right = right.sort_values('available_at').drop_duplicates('available_at', keep='last')
    if right.empty:
        return pd.Series(np.nan, index=left.index)
    result = pd.merge_asof(left, right, on='available_at', direction='backward', allow_exact_matches=True)
    return result.value


def _higher_trend(frame, span):
    target = pd.Timedelta(hours=4) if span < pd.Timedelta(hours=4) else pd.Timedelta(days=1)
    rule = '4h' if target == pd.Timedelta(hours=4) else '1D'
    work = frame.set_index('timestamp')
    groups = work.groupby(work.index.floor(rule), sort=True)
    hourly = groups.agg(close=('close', 'last'), count=('close', 'size'))
    # No partly formed source candle is admitted, even at the beginning/end.
    hourly = hourly[hourly['count'].eq(int(target/span))]
    ema = hourly.close.ewm(span=50, adjust=False, min_periods=20).mean()
    direction = np.sign(hourly.close-ema)
    return _asof_values(frame.timestamp+span, hourly.index+target, direction)


def build_features(frame, context=None):
    """Causal current-close features; every source is available by decision time.

    Context is keyed by 'BTC', 'ETH', and 'BNB'. Its bars can have a different
    frequency: joins use source bar CLOSE availability, never source bar open.
    No context value earlier than its first completed candle is manufactured.
    """
    out, span = _validate(frame)
    prior = out.close.shift()
    tr = pd.concat([out.high-out.low, (out.high-prior).abs(), (out.low-prior).abs()], axis=1).max(axis=1)
    out['atr'] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    out['return'] = out.close.pct_change(fill_method=None)
    out['rv'] = out['return'].rolling(32, min_periods=32).std(ddof=1)
    out['rv_reference'] = out.rv.shift().rolling(96, min_periods=48).median()
    out['rv_ratio'] = out.rv/out.rv_reference.replace(0., np.nan)
    out['autocorr'] = out['return'].rolling(48, min_periods=32).corr(out['return'].shift())
    out['ema_fast'] = out.close.ewm(span=32, adjust=False, min_periods=32).mean()
    out['ema_slow'] = out.close.ewm(span=96, adjust=False, min_periods=96).mean()
    out['trend_strength'] = (out.ema_fast-out.ema_slow).abs()/out.atr.replace(0., np.nan)
    out['rvol'] = out.volume/out.volume.shift().rolling(32, min_periods=32).mean().replace(0., np.nan)
    out['regime'] = np.select([out.rv_ratio > 1.75, out.trend_strength > 1.], ['high_volatility', 'trend'], default='range')
    out.loc[out.ema_slow.isna() | out.rv_reference.isna(), 'regime'] = 'warmup'
    # Keep the predeclared core regime stable. Secondary, interpretable
    # classifications expose liquidity and return dependence without fitting
    # thresholds to performance or changing the family's entry definitions.
    out['liquidity_regime'] = np.select([out.rvol >= 1.5, out.rvol < .5], ['high_volume', 'low_volume'], default='normal_volume')
    out.loc[out.rvol.isna(), 'liquidity_regime'] = 'warmup'
    out['serial_regime'] = np.select([out.autocorr >= .1, out.autocorr <= -.1], ['positive_serial', 'negative_serial'], default='weak_serial')
    out.loc[out.autocorr.isna(), 'serial_regime'] = 'warmup'
    trend_label = np.where(out.ema_fast >= out.ema_slow, 'trend_up', 'trend_down')
    core_detail = pd.Series(np.where(out.regime.eq('trend'), trend_label, out.regime), index=out.index)
    out['regime_detail'] = core_detail+'|'+out.liquidity_regime+'|'+out.serial_regime
    session = out.timestamp.dt.floor('D')
    typical = (out.high+out.low+out.close)/3
    cum_volume = out.volume.groupby(session).cumsum()
    out['session_vwap'] = (typical*out.volume).groupby(session).cumsum()/cum_volume.replace(0., np.nan)
    out['htf_trend'] = _higher_trend(out, span).to_numpy()
    for symbol, source in (context or {}).items():
        if symbol not in ('BTC', 'ETH', 'BNB'):
            continue
        # Context gaps remain explicit. An already completed source close is
        # only carried as an information feature; no tradeable candle is filled.
        source, source_span = _validate(source)
        out[f'context_{symbol}_close'] = _asof_values(out.timestamp+span, source.timestamp+source_span, source.close).to_numpy()
    if 'settled_funding' in out:
        # The ingestion layer has already gated these observations until at
        # least one hour after their real settlement timestamps.
        out['past_settled_funding'] = out.settled_funding
    elif 'funding_rate' in out:
        # Raw settlement is sparse, NaN on non-events. Delay event information
        # one CLOCK hour (not one native candle) before any signal may use it.
        observed = out.funding_rate.notna()
        out['past_settled_funding'] = _asof_values(
            out.timestamp+span, out.loc[observed, 'timestamp']+pd.Timedelta(hours=1),
            out.loc[observed, 'funding_rate']).to_numpy()
    else:
        out['past_settled_funding'] = np.nan
    out.attrs.update(frame.attrs)
    out.attrs['feature_duration'] = str(span)
    out.attrs['regime_classifier'] = ('Core: fixed trend-strength and lagged-relative-volatility thresholds. '
                                       'Secondary labels: lagged-volume ratio >=1.5/<0.5; '
                                       'rolling lag-one return autocorrelation >=0.1/<=-0.1. '
                                       'Secondary labels are diagnostics and do not alter core entry filters.')
    return out


def _stateful(entries, exits):
    state = 0
    result = np.zeros(len(entries), dtype=np.int8)
    for i, (entry, leave) in enumerate(zip(entries, exits)):
        if leave:
            state = 0
        if entry:
            state = int(entry)
        result[i] = state
    return result


def build_signal(frame, specification, context=None):
    """Return desired exposure computed at each completed input candle close."""
    out = frame.copy() if {'atr', 'regime', 'htf_trend', 'session_vwap'}.issubset(frame.columns) and context is None else build_features(frame, context)
    parameters = specification.get('parameters', {})
    family = specification['family']
    lookback = int(parameters.get('lookback', 48))
    momentum = out.close.pct_change(lookback, fill_method=None)
    normalized = momentum/(out.rv*np.sqrt(lookback)).replace(0., np.nan)
    direction = np.sign(out.ema_fast-out.ema_slow)
    signal = pd.Series(0., index=out.index)
    if family == 'flat':
        pass
    elif family == 'buy_hold':
        signal[:] = 1.
    elif family == 'simple_momentum':
        signal = np.sign(momentum)
    elif family in ('tsmom', 'vol_momentum'):
        signal = np.sign(normalized).where(normalized.abs() >= parameters.get('threshold', .35), 0.)
        if family == 'vol_momentum':
            signal = signal.where(out.rv_ratio <= parameters['maximum_rv_ratio'], 0.)
    elif family == 'channel':
        upper = out.high.shift().rolling(lookback, min_periods=lookback).max()
        lower = out.low.shift().rolling(lookback, min_periods=lookback).min()
        midpoint = (upper+lower)/2
        entry = np.select([out.close > upper, out.close < lower], [1, -1], default=0)
        # Reversal/neutral midpoint crossings terminate the previous break.
        leave = ((out.close-midpoint)*(out.close.shift()-midpoint.shift()) <= 0).fillna(False)
        signal = pd.Series(_stateful(entry, leave), index=out.index)
    elif family in ('zscore', 'vwap_reversion'):
        if family == 'zscore':
            average = out.close.rolling(lookback, min_periods=lookback).mean()
            scale = out.close.rolling(lookback, min_periods=lookback).std(ddof=1)
            z = (out.close-average)/scale.replace(0., np.nan)
            entry_level, exit_level = parameters['entry'], parameters['exit']
        else:
            z = (out.close-out.session_vwap)/out.atr.replace(0., np.nan)
            entry_level, exit_level = parameters['entry_atr'], parameters['exit_atr']
        ranged = out.regime.eq('range')
        entry = np.select([ranged & (z < -entry_level) & (z > -4.), ranged & (z > entry_level) & (z < 4.)], [1, -1], default=0)
        leave = ~ranged | (z.abs() <= exit_level) | (z*z.shift() <= 0) | z.isna()
        signal = pd.Series(_stateful(entry, leave), index=out.index)
        # VWAP anchor changes at UTC midnight; a previous session's exposure
        # is allowed only if it requalifies against the new session's value.
        if family == 'vwap_reversion':
            sessions = out.timestamp.dt.floor('D')
            boundaries = sessions.ne(sessions.shift())
            leave = leave | boundaries
            signal = pd.Series(_stateful(entry, leave), index=out.index)
    elif family == 'trend_pullback':
        fast = out.close.ewm(span=parameters['fast'], adjust=False, min_periods=parameters['fast']).mean()
        slow = out.close.ewm(span=parameters['slow'], adjust=False, min_periods=parameters['slow']).mean()
        displacement = (out.close-fast)/out.atr.replace(0., np.nan)
        entry = np.select([
            (fast > slow) & out.htf_trend.eq(1) & displacement.between(-parameters['pullback_atr'], 0),
            (fast < slow) & out.htf_trend.eq(-1) & displacement.between(0, parameters['pullback_atr'])], [1, -1], default=0)
        alignment = np.sign(fast-slow)
        leave = alignment.ne(alignment.shift()) | out.htf_trend.ne(out.htf_trend.shift()) | out.htf_trend.isna()
        signal = pd.Series(_stateful(entry, leave), index=out.index)
    elif family in ('btc_relative', 'cross_relative'):
        symbol = specification.get('symbol')
        if symbol is None and 'ticker' in out:
            raw = str(out.ticker.iloc[0])
            symbol = 'ETH' if 'ETHUSDT' in raw else 'BNB' if 'BNBUSDT' in raw else None
        peer = 'BTC' if family == 'btc_relative' else {'ETH': 'BNB', 'BNB': 'ETH'}.get(symbol)
        column = f'context_{peer}_close'
        if column in out:
            relative = (out.close/out[column]).pct_change(lookback, fill_method=None)
            signal = np.sign(relative).where(np.sign(relative).eq(direction) & np.sign(relative).eq(np.sign(momentum)), 0.)
    elif family == 'funding_fade':
        past = out.past_settled_funding
        z = (out.close-out.ema_fast)/out.atr.replace(0., np.nan)
        signal = pd.Series(np.select([(past > parameters['threshold']) & (z > 0), (past < -parameters['threshold']) & (z < 0)], [-1, 1], default=0), index=out.index)
    else:
        raise ValueError(f'Unknown strategy family: {family}')
    signal = pd.Series(signal, index=out.index).replace([np.inf, -np.inf], np.nan).fillna(0.)
    if family not in ('flat', 'buy_hold'):
        signal = signal.where(out.atr.notna(), 0.)
    out['signal'] = signal.astype(np.int8)
    out.attrs['specification_id'] = specification['id']
    return out

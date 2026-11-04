"""Calendar attribution and retrospective dependent-return diagnostics.

Bar-open dates own a candle's P&L. A candle ending at midnight consequently
belongs to the preceding date. Portfolio sleeves are funded separately before
simulation; this module sums their account values without rescaling or claiming
that correlated crypto exposures diversify risk.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


YEAR = 365.25


def _daily_equity(curve):
    if isinstance(curve, pd.Series):
        work = pd.DataFrame(dict(equity=curve.to_numpy()), index=pd.DatetimeIndex(pd.to_datetime(curve.index, utc=True)))
    else:
        source = 'bar_open' if 'bar_open' in curve else 'timestamp'
        if source not in curve or 'equity' not in curve:
            raise ValueError('Equity curve requires equity and bar_open/timestamp')
        work = pd.DataFrame(dict(equity=curve.equity.to_numpy()), index=pd.DatetimeIndex(pd.to_datetime(curve[source], utc=True)))
    if work.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([], tz='UTC'), name='equity')
    if not work.index.is_monotonic_increasing or work.index.has_duplicates:
        raise ValueError('Curve times must be unique and increasing')
    if not np.isfinite(work.equity).all() or (work.equity <= 0).any():
        raise ValueError('Equity must be positive and finite')
    return work.equity.groupby(work.index.floor('D')).last().rename('equity')


def daily_returns(curve, initial=50000.):
    """Calendar-day returns, including the first day's change from initial.

    Uses ``bar_open`` where present; ``timestamp`` fallback assumes timestamp
    already identifies the attribution date. No missing dates/prices are filled.
    A Series input represents dated daily equity values, not daily returns.
    """
    if not np.isfinite(initial) or initial <= 0:
        raise ValueError('Initial capital must be positive and finite')
    equity = _daily_equity(curve)
    result = equity.pct_change(fill_method=None)
    if len(result):
        result.iloc[0] = equity.iloc[0]/initial-1
    return result.rename('daily_return')


def block_statistics(series, draws=4999, seed=20261103, block=7):
    """Circular block percentile interval and centered one-sided mean-null p.

    The null is zero mean daily return; p = Pr(centered bootstrap mean >=
    observed mean). Common seed, equal calendar and equal sample length use
    identical resampling indices across strategy columns. Block stationarity
    is an assumption. These historical diagnostics are not future odds.
    ``annual_mean_daily_*`` are arithmetic daily-mean interval bounds ×365.25,
    not CAGR or a prediction interval. Small samples receive an explicit flag.
    """
    values = np.asarray(series, dtype=float).reshape(-1)
    if not np.isfinite(values).all():
        raise ValueError('Bootstrap returns must be finite; do not fill missing returns')
    if not isinstance(draws, int) or draws < 1 or not isinstance(block, int) or block < 1:
        raise ValueError('Positive integer draws and block length required')
    n = len(values)
    base = dict(observations=n, draws=draws, block_days=min(block, n), seed=seed,
                method='centered one-sided circular day-block bootstrap; percentile mean interval',
                insufficient_evidence=n < max(30, 4*block))
    if not n:
        return dict(**base, mean_daily=None, mean_daily_lower=None, mean_daily_upper=None,
                    annual_mean_daily_lower=None, annual_mean_daily_upper=None,
                    pvalue_centered_1s=1.)
    length = min(block, n)
    # Prefix sums turn each full/remainder circular block into one lookup.
    # Batches avoid a draws × days allocation for long histories.
    doubled = np.r_[values, values[:length]]
    cumulative = np.r_[0., np.cumsum(doubled)]
    starts = np.arange(n)
    sums = cumulative[starts+length]-cumulative[starts]
    full, remainder = divmod(n, length)
    remainder_sums = cumulative[starts+remainder]-cumulative[starts] if remainder else None
    rng = np.random.default_rng(seed)
    samples = np.empty(draws)
    for left in range(0, draws, 256):
        right = min(draws, left+256)
        # Always draw the extra remainder index so RNG order is independent
        # of the block remainder and reproducible between equal-length runs.
        indices = rng.integers(0, n, size=(right-left, full+1))
        total = sums[indices[:, :full]].sum(axis=1)
        if remainder:
            total += remainder_sums[indices[:, -1]]
        samples[left:right] = total/n
    mean = float(values.mean())
    lower, upper = np.quantile(samples, [.025, .975])
    null = samples-mean
    # The tiny tolerance avoids round-off changing exact all-zero ties.
    tolerance = np.finfo(float).eps*max(1., abs(mean))*8
    p = (1+int(np.count_nonzero(null >= mean-tolerance)))/(draws+1)
    return dict(**base, mean_daily=mean, mean_daily_lower=float(lower), mean_daily_upper=float(upper),
                annual_mean_daily_lower=float(lower*YEAR), annual_mean_daily_upper=float(upper*YEAR),
                pvalue_centered_1s=float(p))


def holm(pvalues, family_size=124):
    """Holm familywise adjusted p values; omitted frozen slots count as p=1.

    ``None``/NaN represent failed or untested hypotheses and are also p=1.
    Family size must include every considered selection hypothesis, rather
    than only the reported winners. Returned values preserve input order.
    """
    if not isinstance(family_size, int) or family_size < len(pvalues):
        raise ValueError('Family size cannot be smaller than the supplied hypotheses')
    values = np.asarray([1. if p is None or pd.isna(p) else float(p) for p in pvalues])
    if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ValueError('p values must lie between zero and one')
    if not len(values):
        return []
    order = np.argsort(values, kind='stable')
    ranked = np.minimum(1., np.maximum.accumulate(values[order]*(family_size-np.arange(len(values)))))
    output = np.empty(len(values))
    output[order] = ranked
    return output.tolist()


def _period_records(returns, pnl, labels):
    rows = []
    for label in pd.unique(labels):
        selected = np.asarray(labels == label)
        values = returns.iloc[np.flatnonzero(selected)]
        deviation = float(values.std(ddof=1)) if len(values) > 1 else 0.
        rows.append(dict(period=str(label), days=int(selected.sum()),
                         net_pnl=float(pnl.iloc[np.flatnonzero(selected)].sum()),
                         net_return=float(np.prod(1+values)-1),
                         mean_daily_return=float(values.mean()),
                         annualized_volatility=float(deviation*np.sqrt(YEAR)),
                         sharpe=float(values.mean()/deviation*np.sqrt(YEAR)) if deviation > 0 else None))
    return rows


def metric_extras(result):
    """JSON-friendly calendar/entry-direction/causal-regime attribution.

    Regime daily results use the previous observed day's final regime, known
    before the current day's returns. Bar-regime P&L is descriptive and kept
    separate. This does not fit thresholds or alter candidate rankings.
    """
    curve, trades, metrics = result['equity'], result['trades'], result['metrics']
    initial = float(metrics.get('initial_capital', 50000.))
    returns = daily_returns(curve, initial)
    equity = _daily_equity(curve)
    pnl = equity.diff()
    if len(pnl):
        pnl.iloc[0] = equity.iloc[0]-initial
    daily = [dict(date=str(day.date()), equity=float(equity.loc[day]), net_pnl=float(pnl.loc[day]),
                  net_return=float(value)) for day, value in returns.items()]
    quarters = pd.Index([f'{d.year}-Q{(d.month-1)//3+1}' for d in returns.index])
    output = dict(daily=daily,
                  monthly=_period_records(returns, pnl, returns.index.strftime('%Y-%m')),
                  quarterly=_period_records(returns, pnl, quarters),
                  yearly=_period_records(returns, pnl, returns.index.strftime('%Y')),
                  block_statistics=block_statistics(returns), long_short={},
                  regime_pnl_attribution=[], daily_regime_performance=[])
    for direction, name in [(1, 'long'), (-1, 'short')]:
        if len(trades) and 'direction' in trades:
            raw = trades.direction
            mask = raw.eq(direction) | raw.astype(str).str.upper().eq(name.upper())
            part = trades.loc[mask]
        else:
            part = trades.iloc[:0]
        net = part.net_pnl if len(part) else pd.Series(dtype=float)
        gains, losses = net[net > 0], net[net < 0]
        output['long_short'][name] = dict(trade_legs=len(part), net_pnl=float(net.sum()),
                                         expectancy=float(net.mean()) if len(net) else None,
                                         win_rate=float((net > 0).mean()) if len(net) else None,
                                         profit_factor=float(gains.sum()/-losses.sum()) if len(losses) else None)
    if len(curve) and 'regime' in curve:
        clock = pd.DatetimeIndex(pd.to_datetime(curve['bar_open'] if 'bar_open' in curve else curve.timestamp, utc=True))
        bars = curve.copy().reset_index(drop=True)
        bars['pnl'] = bars.equity.diff()
        bars.loc[0, 'pnl'] = bars.equity.iloc[0]-initial
        bars['day'] = clock.floor('D')
        bars['regime'] = bars.regime.fillna('unknown').astype(str)
        for regime, group in bars.groupby('regime', sort=True):
            output['regime_pnl_attribution'].append(dict(regime=regime, net_pnl=float(group.pnl.sum()),
                                                        observations=len(group), days=int(group.day.nunique())))
        daily_regime = bars.groupby('day').regime.last().reindex(returns.index).shift(1).fillna('unknown')
        for regime in sorted(daily_regime.unique()):
            mask = daily_regime.eq(regime)
            values = returns.loc[mask]
            output['daily_regime_performance'].append(dict(regime=regime, days=len(values),
                                                           net_pnl=float(pnl.loc[mask].sum()),
                                                           mean_daily_return=float(values.mean()),
                                                           note='previous observed day final regime; noncontiguous returns are not a standalone strategy'))
    return output


def combine_sleeves(curves, initial=50000.):
    """Sum independently funded equal-capital sleeves without leverage uplift.

    Each curve must already be simulated with ``initial/len(curves)`` capital.
    A Series input is a dated daily EQUITY series. Different candle horizons
    are compared at day close. Only intersecting dates are retained; missing
    equity is never filled. Daily sum-of-minima is a conservative bound because
    the component troughs need not occur simultaneously. Per-sleeve max1x caps
    imply combined <=1x at construction, subject to marked exposure drift.
    """
    if not curves or not np.isfinite(initial) or initial <= 0:
        raise ValueError('At least one sleeve and positive capital are required')
    sleeve_initial = initial/len(curves)
    equities, cashes, lows, exposures = [], [], [], []
    for number, curve in enumerate(curves):
        daily = _daily_equity(curve).rename(f'sleeve_{number}')
        equities.append(daily)
        if isinstance(curve, pd.Series):
            cashes.append(daily)
            lows.append(daily)
            exposures.append(None)
            continue
        clock = pd.DatetimeIndex(pd.to_datetime(curve['bar_open'] if 'bar_open' in curve else curve.timestamp, utc=True)).floor('D')
        cash = curve.cash if 'cash' in curve else curve.equity
        worst = curve.intrabar_worst_equity if 'intrabar_worst_equity' in curve else curve.equity
        cashes.append(pd.Series(cash.to_numpy(), index=clock).groupby(level=0).last())
        lows.append(pd.Series(worst.to_numpy(), index=clock).groupby(level=0).min())
        exposures.append(pd.Series(curve.exposed.to_numpy(dtype=float), index=clock).groupby(level=0).mean() if 'exposed' in curve else None)
    aligned = pd.concat(equities, axis=1, join='inner').dropna()
    if aligned.empty:
        raise ValueError('Sleeves have no common observed dates')
    # A late-starting sleeve cannot be reinterpreted as initially funded at an
    # earlier shared date. Otherwise the initial-day correlation is distorted.
    if any(series.index[0] != aligned.index[0] for series in equities):
        raise ValueError('Sleeves must share their initial attribution date')
    values = aligned.sum(axis=1)
    daily = values.pct_change(fill_method=None)
    daily.iloc[0] = values.iloc[0]/initial-1
    sleeve_returns = aligned.pct_change(fill_method=None)
    sleeve_returns.iloc[0] = aligned.iloc[0]/sleeve_initial-1
    cash = pd.concat(cashes, axis=1).reindex(aligned.index).sum(axis=1)
    adverse = pd.concat(lows, axis=1).reindex(aligned.index).sum(axis=1)
    combined = pd.DataFrame(dict(bar_open=aligned.index, timestamp=aligned.index+pd.Timedelta(days=1),
                                 equity=values.to_numpy(), cash=cash.to_numpy(),
                                 intrabar_worst_equity=adverse.to_numpy()))
    peak = np.maximum(initial, np.maximum.accumulate(values.to_numpy()))
    metrics = dict(initial_capital=float(initial), final_equity=float(values.iloc[-1]),
                   net_pnl=float(values.iloc[-1]-initial), net_return=float(values.iloc[-1]/initial-1),
                   max_drawdown=float(np.max(1-values.to_numpy()/peak)),
                   max_intrabar_drawdown_bound=float(np.max(1-adverse.to_numpy()/peak)),
                   covariance_assumption='none; observed sleeve returns correlated on common dates',
                   adverse_bound_note='sum of same-day component minima; troughs need not be simultaneous',
                   omitted_noncommon_days=int(len(set().union(*(set(x.index) for x in equities)))-len(aligned)))
    if all(exposure is not None for exposure in exposures):
        exposure = pd.concat(exposures, axis=1).reindex(aligned.index)
        metrics['mean_sleeve_exposure_fraction'] = float(exposure.to_numpy().mean())
        metrics['days_all_sleeves_exposed'] = int(exposure.gt(0).all(axis=1).sum())
    return dict(equity=combined, daily_returns=daily.rename('daily_return'),
                correlation=sleeve_returns.corr(), metrics=metrics)

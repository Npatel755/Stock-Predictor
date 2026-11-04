"""Formation adapter copied from the frozen parent research engine.

Adds a one-entry-per-setup guard and optional causal structural brackets.
When these columns are absent its trade/fill behavior matches the parent.

Signals express desired direction at a completed candle's close. All signal
orders execute at a later candle open. Capacity is limited using *previous*
completed volume; stop/target orders are triggered market orders with adverse
costs. Partial exits retain risk. Terminal liquidation is an explicitly synthetic
accounting close, outside the capacity model. Exchange mark prices and historical
maintenance tiers are unavailable: liquidation checks are a stress proxy only.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd


DEFAULTS = dict(initial_capital=50000., risk_fraction=.0025, max_leverage=1.,
                fee_bps=5., slippage_bps=2., spread_bps=1., participation_cap=.001,
                qty_step=.001, tick_size=.01, min_notional=5., stop_atr=2.,
                reward_r=3., trail_atr=0., max_hold_bars=48,
                annual_periods=365.25*24, funding_bps_daily=3.,
                maintenance_margin=.005, execution_delay_bars=1,
                skip_entry_timestamps=(), force_terminal_close=True,
                sizing_mode='risk', notional_fraction=1., sizing='risk_fraction')


@dataclass
class Position:
    direction: int
    quantity: float
    entry_price: float
    stop: float
    target: float
    entry_index: int
    entry_time: pd.Timestamp
    entry_fee: float
    funding: float = 0.
    regime: str = 'unknown'
    setup_id: str | None = None


def _metrics(curve, trades, cfg, counters):
    initial = cfg['initial_capital']
    eq = curve.equity.to_numpy()
    returns = pd.Series(eq).pct_change().fillna(eq[0]/initial-1)
    daily = pd.Series(eq, index=pd.DatetimeIndex(curve.bar_open)).resample('1D').last().dropna()
    daily_returns = daily.pct_change().fillna(daily.iloc[0]/initial-1)
    annual = 365.25
    std = daily_returns.std(ddof=1)
    downside = np.sqrt(np.mean(np.minimum(daily_returns, 0.)**2))
    peak = np.maximum(initial, np.maximum.accumulate(eq))
    # Close drawdown is exactly ordered. OHLC worst versus this candle's close
    # peak is a conservative bound: that peak can occur AFTER the adverse mark.
    # It must not be presented as an observed tick-ordered intrabar drawdown.
    close_dd = 1-eq/peak
    max_dd = float(max(0., np.max(close_dd)))
    worst_bound = float(max(0., np.max(1-curve.intrabar_worst_equity.to_numpy()/peak)))
    elapsed = (curve.timestamp.iloc[-1]-curve.bar_open.iloc[0]).total_seconds()/86400
    cagr = (eq[-1]/initial)**(365.25/elapsed)-1 if elapsed >= 365.25 and eq[-1] > 0 else None
    net = trades.net_pnl if len(trades) else pd.Series(dtype=float)
    winners, losers = net[net > 0], net[net < 0]
    under = eq < peak
    streak = max_streak = 0
    for item in under:
        streak = streak+1 if item else 0
        max_streak = max(max_streak, streak)
    result = dict(initial_capital=float(initial), final_equity=float(eq[-1]),
                  net_pnl=float(eq[-1]-initial), net_return=float(eq[-1]/initial-1),
                  cagr=float(cagr) if cagr is not None else None,
                  annualized_volatility=float(std*np.sqrt(annual)) if np.isfinite(std) else None,
                  sharpe=float(daily_returns.mean()/std*np.sqrt(annual)) if std > 0 else None,
                  sortino=float(daily_returns.mean()/downside*np.sqrt(annual)) if downside > 0 else None,
                  calmar=float(cagr/max_dd) if cagr is not None and max_dd > 0 else None,
                  max_drawdown=max_dd, max_intrabar_drawdown=worst_bound,
                  intrabar_drawdown_convention='conservative OHLC bound against running bar-close peak; intrabar event order unobserved',
                  max_time_under_water_days=float(max_streak*elapsed/len(curve)),
                  underwater_fraction=float(under.mean()),
                  trade_legs=len(trades), trades=int(counters['entries']),
                  expectancy=float(net.mean()) if len(net) else None,
                  win_rate=float((net > 0).mean()) if len(net) else None,
                  average_winner=float(winners.mean()) if len(winners) else None,
                  average_loser=float(losers.mean()) if len(losers) else None,
                  payoff_ratio=float(winners.mean()/-losers.mean()) if len(winners) and len(losers) else None,
                  profit_factor=float(winners.sum()/-losers.sum()) if len(losers) else None,
                  turnover=float(counters['notional']/initial),
                  market_exposure=float(curve.exposed.mean()),
                  total_fees=float(counters['fees']), total_funding=float(counters['funding']),
                  liquidation_events=int(counters['liquidations']),
                  partial_exit_legs=int(counters['partial_exits']),
                  rejected_orders=int(counters['rejected']),
                  terminal_capacity_bypass=bool(counters['terminal_bypass']),
                  funding_mode=counters['funding_mode'], cost_config=cfg.copy())
    for direction, label in [(1, 'long'), (-1, 'short')]:
        part = trades[trades.direction.eq(direction)] if len(trades) else trades
        result[f'{label}_net_pnl'] = float(part.net_pnl.sum()) if len(part) else 0.
        result[f'{label}_trade_legs'] = len(part)
    result['liquidation_model'] = 'OHLC last-price maintenance proxy; not exchange mark-price/tier reconstruction'
    return result


def simulate(frame: pd.DataFrame, config: dict | None = None) -> dict:
    """Return ``metrics``, ``trades`` and ``equity`` DataFrames/dict.

    Required: UTC ``timestamp`` (bar open), OHLCV, ``signal``, ``atr``.
    Optional: ``funding_rate`` exact settlement event rates (NaN on other
    bars), ``regime`` known at signal time. Sparse funding rates require full
    settlement coverage established by ingestion; this engine cannot infer it.
    Price/quantity precision is a fixed explicit assumption, not claimed to be
    historically correct exchange metadata. ``execution_delay_bars`` is >=1.
    """
    cfg = {**DEFAULTS, **(config or {})}
    unknown = set(cfg)-set(DEFAULTS)
    if unknown:
        raise ValueError(f'Unknown execution settings: {sorted(unknown)}')
    positive = ['initial_capital', 'risk_fraction', 'max_leverage', 'participation_cap',
                'qty_step', 'tick_size', 'annual_periods']
    if any(not math.isfinite(cfg[k]) or cfg[k] <= 0 for k in positive):
        raise ValueError('Execution sizes and limits must be finite and positive')
    if cfg['sizing'] not in {'risk_fraction', 'buy_hold'}:
        raise ValueError('Unknown sizing policy')
    if cfg['sizing_mode'] not in {'risk', 'notional'} or not 0 < cfg['notional_fraction'] <= 1:
        raise ValueError('Unknown sizing mode or invalid notional fraction')
    notional_sizing = cfg['sizing_mode'] == 'notional' or cfg['sizing'] == 'buy_hold'
    if not notional_sizing and min(cfg['stop_atr'], cfg['reward_r']) <= 0:
        raise ValueError('Risk sizing requires positive protective stop/target geometry')
    if cfg['max_leverage'] > 3 or cfg['risk_fraction'] > .05 or cfg['participation_cap'] > .1:
        raise ValueError('Research leverage/risk/capacity exceeds bounded limits')
    if not math.isfinite(cfg['maintenance_margin']) or not 0 < cfg['maintenance_margin'] < 1:
        raise ValueError('Maintenance margin must be a finite fraction between zero and one')
    if any(cfg[k] < 0 or not math.isfinite(cfg[k]) for k in ['fee_bps', 'slippage_bps', 'spread_bps', 'funding_bps_daily', 'min_notional', 'trail_atr']):
        raise ValueError('Costs and thresholds must be finite and nonnegative')
    delay = cfg['execution_delay_bars']
    if not isinstance(delay, int) or delay < 1 or not isinstance(cfg['max_hold_bars'], int) or cfg['max_hold_bars'] < 0:
        raise ValueError('Execution delay and holding period must be valid integers')
    frame = frame.copy().reset_index(drop=True)
    needed = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'signal', 'atr']
    if not len(frame) or not set(needed).issubset(frame.columns):
        raise ValueError('A nonempty complete OHLCV/signal/ATR frame is required')
    times = pd.DatetimeIndex(frame.timestamp)
    if times.tz is None or str(times.tz) not in {'UTC', 'utc'} or not times.is_monotonic_increasing or times.has_duplicates:
        raise ValueError('Timestamp must be ordered, unique and UTC-aware')
    step = times[1]-times[0] if len(times) > 1 else pd.Timedelta(hours=1)
    if len(times) > 1 and not np.all(np.diff(times.as_unit('ns').asi8) == step.value):
        raise ValueError('Missing or irregular candles: split into separately audited segments')
    prices = frame[['open', 'high', 'low', 'close', 'volume']].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or np.any(prices[:, :4] <= 0) or np.any(prices[:, 4] < 0):
        raise ValueError('OHLCV must be finite with positive prices/nonnegative volume')
    if np.any(prices[:, 1] < np.max(prices[:, [0, 2, 3]], axis=1)) or np.any(prices[:, 2] > np.min(prices[:, [0, 1, 3]], axis=1)):
        raise ValueError('Invalid OHLC ordering')
    if not frame.signal.dropna().isin([-1, 0, 1]).all():
        raise ValueError('Signals must be -1, 0, 1 or NaN')
    use_actual = 'funding_rate' in frame and frame.funding_rate.notna().any()
    if use_actual and not np.isfinite(frame.funding_rate.dropna()).all():
        raise ValueError('Funding rates must be finite')
    skips = {pd.Timestamp(x) for x in cfg['skip_entry_timestamps']}
    cash, p, records, legs = float(cfg['initial_capital']), None, [], []
    counters = dict(entries=0, fees=0., funding=0., notional=0., liquidations=0,
                    partial_exits=0, rejected=0, terminal_bypass=False,
                    funding_mode='actual_settlement' if use_actual else 'adverse_continuous_assumption')
    entered_setups = set()
    fee_rate = cfg['fee_bps']/10000
    adverse = (cfg['slippage_bps']+cfg['spread_bps']/2)/10000
    budget = 0.
    worst = cash
    ever_exposed = False

    def round_price(price, side):
        units = price*(1+side*adverse)/cfg['tick_size']
        return (math.ceil(units-1e-10) if side == 1 else math.floor(units+1e-10))*cfg['tick_size']

    def equity(price):
        return cash+(p.direction*p.quantity*(price-p.entry_price) if p else 0.)

    def mark(price):
        nonlocal worst
        worst = min(worst, equity(price))

    def exit_at(raw_price, i, reason, *, terminal=False):
        nonlocal cash, p, budget
        if p is None:
            return
        qty = p.quantity if terminal else min(p.quantity, budget)
        qty = math.floor(qty/cfg['qty_step']+1e-8)*cfg['qty_step']
        if qty < cfg['qty_step']*.5:
            return
        if terminal and qty > budget+1e-9:
            counters['terminal_bypass'] = True
        fill = round_price(raw_price, -p.direction)
        fee = qty*fill*fee_rate
        fraction = qty/p.quantity
        entry_fee, funding = p.entry_fee*fraction, p.funding*fraction
        gross = p.direction*qty*(fill-p.entry_price)
        cash += gross-fee
        counters['fees'] += fee
        counters['notional'] += qty*fill
        counters['liquidations'] += int(reason in {'liquidation_proxy', 'liquidation_open'})
        counters['partial_exits'] += int(qty < p.quantity-1e-9)
        bounded = reason not in {'signal', 'timeout', 'gap_stop', 'gap_target', 'liquidation_open'}
        legs.append(dict(entry_time=p.entry_time, exit_time=times[i]+step if bounded else times[i],
                         exit_time_is_bar_bound=bounded,
                         direction=p.direction, quantity=qty, entry_price=p.entry_price, exit_price=fill,
                         gross_pnl=gross, entry_fee=entry_fee, exit_fee=fee,
                         funding=funding, net_pnl=gross-entry_fee-fee-funding,
                         reason=reason, regime=p.regime, bars_held=i-p.entry_index+1, setup_id=p.setup_id))
        p.quantity -= qty
        p.entry_fee -= entry_fee
        p.funding -= funding
        budget = max(0., budget-qty)
        if p.quantity < cfg['qty_step']*.5:
            p = None
        mark(raw_price)

    rows = list(frame.itertuples(index=False))
    for i, row in enumerate(rows):
        budget = math.floor((rows[i-1].volume if i else 0.)*cfg['participation_cap']/cfg['qty_step'])*cfg['qty_step']
        worst = equity(row.open)
        ever_exposed = p is not None
        if p:
            if use_actual:
                rate = getattr(row, 'funding_rate', np.nan)
                charge = p.direction*p.quantity*row.open*(float(rate) if pd.notna(rate) else 0.)
            else:
                # Adverse cost for BOTH sides, not an invented historical rate.
                charge = p.quantity*row.open*cfg['funding_bps_daily']/10000*(step/pd.Timedelta(days=1))
            cash -= charge
            p.funding += charge
            counters['funding'] += charge
        mark(row.open)
        protective_exit = False
        if p:
            hit_stop = row.open <= p.stop if p.direction == 1 else row.open >= p.stop
            hit_target = row.open >= p.target if p.direction == 1 else row.open <= p.target
            if hit_stop or hit_target:
                protective_exit = True
                exit_at(row.open if hit_stop else p.target, i, 'gap_stop' if hit_stop else 'gap_target')
            elif equity(row.open) <= p.quantity*row.open*cfg['maintenance_margin']:
                protective_exit = True
                exit_at(row.open, i, 'liquidation_open')
        signal_row = rows[i-delay] if i >= delay else None
        desired = int(signal_row.signal) if signal_row is not None and pd.notna(signal_row.signal) else 0
        setup_key = str(signal_row.setup_id) if signal_row is not None and hasattr(signal_row, 'setup_id') and pd.notna(signal_row.setup_id) else None
        timeout = p is not None and cfg['max_hold_bars'] > 0 and i-p.entry_index >= cfg['max_hold_bars']
        if p and not protective_exit and (desired != p.direction or timeout):
            exit_at(row.open, i, 'timeout' if timeout else 'signal')
            if timeout:
                protective_exit = True
        if p is None and desired and signal_row is not None and not protective_exit and times[i] not in skips and cash > 0 and (setup_key is None or setup_key not in entered_setups):
            atr = float(signal_row.atr)
            distance = atr*cfg['stop_atr']
            buy_hold = notional_sizing
            if buy_hold or (math.isfinite(distance) and distance > 0):
                fill = round_price(row.open, desired)
                stop = signal_row.close-desired*distance if not buy_hold else (-float('inf') if desired == 1 else float('inf'))
                target = signal_row.close+desired*distance*cfg['reward_r'] if not buy_hold else (float('inf') if desired == 1 else -float('inf'))
                if not buy_hold and hasattr(signal_row, 'planned_stop') and pd.notna(signal_row.planned_stop):
                    stop = float(signal_row.planned_stop)
                if not buy_hold and hasattr(signal_row, 'planned_target') and pd.notna(signal_row.planned_target):
                    target = float(signal_row.planned_target)
                # Trigger prices use adverse tick rounding rather than float-only precision.
                if not buy_hold:
                    stop = (math.floor(stop/cfg['tick_size']) if desired == 1 else math.ceil(stop/cfg['tick_size']))*cfg['tick_size']
                    target = (math.floor(target/cfg['tick_size']) if desired == 1 else math.ceil(target/cfg['tick_size']))*cfg['tick_size']
                risk_per_unit = desired*(fill-stop)+(fill+stop)*fee_rate+stop*adverse+cfg['tick_size'] if not buy_hold else 1.
                valid = buy_hold or (desired*(fill-stop) > 0 and desired*(target-fill) > 0 and stop > 0)
                risk_size = cash*cfg['notional_fraction']*cfg['max_leverage']/fill if buy_hold else cash*cfg['risk_fraction']/risk_per_unit if valid else 0.
                qty = min(risk_size,
                          cash*cfg['max_leverage']/(fill*(1+fee_rate)), budget)
                qty = math.floor(max(0., qty)/cfg['qty_step'])*cfg['qty_step']
                if valid and qty >= cfg['qty_step'] and qty*fill >= cfg['min_notional']:
                    fee = qty*fill*fee_rate
                    cash -= fee
                    counters['fees'] += fee
                    counters['notional'] += qty*fill
                    counters['entries'] += 1
                    p = Position(desired, qty, fill, stop, target, i, times[i], fee,
                                 regime=str(getattr(signal_row, 'regime', 'unknown')), setup_id=setup_key)
                    if setup_key is not None:
                        entered_setups.add(setup_key)
                    budget -= qty
                    ever_exposed = True
                    mark(row.open)
                else:
                    counters['rejected'] += 1
        if p:
            low, high = row.low, row.high
            adverse_price = low if p.direction == 1 else high
            favorable_price = high if p.direction == 1 else low
            # Equity = cash + direction*q*(mark-entry). Solve maintenance floor.
            denominator = p.quantity*(p.direction-cfg['maintenance_margin'])
            liquidation = (p.direction*p.quantity*p.entry_price-cash)/denominator
            stop_hit = low <= p.stop if p.direction == 1 else high >= p.stop
            target_hit = high >= p.target if p.direction == 1 else low <= p.target
            liquidation_hit = liquidation > 0 and (low <= liquidation if p.direction == 1 else high >= liquidation)
            if stop_hit or liquidation_hit:
                trigger = p.stop if stop_hit else liquidation
                reason = 'stop'
                if liquidation_hit and (not stop_hit or (liquidation > p.stop if p.direction == 1 else liquidation < p.stop)):
                    trigger, reason = liquidation, 'liquidation_proxy'
                mark(trigger)
                exit_at(trigger, i, reason)
                if p:
                    mark(adverse_price)  # Partial stop leaves genuine residual risk.
            elif target_hit:
                mark(adverse_price)
                exit_at(p.target, i, 'target')
            else:
                mark(adverse_price)
            if p:
                mark(row.close)
                if cfg['trail_atr'] and pd.notna(row.atr):
                    proposal = row.close-p.direction*float(row.atr)*cfg['trail_atr']
                    proposal = (math.floor(proposal/cfg['tick_size']) if p.direction == 1 else math.ceil(proposal/cfg['tick_size']))*cfg['tick_size']
                    p.stop = max(p.stop, proposal) if p.direction == 1 else min(p.stop, proposal)
        if i == len(rows)-1 and p and cfg['force_terminal_close']:
            exit_at(row.close, i, 'terminal_accounting', terminal=True)
        mark(row.close)
        records.append(dict(bar_open=times[i], timestamp=times[i]+step, cash=cash,
                            equity=equity(row.close), intrabar_worst_equity=worst,
                            position_qty=p.direction*p.quantity if p else 0.,
                            exposed=ever_exposed, regime=str(getattr(row, 'regime', 'unknown'))))
    curve = pd.DataFrame(records)
    columns = ['entry_time', 'exit_time', 'exit_time_is_bar_bound', 'direction', 'quantity',
               'entry_price', 'exit_price', 'gross_pnl', 'entry_fee', 'exit_fee', 'funding',
               'net_pnl', 'reason', 'regime', 'bars_held', 'setup_id']
    trades = pd.DataFrame(legs, columns=columns)
    metrics = _metrics(curve, trades, cfg, counters)
    metrics['open_position'] = vars(p).copy() if p else None
    if p is None and abs(trades.net_pnl.sum()-(cash-cfg['initial_capital'])) > 1e-6:
        raise AssertionError('Closed trade ledger does not reconcile with account cash')
    return dict(metrics=metrics, trades=trades, equity=curve)

"""Visualize exact broker events without changing the frozen simulator."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .market_data import BAR


def equity_curve(bars, events, config):
    """Reconstruct bar-close cash/positions from actual ordered fill events.

    Entry/exit fees and financing are taken at their broker event bars. Open
    P&L is marked against each real candle close, not interpolated from exits.
    """
    cash, quantity, direction, entry = config.initial_capital, 0., 0, 0.
    states = []
    for event in events.to_dict('records'):
        kind = event['event']
        if kind == 'entry':
            if quantity > 0:
                raise ValueError('Visual replay does not permit pyramiding')
            quantity, direction, entry = float(event['quantity']), int(event['direction']), float(event['price'])
            cash -= quantity*entry*config.point_value*config.commission_bps/10000
        elif kind == 'financing':
            cash -= float(event['amount'])
        elif kind in {'stop', 'target', 'time_stop', 'margin_call', 'gap_boundary'}:
            amount, fill = float(event['quantity']), float(event['price'])
            if amount > quantity+1e-8:
                raise ValueError('Visual exit exceeds the open quantity')
            cash += direction*amount*(fill-entry)*config.point_value
            cash -= amount*fill*config.point_value*config.commission_bps/10000
            quantity -= amount
            if quantity < .0005:
                quantity, direction, entry = 0., 0, 0.
        elif kind == 'stop_update':
            continue
        else:
            raise ValueError(f'Unsupported broker event: {kind}')
        states.append(dict(timestamp=event['bar_open'], cash=cash, position_qty=direction*quantity, entry_price=entry))
    times = pd.DatetimeIndex(bars.timestamp)
    if states:
        state = pd.DataFrame(states)
        state['timestamp'] = pd.to_datetime(state.timestamp, utc=True)
        state = state.groupby('timestamp', sort=True).last().reindex(times, method='ffill')
        state = state.fillna({'cash': config.initial_capital, 'position_qty': 0., 'entry_price': 0.})
    else:
        state = pd.DataFrame(dict(cash=config.initial_capital, position_qty=0., entry_price=0.), index=times)
    equity = state.cash.to_numpy()+state.position_qty.to_numpy()*(bars.close.to_numpy()-state.entry_price.to_numpy())*config.point_value
    peak = np.maximum(config.initial_capital, np.maximum.accumulate(equity))
    return pd.DataFrame(dict(timestamp=times+BAR, cash=state.cash.to_numpy(), equity=equity,
                             position_qty=state.position_qty.to_numpy(), close_drawdown_pct=(equity/peak-1)*100))


def performance_chart(curve, initial_capital, version='v1.3'):
    # Daily extrema preserve visible equity troughs/peaks in long replays.
    work = curve.copy()
    work['day'] = work.timestamp.dt.floor('D')
    grouped = work.groupby('day')
    indices = {0, len(work)-1}
    for column in ['equity', 'close_drawdown_pct']:
        indices.update(grouped[column].idxmin())
        indices.update(grouped[column].idxmax())
    indices.update(grouped.tail(1).index)
    display = work.loc[sorted(indices)]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.72, .28], vertical_spacing=.06)
    fig.add_trace(go.Scatter(x=display.timestamp, y=display.equity, name='Account equity',
                             line=dict(color='#38bdf8', width=2), hovertemplate='%{x}<br>$%{y:,.2f}<extra>Equity</extra>'), row=1, col=1)
    fig.add_hline(y=initial_capital, line_dash='dot', line_color='#64748b', row=1, col=1)
    fig.add_trace(go.Scatter(x=display.timestamp, y=display.close_drawdown_pct, name='Drawdown at candle close',
                             fill='tozeroy', line=dict(color='#fb7185'), hovertemplate='%{x}<br>%{y:.2f}%<extra>Close drawdown</extra>'), row=2, col=1)
    fig.update_layout(template='plotly_dark', height=610, title=f'ETH {version} · Equity and drawdown',
                      margin=dict(l=25, r=20, t=55, b=25), legend=dict(orientation='h'), hovermode='x unified')
    fig.update_yaxes(title_text='Equity ($)', row=1, col=1)
    fig.update_yaxes(title_text='Drawdown (%)', row=2, col=1)
    return fig


def monthly_chart(curve, initial_capital):
    changes = curve.equity.diff()
    changes.iloc[0] = curve.equity.iloc[0]-initial_capital
    # A 00:00 candle close belongs to the preceding trading day/month.
    months = (curve.timestamp-pd.Timedelta(nanoseconds=1)).dt.strftime('%Y-%m')
    values = changes.groupby(months).sum()
    fig = go.Figure(go.Bar(x=values.index, y=values.to_numpy(), name='Monthly net P&L',
                          marker_color=np.where(values >= 0, '#34d399', '#fb7185'),
                          hovertemplate='%{x}<br>$%{y:,.2f}<extra></extra>'))
    fig.update_layout(template='plotly_dark', height=280, title='Monthly marked P&L · fees and financing included',
                      margin=dict(l=25, r=20, t=50, b=25), yaxis_title='Net P&L ($)')
    return fig


def trade_chart(bars, trade, events, reward_r):
    start, end = pd.Timestamp(trade.entry_bar_open), pd.Timestamp(trade.exit_bar_open)
    window = bars[(bars.timestamp >= start-pd.Timedelta(hours=6)) & (bars.timestamp <= end+pd.Timedelta(hours=6))]
    # Bound rendering cost for unusually long positions while keeping fills.
    rule = '5min'
    if len(window) > 3000:
        rule = '1h'
        window = window.set_index('timestamp').resample(rule).agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna().reset_index()
    fig = go.Figure(go.Candlestick(x=window.timestamp, open=window.open, high=window.high, low=window.low, close=window.close, name='ETH candles'))
    signal = bars[bars.timestamp == start-BAR]
    if len(signal):
        signal_close = float(signal.close.iloc[0])
        initial_distance = abs(float(trade.target)-signal_close)/reward_r
        initial_stop = signal_close-(1 if trade.direction == 'LONG' else -1)*initial_distance
        updates = events[(events.event == 'stop_update') & (events.bar_open >= start) & (events.bar_open < end)]
        xs = [start] + list(updates.bar_open+BAR) + [end+BAR]
        ys = [initial_stop] + list(updates.price) + [float(trade.stop)]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode='lines', line=dict(color='#fb7185', shape='hv', dash='dash'), name='Active stop'))
    else:
        fig.add_hline(y=float(trade.stop), line_dash='dash', line_color='#fb7185', annotation_text='Stop at exit')
    fig.add_trace(go.Scatter(x=[start, end+BAR], y=[trade.target, trade.target], mode='lines', line=dict(color='#34d399', dash='dash'), name='Target'))
    fig.add_trace(go.Scatter(x=[start, end], y=[trade.entry_price, trade.exit_price], mode='markers+text',
                             text=['Entry', 'Exit'], textposition=['bottom center', 'top center'],
                             marker=dict(size=13, color=['#38bdf8', '#fbbf24'], symbol=['triangle-up' if trade.direction == 'LONG' else 'triangle-down', 'x']), name='Simulated fills'))
    fig.update_layout(template='plotly_dark', height=490, xaxis_rangeslider_visible=False,
                      title=f"{trade.direction} · {start:%Y-%m-%d %H:%M} UTC · net ${trade.net_pnl:,.2f}",
                      margin=dict(l=25, r=20, t=55, b=25), legend=dict(orientation='h'))
    return fig, rule

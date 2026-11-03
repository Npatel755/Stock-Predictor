"""Replay and display filtered experimental rules without mutating versions."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .alternative_strategies import SignalRule, simulate
from .config import StrategyConfig
from .independent_visuals import equity_curve, monthly_chart, performance_chart, trade_chart
from .optimize import write_json
from .regime_filters import RegimeFilter, apply_filter, prepare_features


def replay(bars, candidate, execution, directory: Path):
    rule = SignalRule(**candidate['rule'])
    filters = RegimeFilter(**candidate['filters'])
    cfg = StrategyConfig(**execution)
    features = apply_filter(prepare_features(bars, rule), filters)
    metrics, trades, events = simulate(bars, rule, cfg, signals=features)
    curve = equity_curve(bars, events, cfg)
    if abs(curve.equity.iloc[-1]-metrics['final_equity']) > 1e-6:
        raise ValueError('Filtered visual equity does not reconcile with the broker')
    period = [str(bars.timestamp.min()), str(bars.available_at.max())]
    result = dict(metrics=metrics, trades=trades, events=events, equity=curve, candidate=candidate,
                  execution=asdict(cfg), period=period, independent_validation=False)
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory/'results.json', {k: v for k, v in result.items() if k not in {'trades', 'events', 'equity'}})
    trades.to_csv(directory/'trades.csv', index=False)
    events.to_csv(directory/'events.csv', index=False)
    curve.to_parquet(directory/'equity.parquet', index=False)
    return result


def display(result, bars, key):
    import streamlit as st
    m, candidate, curve, trades = [result[k] for k in ['metrics', 'candidate', 'equity', 'trades']]
    st.subheader(f"Research replay · {candidate['label']}")
    st.caption(f"Completed replay: {result['period'][0]} to {result['period'][1]} exclusive. Saved numbered versions are unchanged. Historical selection results are not independent forward validation.")
    a, b, c = st.columns(3)
    a.metric('Research net P&L', f"${m['final_equity']-m['initial_capital']:,.2f}")
    b.metric('Research entries', m['entries'])
    c.metric('Research running-peak drawdown', f"{m['max_intrabar_drawdown']:.2%}")
    figure = performance_chart(curve, m['initial_capital'])
    figure.update_layout(title=f"{candidate['label']} · Equity and drawdown")
    st.plotly_chart(figure, width='stretch', key=f'filtered_equity_{key}')
    st.caption('Equity includes simulated fees, financing and open-position marks at candle close. The chart shows close-based drawdown; the metric above includes intrabar movement.')
    monthly, candles, ledger = st.tabs(['Research monthly P&L', 'Research trade chart', 'Research ledger'])
    with monthly:
        st.plotly_chart(monthly_chart(curve, m['initial_capital']), width='stretch', key=f'filtered_monthly_{key}')
    with candles:
        if len(trades):
            index = st.selectbox('Inspect research trade', list(range(len(trades))), key=f'filtered_trade_{key}',
                                 format_func=lambda i: f"{i+1} · {trades.iloc[i].direction} · {trades.iloc[i].entry_bar_open} · ${trades.iloc[i].net_pnl:,.2f}")
            original = bars[(bars.timestamp >= pd.Timestamp(result['period'][0])) & (bars.timestamp < pd.Timestamp(result['period'][1]))]
            fig, resolution = trade_chart(original, trades.iloc[index], result['events'], candidate['rule']['reward_r'])
            st.plotly_chart(fig, width='stretch', key=f'filtered_candles_{key}')
            st.caption(f'{resolution} candles; intrabar fill timestamps are bounds. The active stop updates only after completed candles.')
        else:
            st.info('No closed research trades in this replay.')
    with ledger:
        st.dataframe(trades, width='stretch', hide_index=True)
        st.download_button('Download filtered research trades', trades.to_csv(index=False), 'eth_filtered_research_trades.csv', 'text/csv', key=f'filtered_csv_{key}')
    if m['open_position']:
        from .reporting import safe_value
        st.json(safe_value(m['open_position']))

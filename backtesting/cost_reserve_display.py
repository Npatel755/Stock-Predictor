"""Visual comparison of the single unpromoted cost-reserve candidate."""
import json

import pandas as pd
import streamlit as st

from .cost_reserve_study import artifact_directory, candidate_directory, registered, sha
from .generalization_policy import digest
from .independent_visuals import performance_chart, monthly_chart, trade_chart
from .optimize import pnl


def render(root):
    directory = artifact_directory(root)/'development'
    path = directory/'results.json'
    if not path.exists():
        return
    st.subheader('ETH v1.12 research candidate: fixed execution-cost budget')
    try:
        plan = registered(root)
        result = json.loads(path.read_text(encoding='utf-8'))
        if result['protocol_sha256'] != digest(plan):
            raise ValueError('Candidate result does not match its registered protocol')
        for name, expected in result['artifacts_sha256'].items():
            if sha(directory/name) != expected:
                raise ValueError(f'Candidate ledger or curve changed: {name}')
    except (ValueError, OSError) as exc:
        st.error(str(exc))
        return
    st.info('Unpromoted candidate. One predefined change: size for 8bp slippage. Entry signals, stop/target/trailing rules and the $100 planned risk remain fixed. Historical results are development diagnostics.')
    st.caption('Earlier stress tests changed both sizing and fill costs together. Here sizing budgets stay fixed while actual market/stop fills are independently stressed. Two ticks, commissions and financing are still charged.')
    st.caption(f"Separate candidate future window: {plan['future_period'][0]} to {plan['future_period'][1]} exclusive. v1.11 retains its original lock. The candidate does not inherit v1.11 validation.")
    proof = directory/'verification.json'
    if proof.exists() and json.loads(proof.read_text())['results_sha256'] == sha(path):
        st.caption('Fresh computational replay reproduced the fixed-budget metrics, ledgers and equity curves. This is not independent future validation.')
    fill = st.selectbox('Actual fill slippage for fixed-budget comparison (bp)', [2., 4., 8.],
                        index=2, key='cost_reserve_fill')
    rows = [r for r in result['scenarios'] if r['period'] == 'full' and r['actual_fill_slippage_bps'] == fill]
    a, b = rows
    columns = st.columns(3)
    columns[0].metric('v1.11 fixed-2bp-budget net', f"${pnl(a['metrics']):,.2f}")
    columns[1].metric('v1.12 candidate fixed-8bp-budget net', f"${pnl(b['metrics']):,.2f}",
                      delta=f"${pnl(b['metrics'])-pnl(a['metrics']):,.2f}")
    columns[2].metric('Candidate intrabar drawdown', f"{b['metrics']['max_intrabar_drawdown']:.2%}")
    if pnl(b['metrics']) < pnl(a['metrics']):
        st.warning('The candidate earns less net profit in this scenario. A smaller position is not evidence of a stronger trading edge; assess the risk trade-off and the separate future test.')
    st.caption(f"Estimated initial-stop exposure at 8bp, excluding gaps/financing: baseline max ${a['planned_risk_at_8bp']['maximum_estimated_usd']:.2f}; candidate max ${b['planned_risk_at_8bp']['maximum_estimated_usd']:.2f}. These estimates are not hard loss caps.")
    curves = [pd.read_parquet(directory/'full'/f"{r['strategy']}_fill{int(fill)}_equity.parquet") for r in rows]
    figure = performance_chart(curves[1], b['metrics']['initial_capital'], version='v1.12 candidate')
    figure.data[0].name = 'v1.12 candidate equity'
    figure.data[1].name = 'v1.12 candidate close drawdown'
    # Use the same daily-extrema reduction as the standard chart to bound UI size.
    baseline_figure = performance_chart(curves[0], a['metrics']['initial_capital'])
    for index, trace in enumerate(baseline_figure.data):
        trace.name = 'v1.11 fixed-budget equity' if index == 0 else 'v1.11 fixed-budget close drawdown'
        trace.line.color = '#fbbf24'
        trace.fill = None
        figure.add_trace(trace, row=index+1, col=1)
    st.plotly_chart(figure, width='stretch', key='cost_reserve_comparison')
    st.caption('Equity includes open marks, modeled fees and financing. Plotted drawdown is at candle close; the metric includes intrabar movement.')
    monthly, candles, table = st.tabs(['Candidate monthly P&L', 'Candidate trade chart', 'Fixed-budget comparison table'])
    with monthly:
        st.plotly_chart(monthly_chart(curves[1], b['metrics']['initial_capital']), width='stretch', key='cost_reserve_monthly')
    with candles:
        prefix = directory/'full'/f"{b['strategy']}_fill{int(fill)}"
        trades = pd.read_csv(str(prefix)+'_trades.csv')
        events = pd.read_csv(str(prefix)+'_events.csv')
        for frame in [trades, events]:
            for name in ['entry_bar_open', 'exit_bar_open', 'bar_open', 'effective_at']:
                if name in frame:
                    frame[name] = pd.to_datetime(frame[name], utc=True)
        if len(trades):
            index = st.selectbox('Inspect candidate trade', list(range(len(trades))), key='cost_reserve_trade',
                                format_func=lambda i: f"{i+1} | {trades.iloc[i].direction} | {trades.iloc[i].entry_bar_open} | ${trades.iloc[i].net_pnl:,.2f}")
            bars = pd.read_parquet(directory/'bars.parquet')
            candidate = json.loads((candidate_directory(root)/'config.json').read_text(encoding='utf-8'))
            figure, resolution = trade_chart(bars, trades.iloc[index], events, candidate['strategy']['rule']['reward_r'])
            st.plotly_chart(figure, width='stretch', key='cost_reserve_candles')
            st.caption(f'{resolution} candles; fill times within candles are bounds.')
        st.download_button('Download candidate trades', trades.to_csv(index=False), 'ETH_v1_12_candidate_trades.csv', 'text/csv', key='cost_reserve_trades')
    with table:
        st.dataframe(pd.DataFrame([dict(period=r['period'], sizing_budget_bp=r['sizing_slippage_bps'],
                                        actual_fill_bp=r['actual_fill_slippage_bps'], net=pnl(r['metrics']),
                                        entries=r['metrics']['entries'], drawdown=r['metrics']['max_intrabar_drawdown'])
                                   for r in result['scenarios']]), hide_index=True)
        st.caption('Annual tests independently reset accounts. Their net sums are not the full-period return.')
    for extension in ['txt', 'pine']:
        file = candidate_directory(root)/f'ETH_Strategy_v1_12_candidate.{extension}'
        st.download_button(f'Download v1.12 candidate .{extension}', file.read_bytes(), file.name,
                           'text/plain', key=f'cost_reserve_export_{extension}')
    st.caption('Pine compilation and trade parity remain unverified. Pine uses two-tick fill slippage; its 8bp input affects sizing only, and financing is not reproduced.')

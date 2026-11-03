"""Read-only experiment progress and causal strategy comparisons."""
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .strategy_lab import directory, load_development, sha
from .generalization_policy import digest, frozen_profile
from .independent_visuals import performance_chart, monthly_chart, trade_chart
from .optimize import pnl


def render(root):
    out = directory(root)
    if not (out/'manifest.json').exists():
        return
    st.subheader('Alternative strategy lab: 24 predefined candidates')
    try:
        frozen_profile(root)
        manifest = json.loads((out/'manifest.json').read_text())
        for name, expected in manifest['source_sha256'].items():
            if sha(root/name) != expected:
                raise ValueError(f'Experiment implementation changed: {name}')
    except (ValueError, OSError) as exc:
        st.error(str(exc)); return
    st.caption('Six alternative families, 1h/4h completed signals, two fixed exit profiles. Training: 2020-2023. Selection check: 2024. Later diagnostic: 2025-2026. Seven-day chronological gaps; every date is consumed development history. The future test remains sealed.')
    st.button('Refresh strategy lab status', key='strategy_lab_refresh')
    rows = [json.loads(p.read_text()) for p in sorted((out/'training').glob('*.json'))]
    if not (out/'results.json').exists():
        st.progress(len(rows)/24, text=f'Training candidates completed: {len(rows)} / 24')
        if rows:
            st.dataframe(pd.DataFrame([dict(candidate=r['candidate']['id'], score=r['rank']['score'],
                                            eligible=r['rank']['eligible']) for r in rows]), hide_index=True)
        st.info('Experiment in progress. This screen reads checkpoints without launching another search.')
        return
    result_path = out/'results.json'
    result = json.loads(result_path.read_text())
    if result['manifest_sha256'] != digest(manifest):
        st.error('Results do not match the experiment manifest'); return
    proof = out/'verification_artifacts.json'
    if proof.exists():
        verification = json.loads(proof.read_text())
        if verification['results_sha256'] != sha(result_path):
            st.error('Replay verification does not match the current results'); return
        for name, expected in verification['artifacts_sha256'].items():
            if sha(out/name) != expected:
                st.error('A verified experiment ledger or equity curve changed'); return
        st.caption('All 24 training candidates, validation choices and later diagnostic replays reproduced exactly. Ledgers and equity curves are hash-pinned. This is computational verification, not independent future validation.')
    selected = result['selected']
    winners = {r['candidate']['id']: r for r in result['validation']}
    st.dataframe(pd.DataFrame([dict(candidate=r['candidate']['id'],
                                    training_score=r['rank']['score'], train_eligible=r['rank']['eligible'],
                                    validation_closed_net=winners[r['candidate']['id']]['result']['closed_net'] if r['candidate']['id'] in winners else None,
                                    validation_eligible=winners[r['candidate']['id']]['rank']['eligible'] if r['candidate']['id'] in winners else False)
                               for r in result['training']]), hide_index=True)
    chart = go.Figure()
    for row in result['training']:
        if row['candidate']['id'] in winners:
            chart.add_bar(x=[str(f['year']) for f in row['folds']], y=[f['closed_net'] for f in row['folds']], name=row['candidate']['id'])
    chart.update_layout(template='plotly_dark', title='Training-family shortlist: annual closed P&L at 8bp fills',
                         yaxis_title='Closed net ($)', barmode='group', height=400)
    st.plotly_chart(chart, width='stretch', key='strategy_lab_training')
    if selected is None:
        st.warning('No alternative passed both fixed training and 2024 gates. No strategy version was promoted.')
        return
    st.write('Selected before the later diagnostic:', selected['id'])
    if result['historical_comparison_passed']:
        st.info('The selected challenger passed the declared historical comparison. It is an unpromoted research candidate and needs its own future protocol.')
    else:
        st.warning('The selected challenger did not pass every historical improvement check. The original benchmark is retained; this outcome does not change the selection or thresholds.')
    fill = st.selectbox('Strategy-lab actual fill slippage (bp)', [2., 4., 8.], index=2, key='strategy_lab_fill')
    table = [r for r in result['audit'] if r['period'] == 'full_development' and r['actual_fill_slippage_bps'] == fill]
    st.dataframe(pd.DataFrame([dict(strategy=r['strategy'], sizing_budget_bp=r['sizing_budget_bps'],
                                    net=pnl(r['metrics']), closed_net=r['closed_net'],
                                    drawdown=r['metrics']['max_intrabar_drawdown'], entries=r['metrics']['entries']) for r in table]), hide_index=True)
    st.caption('Every rule gets causal 2020-2022 indicator warm-up before this 2023-2026 comparison. This differs from initializing at January 2023; the original saved score remains a separate reference.')
    challenger = next(r for r in table if r['strategy'] == 'challenger')
    prefix = out/'audit/full_development'/f'challenger_fill{int(fill)}'
    curve = pd.read_parquet(prefix/'equity.parquet')
    figure = performance_chart(curve, 50000., version='alternative challenger')
    for row, color in [('v1.11_original_budget', '#fbbf24'), ('v1.12_8bp_budget', '#c084fc')]:
        base = pd.read_parquet(out/'audit/full_development'/f'{row}_fill{int(fill)}'/'equity.parquet')
        reference = performance_chart(base, 50000.)
        for i, trace in enumerate(reference.data):
            trace.name = f'{row} {"equity" if i == 0 else "close drawdown"}'
            trace.line.color = color; trace.fill = None
            figure.add_trace(trace, row=i+1, col=1)
    st.plotly_chart(figure, width='stretch', key='strategy_lab_equity')
    monthly, candle_tab, audit = st.tabs(['Alternative monthly P&L', 'Alternative trade chart', 'Later diagnostic results'])
    with monthly:
        st.plotly_chart(monthly_chart(curve, 50000.), width='stretch', key='strategy_lab_monthly')
    with candle_tab:
        if challenger['metrics']['closed_trade_legs']:
            trades = pd.read_csv(prefix/'trades.csv')
            events = pd.read_csv(prefix/'events.csv')
            for frame in [trades, events]:
                for name in ['entry_bar_open', 'exit_bar_open', 'bar_open', 'effective_at']:
                    if name in frame:
                        frame[name] = pd.to_datetime(frame[name], utc=True)
            index = st.selectbox('Inspect alternative trade', list(range(len(trades))), key='strategy_lab_trade',
                                format_func=lambda i: f"{i+1} | {trades.iloc[i].direction} | {trades.iloc[i].entry_bar_open} | ${trades.iloc[i].net_pnl:,.2f}")
            bars = load_development(root, manifest)
            figure, resolution = trade_chart(bars, trades.iloc[index], events, selected['rule']['reward_r'])
            st.plotly_chart(figure, width='stretch', key='strategy_lab_candles')
            st.caption(f'{resolution} candles; intrabar fills have bounded timestamps.')
            st.download_button('Download alternative trades', trades.to_csv(index=False), 'alternative_ETH_research_trades.csv', 'text/csv', key='strategy_lab_csv')
    with audit:
        st.dataframe(pd.DataFrame([dict(period=r['period'], strategy=r['strategy'],
                                        fill_bp=r['actual_fill_slippage_bps'], net=pnl(r['metrics']),
                                        closed_net=r['closed_net'], drawdown=r['metrics']['max_intrabar_drawdown'])
                                   for r in result['audit']]), hide_index=True)
        st.json(result['comparison_checks'])

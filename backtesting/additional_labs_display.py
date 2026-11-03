"""Read-only ML and coarse-timeframe research results alongside the main lab."""
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .generalization_policy import digest, frozen_profile
from .independent_visuals import performance_chart, monthly_chart
from .optimize import pnl
from .strategy_lab import sha


def render(root):
    for name, title in [('trade_quality_round1', 'Trade-quality models: Ridge, XGBoost and neural network'),
                         ('channel_timeframes_round1', 'Classic channels: 1h, 4h and daily'),
                         ('robust_structure_round1', 'Structural robustness: wider stops, fresh-breakout guard, parameter ensembles'),
                         ('v2_scale_in_round1', 'v2 scale-in candidates: half risk at the signal, half after follow-through'),
                         ('v2_funding_fade_round1', 'v2 funding-crowding fade: a second return source beside v1.11')]:
        out = root/'artifacts/strategy_lab'/name
        if not (out/'manifest.json').exists():
            continue
        st.subheader(title)
        try:
            frozen_profile(root)
            manifest = json.loads((out/'manifest.json').read_text())
            for path, expected in manifest['source_sha256'].items():
                if sha(root/path) != expected:
                    raise ValueError(f'Registered experiment source changed: {path}')
        except (ValueError, OSError) as exc:
            st.error(str(exc)); continue
        st.caption('Consumed development data with chronological selection and fixed costs. These experiments do not access the future test or promote a strategy version.')
        result_path = out/'results.json'
        if not result_path.exists():
            checkpoint = out/'status.json'
            if checkpoint.exists():
                status = json.loads(checkpoint.read_text())
                if status['stage'] == 'training':
                    st.progress(status['complete']/status['total'], text=f"Training {status['complete']}/{status['total']}")
            st.info('Experiment running; refresh to read the latest completed checkpoints.')
            continue
        result = json.loads(result_path.read_text())
        if result['manifest_sha256'] != digest(manifest):
            st.error('Experiment results differ from the registered plan'); continue
        proof = out/'verification.json'
        if proof.exists():
            verification = json.loads(proof.read_text())
            if verification['results_sha256'] != sha(result_path):
                st.error('Replay certificate does not match results'); continue
            changed = any(sha(out/path) != expected for path, expected in verification['artifacts_sha256'].items())
            if changed:
                st.error('A pinned research artifact changed'); continue
            st.caption('Fresh replay reproduced the registered candidate outcomes. This verifies computation, not future performance.')
        if name == 'trade_quality_round1':
            st.write('Closed training trades:', result['training_samples'])
            st.caption('Targets are net trade P&L per $100 planned risk. Models and scaler fit 2020-2022 closed trades only; six model/threshold pairs are selected on 2023. Unconverged models are ineligible.')
            rows = [dict(candidate=r['id'], closed_net_2023=r['rank']['closed_net'],
                          unfiltered_closed_net=r['rank']['parent_closed_net'],
                          converged=r['fit_converged'], eligible=r['rank']['eligible']) for r in result['selection']]
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            for model, messages in result['fitting_warnings'].items():
                if messages:
                    st.warning(f'{model}: '+ '; '.join(messages))
            fig = go.Figure(go.Bar(x=[r['candidate'] for r in rows], y=[r['closed_net_2023'] for r in rows]))
            fig.add_hline(y=rows[0]['unfiltered_closed_net'], line_dash='dash', annotation_text='Unfiltered same-budget baseline')
            fig.update_layout(template='plotly_dark', title='2023 selection-period closed net at 8bp actual fills', yaxis_title='Closed net ($)', height=380)
            st.plotly_chart(fig, width='stretch', key='quality_models_comparison')
        elif name == 'v2_funding_fade_round1':
            st.caption('Six predefined fades of positioning crowding measured from settled funding (90th/95th/98th percentile of the 24h mean rate over 30 days, with or without a prior-24h-range break), fixed 2 ATR stop / 3R target / 96h time stop. Standalone training 2020-2023 must be positive; portfolio gate against unchanged v1.11. Dates are consumed; nothing here is forward evidence.')
            rows = [dict(candidate=r['candidate']['id'], score=r['rank']['score'], median_annual_closed=r['rank']['median_closed_net'],
                         entries=sum(f['metrics']['entries'] for f in r['folds']), eligible=r['rank']['eligible']) for r in result['training']]
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            fig = go.Figure(go.Bar(x=[r['candidate'] for r in rows], y=[r['score'] for r in rows]))
            fig.add_hline(y=0, line_dash='dash', annotation_text='Standalone eligibility: positive score')
            fig.update_layout(template='plotly_dark', title='Penalized annual training score at 8bp fills', height=380)
            st.plotly_chart(fig, width='stretch', key='funding_fade_training')
            if result.get('candidate_registered'):
                st.info('Frozen selection registered as an unpromoted v2.0 research candidate in candidates/eth_v2_0; only its sealed future period can validate it.')
        elif name == 'v2_scale_in_round1':
            st.caption('Six predefined ways to deploy the $100 planned risk in two legs (core at the v1.11 signal, add-on after 0.5/1.0/1.5R of follow-through; breakeven or original stop). Entries, filters, target and trail are frozen v1.11 rules. Training 2020-2023 against a same-budget v1.11 replica, selection 2024; seven-day gaps. Drawdowns are upper bounds.')
            rows = [dict(candidate=r['candidate']['id'], score=r['rank']['score'], median_annual_closed=r['rank']['median_closed_net'],
                         eligible=r['rank']['eligible']) for r in result['training']]
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            fig = go.Figure(go.Bar(x=[r['candidate'] for r in rows], y=[r['score'] for r in rows]))
            fig.add_hline(y=result['baseline_training']['rank']['score'], line_dash='dash', annotation_text='Same-budget v1.11 replica')
            fig.update_layout(template='plotly_dark', title='Penalized annual training score at 8bp fills', height=380)
            st.plotly_chart(fig, width='stretch', key='scale_in_training')
            if result.get('candidate_registered'):
                st.info('Frozen selection registered as an unpromoted v2.0 research candidate in candidates/eth_v2_0; only its sealed future period can validate it.')
        elif name == 'robust_structure_round1':
            st.caption('Ten predefined structural variants of the frozen v1.11 entries: 2.0/2.5/3.0 ATR stops at a fixed 8.25 ATR target, a 72-hour fresh-breakout guard, and 3/3/9-member parameter ensembles traded as independent sub-accounts. Training 2020-2023 against a same-budget v1.11 replica, selection 2024; seven-day gaps. Ensemble drawdowns are upper bounds.')
            rows = [dict(candidate=r['candidate']['id'], group=r['candidate']['group'], score=r['rank']['score'],
                         median_annual_closed=r['rank']['median_closed_net'], eligible=r['rank']['eligible']) for r in result['training']]
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            fig = go.Figure(go.Bar(x=[r['candidate'] for r in rows], y=[r['score'] for r in rows]))
            fig.add_hline(y=result['baseline_training']['rank']['score'], line_dash='dash', annotation_text='Same-budget v1.11 replica')
            fig.update_layout(template='plotly_dark', title='Penalized annual training score at 8bp fills', height=380)
            st.plotly_chart(fig, width='stretch', key='robust_structure_training')
        else:
            st.caption('Twelve predefined variants: 20/55-candle channels, EMA200 direction, two exit profiles. No tuned volume or trend-distance threshold. Training 2020-2023, selection 2024; seven-day gaps.')
            rows = [dict(candidate=r['candidate']['id'], score=r['rank']['score'], eligible=r['rank']['eligible']) for r in result['training']]
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            fig = go.Figure(go.Bar(x=[r['candidate'] for r in rows], y=[r['score'] for r in rows]))
            fig.update_layout(template='plotly_dark', title='Penalized annual training score at 8bp fills', height=380)
            st.plotly_chart(fig, width='stretch', key='channel_timeframes_training')
        selected = result['selected']
        if selected is None:
            st.warning('No candidate passed the fixed selection gates. No version was promoted.')
            continue
        st.write('Selected before later diagnostics:', selected['id'])
        full = [r for r in result['audit'] if r['period'] == 'full_development']
        st.dataframe(pd.DataFrame([dict(strategy=r['strategy'], actual_fill_bp=r['fill_bps'], net=pnl(r['metrics']),
                                        closed_net=r['closed_net'], drawdown=r['metrics']['max_intrabar_drawdown'],
                                        entries=r['metrics']['entries']) for r in full]), hide_index=True)
        challenger_name = 'filtered' if name == 'trade_quality_round1' else 'challenger'
        prefix = out/'audit/full_development'/f'{challenger_name}_fill8'
        curve = pd.read_parquet(prefix/'equity.parquet')
        st.plotly_chart(performance_chart(curve, 50000., version=selected['id']), width='stretch', key=f'{name}_equity')
        st.plotly_chart(monthly_chart(curve, 50000.), width='stretch', key=f'{name}_monthly')

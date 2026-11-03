"""Visible generalization status, historical diagnostics and frozen data tests."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from .generalization_policy import policy,frozen_profile,forward_status


def render(root):
    p=policy(root)
    st.subheader('Generalization and overfitting controls')
    if p is None:st.info('No generalization protocol has been initialized.');return
    st.warning('Future usability is unproven. Inspected historical results cannot be turned into an untouched holdout by resplitting them.')
    st.write('Forward status:',forward_status(root))
    try:frozen_profile(root)
    except (ValueError,OSError) as exc:st.error(str(exc));return
    st.write(f"Frozen strategy: **{p['frozen_version']}** · {p['historical_search_slots_at_freeze']} logged historical search slots")
    st.write(f"Locked future window: **{p['future_start_utc']} → {p['future_end_exclusive_utc']}**")
    st.caption('Whole-history profit optimization and historical-only version promotion are disabled. Fixed-rule replay and transfer diagnostics remain available.')
    st.caption(f"Final evaluation needs at least {p['minimum_closed_trades']} closed trades, positive main/4bp/8bp stressed net, no margin calls, ≤{p['maximum_intrabar_drawdown']:.0%} drawdown and a positive lower seven-day-block confidence bound. A passing test still does not certify future profitability or funded-account execution.")
    final=root/'artifacts/generalization/forward/forward_certificate.json'
    if final.exists() and forward_status(root) not in {'premature_certificate_rejected','invalidated_certificate'}:
        certificate=json.loads(final.read_text())
        st.json(certificate)
        curve_path=final.parent/'equity.parquet'
        if curve_path.exists():
            from .independent_visuals import performance_chart,monthly_chart
            curve=pd.read_parquet(curve_path)
            fig=performance_chart(curve,50000.);fig.update_layout(title=f"Locked forward ETH · {p['frozen_version']} · Equity and drawdown")
            st.plotly_chart(fig,width='stretch',key='locked_forward_equity')
            st.plotly_chart(monthly_chart(curve,50000.),width='stretch',key='locked_forward_monthly')
    else:st.info('Locked future evaluation: pending. There is no forward-validation certificate yet.')
    from .cost_reserve_display import render as show_cost_reserve
    show_cost_reserve(root)
    from .strategy_lab_display import render as show_strategy_lab
    show_strategy_lab(root)
    from .additional_labs_display import render as show_additional_labs
    show_additional_labs(root)
    from .forward_collection import collect,latest
    st.subheader('Blinded forward-data collection')
    st.caption('Collect completed UTC source days and coverage only. No strategy signals, trades or returns are calculated. This is a manual collector; no background schedule is running.')
    if st.button('Collect completed ETH days without evaluating returns'):
        try:
            with st.spinner('Verifying source checksums and retaining data snapshots…'):collect(root)
        except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
    try:collection=latest(root)
    except (ValueError,OSError) as exc:st.error(str(exc));collection=None
    if collection:
        st.write('Collection status:',collection['state'])
        a,b,c=st.columns(3)
        a.metric('Verified five-minute source rows',f"{collection['rows']:,}")
        b.metric('Collected forward-test rows',f"{collection['forward_rows']:,}")
        c.metric('Missing completed source intervals',f"{collection.get('missing_bars',0):,}")
        st.caption(f"Coverage checked as of {collection['as_of_utc']}. Completed days through {collection['completed_data_end_exclusive_utc']} exclusive. First-seen daily sources and every retained snapshot are hash-pinned.")
        if collection.get('gaps'):
            st.warning('The required data coverage is incomplete. No source gap is filled or replaced. Final evaluation cannot pass with missing required candles.')
            st.dataframe(pd.DataFrame(collection['gaps']),hide_index=True)
        with st.expander('Forward collection provenance'):
            st.json(collection)
    default_path=root/collection['snapshot_path'] if collection and collection.get('snapshot_path') else root/'data/generalization/forward_eth.parquet'
    future_path=st.text_input('Forward ETH Parquet path',str(default_path))
    complete=pd.Timestamp.now(tz='UTC')>=pd.Timestamp(p['future_end_exclusive_utc'])
    if st.button('Run final locked forward evaluation',disabled=not complete):
        from .forward_validation import evaluate
        try:st.json(evaluate(Path(future_path),root))
        except (ValueError,OSError) as exc:st.error(str(exc))
    path=root/'artifacts/generalization/retrospective/results.json'
    if path.exists():
        result=json.loads(path.read_text())
        st.subheader('Retrospective walk-forward diagnostic')
        st.caption('The saved candidate pool was already selected on this history. These outer folds are retrospective; this is not fresh validation. Choices use only preceding inner blocks, purged outcomes and a seven-day gap.')
        st.dataframe(pd.DataFrame([dict(start=r['test_start'],end=r['test_end'],chosen=r['chosen'] or 'No trade',**r['outcome']) for r in result['folds']]),hide_index=True)
        adjusted=result['multiplicity']['bonferroni_adjusted_upper95']
        st.metric('Adjusted historical p-value upper bound',f'{adjusted:.4f}')
        st.caption('Uses a lower-bound logged search count and bootstrap assumptions. This is not a probability of overfitting or a forward-validity certificate.')
        st.write('Multiple-testing diagnostic',result['multiplicity'])
        st.write('Parameter-neighborhood stability',result['parameter_stability'])
    from .external_validation import render as show_external
    show_external('eth2017',root)
    from .kraken_validation import render as show_kraken
    show_kraken(root)
    from .coinbase_validation import render as show_coinbase
    show_coinbase('ETH-USD',root)

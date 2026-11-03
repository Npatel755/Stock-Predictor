"""Local-only Streamlit dashboard. Launch from the repository root."""
from __future__ import annotations

from pathlib import Path
from dataclasses import asdict
import json
import sys

# Streamlit executes this file as a script rather than a Python module.
REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backtesting.config import StrategyConfig
from backtesting.date_ranges import default_dates, select_dates
from backtesting.engine import backtest
from backtesting.market_data import download_history, load_history
from backtesting.paths import PARQUET, RUNS, ROOT
from backtesting.reporting import chart, save_result, safe_value
from backtesting.profiles import attach_research_profile
from backtesting.versioned_profiles import load_profile

st.set_page_config(page_title="DVS ETH Research", page_icon="◇", layout="wide")
st.title("DVS ETH · Futures research")
st.caption("Five-minute Binance ETHUSDT perpetuals · local backtests · no exchange execution")
st.info("Choose v1.5 for the volume-filter strategy with a $6,000 historical baseline. Earlier versions remain available. TradingView parity remains unverified.")


@st.cache_data(show_spinner=False)
def cached_data(path: str, modified: float):
    return load_history(Path(path))


def use_complete_range(revision_key):
    # Recreate the date widget with its range default rather than assigning a
    # widget value after construction or changing its single-date/range type.
    st.session_state[revision_key] = st.session_state.get(revision_key, 0) + 1


def replay_independent(selected_bars, rule, config, metadata, version='v1.3'):
    from backtesting.alternative_strategies import simulate
    from backtesting.independent_visuals import equity_curve
    from backtesting.optimize import write_json
    filters = metadata.get('entry_filters')
    if filters:
        from backtesting.regime_filters import RegimeFilter, apply_filter, prepare_features
        signals = apply_filter(prepare_features(selected_bars, rule), RegimeFilter(**filters))
    else:
        signals = None
    metrics, trades, events = simulate(selected_bars, rule, config, signals=signals)
    period = [str(selected_bars.timestamp.min()), str(selected_bars.available_at.max())]
    location = ROOT / f"artifacts/independent/{version.replace('.', '_')}_dashboard"
    location.mkdir(parents=True, exist_ok=True)
    write_json(location / "results.json", {"metrics": metrics, "rule": asdict(rule), "execution": asdict(config),
                                           "profile": metadata, "period": period, "filters": filters})
    trades.to_csv(location / "trades.csv", index=False)
    events.to_csv(location / "events.csv", index=False)
    curve = equity_curve(selected_bars, events, config)
    if abs(curve.equity.iloc[-1]-metrics['final_equity']) > 1e-6:
        raise ValueError("Visual equity does not reconcile with the broker result")
    curve.to_parquet(location / "equity.parquet", index=False)
    st.session_state[f"independent_{version.replace('.', '')}_result"] = {"metrics": metrics, "trades": trades, "events": events, "period": period,
                                                 "equity": curve, "rule": asdict(rule), "execution": asdict(config),
                                                 "filters": filters,
                                                 "profile_sha256": metadata['configuration_sha256']}


def display_independent_result(key, version='v1.3'):
    result_key = f"independent_{version.replace('.', '')}_result"
    if result_key not in st.session_state:
        st.write(f"Choose UTC dates and run {version}. Results will appear here.")
        return
    replay = st.session_state[result_key]
    m = replay["metrics"]
    st.subheader(f"Completed run · Research · ETH {version}")
    st.caption(f"Completed {version} replay: {replay['period'][0]} to {replay['period'][1]} exclusive. Sidebar changes require another run.")
    current_rule, current_cfg, current_meta, _ = load_profile(ROOT, version=version)
    if (replay.get('rule', asdict(current_rule)) != asdict(current_rule)
            or replay.get('execution', asdict(current_cfg)) != asdict(current_cfg)
            or replay.get('filters') != current_meta.get('entry_filters')):
        st.warning(f"The saved {version} strategy has been refined since this replay. Run {version} again to see the updated strategy's results; the charts below show your previous run.")
    a, b, c = st.columns(3)
    a.metric("Net P&L", f"${m['final_equity'] - m['initial_capital']:,.2f}")
    b.metric("Entries", m["entries"])
    c.metric("Running-peak drawdown", f"{m['max_intrabar_drawdown']:.2%}")
    if current_meta.get('baseline_net_usd') is not None:
        expected_period = [pd.Timestamp(t, tz='UTC') for t in current_meta['baseline_period']]
        actual_period = [pd.Timestamp(t) for t in replay['period']]
        if actual_period == expected_period:
            gain = m['final_equity']-m['initial_capital']-current_meta['baseline_net_usd']
            st.metric('Above requested $6,000 baseline', f'${gain:,.2f}')
        else:
            st.caption('The $6,000 baseline applies to January 1, 2023 through October 27, 2026 UTC at $100 risk. This replay uses different dates.')
    from backtesting.independent_visuals import equity_curve, performance_chart, monthly_chart, trade_chart
    replay_bars = bars[(bars.timestamp >= pd.Timestamp(replay['period'][0])) &
                       (bars.timestamp < pd.Timestamp(replay['period'][1]))]
    # Upgrade an existing browser result directly from its fill/financing events.
    # Changing the sidebar dates must not change a previously completed chart.
    if "equity" not in replay:
        rule, config, _, _ = load_profile(ROOT, version=version)
        curve = equity_curve(replay_bars, replay["events"], config)
        if abs(curve.equity.iloc[-1]-m['final_equity']) > 1e-6:
            st.warning(f"This older result cannot be reconciled for charting. Run {version} again to refresh it.")
            return
        replay.update(equity=curve, rule=asdict(rule), execution=asdict(config))
    curve = replay["equity"]
    equity_figure = performance_chart(curve, m["initial_capital"])
    equity_figure.update_layout(title=f"ETH {version} · Equity and drawdown")
    st.plotly_chart(equity_figure, width="stretch", key=f"{version}_equity_{key}")
    st.caption("The chart marks open positions at each candle close and includes actual simulated fees and financing. Its close-based drawdown differs from the intrabar drawdown metric above.")
    monthly, trade_view, ledger_view = st.tabs(["Monthly P&L", "Trade chart", "Trade ledger"])
    with monthly:
        st.plotly_chart(monthly_chart(curve, m["initial_capital"]), width="stretch", key=f"{version}_monthly_{key}")
    with trade_view:
        trades = replay["trades"]
        if len(trades):
            chosen = st.selectbox(f"Inspect {version} trade", list(range(len(trades))), key=f"{version}_trade_{key}",
                                  format_func=lambda i: f"{i+1} · {trades.iloc[i].direction} · {trades.iloc[i].entry_bar_open} · ${trades.iloc[i].net_pnl:,.2f}")
            fig, resolution = trade_chart(replay_bars, trades.iloc[chosen], replay["events"], replay["rule"]["reward_r"])
            st.plotly_chart(fig, width="stretch", key=f"{version}_price_{key}")
            st.caption(f"{resolution} candles; fill markers use candle-open timestamps. Intrabar exit times are bounds. Stops move only after completed candles.")
        else:
            st.info("No closed trades in this replay yet.")
    with ledger_view:
        st.dataframe(replay["trades"], width="stretch", hide_index=True)
        st.download_button(f"Download {version} replay trades", replay["trades"].to_csv(index=False), f"eth_{version.replace('.', '_')}_trades.csv", "text/csv", key=f"{version}_trades_{key}")
    if m["open_position"]:
        st.json(safe_value(m["open_position"]))


with st.sidebar:
    st.header("Historical data")
    if st.button("Update public archives", help="Downloads completed UTC days from Binance; no account credentials"):
        with st.spinner("Checking public archive cache and importing completed days…"):
            try:
                download_history()
                st.cache_data.clear()
                st.success("Data import complete")
            except Exception as exc:
                st.error(str(exc))
    if not PARQUET.exists():
        st.warning("Import the historical dataset to begin.")
        st.stop()
    try:
        bars, quality = cached_data(str(PARQUET), PARQUET.stat().st_mtime)
    except Exception as exc:
        st.error(str(exc))
        st.stop()
    profile_path = ROOT / "configs/dvs_eth_v1_2.json"
    version_options = ["v1.1", "v1.2", "v1"] if profile_path.exists() else ["v1.1", "v1"]
    for version in ['v1.3', 'v1.4', 'v1.5']:
        if (ROOT / f"configs/eth_strategy_{version.replace('.', '_')}.json").exists():
            version_options.insert(-1, version)
    selected_version = st.selectbox("Pine strategy version", version_options, key="pine_strategy_version")
    independent_selected = selected_version in {'v1.3', 'v1.4', 'v1.5'}
    independent_version = selected_version if independent_selected else next((v for v in ['v1.5', 'v1.4', 'v1.3'] if v in version_options), 'v1.3')
    saved_profile = None
    if independent_selected:
        try:
            selected_rule, selected_independent_cfg, selected_independent_meta, _ = load_profile(ROOT, version=selected_version)
            saved_profile = asdict(selected_independent_cfg)
            strategy_version = selected_independent_cfg.strategy_version
        except (ValueError, KeyError, OSError) as exc:
            st.error(f"Could not load saved {selected_version}: {exc}")
            st.stop()
    elif selected_version == "v1.2":
        saved_profile = json.loads(profile_path.read_text(encoding="utf-8"))
        strategy_version = saved_profile["strategy_version"]
    else:
        strategy_version = selected_version
    mode_label = st.radio("Mode", ["A · TradingView parity candidate", "B · Research"],
                          index=1 if saved_profile else 0, disabled=saved_profile is not None,
                          key=f"dvs_{selected_version.replace('.', '_')}_mode" if saved_profile else "dvs_manual_mode")
    mode = "parity" if mode_label.startswith("A") else "research"
    if independent_selected:
        st.caption(f"{selected_version} loads the saved independent hourly channel strategy in Research mode. Historical research only; TradingView parity is unverified.")
    elif saved_profile:
        st.caption("v1.2 uses its saved Research configuration automatically. Choose v1.1 or v1 to use parity mode or manual settings.")
        st.caption("Historical research only: earlier-regime and slippage failures are retained in the reports.")
        profile_metadata = profile_path.with_name("dvs_eth_v1_2.metadata.json")
        if profile_metadata.exists() and not json.loads(profile_metadata.read_text(encoding="utf-8")).get("passed_predeclared_validation_gate", False):
            st.caption("v1.2 has not passed the strict validation gate. Results and failed checks are retained in Strategy research.")
    try:
        requires_complete = mode == "parity" or (saved_profile is not None and saved_profile["gap_policy"] == "reject")
        suggested_dates = default_dates(bars, "parity" if requires_complete else mode)
    except ValueError as exc:
        st.warning(str(exc))
        st.stop()
    range_label = selected_version.replace(".", "_") if saved_profile else mode
    revision_key = f"dvs_period_revision_{range_label}"
    period_key = f"dvs_period_{range_label}_{st.session_state.get(revision_key, 0)}"
    period = st.date_input("Backtest UTC dates", value=suggested_dates, key=period_key,
                           min_value=bars.timestamp.min().date(), max_value=bars.timestamp.max().date())
    if requires_complete:
        range_name = "Complete data range" if independent_selected else "Complete parity range"
        st.caption(f"{range_name}: {suggested_dates[0]} through {suggested_dates[1]} UTC. Later candles remain available in Research mode.")
        st.button("Use complete parity range", on_click=use_complete_range, args=(revision_key,))
    selected_bars, selected_quality, selection_error = None, None, None
    try:
        selected_bars, selected_quality = select_dates(bars, period)
    except ValueError as exc:
        selection_error = str(exc)
    values = saved_profile or {}
    risk = st.number_input("Planned risk / trade ($)", min_value=1., value=float(values.get("risk_usd", 100.)), step=25., disabled=saved_profile is not None)
    reward = st.number_input("Reward / risk", min_value=1., value=float(selected_rule.reward_r if independent_selected else values.get("reward_r", 2.)), step=.25, disabled=saved_profile is not None)
    max_daily = st.number_input("Personal daily loss gate ($)", min_value=1., value=float(values.get("max_daily_loss", 300.)), step=50., disabled=saved_profile is not None)
    maximum_entries = st.number_input("Daily entry limit", min_value=1, value=int(values.get("max_trades_day", 3)), step=1, disabled=saved_profile is not None)
    research = {}
    if mode == "research" and saved_profile is None:
        segment = st.checkbox("Split at data gaps; close at last known price", value=True)
        commission = st.number_input("Commission (basis points / side)", min_value=0., value=4., step=.5)
        slip = st.number_input("Extra slippage (basis points)", min_value=0., value=2., step=.5)
        next_open = st.checkbox("Enter on next bar open", value=True)
        pessimistic = st.checkbox("Stop first if both stop and target are touched", value=True)
        swap = st.number_input("Daily financing (basis points; six snapshots)", min_value=0., value=3.3, step=.1)
        research = dict(gap_policy="segment" if segment else "reject", commission_bps=commission,
                        slippage_bps=slip, entry_timing="next_open" if next_open else "signal_close",
                        intrabar_policy="stop_first" if pessimistic else "tradingview", swap_daily_bps=swap)
    elif saved_profile:
        research = {"gap_policy": saved_profile["gap_policy"]}
        st.caption(f"The saved {selected_version} preset uses fixed experimental settings.")
        with st.expander(f"{selected_version} configuration"):
            st.json({"rule": asdict(selected_rule), "execution": saved_profile, "filters": selected_independent_meta.get('entry_filters')} if independent_selected else saved_profile)
    else:
        pine_commission = "0.04%" if strategy_version == "v1.1" else "0.05%"
        st.caption(f"Pine {strategy_version} properties: {pine_commission} per side, 2 ticks slippage, 20% margin, close-of-bar entry. Gap ranges are rejected.")
    gap_blocked = selected_quality is not None and selected_quality["missing_bars"] > 0 and research.get("gap_policy", "reject") == "reject"
    if selection_error:
        st.warning(selection_error)
    elif gap_blocked:
        st.warning(f"This range contains {selected_quality['missing_bars']:,} missing candles. Choose the complete parity range or use Research with gap segmentation.")
    run = st.button(f"Run {selected_version} backtest" if independent_selected else "Run DVS backtest", type="primary", width="stretch", disabled=bool(selection_error or gap_blocked))

quality_tab, strategy_tab, models_tab, research_tab, independent_tab = st.tabs(["Data quality", f"{selected_version} backtest" if independent_selected else "DVS backtest", "ML experiments", "Strategy research", f"ETH {independent_version}"])
with quality_tab:
    display_quality = selected_quality or quality
    st.subheader("Selected backtest range")
    a, b, c, d = st.columns(4)
    a.metric("Five-minute candles", f"{display_quality['rows']:,}")
    b.metric("Missing candles", f"{display_quality['missing_bars']:,}")
    c.metric("Duplicates removed", display_quality["true_duplicates_removed"])
    d.metric("Zero-volume candles", display_quality["zero_volume_bars"])
    st.write(f"Selected coverage: {display_quality['first_open_utc']} → {display_quality['last_close_exclusive_utc']}")
    st.caption("Exchange open times remain unchanged. Exchange close times and the exclusive information-availability boundary are stored separately.")
    if display_quality["gaps"]:
        st.warning("The selected range contains unavailable candles. No candles were fabricated or forward-filled.")
        st.dataframe(pd.DataFrame(display_quality["gaps"]), width="stretch", hide_index=True)
    elif selected_quality is not None:
        st.success("The selected range has complete five-minute candles and is ready to backtest.")
    st.dataframe((selected_bars if selected_bars is not None else bars).tail(12), width="stretch", hide_index=True)
    with st.expander("Archive manifest and checksum audit"):
        st.write(f"All downloaded history: {quality['first_open_utc']} → {quality['last_close_exclusive_utc']}")
        if quality["gaps"]:
            st.caption("Unavailable periods across the original download request, including dates outside the selected range:")
            st.dataframe(pd.DataFrame(quality["gaps"]), width="stretch", hide_index=True)
        st.json(quality)

if run and independent_selected:
    with st.spinner(f"Replaying independent {selected_version} hourly signals on five-minute candles…"):
        try:
            replay_independent(selected_bars, selected_rule, selected_independent_cfg, selected_independent_meta, version=selected_version)
        except Exception as exc:
            st.error(str(exc))
elif run:
    if not isinstance(period, (tuple, list)) or len(period) != 2:
        st.error("Select a start and end date.")
    else:
        with st.spinner("Replaying DVS signals and order events…"):
            try:
                cfg = (StrategyConfig(**saved_profile) if saved_profile else
                       StrategyConfig(mode=mode, strategy_version=strategy_version, risk_usd=float(risk), reward_r=float(reward),
                                      max_daily_loss=float(max_daily), max_trades_day=int(maximum_entries), **research))
                result = backtest(selected_bars, cfg, quality=selected_quality)
                if saved_profile:
                    attach_research_profile(result, profile_path)
                location = RUNS / ("dashboard_v1_2" if saved_profile else f"dashboard_{mode}_{strategy_version.replace('.', '_')}")
                save_result(result, location, PARQUET)
                st.session_state["dvs_result"] = result
                st.session_state["dvs_location"] = str(location)
            except Exception as exc:
                st.error(str(exc))

# Existing browser sessions may hold a result from the pre-versioned engine.
# Keep its disk artifact, but do not render it as a new v1.1 result.
stored_result = st.session_state.get("dvs_result")
if stored_result is not None and ("strategy_version" not in stored_result.config or
                                   "max_closed_equity_drawdown_usd" not in stored_result.metrics):
    del st.session_state["dvs_result"]
    st.session_state.pop("dvs_location", None)
    st.info("The strategy implementation has been updated. Run the selected Pine version to refresh the displayed result.")

with strategy_tab:
    if independent_selected:
        display_independent_result("main", version=selected_version)
    elif "dvs_result" not in st.session_state:
        st.write("Choose a UTC date range and run the strategy. Indicators initialize from that range's first candle.")
        st.caption("Parity mode requires a range without the missing periods listed under Data quality.")
    else:
        result = st.session_state["dvs_result"]
        m = result.metrics
        displayed_version = result.provenance.get("research_profile", result.config["strategy_version"])
        st.subheader(f"Completed run · {result.config['mode']} · {displayed_version}")
        st.caption(f"Saved to {st.session_state['dvs_location']}. Sidebar changes take effect only after another run.")
        cols = st.columns(4)
        cols[0].metric("Final equity", f"${m['final_equity']:,.2f}")
        cols[1].metric("Net return", f"{m['net_return']:.2%}")
        cols[2].metric("Entries", m["entries"])
        cols[3].metric("Drawdown from closed-equity peak", f"${m['max_closed_equity_drawdown_usd']:,.2f}",
                       help="TradingView-style anchor to prior closed-trade equity; still unverified against an export.")
        st.caption(f"Drawdown from closed-equity peak: {m['max_closed_equity_drawdown_fraction']:.2%}. "
                   f"Drawdown from running unrealized equity peak: {m['max_intrabar_drawdown']:.2%}. These are different measures.")
        st.plotly_chart(chart(result), width="stretch")
        trade_tab, signal_tab, settings_tab, compare_tab = st.tabs(["Trade ledger", "Signal audit", "Run assumptions", "TradingView reconciliation"])
        with trade_tab:
            st.dataframe(result.trades, width="stretch", hide_index=True)
            st.download_button("Download trade CSV", result.trades.to_csv(index=False), "dvs_trades.csv", "text/csv")
            if len(result.trades):
                selected = st.selectbox("Inspect trade leg", list(range(len(result.trades))),
                                        format_func=lambda i: f"{i + 1} · {result.trades.iloc[i].direction} · {result.trades.iloc[i].entry_bar_open}")
                trade = result.trades.iloc[selected]
                window = bars[(bars.timestamp >= trade.entry_bar_open - pd.Timedelta(hours=2)) &
                              (bars.timestamp <= trade.exit_bar_open + pd.Timedelta(hours=2))]
                if len(window) > 2000:
                    st.caption("Showing the first 2,000 candles around this trade; the full ledger remains available.")
                    window = window.iloc[:2000]
                price_chart = go.Figure(go.Candlestick(x=window.timestamp, open=window.open, high=window.high,
                                                      low=window.low, close=window.close, name="ETHUSDT perpetual"))
                price_chart.add_hline(y=float(trade.stop), line_dash="dash", line_color="#fb7185", annotation_text="Stop")
                price_chart.add_hline(y=float(trade.target), line_dash="dash", line_color="#34d399", annotation_text="Target")
                price_chart.add_trace(go.Scatter(x=[trade.entry_bar_open, trade.exit_bar_open],
                                                 y=[trade.entry_price, trade.exit_price], mode="markers",
                                                 marker=dict(size=11, color=["#38bdf8", "#fbbf24"]), name="Entry / exit"))
                price_chart.update_layout(template="plotly_dark", height=430, xaxis_rangeslider_visible=False,
                                           title="Trade audit · candle-open labels; simulated fill prices")
                st.plotly_chart(price_chart, width="stretch")
            if m["open_position"]:
                st.write("Open position at final mark")
                st.json(safe_value(m["open_position"]))
        with signal_tab:
            show_events = result.signals[result.signals.long_break | result.signals.short_break | result.signals.entered | result.signals.failed]
            st.dataframe(show_events, width="stretch", hide_index=True)
            st.dataframe(result.events, width="stretch", hide_index=True)
        with settings_tab:
            st.json({"config": result.config, "provenance": result.provenance})
            st.write("The Pine daily loss rule gates new entries; it does not flatten positions. It is not a funded-account rule simulation.")
        with compare_tab:
            st.write("Upload a normalized TradingView trade export using columns entry_bar_open, exit_bar_open, direction, quantity, entry_price, exit_price. Timestamps must include their UTC offset.")
            uploaded = st.file_uploader("TradingView comparison CSV", type="csv")
            if uploaded:
                from backtesting.reconcile import compare_trades
                try:
                    comparison = compare_trades(result.trades, pd.read_csv(uploaded))
                    st.json(comparison["summary"])
                    st.dataframe(comparison["differences"], width="stretch", hide_index=True)
                    st.caption("Matching normalized rows is evidence for that period only; it does not automatically certify all Pine behavior.")
                except Exception as exc:
                    st.error(str(exc))

with models_tab:
    st.write("Direction classifiers are separate experiments; they are not the DVS strategy.")
    for label, path in [("ETH perpetual futures", "ethusd_model_comparison.md"),
                        ("Massive ETH/USD spot proxy", "ethusd_massive_proxy_comparison.md")]:
        with st.expander(label):
            report = Path(__file__).parent / "reports" / path
            st.markdown(report.read_text(encoding="utf-8") if report.exists() else "No saved model benchmark.")

with research_tab:
    st.subheader("Strategy improvement experiments")
    st.write("Candidates use fixed $100 planned risk, next-open execution, 0.04% fees per side, two ticks plus two basis points assumed slippage, and financing. Parity mode stays separate.")
    from backtesting.research_inventory import search_manifests
    runs = search_manifests(ROOT)
    if not runs:
        st.caption("No experiment checkpoints have been saved yet.")
    else:
        chosen_run = st.selectbox("Research experiment", [p.parent.name for p in runs])
        if st.button("Refresh research results"):
            st.rerun()
        try:
            from backtesting.research_display import search_status, overview_rows, training_overview
            status = search_status(ROOT / "artifacts/optimization" / chosen_run)
            plan, training, validation, summary = [status[k] for k in ["manifest", "training", "validation", "summary"]]
            historical_profit_search = plan.get("historical_profit_selection", False) or plan.get("name") == "Explicit historical net-profit improvement"
            st.progress(min(1., len(training) / plan["candidate_count"]), text=f"Recorded training: {len(training)} / {plan['candidate_count']} candidates")
            st.caption(f"Validation checkpoints: {len(validation)}. Checkpoints show saved work, not whether a process is still running.")
            training_period = plan.get("selection_window", plan.get("training", plan.get("train", [plan.get("start", "2023-01-01"), plan.get("end_exclusive", "2025-01-01")])))
            if historical_profit_search:
                st.write(f"Profit-selection window: {training_period}. The entire inspected period, including 2026, selects parameters. Additional checks reuse 2025 halves, earlier regimes and higher costs; they are not independent validation.")
            else:
                st.write(f"Training windows: {training_period}. Selection uses chronological 2025 halves. Historical data was previously inspected; this is not a fresh holdout.")
            if summary:
                selection = summary["selection"]
                candidate = selection["candidate"]
                gate = selection["passed_predeclared_validation_gate"]
                gate_label = "historical-profit checks" if selection.get('selection_is_historical_profit_optimization') else "predefined historical validation gate"
                st.write(f"Frozen selection: **{candidate['label']}**. Passed {gate_label}: **{gate}**.")
                if selection.get('selection_is_historical_profit_optimization'):
                    st.caption("The 2023–2026 period, including 2026, was used to select this candidate for higher historical net P&L. These results are not independent validation.")
                st.dataframe(pd.DataFrame(overview_rows(summary)), width="stretch", hide_index=True)
                st.json({"selection_checks": selection["validation"], "historical_replays" if historical_profit_search else "retrospective_audit": summary.get("audit", summary.get("evaluation"))}, expanded=False)
                independent = "rule" in candidate
                payload = {"rule": candidate["rule"], "execution": selection["execution_config"]} if independent else candidate["config"]
                if 'filters' in candidate:
                    payload['filters'] = candidate['filters']
                    st.caption("This is an entry-filter experiment. Saved v1.4 remains unchanged; these filters are not omitted when comparing results or exporting settings.")
                    preview = ROOT / 'reference/experimental/ETH_Volume_Research.pine'
                    preview_metadata = preview.with_suffix('.metadata.json')
                    if preview.exists() and preview_metadata.exists() and json.loads(preview_metadata.read_text(encoding='utf-8')).get('experiment') == chosen_run:
                        st.download_button('Download volume research Pine Editor text', preview.read_bytes(), 'ETH_Volume_Research.txt', 'text/plain')
                    if st.button('Backtest filtered research candidate on selected dates', disabled=bool(selection_error or selected_quality is None or selected_quality.get('missing_bars', 0))):
                        from backtesting.filtered_replay import replay as replay_filtered
                        try:
                            with st.spinner('Replaying the full strategy with the selected entry filters…'):
                                st.session_state[f'filtered_research_{chosen_run}'] = replay_filtered(selected_bars, candidate, selection['execution_config'], ROOT / 'artifacts/independent' / f'research_{chosen_run}')
                        except (ValueError, KeyError, OSError) as exc:
                            st.error(str(exc))
                    if f'filtered_research_{chosen_run}' in st.session_state:
                        from backtesting.filtered_replay import display as display_filtered
                        display_filtered(st.session_state[f'filtered_research_{chosen_run}'], bars, chosen_run)
                st.download_button("Download experimental configuration", json.dumps(payload, indent=2),
                                   "eth_independent_candidate.json" if independent else "dvs_research_candidate.json", "application/json")
                with st.expander("Selected research rules"):
                    st.json(payload)
                if independent:
                    st.caption("Independent hourly signals use five-minute execution. These saved replays are separate from DVS. Repeated historical selection does not establish future profitability; prior failures remain in the research record.")
                    for exported_version in ['v1.3', 'v1.4', 'v1.5']:
                        suffix = exported_version.replace('.', '_')
                        text_path = ROOT / f"downloads/ETH_Strategy_{suffix}.txt"
                        metadata_path = ROOT / f"configs/eth_strategy_{suffix}.metadata.json"
                        if text_path.exists() and metadata_path.exists() and json.loads(metadata_path.read_text(encoding="utf-8")).get("experiment") == chosen_run:
                            st.download_button(f"Download {exported_version} Pine Editor text", text_path.read_bytes(), f"ETH_Strategy_{suffix}.txt", "text/plain")
                st.caption("The experimental run uses the frozen configuration above and the selected UTC dates; the manual sidebar risk inputs do not change it.")
                if not independent and st.button("Backtest experimental candidate on selected dates", disabled=bool(selection_error)):
                    with st.spinner("Replaying the frozen research configuration…"):
                        cfg = StrategyConfig(**candidate["config"])
                        result = backtest(selected_bars, cfg, quality=selected_quality)
                        location = RUNS / f"experiment_{chosen_run}"
                        save_result(result, location, PARQUET)
                        st.session_state["dvs_result"] = result
                        st.session_state["dvs_location"] = str(location)
                        st.rerun()
            elif training:
                top = sorted(training, key=lambda r: -r["score"])[:10]
                st.caption("Provisional historical-profit leaders only. Selection waits for the fixed cost/regime checks." if historical_profit_search else "Provisional training leaders only. Selection waits for chronological validation.")
                st.dataframe(pd.DataFrame([training_overview(r) for r in top]),
                             width="stretch", hide_index=True)
        except (ValueError, KeyError, OSError) as exc:
            st.warning(f"Could not read this experiment: {exc}")

with independent_tab:
    st.subheader(f"ETH {independent_version} · Independent hourly channel breakout")
    try:
        rule, independent_cfg, independent_meta, pine_path = load_profile(ROOT, version=independent_version)
        st.write(f"This alternative uses a {rule.lookback}-hour channel, {rule.slow}-hour EMA filter, {rule.stop_atr:g} ATR initial stop, {rule.reward_r:g}R target and {rule.trail_atr:g} ATR trailing stop. Signals confirm hourly; execution uses five-minute candles.")
        if independent_meta.get('entry_filters'):
            st.write(f"Entry volume filter: completed-hour volume must be at least {independent_meta['entry_filters']['min_rvol']:g} times the mean of the preceding 20 completed hours.")
            st.caption('Requested baseline: $6,000 net on the original 2023-2026 perpetual period at unchanged $100 risk. Additional spot data is a separate transfer test and does not inflate that comparison.')
        st.caption("v1.2 remains a separate DVS strategy. Reused historical data is not independent forward validation. Pine compilation and trade matching remain unverified.")
        if independent_meta.get('selection_is_historical_profit_optimization'):
            st.caption(independent_meta['selection_note'])
        st.download_button(f"Download ETH {independent_version} text for Pine Editor", pine_path.read_bytes(), f"ETH_Strategy_{independent_version.replace('.', '_')}.txt", "text/plain")
        with st.expander(f"{independent_version} saved rules and execution assumptions"):
            st.json({"rule": asdict(rule), "execution": asdict(independent_cfg), "metadata": independent_meta})
        st.caption(f"Replay uses the UTC dates selected in the sidebar and the saved {independent_version} settings. DVS risk/version controls do not alter this profile. Indicators initialize at the selected start; allow at least {rule.slow} hours for warm-up. Missing candle ranges are rejected.")
        if st.button(f"Run independent {independent_version} on selected dates", disabled=bool(selection_error or selected_quality is None or selected_quality.get("missing_bars", 0))):
            with st.spinner("Replaying hourly channel signals on five-minute candles…"):
                replay_independent(selected_bars, rule, independent_cfg, independent_meta, version=independent_version)
                if independent_selected:
                    st.rerun()
        if not independent_selected:
            display_independent_result("independent_tab", version=independent_version)
        report = ROOT / f"{independent_version.upper().replace('.', '_')}.md"
        if report.exists():
            st.markdown(report.read_text(encoding="utf-8"))
    except (ValueError, KeyError, OSError) as exc:
        st.info(f"{independent_version} profile unavailable: {exc}")

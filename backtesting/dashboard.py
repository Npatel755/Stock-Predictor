"""Local-only Streamlit dashboard. Launch from the repository root."""
from __future__ import annotations

from pathlib import Path
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

st.set_page_config(page_title="DVS ETH Research", page_icon="◇", layout="wide")
st.title("DVS ETH · Futures research")
st.caption("Five-minute Binance ETHUSDT perpetuals · local backtests · no exchange execution")
st.info("DVS ETH v1.1 is the default source; the original v1 is also available. TradingView parity has not yet been verified against exported trades.")


@st.cache_data(show_spinner=False)
def cached_data(path: str, modified: float):
    return load_history(Path(path))


def use_complete_range(revision_key):
    # Recreate the date widget with its range default rather than assigning a
    # widget value after construction or changing its single-date/range type.
    st.session_state[revision_key] = st.session_state.get(revision_key, 0) + 1


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
    mode_label = st.radio("Mode", ["A · TradingView parity candidate", "B · Research"])
    mode = "parity" if mode_label.startswith("A") else "research"
    strategy_version = st.selectbox("Pine strategy version", ["v1.1", "v1"], key="pine_strategy_version")
    try:
        suggested_dates = default_dates(bars, mode)
    except ValueError as exc:
        st.warning(str(exc))
        st.stop()
    revision_key = f"dvs_period_revision_{mode}"
    period_key = f"dvs_period_{mode}_{st.session_state.get(revision_key, 0)}"
    period = st.date_input("Backtest UTC dates", value=suggested_dates, key=period_key,
                           min_value=bars.timestamp.min().date(), max_value=bars.timestamp.max().date())
    if mode == "parity":
        st.caption(f"Complete parity range: {suggested_dates[0]} through {suggested_dates[1]} UTC. Later candles remain available in Research mode.")
        st.button("Use complete parity range", on_click=use_complete_range, args=(revision_key,))
    selected_bars, selected_quality, selection_error = None, None, None
    try:
        selected_bars, selected_quality = select_dates(bars, period)
    except ValueError as exc:
        selection_error = str(exc)
    risk = st.number_input("Planned risk / trade ($)", min_value=1., value=100., step=25.)
    reward = st.number_input("Reward / risk", min_value=1., value=2., step=.25)
    max_daily = st.number_input("Personal daily loss gate ($)", min_value=1., value=300., step=50.)
    maximum_entries = st.number_input("Daily entry limit", min_value=1, value=3, step=1)
    research = {}
    if mode == "research":
        segment = st.checkbox("Split at data gaps; close at last known price", value=True)
        commission = st.number_input("Commission (basis points / side)", min_value=0., value=4., step=.5)
        slip = st.number_input("Extra slippage (basis points)", min_value=0., value=2., step=.5)
        next_open = st.checkbox("Enter on next bar open", value=True)
        pessimistic = st.checkbox("Stop first if both stop and target are touched", value=True)
        swap = st.number_input("Daily financing (basis points; six snapshots)", min_value=0., value=3.3, step=.1)
        research = dict(gap_policy="segment" if segment else "reject", commission_bps=commission,
                        slippage_bps=slip, entry_timing="next_open" if next_open else "signal_close",
                        intrabar_policy="stop_first" if pessimistic else "tradingview", swap_daily_bps=swap)
    else:
        pine_commission = "0.04%" if strategy_version == "v1.1" else "0.05%"
        st.caption(f"Pine {strategy_version} properties: {pine_commission} per side, 2 ticks slippage, 20% margin, close-of-bar entry. Gap ranges are rejected.")
    gap_blocked = selected_quality is not None and selected_quality["missing_bars"] > 0 and research.get("gap_policy", "reject") == "reject"
    if selection_error:
        st.warning(selection_error)
    elif gap_blocked:
        st.warning(f"This range contains {selected_quality['missing_bars']:,} missing candles. Choose the complete parity range or use Research with gap segmentation.")
    run = st.button("Run DVS backtest", type="primary", width="stretch", disabled=bool(selection_error or gap_blocked))

quality_tab, strategy_tab, models_tab, research_tab = st.tabs(["Data quality", "DVS backtest", "ML experiments", "Strategy research"])
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

if run:
    if not isinstance(period, (tuple, list)) or len(period) != 2:
        st.error("Select a start and end date.")
    else:
        with st.spinner("Replaying DVS signals and order events…"):
            try:
                cfg = StrategyConfig(mode=mode, strategy_version=strategy_version, risk_usd=float(risk), reward_r=float(reward),
                                      max_daily_loss=float(max_daily), max_trades_day=int(maximum_entries), **research)
                result = backtest(selected_bars, cfg, quality=selected_quality)
                location = RUNS / f"dashboard_{mode}_{strategy_version.replace('.', '_')}"
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
    if "dvs_result" not in st.session_state:
        st.write("Choose a UTC date range and run the strategy. Indicators initialize from that range's first candle.")
        st.caption("Parity mode requires a range without the missing periods listed under Data quality.")
    else:
        result = st.session_state["dvs_result"]
        m = result.metrics
        st.subheader(f"Completed run · {result.config['mode']} · {result.config['strategy_version']}")
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
    runs = sorted((ROOT / "artifacts/optimization").glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not runs:
        st.caption("No experiment checkpoints have been saved yet.")
    else:
        chosen_run = st.selectbox("Research experiment", [p.parent.name for p in runs])
        if st.button("Refresh research results"):
            st.rerun()
        try:
            from backtesting.search_results import search_status
            status = search_status(ROOT / "artifacts/optimization" / chosen_run)
            plan, training, validation, summary = [status[k] for k in ["manifest", "training", "validation", "summary"]]
            st.progress(min(1., len(training) / plan["candidate_count"]), text=f"Recorded training: {len(training)} / {plan['candidate_count']} candidates")
            st.caption(f"Validation checkpoints: {len(validation)}. Checkpoints show saved work, not whether a process is still running.")
            st.write("Search: 2023–2024 training, two chronological validation halves in 2025. The 2026 audit was previously inspected and is not a fresh holdout.")
            if summary:
                selection = summary["selection"]
                candidate = selection["candidate"]
                gate = selection["passed_predeclared_validation_gate"]
                st.write(f"Frozen selection: **{candidate['label']}**. Passed the predefined validation gate: **{gate}**.")
                rows = []
                for name, values in summary["full_history"].items():
                    rows.append({"scenario": name, "net_pnl": values["final_equity"] - values["initial_capital"],
                                 "trades": values["entries"], "intrabar_drawdown": values["max_intrabar_drawdown"]})
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
                st.json({"validation": selection["validation"], "retrospective_2026_audit": summary["audit"]}, expanded=False)
                st.download_button("Download experimental configuration", json.dumps(candidate["config"], indent=2),
                                   "dvs_research_candidate.json", "application/json")
                with st.expander("Selected research rules"):
                    st.json(candidate["config"])
                st.caption("The experimental run uses the frozen configuration above and the selected UTC dates; the manual sidebar risk inputs do not change it.")
                if st.button("Backtest experimental candidate on selected dates", disabled=bool(selection_error)):
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
                st.caption("Provisional training leaders only. Selection waits for chronological validation.")
                st.dataframe(pd.DataFrame([{"candidate": r["label"], "training_pnl": r["metrics"]["final_equity"] - 50000,
                                            "entries": r["metrics"]["entries"], "score": r["score"]} for r in top]),
                             width="stretch", hide_index=True)
        except (ValueError, KeyError, OSError) as exc:
            st.warning(f"Could not read this experiment: {exc}")

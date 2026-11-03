"""Local-only Streamlit dashboard. Launch from the repository root."""
from __future__ import annotations

from pathlib import Path
import sys

# Streamlit executes this file as a script rather than a Python module.
REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backtesting.config import StrategyConfig
from backtesting.engine import backtest
from backtesting.market_data import clean_candles, download_history, load_history, utc
from backtesting.paths import PARQUET, RUNS
from backtesting.reporting import chart, save_result, safe_value

st.set_page_config(page_title="DVS ETH Research", page_icon="◇", layout="wide")
st.title("DVS ETH · Futures research")
st.caption("Five-minute Binance ETHUSDT perpetuals · local backtests · no exchange execution")
st.info("The available source is DVS ETH v1. TradingView parity is a candidate implementation and has not been verified against exported trades.")


@st.cache_data(show_spinner=False)
def cached_data(path: str, modified: float):
    return load_history(Path(path))


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
    period = st.date_input("Backtest UTC dates", value=(bars.timestamp.min().date(), bars.timestamp.max().date()),
                           min_value=bars.timestamp.min().date(), max_value=bars.timestamp.max().date())
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
        st.caption("Pine-fixed properties: 0.05% per side, 2 ticks slippage, 20% margin, close-of-bar entry. Gap ranges are rejected.")
    run = st.button("Run DVS backtest", type="primary", width="stretch")

quality_tab, strategy_tab, models_tab = st.tabs(["Data quality", "DVS backtest", "ML experiments"])
with quality_tab:
    a, b, c, d = st.columns(4)
    a.metric("Five-minute candles", f"{quality['rows']:,}")
    b.metric("Missing candles", f"{quality['missing_bars']:,}")
    c.metric("Duplicates removed", quality["true_duplicates_removed"])
    d.metric("Zero-volume candles", quality["zero_volume_bars"])
    st.write(f"Available history: {quality['first_open_utc']} → {quality['last_close_exclusive_utc']}")
    st.caption("Exchange open times remain unchanged. Exchange close times and the exclusive information-availability boundary are stored separately.")
    if quality["gaps"]:
        st.warning("Some requested candles are unavailable. No candles were fabricated or forward-filled.")
        st.dataframe(pd.DataFrame(quality["gaps"]), width="stretch", hide_index=True)
    st.dataframe(bars.tail(12), width="stretch", hide_index=True)
    with st.expander("Archive manifest and checksum audit"):
        st.json(quality)

if run:
    if not isinstance(period, (tuple, list)) or len(period) != 2:
        st.error("Select a start and end date.")
    else:
        with st.spinner("Replaying DVS signals and order events…"):
            try:
                cfg = StrategyConfig(mode=mode, risk_usd=float(risk), reward_r=float(reward),
                                      max_daily_loss=float(max_daily), max_trades_day=int(maximum_entries), **research)
                start, end = utc(period[0]), utc(period[1]) + pd.Timedelta(days=1)
                subset = bars[(bars.timestamp >= start) & (bars.available_at <= end)]
                subset, run_quality = clean_candles(subset, start, end)
                result = backtest(subset, cfg, quality=run_quality)
                location = RUNS / f"dashboard_{mode}"
                save_result(result, location, PARQUET)
                st.session_state["dvs_result"] = result
                st.session_state["dvs_location"] = str(location)
            except Exception as exc:
                st.error(str(exc))

with strategy_tab:
    if "dvs_result" not in st.session_state:
        st.write("Choose a UTC date range and run the strategy. Indicators initialize from that range's first candle.")
        st.caption("Parity mode requires a range without the missing periods listed under Data quality.")
    else:
        result = st.session_state["dvs_result"]
        m = result.metrics
        st.subheader(f"Completed run · {result.config['mode']}")
        st.caption(f"Saved to {st.session_state['dvs_location']}. Sidebar changes take effect only after another run.")
        cols = st.columns(4)
        cols[0].metric("Final equity", f"${m['final_equity']:,.2f}")
        cols[1].metric("Net return", f"{m['net_return']:.2%}")
        cols[2].metric("Entries", m["entries"])
        cols[3].metric("Modeled intrabar drawdown", f"{m['max_intrabar_drawdown']:.2%}")
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

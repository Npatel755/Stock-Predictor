from datetime import date
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from backtesting.date_ranges import complete_windows, default_dates, select_dates
from backtesting.market_data import BAR, clean_candles


def history(days=5):
    times = pd.date_range("2025-01-01", periods=288 * days, freq="5min", tz="UTC")
    return pd.DataFrame({"timestamp": times, "exchange_close_time": times + BAR - pd.Timedelta(milliseconds=1),
                         "ticker": "BINANCE:ETHUSDT.P", "open": 2000., "high": 2001., "low": 1999.,
                         "close": 2000., "volume": 10.})


def test_parity_default_uses_complete_window_and_research_keeps_available_history():
    bars = history().drop(index=range(288, 576))  # missing January 2
    assert default_dates(bars, "parity") == (date(2025, 1, 3), date(2025, 1, 5))
    assert default_dates(bars, "research") == (date(2025, 1, 1), date(2025, 1, 5))
    selected, quality = select_dates(bars, default_dates(bars, "parity"))
    assert len(selected) == 3 * 288
    assert quality["missing_bars"] == 0
    assert select_dates(bars, default_dates(bars, "research"))[1]["missing_bars"] == 288


def test_partial_days_are_excluded_without_rounding_or_filling_candles():
    bars = history(3).iloc[20:-30]
    assert default_dates(bars, "parity") == (date(2025, 1, 2), date(2025, 1, 2))
    assert complete_windows(bars) == [(pd.Timestamp("2025-01-02", tz="UTC"), pd.Timestamp("2025-01-03", tz="UTC"))]


def test_one_missing_bar_disqualifies_its_utc_day():
    bars = history().drop(index=800)
    assert default_dates(bars, "parity") == (date(2025, 1, 4), date(2025, 1, 5))
    assert select_dates(bars, (date(2025, 1, 1), date(2025, 1, 5)))[1]["missing_bars"] == 1


def test_no_complete_day_or_unfinished_date_selection_has_clear_error():
    with pytest.raises(ValueError, match="No complete UTC day"):
        default_dates(history().iloc[:20], "parity")
    with pytest.raises(ValueError, match="Select a start and end date"):
        select_dates(history(), (date(2025, 1, 1),))


def test_dashboard_defaults_to_valid_parity_and_offers_recovery_for_invalid_selection(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import backtesting.paths as paths

    bars, quality = clean_candles(history().drop(index=range(288, 576)))
    path = tmp_path / "candles.parquet"
    bars.to_parquet(path, index=False)
    quality["parquet_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".quality.json").write_text(json.dumps(quality), encoding="utf-8")
    monkeypatch.setattr(paths, "PARQUET", path)
    monkeypatch.setattr(paths, "RUNS", tmp_path / "runs")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dashboard.py"), default_timeout=30).run()

    def button(label):
        return next(item for item in app.sidebar.button if item.label == label)

    assert not app.exception and not app.error
    assert app.sidebar.date_input[0].value == (date(2025, 1, 3), date(2025, 1, 5))
    assert next(item for item in app.metric if item.label == "Missing candles").value == "0"
    assert not button("Run DVS backtest").disabled
    app.sidebar.date_input[0].set_value((date(2025, 1, 1), date(2025, 1, 5))).run()
    assert app.sidebar.date_input[0].value == (date(2025, 1, 1), date(2025, 1, 5))
    assert button("Run DVS backtest").disabled
    assert not app.exception and not app.error
    button("Use complete parity range").click().run()
    assert app.sidebar.date_input[0].value == (date(2025, 1, 3), date(2025, 1, 5))
    assert not button("Run DVS backtest").disabled
    button("Run DVS backtest").click().run()
    assert not app.exception and not app.error
    assert app.session_state["dvs_result"].config["mode"] == "parity"
    assert app.session_state["dvs_result"].quality["missing_bars"] == 0


def test_dashboard_loads_with_old_cached_reporting_module_without_new_profile_helper(tmp_path, monkeypatch):
    """Reproduce a long-running Streamlit process predating the new helper."""
    from streamlit.testing.v1 import AppTest
    import backtesting.paths as paths
    import backtesting.reporting as reporting

    monkeypatch.delattr(reporting, "attach_research_profile")
    with pytest.raises(ImportError):
        exec("from backtesting.reporting import attach_research_profile", {})
    bars, quality = clean_candles(history())
    path = tmp_path / "candles.parquet"
    bars.to_parquet(path, index=False)
    quality["parquet_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".quality.json").write_text(json.dumps(quality), encoding="utf-8")
    monkeypatch.setattr(paths, "PARQUET", path)
    monkeypatch.setattr(paths, "RUNS", tmp_path / "runs")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dashboard.py"), default_timeout=30).run()
    assert not app.exception and not app.error
    next(button for button in app.sidebar.button if button.label == "Run DVS backtest").click().run()
    assert not app.exception and not app.error
    assert "dvs_result" in app.session_state

import pandas as pd
import pytest
from quant_futures.config import ResearchConfig, Costs
from quant_futures.data import canonical
from quant_futures.portfolio import run_portfolio


def inputs(bars, correlated=1, daily=300):
    datasets, configs, signals = {}, {}, {}
    for name in ("MES", "MNQ"):
        b = bars.iloc[:4].copy()
        b["instrument"], b["contract"] = name, name+"H26"
        b[["open", "close"]] = 6000.
        b["high"], b["low"] = 6000.25, 5999.75
        datasets[name] = canonical(b)
        cfg = ResearchConfig(instrument=name, costs=Costs(commission_per_side=0, exchange_per_side=0,
            regulatory_per_side=0, slippage_ticks=0, spread_ticks=0))
        configs[name] = cfg.model_copy(update={"risk": cfg.risk.model_copy(update={"max_correlated_contracts": correlated, "max_daily_loss": daily})})
        signals[name] = pd.Series([1]*4)
    return datasets, signals, configs


def test_shared_portfolio_enforces_correlated_cap_and_single_balance(bars):
    result = run_portfolio(*inputs(bars))
    assert result["curve"].quantity.max() == 1
    assert result["curve"].cash.iloc[0] == 50000
    assert any(e.get("reason") == "correlated_exposure" for e in result["events"])
    assert result["curve"].equity.iloc[-1] == pytest.approx(50000+result["trades"].net_pnl.sum())


def test_combined_loss_locks_both_sleeves(bars):
    datasets, signals, configs = inputs(bars, correlated=2, daily=20)
    for data in datasets.values():
        data.loc[2, "low"] = 5997.
    result = run_portfolio(datasets, signals, configs)
    assert result["curve"].quantity.iloc[1] == 2
    assert result["curve"].risk_locked.iloc[2]
    assert result["curve"].quantity.iloc[2] == 0
    assert result["curve"].cash.iloc[-1] == pytest.approx(49979)
    assert len(result["trades"]) == 2
    assert set(result["trades"].reason) == {"portfolio_risk_exit"}


def test_portfolio_rejects_unsynchronized_data(bars):
    datasets, signals, configs = inputs(bars)
    datasets["MNQ"] = datasets["MNQ"].iloc[:-1]
    with pytest.raises(ValueError, match="Synchronized"):
        run_portfolio(datasets, signals, configs)


def test_intrabar_exit_does_not_free_same_open_capacity(bars):
    datasets, signals, configs = inputs(bars)
    for data in datasets.values():
        data.loc[1, "low"] = 5990.
    result = run_portfolio(datasets, signals, configs)
    entries = [event for event in result["events"] if event["event"] == "full_fill" and event.get("order_id", "").startswith("entry-")]
    first_time = min(pd.Timestamp(event["timestamp"]) for event in entries)
    assert sum(pd.Timestamp(event["timestamp"]) == first_time for event in entries) == 1

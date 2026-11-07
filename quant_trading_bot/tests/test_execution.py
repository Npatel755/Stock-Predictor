import pandas as pd
import pytest
from quant_futures.config import Costs, ResearchConfig
from quant_futures.execution import PaperBroker, Order, live_adapter
from quant_futures.backtest import run_backtest
from quant_futures.risk import RiskManager, fixed_dollar_size


def order(kind="market", **kwargs):
    return Order("one", "MES", "MESH26", 1, 2, pd.Timestamp("2026-01-05T14:29Z"), kind=kind, **kwargs)


def test_order_lifecycle(bars):
    broker = PaperBroker()
    with pytest.raises(ConnectionError):
        broker.submit_order(order())
    broker.connect()
    o = order()
    broker.submit_order(o)
    with pytest.raises(ValueError, match="Duplicate"):
        broker.submit_order(o)
    fill = broker.match(o, bars.iloc[0], previous_volume=100, participation=.01)
    assert fill["quantity"] == 1 and o.status == "partial"
    broker.disconnect()
    assert o.status == "cancelled"
    with pytest.raises(PermissionError):
        live_adapter()


def test_limit_touch_and_stop_limit(bars):
    broker = PaperBroker()
    broker.connect()
    b = bars.iloc[0].copy()
    b["open"], b["high"], b["low"] = 6000, 6002, 5999
    o = order("limit", limit_price=5999)
    broker.submit_order(o)
    assert broker.match(o, b, 1000) is None
    b["low"] = 5998.75
    assert broker.match(o, b, 1000)["price"] == 5999
    s = Order("two", "MES", "MESH26", 1, 1, o.submitted_at, kind="stop_limit", stop_price=6001, limit_price=6001)
    broker.submit_order(s)
    assert broker.match(s, b, 1000) is None
    assert s.triggered


def test_no_same_bar_fill_and_exact_accounting(bars):
    b = bars.iloc[:5].copy()
    b[["open", "close"]] = 6000.
    b["high"], b["low"] = 6000.25, 5999.75
    cfg = ResearchConfig(costs=Costs(commission_per_side=1, exchange_per_side=0, regulatory_per_side=0, spread_ticks=0, slippage_ticks=0))
    result = run_backtest(b, [1, 1, 0, 0, 0], cfg)
    assert len(result["trades"]) == 1
    trade = result["trades"].iloc[0]
    assert pd.Timestamp(trade.entry_time) == b.timestamp_utc.iloc[1]
    assert pd.Timestamp(trade.exit_time) == b.timestamp_utc.iloc[3]
    assert trade.gross_pnl == 0 and trade.net_pnl == -2
    assert result["curve"].equity.iloc[-1] == 49998


def test_ambiguous_bar_is_stop_first(bars):
    b = bars.iloc[:4].copy()
    b[["open", "close"]] = 6000.
    b["high"], b["low"] = 6010., 5990.
    result = run_backtest(b, [1, 0, 0, 0])
    assert result["trades"].reason.iloc[0] == "stop_ambiguous"
    assert result["trades"].net_pnl.iloc[0] < 0


def test_roll_cannot_create_profit(bars):
    b = bars.iloc[:5].copy()
    b.loc[2:, "contract"] = "MESM26"
    b.loc[2:, ["open", "close", "high", "low"]] += 100
    with pytest.raises(RuntimeError, match="liquidation"):
        run_backtest(b, [1, 1, 1, 1, 1])
    result = run_backtest(b, [0]*5)
    assert result["curve"].equity.iloc[-1] == 50000


def test_hard_risk_and_reconciliation():
    cfg = ResearchConfig()
    risk = RiskManager(cfg.risk, 50000)
    assert fixed_dollar_size(50, 4, 5, 2, 10) == 2
    assert not risk.permit(timestamp=pd.Timestamp("2026-01-01T00:00Z"), quantity=2, risk_per_contract=20)[0]
    risk.observe(48000)
    risk.begin_session("new", 48000)
    assert risk.killed
    broker = PaperBroker()
    broker.connect()
    with pytest.raises(RuntimeError, match="Unexpected"):
        broker.reconcile({"MESH26": 1})
    assert not broker.connected

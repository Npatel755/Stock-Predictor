from pathlib import Path
import sys
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from mass_metrics import summarize_execution


def ledger():
    # One trade exits on session 2: +15 gross, -2 total fees = +13 net.
    result = dict(equity=np.array([99.,105.,113.,110.,108.,108.]),
        cash=np.array([99.,99.,113.,112.,108.,108.]),
        worst=np.array([98.,102.,112.,108.,107.,108.]),
        quantity=np.array([1,1,0,-1,0,0]),trade_entry=np.array([0,3]),trade_exit=np.array([2,4]),
        trade_net=np.array([13.,-5.]),trade_fees=np.array([2.,2.]),trade_qty=np.array([1,1]),
        trade_reason=np.array([4,3]),lock=0,funded_failed=False)
    data = dict(timestamp=np.arange(6,dtype=np.int64)*900_000_000_000,
        session=np.array([0,0,1,1,2,3]),month=np.array([202301,202301,202301,202301,202302,202302]),
        regime=np.array([1,0,0,0,0,0]))
    return result,data


def test_ledger_daily_marks_months_drawdowns_and_fees_reconcile():
    result,data = ledger()
    m = summarize_execution(result,data,initial=100)
    assert m["net_pnl"] == 8 and m["gross_pnl"] == 12 and m["fees"] == 4
    assert m["daily_pnl"] == {"0":5.,"1":5.,"2":-2.,"3":0.}
    assert m["monthly_pnl"] == {"2023-01":10.,"2023-02":-2.}
    assert m["annual_pnl"] == {"2023":8.}
    assert m["max_drawdown"] == 5 and m["realized_drawdown"] == 5 and m["intrabar_drawdown"] == 6
    assert m["profit_factor"] == 13/5 and m["win_rate"] == .5 and m["expectancy"] == 4
    assert m["avg_duration"] == 22.5 and m["avg_duration_bars"] == 1.5
    assert m["regime_pnl"] == {"trend":13.,"range":-5.}
    assert m["top_trade_share"] == 1 and m["top_trade_share_of_net"] == 13/8
    assert m["consistency"] == 5/8 and not m["consistency_50_pass"]
    assert m["positive_months"] == 1 and m["total_months"] == 2
    assert m["trading_days"] == 4 and m["active_trading_days"] == 2
    returns = np.array([5,5,-2,0],dtype=float)/100
    assert m["sharpe"] == pytest.approx(np.sqrt(252)*returns.mean()/returns.std(ddof=1))


def test_initial_capital_is_included_in_every_drawdown_and_loss_denominator():
    result = dict(equity=np.array([95.]),cash=np.array([95.]),worst=np.array([90.]),quantity=np.array([0]),
        trade_entry=np.array([0]),trade_exit=np.array([0]),trade_net=np.array([-5.]),trade_fees=np.array([2.]),
        trade_qty=np.array([1]),lock=1,funded_failed=True)
    data = dict(timestamp=np.array([1]),session=np.array([0]),month=np.array([202301]))
    m = summarize_execution(result,data,initial=100)
    assert (m["max_drawdown"],m["realized_drawdown"],m["intrabar_drawdown"]) == (5,5,10)
    assert m["consistency"] is None and not m["consistency_50_pass"]
    assert m["profit_factor"] == 0 and m["win_rate"] == 0
    assert m["killed"] and m["funded_failed"] and m["sharpe"] is None


def test_zero_trades_still_include_flat_observed_days():
    empty = np.array([],dtype=float)
    result = dict(equity=np.array([100.,100.]),cash=np.array([100.,100.]),worst=np.array([100.,100.]),
        quantity=np.array([0,0]),trade_entry=empty,trade_exit=empty,trade_net=empty,trade_fees=empty,trade_qty=empty,lock=0,funded_failed=False)
    data = dict(timestamp=np.array([1,2]),session=np.array([0,1]),month=np.array([202301,202302]))
    m = summarize_execution(result,data,initial=100)
    assert m["net_pnl"] == m["max_drawdown"] == 0
    assert m["trading_days"] == 2 and m["total_months"] == 2
    assert m["trades"] == 0 and m["expectancy"] is None and m["profit_factor"] is None
    assert m["top_trade_share"] is None and m["sharpe"] is None


@pytest.mark.parametrize("mutation,message",[
    (lambda r,d:r["trade_net"].__setitem__(0,14),"does not reconcile"),
    (lambda r,d:r["quantity"].__setitem__(-1,1),"inventory"),
    (lambda r,d:r["trade_qty"].__setitem__(0,0),"quantities"),
    (lambda r,d:r["worst"].__setitem__(0,110),"adverse bound"),
    (lambda r,d:d["timestamp"].__setitem__(1,0),"Chronological"),
    (lambda r,d:d["month"].__setitem__(-1,202313),"YYYYMM"),
])
def test_invalid_or_unreconciled_execution_is_rejected(mutation,message):
    result,data = ledger()
    mutation(result,data)
    with pytest.raises(ValueError,match=message):
        summarize_execution(result,data,initial=100)


def test_extra_nonexecuted_allocation_is_not_silently_counted_as_trades():
    result,data = ledger()
    result["trade_entry"] = np.r_[result["trade_entry"],0]
    with pytest.raises(ValueError,match="Aligned"):
        summarize_execution(result,data,initial=100)


def test_nanosecond_timestamps_do_not_lose_integer_precision():
    result,data = ledger()
    data["timestamp"] = 1_700_000_000_000_000_000+np.arange(6,dtype=np.int64)
    assert summarize_execution(result,data,initial=100)["net_pnl"] == 8

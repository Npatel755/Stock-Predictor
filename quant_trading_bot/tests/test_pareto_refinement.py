from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pareto_refinement_study as refinement
import risk_expansion_study as baseline
import profit_drawdown_followup as followup
from quant_futures.data import canonical
from quant_futures.execution import Action


def candidate(**changes):
    return dict(contracts=2, stop_points=40, payoff=3, sizing="fixed",
                risk_stop=1900, protection="none", **changes)


def market(bars):
    result = bars.iloc[:8].copy()
    result["instrument"], result["contract"] = "MNQ", "MNQH26"
    result[["open", "close"]] = 20000.
    result["high"], result["low"] = 20000.25, 19999.75
    return canonical(result)


def test_no_protection_reproduces_shared_execution(bars):
    data = market(bars)
    signals = pd.Series([Action.LONG] + [Action.HOLD]*5 + [Action.EXIT, Action.HOLD])
    expected = baseline.replay(data, signals, candidate(), "MNQ")
    actual = refinement.replay(data, signals, candidate(), "MNQ")
    pd.testing.assert_frame_equal(actual["trades"], expected["trades"])
    pd.testing.assert_frame_equal(actual["curve"], expected["curve"].drop(columns="requested_contracts"))


@pytest.mark.parametrize("side", [1, -1])
def test_protection_uses_prior_close_and_never_current_high(bars, side):
    data = market(bars)
    # The entry candle crosses 1R but closes below it. Its low/high would
    # stop the trade if that same candle's excursion could tighten the stop.
    if side == 1:
        data.loc[1, ["high", "low", "close"]] = [20060., 19999., 20010.]
        data.loc[2, ["open", "high", "low", "close"]] = [20010., 20060., 20005., 20050.]
        data.loc[3, ["open", "high", "low", "close"]] = [20050., 20051., 19999., 20000.]
    else:
        data.loc[1, ["high", "low", "close"]] = [20001., 19940., 19990.]
        data.loc[2, ["open", "high", "low", "close"]] = [19990., 19995., 19940., 19950.]
        data.loc[3, ["open", "high", "low", "close"]] = [19950., 20001., 19949., 20000.]
    signals = pd.Series([Action.LONG if side == 1 else Action.SHORT] + [Action.HOLD]*7)
    params = candidate()
    params["protection"] = "entry_1"
    actual = refinement.replay(data, signals, params, "MNQ")
    trade = actual["trades"].iloc[0]
    assert trade.exit_time == str(data.timestamp_utc.iloc[3])
    assert trade.reason == "stop"
    assert side*(trade.exit_price-trade.entry_price) > 0
    altered = data.copy()
    altered.loc[1, "high" if side == 1 else "low"] += side*20
    perturbed = refinement.replay(altered, signals, params, "MNQ")
    pd.testing.assert_frame_equal(actual["trades"], perturbed["trades"])


def test_followup_fixed_size_preserves_protected_execution(bars):
    data = market(bars)
    signals = pd.Series([Action.LONG] + [Action.HOLD]*5 + [Action.EXIT, Action.HOLD])
    params = candidate()
    params["protection"] = "entry_075"
    expected = refinement.replay(data, signals, params, "MNQ")
    actual = followup.replay(data, signals, params, "MNQ")
    pd.testing.assert_frame_equal(actual["trades"], expected["trades"])
    pd.testing.assert_frame_equal(actual["curve"].drop(columns="requested_contracts"), expected["curve"])


def test_followup_taper_cannot_use_current_bar_loss(bars):
    data = market(bars)
    params = candidate()
    params.update(contracts=3, sizing="drawdown_taper", taper_thresholds=[20, 40])
    signals = pd.Series([Action.LONG] + [Action.HOLD]*7)
    expected = followup.replay(data, signals, params, "MNQ")
    altered = data.copy()
    altered.loc[3:, "low"] -= 30
    altered.loc[3:, "close"] -= 20
    actual = followup.replay(altered, signals, params, "MNQ")
    pd.testing.assert_series_equal(expected["curve"].requested_contracts.iloc[:4], actual["curve"].requested_contracts.iloc[:4])
    assert actual["curve"].requested_contracts.iloc[3] == 3
    assert actual["curve"].requested_contracts.iloc[4] == 1


def test_followup_exit_is_requested_at_previous_completed_close(bars):
    params = dict(candidate(), name=refinement.NAME, exit_minute=690,
                  gap_low=.1, gap_high=.6, momentum_min=.05)
    early = followup.signals_for(bars.iloc[:180], params)
    later = followup.signals_for(bars.iloc[:180], dict(params, exit_minute=720))
    assert early.iloc[119] == Action.EXIT  # 11:29 ET close -> 11:30 open.
    assert later.iloc[119] == Action.HOLD
    assert later.iloc[149] == Action.EXIT  # 11:59 ET close -> noon open.

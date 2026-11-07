import numpy as np
import pandas as pd
import pytest
import importlib.util
from quant_futures.funded import AccountRules, FundedAccount, funded_payout_eligibility
from quant_futures.features import build_features
from quant_futures.labels import future_returns
from quant_futures.models import fit_model, calibration_metrics
from quant_futures.strategies import BASELINES, baseline, ensemble, regime_strategy
from quant_futures.metrics import block_bootstrap


def test_eod_drawdown_and_locked_floor():
    account = FundedAccount(AccountRules(consistency=.5))
    account.mark(52000, session="a", closing_balance=51000)
    assert account.floor == 48000  # No intraday EOD trailing.
    account.mark(51100, session="b", closing_balance=51100)
    assert account.floor == 49000
    account.end_session(52200)
    assert account.floor == 50100 and account.locked_floor
    account.mark(50100, session="c")
    assert account.failed  # Equality is a breach.


def test_dll_and_consistency():
    a = FundedAccount(AccountRules(daily_loss=300, consistency=.5, minimum_days=2))
    a.mark(49700, session="a")
    assert a.day_locked and not a.failed
    a.mark(50000, session="b")
    assert not a.day_locked
    b = FundedAccount(AccountRules(consistency=.5, minimum_days=2))
    b.mark(51500, session="a", closing_balance=51500)
    b.mark(53000, session="b", closing_balance=53000)
    b.end_session(53000)
    summary = b.summary()
    assert summary["consistency_ratio"] == .5
    assert summary["simulated_objectives_met"] and not summary["operationally_eligible"]
    assert funded_payout_eligibility([150]*5, 2000, 1000)
    assert not funded_payout_eligibility([150]*4, 2000, 1000)
    funded = FundedAccount(AccountRules(phase="funded"))
    assert funded.permit_position(20) and not funded.permit_position(21)
    funded.mark(51000, session="a")
    funded.end_session(51000)
    assert funded.permit_position(30) and not funded.permit_position(31)


def test_all_baselines(bars):
    f = build_features(bars)
    signals = {}
    for name in BASELINES:
        signals[name] = baseline(name, bars, f)
        assert set(signals[name].unique()) <= {-1, 0, 1}
    assert len(ensemble(signals)) == len(bars)
    assert len(regime_strategy(bars, f)) == len(bars)


@pytest.mark.parametrize("name", ["logistic", "ridge", "tree", "lightgbm", "xgboost"])
def test_training_only_and_calibration(bars, name):
    if name in ("lightgbm", "xgboost") and importlib.util.find_spec(name) is None:
        pytest.skip("Optional model dependency unavailable")
    f, y = build_features(bars), future_returns(bars)
    model = fit_model(name, f.iloc[:500], y.iloc[:500], bars.iloc[:500])
    prediction = model.predict_probability(f.iloc[500:600])
    assert np.isfinite(prediction).all() and ((prediction > 0) & (prediction < 1)).all()
    m = calibration_metrics((y.forward_return.iloc[500:600] > 0).astype(int), prediction)
    assert 0 <= m["brier"] <= 1
    # Values after training cannot influence fitted preprocessing or parameters.
    f.loc[600:, :] = 1e9
    model2 = fit_model(name, f.iloc[:500], y.iloc[:500], bars.iloc[:500])
    np.testing.assert_allclose(prediction, model2.predict_probability(f.iloc[500:600]))


def test_uncertainty_small_sample():
    result = block_bootstrap([1, -1, 2], draws=10)
    assert result["insufficient_evidence"]
    assert block_bootstrap([])["insufficient_evidence"]

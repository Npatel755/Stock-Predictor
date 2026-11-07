from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from risk_expansion_study import replay, requested_size, configuration
from quant_futures.data import canonical
from quant_futures.execution import Action


def test_larger_positions_use_real_partial_fills_and_per_contract_fees(bars):
    b = bars.iloc[:8].copy()
    b["instrument"], b["contract"] = "MNQ", "MNQH26"
    b[["open", "close"]] = 20000.
    b["high"], b["low"], b["volume"] = 20000.25, 19999.75, 150
    b = canonical(b)
    signals = pd.Series([Action.LONG]+[Action.HOLD]*5+[Action.EXIT, Action.HOLD])
    candidate = dict(contracts=2, stop_points=40, payoff=3, sizing="fixed")
    partial = replay(b, signals, candidate, "MNQ")
    assert partial["trades"].quantity.tolist() == [1]
    assert partial["trades"].fees.tolist() == [1.]
    full_bars = b.copy()
    full_bars["volume"] = 1000
    full = replay(full_bars, signals, candidate, "MNQ")
    assert full["trades"].quantity.tolist() == [2]
    assert full["trades"].fees.tolist() == [2.]
    assert full["trades"].net_pnl.iloc[0] == 2*partial["trades"].net_pnl.iloc[0]


def test_drawdown_taper_uses_preceding_equity_not_current_high_low(bars):
    candidate = dict(contracts=3, stop_points=40, payoff=3, sizing="drawdown_taper", taper_thresholds=[300, 600])
    assert [requested_size(candidate, dd) for dd in (0, 299, 300, 599, 600, 1200)] == [3, 3, 2, 2, 1, 1]
    b = bars.iloc[:40].copy()
    b["instrument"], b["contract"] = "MNQ", "MNQH26"
    b = canonical(b)
    signals = pd.Series([Action.LONG]+[Action.HOLD]*39)
    full = replay(b, signals, candidate, "MNQ")
    prefix = replay(b.iloc[:10], signals.iloc[:10], candidate, "MNQ")
    np.testing.assert_array_equal(full["curve"].requested_contracts.iloc[:10], prefix["curve"].requested_contracts)
    changed = b.copy()
    changed.loc[10:, "low"] -= 200
    perturbed = replay(changed, signals, candidate, "MNQ")
    np.testing.assert_array_equal(full["curve"].requested_contracts.iloc[:11], perturbed["curve"].requested_contracts.iloc[:11])


def test_higher_internal_risk_stop_cannot_remove_2000_ceiling():
    import pytest
    candidate = dict(contracts=2, stop_points=40, payoff=3, sizing="fixed", risk_stop=1900)
    assert configuration("MNQ", candidate).risk.max_drawdown == 1900
    assert configuration("NQ", candidate).risk.max_drawdown == 19000
    with pytest.raises(ValueError):
        configuration("MNQ", dict(candidate, risk_stop=2000))

from dataclasses import asdict, replace
import json

import pandas as pd
import pytest

from backtesting.execution_audit import concentration
from backtesting.optimize import baseline
from backtesting.transfer_audit import freeze_plan


def test_transfer_plan_is_fixed_before_results_and_rejects_changed_candidate(tmp_path):
    selected = tmp_path / "selection.json"
    parent = tmp_path / "parent.json"
    parent.write_text(json.dumps(asdict(baseline())), encoding="utf-8")
    config = asdict(replace(baseline(), reward_r=4.5, stop_atr=.4))
    selected.write_text(json.dumps({"candidate": {"config": config}}), encoding="utf-8")
    plan = freeze_plan(tmp_path, selected, parent)
    assert plan["configs"]["refined_v1_2"] == config
    assert plan["evaluation_windows"][-1] == ["2020-01-01", "2023-01-01"]
    assert "cannot reselect" in plan["decision"]
    assert freeze_plan(tmp_path, selected, parent) == plan
    config["reward_r"] = 5
    selected.write_text(json.dumps({"candidate": {"config": config}}), encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        freeze_plan(tmp_path, selected, parent)


def test_concentration_reports_mechanical_subtraction_and_losing_streak():
    trades = pd.DataFrame({"net_pnl": [400., -100., -100., 300., -100., -100., -100., 400.]})
    result = concentration(trades)
    assert result["closed_trade_pnl"] == 600
    assert result["pnl_excluding_best_1_legs"] == 200
    assert result["pnl_excluding_best_3_legs"] == -500
    assert result["longest_losing_leg_streak"] == 3
    assert "not an executable counterfactual" in result["note"]

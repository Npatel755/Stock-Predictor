from pathlib import Path
import sys
from collections import Counter
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import training_search_200k as study
import training_200k_policy as policy
from mass_configurations import generate as base_generate, semantic_key
from mass_continuation_configurations import generate as cont_generate


def test_200k_manifest_is_unique_disjoint_and_balanced():
    excluded = {semantic_key(c) for c in base_generate()}
    batch = cont_generate(excluded, seed=study.SEED)
    assert len(batch) == 10000
    keys = {semantic_key(c) for c in batch}
    assert len(keys) == 10000 and keys.isdisjoint(excluded)
    counts = Counter((c['instrument'], c['family']) for c in batch)
    assert len(counts) == 40 and set(counts.values()) == {250}
    assert study.SEED == 20261123 and study.TARGET == 200000


def test_robustness_metric_favors_high_pf_and_low_dd():
    # Strategy A: Churn scalper (High PnL, Low PF, High DD)
    score_a = policy.robustness_metric(13920.5, 1.19, 1593.0)
    # Strategy B: High-asymmetry breakout (Clean PnL, High PF, Low DD)
    score_b = policy.robustness_metric(10752.0, 1.61, 1098.0)
    assert score_b > 2.5 * score_a, f"Expected Strategy B score ({score_b}) to be > 2.5x Strategy A ({score_a})"


def test_qualification_rules():
    fold_good = dict(
        net_pnl=2000.0, trades=75, killed=False, funded_failed=False,
        intrabar_drawdown=1000.0, max_drawdown=1000.0, realized_drawdown=1000.0,
        consistency=0.3, consistency_50_pass=True, label="2020",
        gross_pnl=2500.0, fees=500.0, positive_trade_pnl=5000.0, negative_trade_pnl=-2500.0,
        profit_factor=2.0, win_rate=0.5, expectancy=26.6, avg_duration=30.0, sharpe=1.5,
        top_trade_share=0.1, positive_months=8, total_months=12, lock=0,
        monthly_pnl={"2020-01": 2000.0}, regime_pnl={"trend": 2000.0}
    )
    cfg = {'config_id': 'test_1', 'instrument': 'MNQ', 'family': 'breakout', 'profit_factor': 1.6, 'net_pnl': 8000.0}
    row = policy.aggregate(cfg, [fold_good]*4, np.zeros(1))
    assert row['qualified'] is True
    assert row['robustness_score'] > 0

    # Low profit factor (< 1.3) should NOT qualify under anti-overfitting policy
    low_pf_fold = dict(fold_good, positive_trade_pnl=1150.0, negative_trade_pnl=-1000.0)
    cfg_low = dict(cfg, config_id='test_2')
    row_low_pf = policy.aggregate(cfg_low, [low_pf_fold]*4, np.zeros(1))
    assert row_low_pf['qualified'] is False


"""Tests for 500k Training Search v2 policy and universe."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))

from training_500k_v2_policy import aggregate, BENCHMARK_ID, BENCHMARK_METRICS
from training_500k_v2_universe import create_bitset, set_bit, is_bit_set, config_to_index


def test_benchmark_is_new_champion():
    assert BENCHMARK_ID == 'mass_e57ba183f302b3ba886b'
    assert BENCHMARK_METRICS['net_pnl'] == 4935.50
    assert BENCHMARK_METRICS['intrabar_drawdown'] == 533.25


def test_aggregate_ranking_criteria():
    c = {
        'config_id': 'test_cand',
        'instrument': 'MNQ',
        'family': 'momentum',
        'parameters': {}
    }
    # Case 1: Beats baseline with DD < 2000
    folds = [
        {'net_pnl': 2000, 'max_drawdown': 400, 'realized_drawdown': 300, 'intrabar_drawdown': 450,
         'gross_pnl': 2100, 'fees': 100, 'positive_trade_pnl': 2500, 'negative_trade_pnl': -400,
         'trades': 25, 'lock': 0, 'funded_failed': False}
        for _ in range(4)
    ]
    res = aggregate(c, folds, None)
    assert res['qualified'] is True
    assert res['net_pnl'] == 8000
    assert res['better_than_baseline'] is True

    # Case 2: DD exceeds 2000
    folds[0]['intrabar_drawdown'] = 2500
    res2 = aggregate(c, folds, None)
    assert res2['qualified'] is False
    assert res2['better_than_baseline'] is False


def test_bitset_uniqueness():
    bitset = create_bitset()
    c = {
        'instrument': 'MNQ', 'family': 'momentum', 'lookback': 16,
        'threshold': 1.5, 'stop_atr': 1.0, 'target_r': 4.0,
        'hold_bars': 12, 'session_start': 585, 'session_end': 945,
        'max_contracts': 1, 'trailing_atr': 2.0
    }
    idx = config_to_index(c)
    assert not is_bit_set(bitset, idx)
    set_bit(bitset, idx)
    assert is_bit_set(bitset, idx)

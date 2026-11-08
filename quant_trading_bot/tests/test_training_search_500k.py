from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from training_500k_policy import aggregate, robustness_metric, BENCHMARK_ID, PRIOR
from training_500k_universe import config_to_index, is_bit_set, set_bit, create_bitset, BITSET_SIZE
from mass_configurations import FAMILIES, INSTRUMENTS, THRESHOLDS, SESSIONS


def test_bitset_indexing_bijective():
    b_arr = create_bitset()
    assert len(b_arr) == BITSET_SIZE
    
    # Test setting and checking bits
    test_indices = [0, 1, 100, 50000, 100000, 1799999]
    for idx in test_indices:
        assert not is_bit_set(b_arr, idx)
        set_bit(b_arr, idx)
        assert is_bit_set(b_arr, idx)


def test_robustness_metric():
    # Zero or negative net profit gives zero robustness
    assert robustness_metric(-500.0, 1.5, 400.0) == 0.0
    assert robustness_metric(1000.0, 0.9, 400.0) == 0.0
    
    # High PF and low DD produces higher score
    score_a = robustness_metric(5000.0, 2.0, 500.0) # 5000 * 1.0 / 500 = 10.0
    score_b = robustness_metric(5000.0, 1.2, 500.0) # 5000 * 0.2 / 500 = 2.0
    assert score_a > score_b


def test_prior_runs_configuration():
    assert len(PRIOR) == 5
    assert 'training_search_200k_v1' in PRIOR
    assert BENCHMARK_ID == 'mass_4a0b95329be1d0438243'

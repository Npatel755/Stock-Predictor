"""Unit tests for the top 15 validation and test evaluation runner."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))

from evaluate_top15_500k_val_test import get_top15


def test_get_top15_returns_15_valid_candidates():
    top15 = get_top15()
    assert len(top15) == 15
    for c in top15:
        assert 'config_id' in c
        assert 'instrument' in c
        assert c['instrument'] == 'MNQ'
        assert 'family' in c
        assert 'parameters' in c
        p = c['parameters']
        assert p['lookback'] >= 2
        assert p['stop_atr'] > 0
        assert p['target_r'] > 0
        assert p['hold_bars'] >= 1

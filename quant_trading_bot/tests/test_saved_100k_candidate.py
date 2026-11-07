from pathlib import Path
import sys
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_saved_100k_candidate as evaluation


def test_saved_100k_candidate_target_and_protocol():
    result = evaluation.read(evaluation.ROOT/'reports/training_search_100k_result.json')
    winner = result['winner']
    assert winner is not None
    assert winner['config_id'] == evaluation.ID
    assert winner['base']['net_pnl'] == 13920.5
    assert winner['stress_2x']['qualified'] is True
    assert winner['base']['parameters']['instrument'] == 'MNQ'
    assert winner['base']['parameters']['family'] == 'trend'


def test_test_data_forbidden():
    catalog = evaluation.read(evaluation.ROOT/'data/catalog.json')
    assert 'validation' in catalog['instruments']['MNQ']['splits']
    # Check that check_meta rejects anything other than validation
    import pytest
    with pytest.raises(PermissionError):
        evaluation.check_meta({'split_role': 'test', 'instrument': 'MNQ'}, 'test')

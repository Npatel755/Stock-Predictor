import json
import pandas as pd
import pytest

from research.codex_eth_bnb.data_pipeline import HERE
from research.codex_eth_bnb.runner import Lab


def test_contaminated_final_is_rejected_before_signal_or_result_access():
    lab = object.__new__(Lab)
    lab.split = json.loads((HERE/'split_manifest.json').read_text())
    spec = dict(id='flat_1h', family='flat', timeframe='1h')
    # Trial guard runs before any attempt to construct signals or read result files.
    with pytest.raises(ValueError, match='Contaminated'):
        lab.trial('ETH', spec, pd.Timestamp('2025-09-01', tz='UTC'), pd.Timestamp('2025-10-01', tz='UTC'), 'FINAL')


def test_predeclared_event_embargo_covers_longest_timeout():
    split = json.loads((HERE/'split_manifest.json').read_text())
    candidates = json.loads((HERE/'candidate_manifest.json').read_text())['specifications']
    longest = max(pd.Timedelta(s['timeframe'])*s['execution']['max_hold_bars'] for s in candidates)
    assert longest <= pd.Timedelta(days=split['embargo_days'])
    for fold in split['folds']:
        assert pd.Timestamp(fold['eval_start'])-pd.Timestamp(fold['fit_end']) >= longest

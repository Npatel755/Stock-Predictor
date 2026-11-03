import json

import pandas as pd
import pytest

from backtesting.verify_numbered_research import exact, verify


def test_reproduction_compares_timestamp_positions_without_rounding_profit():
    actual=dict(final_equity=60799.669772006622,open_position=dict(entry_time=pd.Timestamp('2026-01-01',tz='UTC')))
    expected=dict(final_equity=60799.669772006622,open_position=dict(entry_time='2026-01-01 00:00:00+00:00'))
    exact(actual,expected,'main')
    expected['final_equity']+=.000001
    with pytest.raises(ValueError,match='differs'): exact(actual,expected,'main')


def test_verifier_rejects_failed_gate_before_loading_market_data(tmp_path):
    for name,payload in [('manifest',{}),('selection',{'passed_predeclared_validation_gate':False}),('summary',{})]:
        (tmp_path/f'{name}.json').write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='failed historical gate'): verify(tmp_path)


def test_verifier_rejects_a_changed_frozen_source_before_replaying(tmp_path):
    manifest=dict(selection_window=['2023-01-01','2026-10-28'],source_hashes={'model.py':'wrong_digest'})
    for name,payload in [('manifest',manifest),('selection',{'passed_predeclared_validation_gate':True}),('summary',{})]:
        (tmp_path/f'{name}.json').write_text(json.dumps(payload))
    (tmp_path/'model.py').write_text('changed source')
    with pytest.raises(ValueError,match='Frozen source_hashes input changed'): verify(tmp_path,root=tmp_path)

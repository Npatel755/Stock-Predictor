"""Count semantics and frozen market coverage for the requested new batch."""
import json
from pathlib import Path
import sqlite3
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collaborative_200k import DD_FIELDS, RUN, TARGET, positive_under_limit


@pytest.mark.parametrize('field',DD_FIELDS)
def test_drawdown_threshold_is_strict_for_each_measure(field):
    row=dict(net_pnl=1.0,realized_drawdown=10,max_drawdown=20,intrabar_drawdown=30,locks=1)
    assert positive_under_limit(row)  # user two-condition count includes locked cases
    row[field]=1999.99
    assert positive_under_limit(row)
    row[field]=2000
    assert not positive_under_limit(row)


@pytest.mark.parametrize('profit',[0,-0.01,-1000])
def test_no_trade_or_losing_case_is_not_counted(profit):
    assert not positive_under_limit(dict(net_pnl=profit,realized_drawdown=0,max_drawdown=0,intrabar_drawdown=0))


def test_prepared_budget_has_all_families_and_opening_horizons():
    if not (RUN/'protocol.json').exists():
        pytest.skip('Integration check requires the prepared research manifest')
    protocol=json.loads((RUN/'protocol.json').read_text())
    assert protocol['new_unique_configurations']==TARGET==200000
    assert protocol['gemini_reserved_configurations']==500000
    with sqlite3.connect(f'file:{(RUN/"checkpoints.sqlite").as_posix()}?mode=ro',uri=True) as db:
        assert db.execute('SELECT COUNT(*) FROM configs').fetchone()[0]==200000
        groups=db.execute("SELECT instrument,json_extract(payload,'$.family'),COUNT(*) FROM configs GROUP BY 1,2").fetchall()
        assert len(groups)==40 and {g[2] for g in groups}=={5000}
        horizons={r[0] for r in db.execute("SELECT DISTINCT lookback FROM configs WHERE json_extract(payload,'$.family')='opening_range'")}
        assert horizons==set(range(15,121,15))

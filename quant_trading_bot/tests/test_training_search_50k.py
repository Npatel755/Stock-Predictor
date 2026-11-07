from pathlib import Path
import sys
import random
import pandas as pd
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import training_search_50k as study
from mass_configurations import generate,semantic_key
from quant_futures.data import canonical


def test50k_universe_reproducible_disjoint_balanced():
    excluded={semantic_key(c) for c in generate()}
    state=random.getstate();rows=study.universe(excluded)
    assert random.getstate()==state and len(rows)==50000
    keys={semantic_key(c) for c in rows};assert len(keys)==50000 and keys.isdisjoint(excluded)
    assert rows==study.universe(excluded)
    assert all(sum(c['instrument']==s for c in rows)==12500 for s in ('ES','NQ','MES','MNQ'))


def test_improvement_needs_higher_net_and_each_dd_strictly_under_2000():
    base=dict(net_pnl=100,max_drawdown=10,realized_drawdown=9,intrabar_drawdown=11)
    row=dict(base,net_pnl=101,qualified=True)
    assert study.better_base(row,base)
    assert not study.better_base(dict(row,net_pnl=100),base)
    assert not study.better_base(dict(row,qualified=False),base)
    for key in ('max_drawdown','realized_drawdown','intrabar_drawdown'):
        assert study.better_base(dict(row,**{key:1999.99}),base)
        assert not study.better_base(dict(row,**{key:2000}),base)


def test_cached_session_signals_equal_original_causal_mask():
    n=500
    close=15000+np.sin(np.arange(n)/7)*10
    bars=canonical(pd.DataFrame(dict(timestamp_utc=pd.date_range('2023-01-02T23:00Z',periods=n,freq='15min'),
        instrument='MNQ',contract='MNQH23',open=close,high=close+1,low=close-1,close=close,volume=1000)))
    f=study.engine.features(bars,8);masks=study.session_masks(bars);cache={}
    for c in generate()[:100]:
        c=dict(c,lookback=8)
        np.testing.assert_array_equal(study.cached_signal(c,f,masks,cache),study.engine.masked_signal(bars,c,f))

from pathlib import Path
import sys
from collections import Counter
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import training_search_100k as study
import training_100k_policy as policy
from mass_configurations import generate,semantic_key


def test100k_manifest_is_unique_disjoint_and_balanced():
    excluded={semantic_key(c) for c in generate()}
    rows=study.universe(excluded)
    keys={semantic_key(c) for c in rows}
    assert len(rows)==len(keys)==100000 and keys.isdisjoint(excluded)
    counts=Counter((c['instrument'],c['family']) for c in rows)
    assert len(counts)==40 and set(counts.values())=={2500}
    assert study.SEED==20261113 and study.TARGET==100000


def test_consistency_phase_changes_classification_only(monkeypatch):
    raw=dict(qualified=False,net_pnl=100,max_drawdown=12,realized_drawdown=10,intrabar_drawdown=15,score=1)
    monkeypatch.setattr(policy.engine,'aggregate',lambda *a:dict(raw))
    fold=dict(net_pnl=25,trades=35,killed=False,funded_failed=False,consistency=.8)
    row=policy.aggregate({},[fold]*4,np.zeros(1))
    assert row['qualified'] and not row['evaluation_phase_qualified']
    assert all(row[k]==raw[k] for k in ('net_pnl','max_drawdown','realized_drawdown','intrabar_drawdown'))
    assert not policy.aggregate({},[dict(fold,killed=True)]*4,np.zeros(1))['qualified']
    monkeypatch.setattr(policy.engine,'aggregate',lambda *a:dict(raw,intrabar_drawdown=2000))
    assert not policy.aggregate({},[fold]*4,np.zeros(1))['qualified']

from pathlib import Path
import sys
import random
import json
import importlib.util
from threading import Thread
from urllib.request import urlopen
from collections import Counter
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mass_configurations as original
import mass_continuation_configurations as continuation


def test_new_batch_is_reproducible_balanced_and_disjoint():
    old=original.generate()
    excluded={original.semantic_key(c) for c in old}
    random.seed(12);state=random.getstate()
    new=continuation.generate(excluded)
    assert random.getstate()==state
    assert new==continuation.generate(excluded)
    keys={original.semantic_key(c) for c in new}
    assert len(new)==len(keys)==10000
    assert keys.isdisjoint(excluded) and len(keys|excluded)==20000
    assert {c['config_id'] for c in new}.isdisjoint({c['config_id'] for c in old})
    counts=Counter((c['instrument'],c['family']) for c in new)
    assert len(counts)==40 and set(counts.values())=={250}
    for c in new:
        assert c['lookback'] in (original.OPENING_LOOKBACKS if c['family']=='opening_range' else original.LOOKBACKS)
        assert c['threshold'] in original.THRESHOLDS[c['family']]
        assert c['stop_atr'] in original.STOP_ATR and c['target_r'] in original.TARGET_R
        assert c['config_id']==original.config_id(c)


def test_continuation_seed_must_be_an_integer():
    with pytest.raises(ValueError): continuation.generate(set(),seed=True)


def test_dashboard_keeps_original_and_continuation_downloads_separate(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('continuation_dashboard',Path(__file__).resolve().parents[1]/'dashboard/light_server.py')
    dashboard=importlib.util.module_from_spec(spec);spec.loader.exec_module(dashboard)
    monkeypatch.setattr(dashboard,'ROOT',tmp_path)
    (tmp_path/'reports').mkdir()
    for folder,name,payload in [('original','mass_research_result.json','original-results'),
                                ('next','mass_continuation_progress.json','continuation-results')]:
        run=tmp_path/'runs'/folder;run.mkdir(parents=True)
        (run/'ranked.csv').write_text(payload,encoding='utf-8')
        (tmp_path/'reports'/name).write_text(json.dumps(dict(run_path=str(run))),encoding='utf-8')
    server=dashboard.ThreadingHTTPServer(('127.0.0.1',0),dashboard.Handler)
    worker=Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        for path,expected in [('/mass/ranked.csv','original-results'),('/continuation/ranked.csv','continuation-results')]:
            with urlopen(f'http://127.0.0.1:{server.server_port}'+path) as response:
                assert response.read().decode('utf-8')==expected
        assert dashboard.mass_artifact('../../outside.csv',continuation=True) is None
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)

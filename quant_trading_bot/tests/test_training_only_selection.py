from pathlib import Path
import sys
import json
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import training_only_selection as study
from quant_futures.validation import freeze_candidate
from quant_futures.config import file_hash


def row(net,dd,locked=False):
    measured = dict(net_pnl=net,max_drawdown=dd,max_intraday_drawdown_bound=dd+100,
        permanent_risk_lock=locked,annual_pnl={"2022":net/2,"2023":net/2},trades=80)
    return dict(candidate_id=str(net),base=measured,stress_2x=measured.copy(),earlier_screen_net=1000)


def test_rank_rejects_risk_stopped_winner_and_ignores_validation_results():
    survivor = row(20000,10000)
    stopped = row(100000,19000,locked=True)
    assert study.rank(survivor) > study.rank(stopped)
    before = study.rank(survivor)
    survivor["validation_net"] = -999999999
    survivor["test_net"] = 999999999
    assert study.rank(survivor) == before


def test_evaluation_failure_cannot_reopen_validation_or_choose_alternative(tmp_path,monkeypatch):
    monkeypatch.setattr(study,"ROOT",tmp_path)
    folder = tmp_path/"runs/training_only_selection_v1"
    folder.mkdir(parents=True)
    for name in ("training_ranking.json","NQ_training_selection_attempts.json"):
        (folder/name).write_text("[]")
    freeze_candidate(folder/"frozen_candidate.json",dict(candidate_id="fixed",source_hash="fixed-source",
        script_hashes={},training_ranking_sha256=file_hash(folder/"training_ranking.json"),
        training_results_sha256=file_hash(folder/"NQ_training_selection_attempts.json")))
    monkeypatch.setattr(study,"code_identity",lambda:dict(source_hash="fixed-source"))
    monkeypatch.setattr(study,"source_paths",lambda:[])
    source = tmp_path/"validation.parquet"
    source.with_suffix(".manifest.json").write_text(json.dumps(dict(dataset_version="fixed-validation")))
    opened = []
    def resolve(name):
        assert (tmp_path/"data/manifests/validation_once/training_only_selection_v1.json").exists()
        assert name == "MNQ:validation"
        opened.append(name)
        return source
    monkeypatch.setattr(study,"resolve_dataset",resolve)
    def fail(version):
        raise RuntimeError("synthetic load failure")
    monkeypatch.setattr(study.cache,"bounded_micro",fail)
    with pytest.raises(RuntimeError,match="synthetic load failure"):
        study.evaluate()
    with pytest.raises(FileExistsError):
        study.evaluate()
    assert opened == ["MNQ:validation"]

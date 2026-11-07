from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import training_session_research as study
from quant_futures.config import file_hash
from quant_futures.data import canonical
from quant_futures.execution import Action


def minute_bars(bars):
    b = bars.iloc[:395].copy()
    b["instrument"],b["contract"] = "NQ","NQH23"
    b["timestamp_utc"] = pd.date_range("2023-01-04T14:30Z",periods=len(b),freq="min")
    b["open"],b["close"] = 20000.,20010.
    b["high"],b["low"] = 20020.,20000.
    return canonical(b)


def parameters():
    return dict(name="opening_momentum_5m",long_only=False,stop_fraction=.5,payoff=2,contracts=1)


def test_incomplete_or_cross_contract_five_minute_bars_are_not_invented(bars):
    b = minute_bars(bars)
    complete = study.five_minute_session(b)
    assert len(complete) == 79
    missing = b.drop(index=2)
    assert len(study.five_minute_session(missing)) == 78
    rolled = b.copy()
    rolled.loc[2,"contract"] = "NQM23"
    assert len(study.five_minute_session(rolled)) == 78


def test_signals_are_prefix_invariant_and_one_attempt_per_session(bars):
    b = study.five_minute_session(minute_bars(bars))
    signals,ranges = study.intent_and_ranges(b,parameters())
    assert signals.eq(Action.LONG).sum() == 1 and signals.iloc[5] == Action.LONG
    prefix,pr = study.intent_and_ranges(b.iloc[:15],parameters())
    pd.testing.assert_series_equal(prefix,signals.iloc[:15])
    np.testing.assert_allclose(pr,ranges.iloc[:15],equal_nan=True)
    changed = b.copy()
    changed.loc[15:,["high","close"]] += 1000
    perturbed,_ = study.intent_and_ranges(changed,parameters())
    pd.testing.assert_series_equal(perturbed.iloc[:15],signals.iloc[:15])


def test_entry_uses_next_open_after_completed_opening_range(bars):
    b = study.five_minute_session(minute_bars(bars))
    signals,ranges = study.intent_and_ranges(b,parameters())
    result = study.replay(b,signals,ranges,parameters())
    assert result["trades"].iloc[0].entry_time == str(b.timestamp_utc.iloc[6])
    assert b.timestamp_utc.iloc[6] == pd.Timestamp("2023-01-04T15:00Z")
    assert result["trades"].quantity.max() == 1


@pytest.mark.parametrize("role",["validation","test"])
def test_training_loader_rejects_nontraining_manifest_without_prices(tmp_path,monkeypatch,role):
    path = tmp_path/"partition.parquet"
    path.write_bytes(b"not-readable-market-data")
    path.with_suffix(".manifest.json").write_text(json.dumps(dict(instrument="NQ",split_role=role,
        raw_contract_prices=True,synthetic=False,dataset_version=file_hash(path))))
    monkeypatch.setattr(study,"resolve_dataset",lambda name:path)
    with pytest.raises(PermissionError):
        study.training_source()

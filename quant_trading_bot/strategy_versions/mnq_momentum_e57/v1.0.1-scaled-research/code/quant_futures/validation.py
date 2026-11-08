"""Chronological folds and immutable, single-use final-test reservations."""
from pathlib import Path
from datetime import datetime, timezone
import json
import numpy as np
import pandas as pd
from .config import digest, file_hash


def walk_forward(bars, label_ends, min_train=240, validation=120, embargo=5, stop=None, rolling=None):
    n = len(bars) if stop is None else stop
    for start in range(min_train+embargo, n-validation+1, validation):
        stop_train = start-embargo
        indexes = np.arange(max(0, stop_train-rolling) if rolling else 0, stop_train)
        # A training label whose final bar is the first validation bar is ineligible.
        ends = pd.to_datetime(label_ends.iloc[indexes], utc=True)
        train = indexes[(ends < bars.timestamp_utc.iloc[start]).to_numpy() & ends.notna().to_numpy()]
        if len(train) >= 30:
            yield train, np.arange(start, start+validation)


def reserve_holdout(path, *, dataset_version, dates, model_version, code_commit, config_hash, source_hash):
    manifest = dict(dataset_version=dataset_version, dates=dates, model_version=model_version,
                    code_commit=code_commit, config_hash=config_hash, source_hash=source_hash,
                    evaluation_timestamp=datetime.now(timezone.utc).isoformat(),
                    state="reserved_once; failures also consume holdout")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation is the guard; never reopen a failed holdout for tuning.
    with open(path, "x", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def freeze_candidate(path, candidate):
    obj = dict(candidate=candidate, candidate_hash=digest(candidate))
    with open(path, "x", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    return obj

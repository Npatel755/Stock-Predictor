from collections import Counter
from pathlib import Path
import random
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import mass_configurations as universe


@pytest.fixture(scope="module")
def configurations():
    return universe.generate()


def test_exact_ten_thousand_globally_distinct_active_configurations(configurations):
    assert len(configurations) == 10000
    assert len({row["config_id"] for row in configurations}) == 10000
    assert len({universe.semantic_key(row) for row in configurations}) == 10000
    assert all(row["config_id"] == universe.config_id(row) for row in configurations)


def test_balanced_across_markets_and_real_families(configurations):
    counts = Counter((row["instrument"], row["family"]) for row in configurations)
    assert len(counts) == 40
    for market in universe.INSTRUMENTS:
        assert sum(row["instrument"] == market for row in configurations) == 2500
        for family in universe.FAMILIES:
            assert counts[(market, family)] == 250


def test_seed_is_reproducible_but_does_not_change_global_rng(configurations):
    random.seed(314159)
    expected = random.getstate()
    assert universe.generate() == configurations
    assert random.getstate() == expected
    assert universe.generate(universe.SEED+1) != configurations


def test_market_tags_seed_and_noop_annotations_do_not_manufacture_uniqueness(configurations):
    original = configurations[0]
    renamed = dict(original, instrument="MNQ", config_id="different", seed=0, unused_parameter="annotation")
    assert universe.semantic_key(original) == universe.semantic_key(renamed)
    assert universe.config_id(original) != universe.config_id(renamed)
    changed = dict(original, stop_atr=2.5)
    assert universe.semantic_key(original) != universe.semantic_key(changed)


def test_equivalent_numeric_representations_are_deduplicated(configurations):
    original = configurations[0]
    equivalent = dict(original, hold_bars=float(original["hold_bars"]), threshold=float(original["threshold"]))
    assert universe.semantic_key(original) == universe.semantic_key(equivalent)
    with pytest.raises(ValueError, match="integer"):
        universe.semantic_key(dict(original, hold_bars=2.5))


def test_fields_are_valid_declared_active_domains(configurations):
    expected = set(universe.ACTIVE_FIELDS)|{"instrument", "config_id"}
    for row in configurations:
        assert set(row) == expected
        assert row["lookback"] in (universe.OPENING_LOOKBACKS if row["family"] == "opening_range" else universe.LOOKBACKS)
        assert row["threshold"] in universe.THRESHOLDS[row["family"]]
        assert row["stop_atr"] in universe.STOP_ATR
        assert row["target_r"] in universe.TARGET_R
        assert row["hold_bars"] in universe.HOLD_BARS
        assert (row["session_start"], row["session_end"]) in universe.SESSIONS
        assert row["session_start"] < row["session_end"] <= 955
        assert row["max_contracts"] in universe.MAX_CONTRACTS
        assert row["trailing_atr"] in universe.TRAILING_ATR


def test_metadata_hash_covers_parameters_and_balance(configurations):
    first = universe.metadata(configurations)
    second = universe.metadata(configurations)
    assert first == second
    assert first["configurations"] == first["distinct_active_configurations"] == 10000
    assert first["market_cases"] == 10000
    assert len(first["universe_sha256"]) == 64
    modified = [dict(row) for row in configurations]
    modified[0]["target_r"] = 9
    assert universe.metadata(modified)["universe_sha256"] != first["universe_sha256"]


def test_invalid_seed_is_rejected():
    for seed in (True, 1.5, "20261106"):
        with pytest.raises(ValueError, match="seed"):
            universe.generate(seed)

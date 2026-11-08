import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quant_futures import ensemble_paper as ep

ROOT = Path(__file__).resolve().parents[1]


def synthetic_bars(start, days, seed, level):
    rng = np.random.default_rng(seed)
    stamps = []
    day = pd.Timestamp(start).tz_localize("UTC") if pd.Timestamp(start).tzinfo is None else pd.Timestamp(start)
    for d in range(days):
        session = (day + pd.Timedelta(days=d)).tz_convert("America/New_York").normalize()
        if session.dayofweek >= 5:
            continue
        stamps.extend(pd.date_range(session + pd.Timedelta(hours=9, minutes=30), session + pd.Timedelta(hours=16), freq="1min", inclusive="left"))
    stamps = pd.DatetimeIndex(stamps).tz_convert("UTC")
    drift = np.repeat(rng.choice([-0.08, 0.08], size=len(stamps) // 780 + 1), 780)[: len(stamps)]
    steps = (rng.normal(0, 0.6, len(stamps)) + drift).cumsum()
    close = np.round((level + steps) * 4) / 4
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + np.round(np.abs(rng.normal(0, 0.5, len(stamps))) * 4) / 4
    low = np.minimum(open_, close) - np.round(np.abs(rng.normal(0, 0.5, len(stamps))) * 4) / 4
    volume = rng.integers(50, 500, len(stamps))
    return pd.DataFrame(dict(timestamp_utc=stamps, open=open_, high=high, low=low, close=close, volume=volume))


def write_sources(folder, days=30, seed=1, through=None):
    paths = {}
    for instrument, level, s in (("MES", 6000.0, seed), ("MNQ", 21000.0, seed + 7)):
        bars = synthetic_bars("2026-09-01", days, s, level)
        if through is not None:
            bars = bars[bars.timestamp_utc <= through]
        path = folder / f"{instrument}.csv"
        bars.to_csv(path, index=False)
        paths[instrument] = path
    return paths


def test_candidate_sleeves_match_research_script_and_screenshot_selection():
    source = (ROOT / "scripts" / "evaluate_multi_strategy_ensembles.py").read_text()
    tree = ast.parse(source)
    sleeves = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "sleeves":
            sleeves = ast.literal_eval(node.value)
    assert sleeves, "research script sleeve table not found"
    wanted = {"portfolio_e": ["MES_MOM_3c", "MNQ_BRK_E_2c"], "ensemble_beta": ["MES_MOM_2c", "MNQ_BRK_E_1c", "MNQ_HYB_C_1c"]}
    for key, names in wanted.items():
        for spec, name in zip(ep.CANDIDATES[key]["sleeves"], names):
            expected = dict(sleeves[name])
            got = {k: v for k, v in spec.items() if k != "name"}
            assert got == expected, (key, name)
    epsilon = [s["name"] for s in ep.CANDIDATES["ensemble_epsilon"]["sleeves"]]
    assert epsilon == ["MES_MOM_1c", "MNQ_VOL_1c", "MNQ_E57_1c"]
    one_contract = {k: v for k, v in ep.CANDIDATES["ensemble_epsilon"]["sleeves"][0].items() if k != "name"}
    assert one_contract == {**sleeves["MES_MOM_2c"], "max_contracts": 1}
    assert sum(s["max_contracts"] for s in ep.CANDIDATES["portfolio_e"]["sleeves"]) == 5
    assert sum(s["max_contracts"] for s in ep.CANDIDATES["ensemble_epsilon"]["sleeves"]) == 3


def test_completed_bars_exclude_the_forming_interval():
    stamps = pd.date_range("2026-11-06 14:00", periods=6, freq="1min", tz="UTC")
    bars = pd.DataFrame(dict(timestamp_utc=stamps, open=1.0, high=1.0, low=1.0, close=1.0, volume=1))
    now = pd.Timestamp("2026-11-06 14:06", tz="UTC")
    kept = ep.completed(bars, now)
    assert list(kept.timestamp_utc) == list(stamps[:4])


def test_aggregate_requires_all_fifteen_source_minutes():
    stamps = pd.date_range("2026-11-06 14:00", periods=45, freq="1min", tz="UTC")
    bars = pd.DataFrame(dict(timestamp_utc=stamps, open=np.arange(45.0), high=np.arange(45.0) + 1, low=np.arange(45.0) - 1,
                             close=np.arange(45.0) + 0.5, volume=1))
    bars = bars.drop(index=20)  # second bucket loses one minute
    out = ep.aggregate(bars)
    assert list(out.timestamp_utc) == [stamps[0], stamps[30]]
    first = out.iloc[0]
    assert (first.open, first.high, first.low, first.close, first.volume) == (0.0, 15.0, -1.0, 14.5, 15)


def test_bar_store_is_append_only_and_logs_revisions(tmp_path):
    store = ep.BarStore(tmp_path, "MES")
    stamps = pd.date_range("2026-11-06 14:00", periods=3, freq="5min", tz="UTC")
    first = pd.DataFrame(dict(timestamp_utc=stamps, open=1.0, high=2.0, low=0.5, close=1.5, volume=10))
    now = datetime(2026, 11, 6, 15, tzinfo=timezone.utc)
    assert store.append(first, now) == dict(added=3, revised=0, stored=3)
    second = first.copy()
    second.loc[1, "close"] = 9.0
    second = pd.concat([second, pd.DataFrame(dict(timestamp_utc=[stamps[-1] + pd.Timedelta(minutes=5)], open=1.0, high=2.0, low=0.5, close=1.5, volume=10))])
    assert store.append(second, now + timedelta(minutes=5)) == dict(added=1, revised=1, stored=4)
    stored = store.read()
    assert len(stored) == 4 and float(stored.loc[1, "close"]) == 1.5
    revisions = [json.loads(line) for line in store.revisions.read_text().splitlines()]
    assert len(revisions) == 1 and revisions[0]["seen"]["close"] == 9.0


def test_read_ledger_skips_incomplete_tail_and_duplicate_sequences(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"seq": 0, "kind": "run"}\n{"seq": 1, "kind": "trade"}\n{"seq": 1, "kind": "trade"}\n{"seq": 2, "kind": "ru')
    records = ep.read_ledger(path)
    assert [r["seq"] for r in records] == [0, 1]


def test_rerun_is_idempotent_and_extends_without_divergence(tmp_path):
    full = tmp_path / "full"
    full.mkdir()
    paths = write_sources(full, days=40)
    bars = pd.read_csv(paths["MES"])
    stamps = pd.to_datetime(bars.timestamp_utc, utc=True)
    cut = stamps.iloc[len(stamps) * 3 // 4]
    partial = tmp_path / "partial"
    partial.mkdir()
    partial_paths = write_sources(partial, days=40, through=cut)
    root = tmp_path / "paper"
    start = stamps.iloc[len(stamps) // 3].normalize()
    now1 = (cut + pd.Timedelta(hours=1)).to_pydatetime()
    first = ep.run_once(root, ep.FileSource(partial_paths), start, now=now1)
    second = ep.run_once(root, ep.FileSource(partial_paths), start, now=now1 + timedelta(hours=1))
    for key in ep.CANDIDATES:
        ledger = ep.read_ledger(root / key / "ledger.jsonl")
        kinds = [r["kind"] for r in ledger]
        assert kinds.count("run") == 2 and "divergence" not in kinds
        trades = [r for r in ledger if r["kind"] == "trade"]
        assert len(trades) == first["candidates"][key]["trades"] == second["candidates"][key]["trades"]
        assert first["candidates"][key]["net"] == second["candidates"][key]["net"]
    now3 = (stamps.iloc[-1] + pd.Timedelta(hours=1)).to_pydatetime()
    third = ep.run_once(root, ep.FileSource(paths), start, now=now3)
    for key in ep.CANDIDATES:
        ledger = ep.read_ledger(root / key / "ledger.jsonl")
        trades = [r for r in ledger if r["kind"] == "trade"]
        assert "divergence" not in [r["kind"] for r in ledger]
        assert len(trades) == third["candidates"][key]["trades"] >= second["candidates"][key]["trades"]
        assert all(ledger[i]["seq"] + 1 == ledger[i + 1]["seq"] for i in range(len(ledger) - 1))
        status = json.loads((root / key / "status.json").read_text())
        assert status["trades"] == len(trades)
        assert status["realized"] == pytest.approx(sum(t["net"] for t in trades), abs=0.01)
    assert (root / "dashboard.json").exists()


def test_revised_history_is_recorded_as_divergence_not_rewritten(tmp_path):
    folder = tmp_path / "src"
    folder.mkdir()
    paths = write_sources(folder, days=40, seed=3)
    bars = pd.read_csv(paths["MES"])
    stamps = pd.to_datetime(bars.timestamp_utc, utc=True)
    start = stamps.iloc[len(stamps) // 3].normalize()
    now = (stamps.iloc[-1] + pd.Timedelta(hours=1)).to_pydatetime()
    root = tmp_path / "paper"
    first = ep.run_once(root, ep.FileSource(paths), start, now=now, candidates=["ensemble_beta"])
    assert first["candidates"]["ensemble_beta"]["trades"] > 0
    store = ep.BarStore(root / "bars", "MES").read()
    paper = store.timestamp_utc >= start
    noise = 1 + np.random.default_rng(9).normal(0, 0.004, int(paper.sum()))
    for column in ("open", "high", "low", "close"):
        store.loc[paper, column] = np.round(store.loc[paper, column].to_numpy() * noise * 4) / 4
    store.to_csv(root / "bars" / "MES_1m.csv", index=False)
    second = ep.run_once(root, ep.FileSource(paths), start, now=now + timedelta(hours=1), candidates=["ensemble_beta"])
    ledger = ep.read_ledger(root / "ensemble_beta" / "ledger.jsonl")
    kinds = [r["kind"] for r in ledger]
    assert "divergence" in kinds
    assert second["candidates"]["ensemble_beta"]["divergences"] > 0
    trades_first = first["candidates"]["ensemble_beta"]["trades"]
    assert sum(1 for k in kinds if k == "trade") >= trades_first

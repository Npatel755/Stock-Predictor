import json
import time
import pandas as pd
import pytest
from quant_futures.config import ResearchConfig
from quant_futures.durable_paper import DurablePaperSession, read_ledger, watchdog_stream
from quant_futures.research import code_identity, json_write
from quant_futures.paper import PaperSession


def setup(tmp_path):
    receipt = tmp_path/"receipt.json"
    json_write(receipt, dict(passed=True, source_hash=code_identity()["source_hash"]))
    bundle = dict(candidate=dict(family="baseline", name="ema"), model=None, synthetic=True,
        config=ResearchConfig().model_dump(), source_hash=code_identity()["source_hash"])
    return receipt, bundle


def test_resume_preserves_account_features_pending_orders_and_ledger(bars, tmp_path):
    receipt, bundle = setup(tmp_path)
    output = tmp_path/"paper"
    session = DurablePaperSession(bundle, output, test_receipt=receipt, replay=True)
    expected = PaperSession(bundle, tmp_path/"expected", test_receipt=receipt, replay=True)
    for index, record in enumerate(bars.iloc[:40].to_dict("records")):
        expected.on_bar(record)
        session.on_bar(record)
        if index == 19:
            session = DurablePaperSession(bundle, output, test_receipt=receipt, replay=True, resume=True)
    ledger = read_ledger(output)
    assert len(ledger) == 40
    assert len(session.simulator.curve) == 1 and not session.simulator.trades
    assert session.simulator.cash == expected.simulator.cash
    assert session.simulator.pending == expected.simulator.pending
    assert session.simulator.broker.get_positions() == expected.simulator.broker.get_positions()
    assert [entry["curve"]["equity"] for entry in ledger] == [row["equity"] for row in expected.simulator.curve]
    assert len(session.feature_state.bars) == 40
    assert session.simulator.order_sequence == expected.simulator.order_sequence


def test_recovery_replays_wal_once_and_removes_torn_ledger_tail(bars, tmp_path):
    receipt, bundle = setup(tmp_path)
    output = tmp_path/"paper"
    session = DurablePaperSession(bundle, output, test_receipt=receipt, replay=True)
    session.on_bar(bars.iloc[0].to_dict())
    record = json.loads(bars.iloc[1:2].to_json(orient="records", date_format="iso"))[0]
    json_write(output/"pending_input.json", dict(sequence=2, record=record, now="2026-01-05T14:33Z"))
    with (output/"ledger.jsonl").open("a") as file:
        file.write('{"sequence":2,')
    resumed = DurablePaperSession(bundle, output, test_receipt=receipt, replay=True, resume=True)
    assert resumed.sequence == 2
    assert [entry["sequence"] for entry in read_ledger(output)] == [1, 2]
    assert not (output/"pending_input.json").exists()
    again = DurablePaperSession(bundle, output, test_receipt=receipt, replay=True, resume=True)
    assert again.sequence == 2 and len(read_ledger(output)) == 2


def test_watchdog_halts_without_arriving_data(bars, tmp_path):
    receipt, bundle = setup(tmp_path)
    session = DurablePaperSession(bundle, tmp_path/"paper", test_receipt=receipt, replay=True)
    class Stalled:
        def stream(self):
            time.sleep(.2)
            yield bars.iloc[0].to_dict()
    with pytest.raises(TimeoutError):
        list(watchdog_stream(Stalled(), session, timeout_seconds=.02))
    assert session.stopped and session.simulator.risk.killed
    with pytest.raises(PermissionError, match="Critical"):
        DurablePaperSession(bundle, tmp_path/"paper", test_receipt=receipt, replay=True, resume=True)


def test_resume_rejects_corrupted_checkpoint(tmp_path):
    receipt, bundle = setup(tmp_path)
    output = tmp_path/"paper"
    DurablePaperSession(bundle, output, test_receipt=receipt, replay=True)
    pointer = json.loads((output/"checkpoint.json").read_text())
    (output/f"checkpoint-{pointer['slot']}.joblib").write_bytes(b"broken")
    with pytest.raises(ValueError, match="checksum"):
        DurablePaperSession(bundle, output, test_receipt=receipt, replay=True, resume=True)


def test_checkpoint_retries_transient_windows_file_lock(tmp_path, monkeypatch):
    from pathlib import Path
    receipt, bundle = setup(tmp_path)
    original = Path.replace
    calls = []
    def sharing_lock_then_replace(self, target):
        if str(target).endswith(".joblib"):
            calls.append(target)
            if len(calls) < 3:
                raise PermissionError("Windows sharing lock")
        return original(self, target)
    monkeypatch.setattr(Path, "replace", sharing_lock_then_replace)
    session = DurablePaperSession(bundle, tmp_path/"paper", test_receipt=receipt, replay=True)
    assert len(calls) == 3
    resumed = DurablePaperSession(bundle, tmp_path/"paper", test_receipt=receipt, replay=True, resume=True)
    assert resumed.sequence == session.sequence == 0

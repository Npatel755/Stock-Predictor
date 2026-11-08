"""Local paper checkpoints, a write-ahead input record and bounded working state.

Checkpoint pickle files are trusted local artifacts, never third-party inputs.
The append-only ledger can contain a repeated sequence after a crash; consumers
must use read_ledger(), which returns one committed result per input sequence.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import queue
import threading
import time
from types import SimpleNamespace
import joblib
import pandas as pd
from .config import file_hash
from .data import canonical
from .paper import PaperSession, verify_test_receipt
from .research import code_identity, json_write


def read_ledger(output):
    entries = {}
    path = Path(output)/"ledger.jsonl"
    if path.exists():
        with path.open(encoding="utf-8") as stream:
            lines = stream.readlines()
        for index, line in enumerate(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                if index == len(lines)-1 and not line.endswith("\n"):
                    continue  # An interrupted append is not a committed record.
                raise
            entries[entry["sequence"]] = entry
    return [entries[key] for key in sorted(entries)]


class DurablePaperSession(PaperSession):
    def __init__(self, bundle, output, *, test_receipt, replay=False, maximum_data_age_seconds=120, resume=False):
        self.sequence, self.generation, self.slot = 0, -1, 1
        self.bundle_signature = joblib.hash(bundle)
        if not resume:
            super().__init__(bundle, output, test_receipt=test_receipt, replay=replay,
                maximum_data_age_seconds=maximum_data_age_seconds)
            self._checkpoint()
            return
        verify_test_receipt(test_receipt)
        if bundle.get("source_hash") != code_identity()["source_hash"]:
            raise PermissionError("Artifact and source version mismatch")
        self.output = Path(output)
        pointer = json.loads((self.output/"checkpoint.json").read_text())
        path = self.output/f"checkpoint-{pointer['slot']}.joblib"
        if file_hash(path) != pointer["sha256"] or pointer["bundle_signature"] != self.bundle_signature:
            raise ValueError("Checkpoint checksum or model identity mismatch")
        state = joblib.load(path)
        if state["source_hash"] != code_identity()["source_hash"] or state["replay"] != replay:
            raise PermissionError("Checkpoint source or execution mode changed")
        self.bundle, self.cfg = bundle, state["config"]
        self.simulator, self.feature_state = state["simulator"], state["features"]
        self.last, self.sequence = state["last"], state["sequence"]
        self.generation, self.slot = pointer["generation"], pointer["slot"]
        self.replay, self.maximum_age = replay, maximum_data_age_seconds
        self.stopped = state["stopped"]
        if self.simulator.risk.killed:
            raise PermissionError("Critical paper kill switch requires review; checkpoint cannot restart it")
        self.stopped = False  # Explicit resume is the recovery procedure for clean interruptions.
        self.reconnect()
        self._repair_ledger_tail()
        pending = self.output/"pending_input.json"
        if pending.exists():
            entry = json.loads(pending.read_text())
            if entry["sequence"] > self.sequence:
                self._process(entry, recovered=True)
            else:
                pending.unlink()

    def _checkpoint(self):
        slot, generation = 1-self.slot, self.generation+1
        path = self.output/f"checkpoint-{slot}.joblib"
        temporary = path.with_suffix(".tmp")
        for attribute in ("previous", "active_quote"):
            value = getattr(self.simulator, attribute)
            if hasattr(value, "_asdict"):
                setattr(self.simulator, attribute, SimpleNamespace(**value._asdict()))
        state = dict(source_hash=code_identity()["source_hash"], config=self.cfg,
            simulator=self.simulator, features=self.feature_state, last=self.last,
            sequence=self.sequence, stopped=self.stopped, replay=self.replay)
        with temporary.open("wb") as file:
            joblib.dump(state, file, compress=3)
            file.flush()
            os.fsync(file.fileno())
        for attempt in range(12):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if attempt == 11:
                    raise
                time.sleep(min(.025*2**attempt, .5))
        json_write(self.output/"checkpoint.json", dict(slot=slot, generation=generation,
            sequence=self.sequence, sha256=file_hash(path), bundle_signature=self.bundle_signature))
        self.slot, self.generation = slot, generation

    def _repair_ledger_tail(self):
        path = self.output/"ledger.jsonl"
        if not path.exists() or not path.stat().st_size:
            return
        with path.open("r+b") as file:
            file.seek(-1, os.SEEK_END)
            if file.read(1) == b"\n":
                return
            end = file.tell()
            while end:
                start = max(0, end-4096)
                file.seek(start)
                block = file.read(end-start)
                newline = block.rfind(b"\n")
                if newline >= 0:
                    file.truncate(start+newline+1)
                    break
                end = start
            else:
                file.truncate(0)
            file.flush()
            os.fsync(file.fileno())

    def _compact(self):
        self.simulator.curve = self.simulator.curve[-1:]
        self.simulator.trades.clear()
        self.simulator.broker.events.clear()
        self.simulator.broker.orders = {key: order for key, order in self.simulator.broker.orders.items()
            if order.status in ("accepted", "partial")}

    def _process(self, entry, recovered=False):
        if entry["sequence"] != self.sequence+1:
            raise ValueError("Noncontiguous paper input sequence")
        event = super().on_bar(entry["record"], now=entry["now"])
        ledger = dict(sequence=entry["sequence"], recovered_input=recovered, monitor=event,
            curve=self.simulator.curve[-1], trades=list(self.simulator.trades), events=list(self.simulator.broker.events))
        # Serialize before append, so an unserializable value cannot tear a line.
        line = json.dumps(ledger, default=str, allow_nan=False)+"\n"
        with (self.output/"ledger.jsonl").open("a", encoding="utf-8") as file:
            file.write(line)
            file.flush()
            os.fsync(file.fileno())
        self.sequence = entry["sequence"]
        self._compact()
        self._checkpoint()
        (self.output/"pending_input.json").unlink(missing_ok=True)
        return event

    def on_bar(self, record, now=None):
        if self.stopped:
            raise RuntimeError("Paper session is halted")
        now = pd.Timestamp(now or datetime.now(timezone.utc))
        try:
            clean = json.loads(canonical(pd.DataFrame([record])).to_json(orient="records", date_format="iso"))[0]
        except (ValueError, TypeError, KeyError):
            self.stop("invalid_data")
            raise
        entry = dict(sequence=self.sequence+1, record=clean, now=str(now))
        json_write(self.output/"pending_input.json", entry)
        try:
            return self._process(entry)
        except Exception:
            self.stop("paper_processing_failure")
            raise

    def stop(self, reason="shutdown"):
        super().stop(reason)
        self._checkpoint()

    def finish(self):
        # Forward paper shutdown preserves an open position and its raw entry.
        self.stop()
        return dict(sequence=self.sequence, positions=self.simulator.broker.get_positions(),
            cash=self.simulator.cash, ledger=str(self.output/"ledger.jsonl"))


def watchdog_stream(adapter, session, timeout_seconds=None):
    """Fail closed on a stalled producer even when its iterator blocks."""
    timeout_seconds = timeout_seconds or session.cfg.timeframe_minutes*60+session.maximum_age
    inbox = queue.Queue(maxsize=1)
    def produce():
        try:
            for record in adapter.stream():
                inbox.put(("bar", record))
        except Exception as error:
            inbox.put(("error", error))
        finally:
            inbox.put(("end", None))
    threading.Thread(target=produce, daemon=True, name="paper-data-reader").start()
    arrival = time.monotonic()
    while True:
        remaining = timeout_seconds-(time.monotonic()-arrival)
        if remaining <= 0:
            session.stop("market_data_timeout")
            raise TimeoutError("No completed market bar arrived before the paper feed timeout")
        try:
            kind, value = inbox.get(timeout=min(1, remaining))
        except queue.Empty:
            continue
        if kind == "end":
            return
        if kind == "error":
            session.stop("market_data_disconnection")
            raise value
        arrival = time.monotonic()
        yield value

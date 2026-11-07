from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
import json
import time
import joblib
import numpy as np
import pandas as pd
from .backtest import Simulator
from .config import ResearchConfig, file_hash
from .data import canonical, validate
from .features import build_features
from .stream_features import FeatureState
from .research import candidate_signal, code_identity, json_write


class MarketDataAdapter(ABC):
    """Providers must yield completed canonical bars; credentials stay external."""
    @abstractmethod
    def connect(self): ...
    @abstractmethod
    def stream(self): ...
    @abstractmethod
    def close(self): ...


class ReplayAdapter(MarketDataAdapter):
    def __init__(self, bars):
        self.bars, self.connected = canonical(bars), False

    def connect(self):
        self.connected = True

    def stream(self):
        if not self.connected:
            raise ConnectionError("Data adapter disconnected")
        yield from self.bars.to_dict("records")

    def close(self):
        self.connected = False


class JsonLinesAdapter(MarketDataAdapter):
    """Read a completed-bar JSONL spool or stdin written by an authorized provider.

    EOF is a clean shutdown, not an implicit reconnect. Reconnection is explicit
    through PaperSession.reconnect, requires contiguous data and reconciliation.
    """
    def __init__(self, file):
        self.file, self.connected = file, False

    def connect(self):
        self.connected = True

    def stream(self):
        if not self.connected:
            raise ConnectionError("Data adapter disconnected")
        for line in self.file:
            if line.strip():
                yield json.loads(line)

    def close(self):
        self.connected = False


def verify_test_receipt(path):
    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    if not receipt.get("passed") or receipt.get("source_hash") != code_identity()["source_hash"]:
        raise PermissionError("Passing tests for the current source are required before paper operation")
    return receipt


class PaperSession:
    def __init__(self, bundle, output, *, test_receipt, replay=False, maximum_data_age_seconds=120):
        verify_test_receipt(test_receipt)
        if bundle.get("source_hash") != code_identity()["source_hash"]:
            raise PermissionError("Artifact and feature source version mismatch")
        self.bundle, self.replay = bundle, replay
        self.cfg = ResearchConfig.model_validate(bundle["config"])
        self.simulator = Simulator(self.cfg)
        self.feature_state = FeatureState(self.cfg.timeframe_minutes)
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.maximum_age = maximum_data_age_seconds
        self.last = None
        self.stopped = False

    def on_bar(self, record, now=None):
        if self.stopped:
            raise RuntimeError("Paper session is halted; explicit new session and review required")
        b, report = validate(pd.DataFrame([record]))
        if report["fatal"]:
            self.stop("invalid_data")
            raise ValueError("Invalid streaming market data")
        bar = b.iloc[0]
        close_time = bar.timestamp_utc+pd.Timedelta(minutes=self.cfg.timeframe_minutes)
        now = pd.Timestamp(now or datetime.now(timezone.utc))
        if not self.replay and (now < close_time or (now-close_time).total_seconds() > self.maximum_age):
            self.stop("stale_or_unfinished_data")
            raise ValueError("Stale or unfinished streaming bar")
        if self.last is not None and bar.timestamp_utc <= self.last:
            self.stop("duplicate_timestamp")
            raise ValueError("Duplicate or out-of-order bar")
        self.last = bar.timestamp_utc
        start = time.perf_counter()
        self.feature_state.update(b.iloc[0].to_dict())
        history, f = self.feature_state.frames()
        signals = candidate_signal(self.bundle["candidate"], history, f, self.cfg, self.bundle["model"])
        signal = int(signals.iloc[-1])
        state = self.simulator.step(next(b.itertuples(index=False)), signal)
        probability = None
        if self.bundle["model"] is not None:
            probability = float(self.bundle["model"].predict_probability(f.iloc[-1:])[0])
        event = dict(mode="historical_paper_replay" if self.replay else "paper", synthetic_model=self.bundle.get("synthetic", True),
            timestamp=str(bar.timestamp_utc), signal=signal, probability=probability,
            inference_seconds=time.perf_counter()-start, data_age_seconds=(now-close_time).total_seconds(),
            equity=state["equity"], cash=state["cash"], unrealized_pnl=state["equity"]-state["cash"],
            position=state["quantity"], risk_locked=self.simulator.risk.killed or self.simulator.risk.day_locked,
            risk_reason=self.simulator.risk.reason)
        with open(self.output/"monitor.jsonl", "a", encoding="utf-8") as file:
            file.write(json.dumps(event)+"\n")
        json_write(self.output/"state.json", event)
        return event

    def reconnect(self):
        if self.simulator.risk.killed:
            raise PermissionError("Critical kill switch requires review; automatic recovery forbidden")
        expected = {self.simulator.position.contract: self.simulator.position.side*self.simulator.position.quantity} if self.simulator.position else {}
        self.simulator.broker.reconcile(expected)
        self.simulator.broker.connect()

    def stop(self, reason="shutdown"):
        self.stopped = True
        self.simulator.pending = None
        self.simulator.broker.disconnect()
        if reason != "shutdown":
            self.simulator.risk.kill(reason)
        # Preserve open-position state; never invent a shutdown fill without a quote.
        json_write(self.output/"shutdown.json", dict(reason=reason, positions=self.simulator.broker.get_positions(),
            emergency_review_required=reason != "shutdown"))

    def finish(self):
        if self.replay:
            result = self.simulator.finish()
            result["curve"].to_parquet(self.output/"paper_equity.parquet", index=False)
            result["trades"].to_parquet(self.output/"paper_trades.parquet", index=False)
            if (self.output/"state.json").exists():
                state = json.loads((self.output/"state.json").read_text(encoding="utf-8"))
                state.update(position=0, equity=self.simulator.cash, cash=self.simulator.cash,
                    unrealized_pnl=0, terminal_accounting_close=True, replay_complete=True)
                json_write(self.output/"state.json", state)
        else:
            result = dict(curve=pd.DataFrame(self.simulator.curve), trades=pd.DataFrame(self.simulator.trades), events=self.simulator.broker.events)
        json_write(self.output/"orders_and_fills.json", result["events"])
        self.stop()
        return result


def feature_drift(reference, current):
    common = reference.select_dtypes(include="number").columns.intersection(current.columns)
    scale = reference[common].std().replace(0, np.nan)
    return ((current[common].mean()-reference[common].mean()).abs()/scale).dropna().to_dict()


def compare_paper_backtest(paper, expected):
    return dict(net_equity_difference=float(paper["curve"].equity.iloc[-1]-expected["curve"].equity.iloc[-1]),
        trade_count_difference=len(paper["trades"])-len(expected["trades"]),
        accounting_matches=bool(np.isclose(paper["curve"].equity.iloc[-1], expected["curve"].equity.iloc[-1])))

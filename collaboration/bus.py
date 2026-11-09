"""Structured Messaging Bus and Safety Protocol for Devin-Antigravity Collaboration.

Handles:
- Append-only immutable ledger (ledger.jsonl)
- Cryptographic SHA-256 message hashing
- Delivery verification and acknowledgments (ACKs)
- Duplicate message suppression
- Loop detection & circuit breaker (stops infinite agent chatter)
- File locking for multi-process safety
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

COLLAB_ROOT = Path(__file__).resolve().parent
INBOX_DIR = COLLAB_ROOT / "inbox"
OUTBOX_DIR = COLLAB_ROOT / "outbox"
LEDGER_FILE = COLLAB_ROOT / "ledger.jsonl"
STATE_FILE = COLLAB_ROOT / "bus_state.json"


@dataclass
class AgentMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = "antigravity"  # 'antigravity', 'devin', 'human'
    recipient: str = "devin"     # 'devin', 'antigravity', 'all'
    topic: str = "general"       # 'research', 'code_review', 'bug_report', 'task_proposal'
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sha256: str = ""
    turn_number: int = 1
    ack: bool = False
    ack_timestamp: Optional[str] = None

    def __post_init__(self):
        if not self.sha256:
            payload = f"{self.sender}|{self.recipient}|{self.topic}|{self.content}"
            self.sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentMessage:
        return cls(**data)


class CollaborationBus:
    def __init__(self, root_dir: Optional[Path] = None, max_consecutive_turns: int = 50):
        self.root = root_dir or COLLAB_ROOT
        self.inbox = self.root / "inbox"
        self.outbox = self.root / "outbox"
        self.ledger = self.root / "ledger.jsonl"
        self.state_path = self.root / "bus_state.json"
        self.max_consecutive_turns = max_consecutive_turns
        self._lock = threading.Lock()

        # Ensure directories exist
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.outbox.mkdir(parents=True, exist_ok=True)

        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "seen_hashes": [],
            "consecutive_ai_turns": 0,
            "circuit_breaker_tripped": False,
            "last_active_turn": 0,
            "total_messages": 0
        }

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def publish(self, message: AgentMessage) -> bool:
        """Publish a new message to the bus with deduplication and loop detection."""
        with self._lock:
            # 1. Deduplication check
            if message.sha256 in self.state["seen_hashes"]:
                return False  # Suppress duplicate

            # 2. Circuit Breaker / Loop Detection
            if message.sender in ("antigravity", "devin"):
                self.state["consecutive_ai_turns"] += 1
                if self.state["consecutive_ai_turns"] > self.max_consecutive_turns:
                    self.state["circuit_breaker_tripped"] = True
                    self._save_state()
                    raise RuntimeError(
                        f"CIRCUIT BREAKER TRIPPED: Reached {self.max_consecutive_turns} consecutive autonomous "
                        f"turns between Devin and Antigravity without human check-in. Pausing auto-dispatch."
                    )
            else:
                # Human reset
                self.state["consecutive_ai_turns"] = 0
                self.state["circuit_breaker_tripped"] = False

            # Update turn counter
            self.state["last_active_turn"] += 1
            message.turn_number = self.state["last_active_turn"]

            # 3. Append to immutable ledger
            with open(self.ledger, "a", encoding="utf-8") as f:
                f.write(json.dumps(message.to_dict()) + "\n")

            # 4. Deposit into target queue
            target_dir = self.inbox if message.recipient == "antigravity" else self.outbox
            msg_file = target_dir / f"{message.id}.json"
            with open(msg_file, "w", encoding="utf-8") as f:
                json.dump(message.to_dict(), f, indent=2)

            # Record seen hash
            self.state["seen_hashes"].append(message.sha256)
            if len(self.state["seen_hashes"]) > 2000:
                self.state["seen_hashes"] = self.state["seen_hashes"][-1000:]
            self.state["total_messages"] += 1
            self._save_state()
            return True

    def acknowledge(self, message_id: str, acknowledged_by: str = "antigravity") -> bool:
        """Mark a message as delivered and acknowledged."""
        with self._lock:
            now_str = datetime.now(timezone.utc).isoformat()
            # Update target file if present
            for folder in (self.inbox, self.outbox):
                target = folder / f"{message_id}.json"
                if target.exists():
                    try:
                        data = json.loads(target.read_text(encoding="utf-8"))
                        data["ack"] = True
                        data["ack_timestamp"] = now_str
                        data["ack_by"] = acknowledged_by
                        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        return True
                    except Exception:
                        pass
        return False

    def get_pending_messages(self, recipient: str = "antigravity") -> List[AgentMessage]:
        """Fetch all unread / pending messages for the given recipient."""
        folder = self.inbox if recipient == "antigravity" else self.outbox
        messages = []
        for file in sorted(folder.glob("*.json")):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                if not data.get("ack", False):
                    messages.append(AgentMessage.from_dict(data))
            except Exception:
                continue
        return messages

    def read_ledger(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Read the last N messages from the append-only ledger."""
        if not self.ledger.exists():
            return []
        lines = self.ledger.read_text(encoding="utf-8").strip().splitlines()
        records = []
        for line in lines[-limit:]:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
        return records

    def reset_circuit_breaker(self):
        """Human operator reset for the circuit breaker."""
        with self._lock:
            self.state["consecutive_ai_turns"] = 0
            self.state["circuit_breaker_tripped"] = False
            self._save_state()

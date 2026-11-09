"""Autonomous Devin-Antigravity Synchronization Daemon.

Runs continuously in the background to:
1. Detect outbound messages from Antigravity -> Devin, dispatching via the Devin API.
2. Poll Devin's session for replies -> deposit into Antigravity's inbox.
3. Enforce loop detection, delivery acks, and immutable ledger recording.
4. Provide a heartbeat and graceful shutdown.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Optional

COLLAB_ROOT = Path(__file__).resolve().parent
if str(COLLAB_ROOT) not in sys.path:
    sys.path.insert(0, str(COLLAB_ROOT))

from bus import AgentMessage, CollaborationBus
from devin_client import DevinAPIError, DevinClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [BridgeDaemon] %(message)s",
    handlers=[
        logging.FileHandler(COLLAB_ROOT / "bridge.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BridgeDaemon")


class BridgeDaemon:
    def __init__(self, config_path: Optional[Path] = None, mock_mode: bool = False):
        self.config_path = config_path or (COLLAB_ROOT / "config.json")
        self.config = self._load_config()
        self.bus = CollaborationBus(root_dir=COLLAB_ROOT, max_consecutive_turns=self.config.get("max_consecutive_autonomous_turns", 10))
        self.mock_mode = mock_mode
        self.client = DevinClient(
            api_key=self.config.get("api_key") or "apk_user_dXNlci0xZGU5NTg0NTI1Zjk0NTg4YmI1MmRhN2FlZTA4ZGU1Y19vcmctYTdmMzYzMGZjOTRjNGIwOWEwZDlhN2QzNGNlMjU3YTE6NjcwYjUwYTE5OGQxNGQ2YjlkZTEwOTcwZGZlZjgxNzA=",
            base_url=self.config.get("api_base_url", "https://api.devin.ai/v1"),
            timeout=self.config.get("request_timeout_seconds", 30),
            max_retries=self.config.get("max_retries", 3),
            backoff_factor=self.config.get("retry_backoff_factor", 2.0),
            org_id=self.config.get("organization_id")
        )
        self.session_id = self.config.get("active_session_id")
        self.polling_interval = self.config.get("polling_interval_seconds", 10)
        self.running = False
        self._last_devin_message_id = None

    def _load_config(self) -> dict:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed to parse config: {e}")
        return {}

    def sync_outbox_to_devin(self):
        """Send pending messages from Antigravity -> Devin."""
        pending = self.bus.get_pending_messages(recipient="devin")
        for msg in pending:
            logger.info(f"Dispatching message {msg.id[:8]} to Devin (Topic: {msg.topic})...")
            if self.mock_mode or not self.client.is_authenticated:
                logger.info(f"[SIMULATED DISPATCH] Devin received: '{msg.content[:60]}...'")
                self.bus.acknowledge(msg.id, acknowledged_by="mock_devin")
                continue

            if not self.session_id:
                logger.warning("No active_session_id configured. Cannot dispatch live to Devin.")
                continue

            try:
                res = self.client.send_message(self.session_id, msg.content)
                logger.info(f"Delivered to Devin API. Response: {res}")
                self.bus.acknowledge(msg.id, acknowledged_by="devin_api")
            except DevinAPIError as e:
                logger.error(f"Failed to send to Devin: {e}")

    def sync_devin_to_inbox(self):
        """Poll Devin session for new messages -> deposit into Antigravity inbox."""
        if self.mock_mode or not self.client.is_authenticated:
            return

        if not self.session_id:
            return

        try:
            session = self.client.get_session(self.session_id)
            messages = session.get("messages", [])
            if not messages:
                return

            last_msg = messages[-1]
            msg_id = last_msg.get("event_id") or last_msg.get("id") or str(hash(str(last_msg)))
            msg_type = last_msg.get("type") or last_msg.get("role") or ""

            # Only process if message is from Devin and new
            if msg_type in ("devin_message", "assistant") and msg_id != self._last_devin_message_id:
                self._last_devin_message_id = msg_id
                content = last_msg.get("message") or last_msg.get("content") or last_msg.get("text", "")
                if content:
                    logger.info(f"New message from Devin detected: '{content[:60]}...'")
                    agent_msg = AgentMessage(
                        sender="devin",
                        recipient="antigravity",
                        topic="collaboration_update",
                        content=content,
                        metadata={"devin_session_id": self.session_id, "devin_message_id": msg_id}
                    )
                    try:
                        published = self.bus.publish(agent_msg)
                        if published:
                            logger.info(f"Message {agent_msg.id[:8]} deposited into Antigravity inbox.")
                    except RuntimeError as e:
                        logger.warning(f"Loop protection triggered: {e}")
        except DevinAPIError as e:
            logger.error(f"Error polling Devin session: {e}")

    def run_once(self):
        """Single synchronization pass."""
        self.sync_outbox_to_devin()
        self.sync_devin_to_inbox()
        try:
            from sync_chat_histories import run_sync_pass
            run_sync_pass()
        except Exception as e:
            logger.error(f"Error syncing perpetual chat histories: {e}")

    def run_loop(self):
        """Continuous background execution loop."""
        self.running = True
        logger.info(f"Bridge Daemon started (Polling: {self.polling_interval}s, Mock: {self.mock_mode})")
        try:
            while self.running:
                self.run_once()
                time.sleep(self.polling_interval)
        except KeyboardInterrupt:
            logger.info("Bridge Daemon stopping gracefully...")
        finally:
            self.running = False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Devin-Antigravity Collaboration Bridge Daemon")
    parser.add_argument("--once", action="store_true", help="Run a single sync pass and exit")
    parser.add_argument("--mock", action="store_true", help="Run in mock/offline mode")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds")
    args = parser.parse_args()

    daemon = BridgeDaemon(mock_mode=args.mock)
    if args.interval:
        daemon.polling_interval = args.interval

    if args.once:
        daemon.run_once()
    else:
        daemon.run_loop()

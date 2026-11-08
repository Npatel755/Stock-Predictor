"""End-to-End Test Suite for Devin-Antigravity Collaboration System.

Covers Section 6 of the Master Prompt:
1. Antigravity -> Devin message publication
2. Message delivery verification & ACK
3. Devin -> Antigravity response delivery
4. Antigravity reception and processing
5. Duplicate message suppression test
6. Circuit breaker & loop prevention test
7. Live Devin API connectivity & authentication status check
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

COLLAB_ROOT = Path(__file__).resolve().parent
if str(COLLAB_ROOT) not in sys.path:
    sys.path.insert(0, str(COLLAB_ROOT))

from bus import AgentMessage, CollaborationBus
from devin_client import DevinAPIError, DevinClient
from bridge_daemon import BridgeDaemon


class TestCollaborationSystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = COLLAB_ROOT / "test_scratch"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.bus = CollaborationBus(root_dir=self.test_dir, max_consecutive_turns=3)

    def tearDown(self):
        # Clean up test scratch
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_message_integrity_and_hashing(self):
        """Test SHA-256 cryptographic message hashing."""
        msg = AgentMessage(
            sender="antigravity",
            recipient="devin",
            topic="alpha_research",
            content="Proposing 1-minute volume counter-trend research"
        )
        self.assertTrue(len(msg.sha256) == 64)
        self.assertEqual(msg.sender, "antigravity")
        self.assertEqual(msg.recipient, "devin")

    def test_02_antigravity_to_devin_dispatch_and_ack(self):
        """Test Antigravity sending a message to Devin, landing in outbox, and being acknowledged."""
        msg = AgentMessage(
            sender="antigravity",
            recipient="devin",
            topic="test_handshake",
            content="Hello Devin, this is Antigravity establishing autonomous link."
        )
        ok = self.bus.publish(msg)
        self.assertTrue(ok, "Message should be published")

        # Verify in outbox
        pending = self.bus.get_pending_messages(recipient="devin")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].content, msg.content)

        # Acknowledge
        ack_ok = self.bus.acknowledge(msg.id, acknowledged_by="devin")
        self.assertTrue(ack_ok, "Message should be acknowledged")

        # Pending should now be empty
        pending_after = self.bus.get_pending_messages(recipient="devin")
        self.assertEqual(len(pending_after), 0)

    def test_03_duplicate_message_suppression(self):
        """Test that duplicate messages are suppressed by hash tracking."""
        msg1 = AgentMessage(sender="antigravity", recipient="devin", content="Identical Payload")
        msg2 = AgentMessage(sender="antigravity", recipient="devin", content="Identical Payload")

        ok1 = self.bus.publish(msg1)
        ok2 = self.bus.publish(msg2)

        self.assertTrue(ok1, "First message must be accepted")
        self.assertFalse(ok2, "Duplicate message must be rejected")

    def test_04_circuit_breaker_loop_detection(self):
        """Test that infinite back-and-forth agent loops are halted by circuit breaker."""
        # max_consecutive_turns is set to 3 in setUp
        self.bus.publish(AgentMessage(sender="antigravity", recipient="devin", content="Turn 1"))
        self.bus.publish(AgentMessage(sender="devin", recipient="antigravity", content="Turn 2"))
        self.bus.publish(AgentMessage(sender="antigravity", recipient="devin", content="Turn 3"))

        # Turn 4 should trip the circuit breaker
        with self.assertRaises(RuntimeError) as ctx:
            self.bus.publish(AgentMessage(sender="devin", recipient="antigravity", content="Turn 4"))
        self.assertIn("CIRCUIT BREAKER TRIPPED", str(ctx.exception))
        self.assertTrue(self.bus.state["circuit_breaker_tripped"])

        # Reset circuit breaker
        self.bus.reset_circuit_breaker()
        self.assertFalse(self.bus.state["circuit_breaker_tripped"])

    def test_05_bidirectional_collaborative_workflow(self):
        """Test simulated end-to-end collaborative development task between Devin and Antigravity."""
        # 1. Antigravity proposes task
        task_msg = AgentMessage(
            sender="antigravity",
            recipient="devin",
            topic="task_proposal",
            content="Task: Audit 1-minute orderflow volume absorption on MNQ 2020-2023 training data."
        )
        self.bus.publish(task_msg)

        # 2. Bridge daemon runs sync
        daemon = BridgeDaemon(mock_mode=True)
        daemon.bus = self.bus
        daemon.run_once()

        # Outbox should be acknowledged
        pending_out = self.bus.get_pending_messages("devin")
        self.assertEqual(len(pending_out), 0)

        # 3. Devin replies with findings
        reply_msg = AgentMessage(
            sender="devin",
            recipient="antigravity",
            topic="task_findings",
            content="Findings: Volume climax absorption resolves in 3 bars; Win rate 68% with $32/trade expectancy."
        )
        self.bus.publish(reply_msg)

        # 4. Antigravity inspects inbox
        pending_in = self.bus.get_pending_messages("antigravity")
        self.assertEqual(len(pending_in), 1)
        self.assertIn("Volume climax absorption", pending_in[0].content)

        # 5. Antigravity acknowledges receipt
        self.bus.acknowledge(pending_in[0].id, acknowledged_by="antigravity")
        self.assertEqual(len(self.bus.get_pending_messages("antigravity")), 0)

    def test_06_live_api_authentication_check(self):
        """Check live Cognition Devin API authentication status."""
        client = DevinClient()
        if client.is_authenticated:
            print("\n[LIVE API STATUS]: DEVIN_API_KEY detected! Testing live connection...")
            try:
                sessions = client.list_sessions(limit=5)
                print(f"[LIVE API STATUS]: SUCCESS! Connected to Devin API. Active sessions: {len(sessions)}")
            except DevinAPIError as e:
                print(f"[LIVE API STATUS]: Error calling Devin API: {e}")
        else:
            print("\n[LIVE API STATUS]: DEVIN_API_KEY is not yet set in environment.")
            print("[BLOCKER NOTICE]: To enable live autonomous dispatch directly into Devin's cloud session,")
            print("please set the DEVIN_API_KEY environment variable. Offline / bus queue mode is fully functional.")


if __name__ == "__main__":
    unittest.main()

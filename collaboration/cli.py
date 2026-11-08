"""Command-Line Interface for Devin-Antigravity Collaboration Bus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

COLLAB_ROOT = Path(__file__).resolve().parent
if str(COLLAB_ROOT) not in sys.path:
    sys.path.insert(0, str(COLLAB_ROOT))

from bus import AgentMessage, CollaborationBus


def cmd_send(args, bus: CollaborationBus):
    msg = AgentMessage(
        sender=args.sender,
        recipient=args.recipient,
        topic=args.topic,
        content=args.message,
        metadata={"cli": True}
    )
    try:
        ok = bus.publish(msg)
        if ok:
            print(f"Message published successfully! ID: {msg.id} (Turn #{msg.turn_number})")
        else:
            print(f"Message suppressed as duplicate. (SHA256: {msg.sha256[:12]}...)")
    except RuntimeError as e:
        print(f"Error publishing message: {e}")
        sys.exit(1)


def cmd_pending(args, bus: CollaborationBus):
    pending = bus.get_pending_messages(recipient=args.recipient)
    if not pending:
        print(f"No pending messages for '{args.recipient}'.")
        return
    print(f"--- Pending Messages for {args.recipient.upper()} ({len(pending)}) ---")
    for m in pending:
        print(f"[{m.timestamp[:19]}] ID: {m.id[:8]} | From: {m.sender} | Topic: {m.topic} | ACK: {m.ack}")
        print(f"Content: {m.content}\n" + "-"*60)


def cmd_ack(args, bus: CollaborationBus):
    ok = bus.acknowledge(args.message_id, acknowledged_by=args.by)
    if ok:
        print(f"Message {args.message_id} acknowledged by {args.by}.")
    else:
        print(f"Message {args.message_id} not found in pending queues.")


def cmd_status(args, bus: CollaborationBus):
    state = bus.state
    print("==================================================")
    print("COLLABORATION BUS STATUS")
    print("==================================================")
    print(f"Total Messages Logged     : {state.get('total_messages', 0)}")
    print(f"Last Active Turn          : #{state.get('last_active_turn', 0)}")
    print(f"Consecutive AI Turns      : {state.get('consecutive_ai_turns', 0)} / {bus.max_consecutive_turns}")
    print(f"Circuit Breaker Tripped   : {state.get('circuit_breaker_tripped', False)}")
    print(f"Unique Seen Hashes        : {len(state.get('seen_hashes', []))}")

    pending_ag = len(bus.get_pending_messages('antigravity'))
    pending_devin = len(bus.get_pending_messages('devin'))
    print(f"Pending for Antigravity   : {pending_ag}")
    print(f"Pending for Devin         : {pending_devin}")


def cmd_log(args, bus: CollaborationBus):
    records = bus.read_ledger(limit=args.limit)
    print(f"=== Last {len(records)} Events in Collaboration Ledger ===")
    for r in records:
        print(f"Turn #{r.get('turn_number', '?'):<2} | [{r.get('timestamp')[:19]}] {r.get('sender').upper()} -> {r.get('recipient').upper()} [{r.get('topic')}]")
        print(f"   {r.get('content')[:120]}...\n")


def cmd_reset_breaker(args, bus: CollaborationBus):
    bus.reset_circuit_breaker()
    print("Circuit breaker has been reset by human operator.")


def main():
    parser = argparse.ArgumentParser(description="Devin-Antigravity Collaboration CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # send
    p_send = sub.add_parser("send", help="Send a message to an agent")
    p_send.add_argument("message", help="Message body")
    p_send.add_argument("--sender", default="antigravity", choices=["antigravity", "devin", "human"])
    p_send.add_argument("--recipient", default="devin", choices=["devin", "antigravity", "all"])
    p_send.add_argument("--topic", default="trading_research", help="Message topic")

    # pending
    p_pend = sub.add_parser("pending", help="List pending un-acknowledged messages")
    p_pend.add_argument("--recipient", default="antigravity", choices=["antigravity", "devin"])

    # ack
    p_ack = sub.add_parser("ack", help="Acknowledge a received message")
    p_ack.add_argument("message_id", help="UUID of the message to acknowledge")
    p_ack.add_argument("--by", default="antigravity", help="Agent name acknowledging")

    # status
    sub.add_parser("status", help="Display collaboration system health and state")

    # log
    p_log = sub.add_parser("log", help="Display recent ledger communication events")
    p_log.add_argument("--limit", type=int, default=20)

    # reset-circuit-breaker
    sub.add_parser("reset-circuit-breaker", help="Reset the autonomous turn circuit breaker")

    args = parser.parse_args()
    bus = CollaborationBus()

    if args.cmd == "send":
        cmd_send(args, bus)
    elif args.cmd == "pending":
        cmd_pending(args, bus)
    elif args.cmd == "ack":
        cmd_ack(args, bus)
    elif args.cmd == "status":
        cmd_status(args, bus)
    elif args.cmd == "log":
        cmd_log(args, bus)
    elif args.cmd == "reset-circuit-breaker":
        cmd_reset_breaker(args, bus)


if __name__ == "__main__":
    main()

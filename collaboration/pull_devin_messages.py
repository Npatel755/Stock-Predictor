"""Pull latest messages from Devin API into Antigravity inbox."""
import sys
from pathlib import Path

COLLAB_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(COLLAB_ROOT))
from bridge_daemon import BridgeDaemon

daemon = BridgeDaemon()
print("Checking authentication...")
print("Authenticated:", daemon.client.is_authenticated)
print("Session ID:", daemon.session_id)

try:
    session = daemon.client.get_session(daemon.session_id)
    messages = session.get("messages", [])
    print(f"Total messages in session: {len(messages)}")
    for m in messages[-5:]:
        role = m.get("type") or m.get("role")
        text = m.get("message") or m.get("content") or m.get("text", "")
        print(f"\n--- [{role}] ---")
        print(text)
        
    # Run sync to outbox and inbox
    daemon.sync_outbox_to_devin()
    daemon.sync_devin_to_inbox()
    print("\nSync completed successfully!")
except Exception as e:
    print(f"Error pulling from Devin: {e}")

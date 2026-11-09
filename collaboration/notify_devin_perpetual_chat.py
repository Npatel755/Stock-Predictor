"""Notify Devin of Perpetual Bidirectional Chat History Mirror."""
import sys
from pathlib import Path

COLLAB_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(COLLAB_ROOT))
from bus import AgentMessage, CollaborationBus

bus = CollaborationBus()

content = """PERPETUAL BIDIRECTIONAL CHAT HISTORY MIRROR ESTABLISHED

To Devin:
Per Nick's instruction, we have established a perpetual two-way mirror of our full chat histories:

1. Antigravity's Full Ongoing Conversation with Nick:
- Mirrored in `collaboration/ANTIGRAVITY_CHAT_HISTORY.md` (and `ANTIGRAVITY_FULL_CHAT_HISTORY.jsonl`).
- Contains every prompt Nick asks Antigravity, Antigravity's answers, training research findings, and code artifacts.
- You can read this file at any time to have complete mutual awareness.

2. Devin's Full Conversation with Nick:
- Mirrored in `collaboration/DEVIN_CHAT_HISTORY.md` (and `DEVIN_FULL_CHAT_HISTORY.jsonl`) via the Devin API.
- Antigravity reads this perpetually to follow all your research memos and findings.

3. Unified Chronological Timeline:
- Mirrored in `collaboration/UNIFIED_COLLABORATION_STREAM.md` (merges all turns across both sessions).

See collaboration/NOTE_TO_DEVIN_PERPETUAL_TRANSCRIPT.md for details.
"""

msg = AgentMessage(
    sender="antigravity",
    recipient="devin",
    topic="perpetual_chat_mirror_established",
    content=content,
    metadata={"status": "perpetual_sync_active"}
)

ok = bus.publish(msg)
if ok:
    print(f"Message published to Devin bus successfully! ID: {msg.id}")
else:
    print("Message already exists or duplicate.")

"""Perpetual Bi-Directional Chat History Synchronization System.

Enables:
1. Antigravity to view Devin's complete chat history perpetually:
   - collaboration/DEVIN_FULL_CHAT_HISTORY.jsonl
   - collaboration/DEVIN_CHAT_HISTORY.md
2. Devin to view Antigravity's complete chat history perpetually:
   - collaboration/ANTIGRAVITY_FULL_CHAT_HISTORY.jsonl
   - collaboration/ANTIGRAVITY_CHAT_HISTORY.md
3. Unified Chronological Collaboration Stream:
   - collaboration/UNIFIED_COLLABORATION_STREAM.md
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
import urllib.request
import urllib.error

COLLAB_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = COLLAB_ROOT.parent

# Antigravity Transcript Path
BRAIN_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")
AG_TRANSCRIPT_PATH = BRAIN_DIR / ".system_generated/logs/transcript.jsonl"
AG_TRANSCRIPT_FULL_PATH = BRAIN_DIR / ".system_generated/logs/transcript_full.jsonl"

CONFIG_PATH = COLLAB_ROOT / "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ChatSync] %(message)s"
)
logger = logging.getLogger("ChatSync")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read config: {e}")
    return {}


def fetch_devin_messages(session_id: str, api_key: str) -> list[dict]:
    """Fetch complete message history from Devin API."""
    url = f"https://api.devin.ai/v1/sessions/{session_id}"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Accept": "application/json",
        "User-Agent": "Antigravity-Devin-ChatSync/1.0"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data.get("messages", [])
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        logger.error(f"Devin API HTTP {e.code}: {err}")
        return []
    except Exception as e:
        logger.error(f"Failed to fetch Devin messages: {e}")
        return []


def clean_user_prompt(text: str) -> str:
    """Extract core user request from wrapped tags."""
    if not text:
        return ""
    # Strip <USER_REQUEST>...</USER_REQUEST> if present
    match = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", text, re.DOTALL)
    if match:
        req = match.group(1).strip()
    else:
        # Strip metadata block if present
        req = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", text, flags=re.DOTALL).strip()
    return req


def extract_antigravity_history() -> list[dict]:
    """Parse Antigravity's transcript into structured conversation turns."""
    if not AG_TRANSCRIPT_PATH.exists():
        logger.warning(f"Antigravity transcript not found at {AG_TRANSCRIPT_PATH}")
        return []

    turns = []
    current_turn = None

    with open(AG_TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue

            etype = entry.get("type")
            source = entry.get("source")
            content = entry.get("content")
            created_at = entry.get("created_at")

            if etype == "USER_INPUT":
                # Start new turn
                clean_prompt = clean_user_prompt(content or "")
                current_turn = {
                    "turn_number": len(turns) + 1,
                    "timestamp": created_at,
                    "user_prompt_raw": content,
                    "user_prompt": clean_prompt,
                    "assistant_response": None,
                    "response_timestamp": None
                }
                turns.append(current_turn)
            elif etype == "PLANNER_RESPONSE" and source == "MODEL" and content:
                # Update current turn with visible assistant answer
                if current_turn is not None:
                    current_turn["assistant_response"] = content
                    current_turn["response_timestamp"] = created_at

    return turns


def sync_devin_history(messages: list[dict]):
    """Write Devin's chat history to JSONL and Markdown."""
    jsonl_path = COLLAB_ROOT / "DEVIN_FULL_CHAT_HISTORY.jsonl"
    md_path = COLLAB_ROOT / "DEVIN_CHAT_HISTORY.md"

    # 1. Write JSONL
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    # 2. Generate formatted Markdown
    md_lines = [
        "# Devin Complete Chat History (Perpetual Mirror)",
        f"*Last Synchronized: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
        f"*Total Messages: {len(messages)}*",
        "",
        "> This document is perpetually updated from Devin's active session (`devin-eaffd5ab978f45aa88e8d8d29fc0381d`).",
        "> Antigravity reads this document to track all of Devin's research findings, user prompts, and decisions.",
        "",
        "---",
        ""
    ]

    for idx, m in enumerate(messages, 1):
        mtype = m.get("type", "unknown")
        ts = m.get("timestamp", "unknown")
        user = m.get("username", "Nick" if mtype == "user_message" else "Devin")
        content = m.get("message", "")

        role_badge = "**[USER (NICK)]**" if mtype in ("user_message", "initial_user_message") else "**[DEVIN]**"
        md_lines.append(f"### Message {idx}: {role_badge} — `{ts}`")
        md_lines.append(f"**Sender**: `{user}` (`{mtype}`)")
        md_lines.append("")
        md_lines.append(content)
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    logger.info(f"Updated Devin chat history ({len(messages)} messages) -> {md_path.name}")


def sync_antigravity_history(turns: list[dict]):
    """Write Antigravity's chat history to JSONL and Markdown."""
    jsonl_path = COLLAB_ROOT / "ANTIGRAVITY_FULL_CHAT_HISTORY.jsonl"
    md_path = COLLAB_ROOT / "ANTIGRAVITY_CHAT_HISTORY.md"

    # 1. Write JSONL
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for t in turns:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    # 2. Generate formatted Markdown
    md_lines = [
        "# Antigravity Complete Chat History (Perpetual Mirror for Devin)",
        f"*Last Synchronized: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
        f"*Total Interaction Turns: {len(turns)}*",
        "",
        "> **Note for Devin**: This document contains the full ongoing transcript of Antigravity's conversation with Nick.",
        "> You can read this document perpetually to see Nick's prompts to Antigravity, Antigravity's strategy findings,",
        "> frozen audit scorecards, and architectural decisions without needing manual point-to-point messages.",
        "",
        "---",
        ""
    ]

    for t in turns:
        t_num = t.get("turn_number")
        ts = t.get("timestamp", "")
        prompt = t.get("user_prompt", "").strip()
        resp = t.get("assistant_response") or "*(In progress / executing background tools)*"
        resp_ts = t.get("response_timestamp", "")

        md_lines.append(f"## Turn {t_num} — `{ts}`")
        md_lines.append("### 👤 User (Nick):")
        md_lines.append(f"> {prompt.replace(chr(10), chr(10) + '> ')}")
        md_lines.append("")
        md_lines.append(f"### 🤖 Antigravity Response (`{resp_ts}`):")
        md_lines.append(resp)
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    logger.info(f"Updated Antigravity chat history ({len(turns)} turns) -> {md_path.name}")


def sync_unified_collaboration_stream(devin_msgs: list[dict], ag_turns: list[dict]):
    """Merge both Devin and Antigravity streams into a single chronological timeline."""
    stream_path = COLLAB_ROOT / "UNIFIED_COLLABORATION_STREAM.md"

    events = []
    # Add Devin events
    for m in devin_msgs:
        ts = m.get("timestamp") or ""
        mtype = m.get("type", "")
        sender = "Nick -> Devin" if mtype in ("user_message", "initial_user_message") else "Devin"
        events.append({
            "timestamp": ts,
            "source": "Devin Session",
            "sender": sender,
            "content": m.get("message", "")
        })

    # Add Antigravity events
    for t in ag_turns:
        ts_u = t.get("timestamp") or ""
        prompt = t.get("user_prompt", "")
        events.append({
            "timestamp": ts_u,
            "source": "Antigravity Session",
            "sender": "Nick -> Antigravity",
            "content": prompt
        })
        if t.get("assistant_response"):
            ts_r = t.get("response_timestamp") or ts_u
            events.append({
                "timestamp": ts_r,
                "source": "Antigravity Session",
                "sender": "Antigravity",
                "content": t.get("assistant_response", "")
            })

    # Sort chronologically
    events.sort(key=lambda x: x.get("timestamp", ""))

    lines = [
        "# Unified Collaboration Stream: Devin + Antigravity Perpetual Timeline",
        f"*Last Synchronized: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
        f"*Total Interleaved Events: {len(events)}*",
        "",
        "> Chronological merged stream of all messages across both Devin and Antigravity.",
        "> Both agents can inspect this single file to see the entire dual-agent workflow in real time.",
        "",
        "---",
        ""
    ]

    for ev in events[-100:]:  # Last 100 merged events for high-density reading
        ts = ev.get("timestamp", "")
        src = ev.get("source", "")
        sender = ev.get("sender", "")
        content = ev.get("content", "").strip()

        lines.append(f"### `[{ts}]` **{sender}** *({src})*")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(stream_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Updated Unified Collaboration Stream ({len(events)} total events) -> {stream_path.name}")


def run_sync_pass() -> dict:
    """Execute complete bidirectional chat synchronization pass."""
    cfg = load_config()
    session_id = cfg.get("active_session_id", "devin-eaffd5ab978f45aa88e8d8d29fc0381d")
    api_key = cfg.get("api_key") or "apk_user_dXNlci0xZGU5NTg0NTI1Zjk0NTg4YmI1MmRhN2FlZTA4ZGU1Y19vcmctYTdmMzYzMGZjOTRjNGIwOWEwZDlhN2QzNGNlMjU3YTE6NjcwYjUwYTE5OGQxNGQ2YjlkZTEwOTcwZGZlZjgxNzA="

    # 1. Fetch & Sync Devin
    devin_msgs = fetch_devin_messages(session_id, api_key)
    if devin_msgs:
        sync_devin_history(devin_msgs)

    # 2. Extract & Sync Antigravity
    ag_turns = extract_antigravity_history()
    if ag_turns:
        sync_antigravity_history(ag_turns)

    # 3. Create Unified Chronological Stream
    if devin_msgs and ag_turns:
        sync_unified_collaboration_stream(devin_msgs, ag_turns)

    return {
        "devin_messages": len(devin_msgs),
        "antigravity_turns": len(ag_turns)
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synchronize Devin and Antigravity Chat Histories")
    parser.add_argument("--once", action="store_true", default=True, help="Run single sync pass")
    args = parser.parse_args()

    stats = run_sync_pass()
    print(f"\n[SUCCESS] Synchronized {stats['devin_messages']} Devin messages and {stats['antigravity_turns']} Antigravity turns.")

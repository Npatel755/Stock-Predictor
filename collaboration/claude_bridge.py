"""Bi-Directional Agent Bridge: Antigravity <-> Claude (<-> Devin).

Perpetually synchronizes:
1. Antigravity chat history -> collaboration/ANTIGRAVITY_CHAT_HISTORY.md & .jsonl
2. Claude chat history       -> collaboration/CLAUDE_CHAT_HISTORY.md & .jsonl
3. Unified stream            -> collaboration/UNIFIED_COLLABORATION_STREAM.md
4. Direct inbox messaging    -> collaboration/ANTIGRAVITY_TO_CLAUDE.md & CLAUDE_TO_ANTIGRAVITY.md
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
import time

COLLAB_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = COLLAB_ROOT.parent

# Antigravity Transcript Path
BRAIN_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")
AG_TRANSCRIPT_PATH = BRAIN_DIR / ".system_generated/logs/transcript.jsonl"

# File Targets
AG_MD_PATH = COLLAB_ROOT / "ANTIGRAVITY_CHAT_HISTORY.md"
AG_JSONL_PATH = COLLAB_ROOT / "ANTIGRAVITY_FULL_CHAT_HISTORY.jsonl"
CLAUDE_MD_PATH = COLLAB_ROOT / "CLAUDE_CHAT_HISTORY.md"
CLAUDE_JSONL_PATH = COLLAB_ROOT / "CLAUDE_FULL_CHAT_HISTORY.jsonl"
DEVIN_MD_PATH = COLLAB_ROOT / "DEVIN_CHAT_HISTORY.md"
DEVIN_JSONL_PATH = COLLAB_ROOT / "DEVIN_FULL_CHAT_HISTORY.jsonl"
UNIFIED_STREAM_PATH = COLLAB_ROOT / "UNIFIED_COLLABORATION_STREAM.md"
AG_TO_CLAUDE_PATH = COLLAB_ROOT / "ANTIGRAVITY_TO_CLAUDE.md"
CLAUDE_TO_AG_PATH = COLLAB_ROOT / "CLAUDE_TO_ANTIGRAVITY.md"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ClaudeBridge] %(message)s"
)
logger = logging.getLogger("ClaudeBridge")


def clean_user_prompt(text: str) -> str:
    """Extract clean user request from wrapped tags."""
    if not text:
        return ""
    match = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", text, flags=re.DOTALL).strip()


def extract_antigravity_turns() -> list[dict]:
    """Parse Antigravity transcript into structured interaction turns."""
    if not AG_TRANSCRIPT_PATH.exists():
        return []

    turns = []
    current_turn = None

    try:
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
                    clean_p = clean_user_prompt(content or "")
                    current_turn = {
                        "turn_number": len(turns) + 1,
                        "timestamp": created_at,
                        "user_prompt_raw": content,
                        "user_prompt": clean_p,
                        "assistant_response": None,
                        "response_timestamp": None
                    }
                    turns.append(current_turn)
                elif etype == "PLANNER_RESPONSE" and source == "MODEL" and content:
                    if current_turn is not None:
                        current_turn["assistant_response"] = content
                        current_turn["response_timestamp"] = created_at
    except Exception as e:
        logger.error(f"Error parsing Antigravity transcript: {e}")

    return turns


def sync_antigravity_files(turns: list[dict]):
    """Sync Antigravity turns to JSONL and Markdown."""
    if not turns:
        return

    # Write JSONL
    with open(AG_JSONL_PATH, "w", encoding="utf-8") as f:
        for t in turns:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    # Write Markdown
    md_lines = [
        "# Antigravity Complete Chat History (Perpetual Mirror for Claude & Nick)",
        f"*Last Synchronized: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
        f"*Total Interaction Turns: {len(turns)}*",
        "",
        "> **Note for Claude**: This document contains the full ongoing transcript of Antigravity's conversation with Nick.",
        "> You can read this document to track all strategy models, mathematical proofs, code edits, and user requests.",
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

    with open(AG_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))


def load_claude_turns() -> list[dict]:
    """Load Claude interaction turns from JSONL."""
    if not CLAUDE_JSONL_PATH.exists():
        return []
    turns = []
    try:
        with open(CLAUDE_JSONL_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    turns.append(json.loads(line))
    except Exception as e:
        logger.error(f"Error loading Claude turns: {e}")
    return turns


def save_claude_turns(turns: list[dict]):
    """Save Claude interaction turns to JSONL and Markdown if changed."""
    jsonl_content = "".join(json.dumps(t, ensure_ascii=False) + "\n" for t in turns)
    if not CLAUDE_JSONL_PATH.exists() or CLAUDE_JSONL_PATH.read_text(encoding="utf-8") != jsonl_content:
        CLAUDE_JSONL_PATH.write_text(jsonl_content, encoding="utf-8")

    md_lines = [
        "# Claude Complete Chat History (Perpetual Mirror for Antigravity & Nick)",
        f"*Last Synchronized: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
        f"*Total Interaction Turns: {len(turns)}*",
        "",
        "> **Note for Antigravity & Nick**: This document contains the full ongoing transcript of Claude's conversation turns,",
        "> research notes, and analyses with Nick.",
        "",
        "---",
        ""
    ]

    for t in turns:
        t_num = t.get("turn_number")
        ts = t.get("timestamp", "")
        prompt = t.get("user_prompt", "").strip()
        resp = t.get("assistant_response", "").strip()
        resp_ts = t.get("response_timestamp", "")

        md_lines.append(f"## Turn {t_num} — `{ts}`")
        md_lines.append("### 👤 User (Nick):")
        md_lines.append(f"> {prompt.replace(chr(10), chr(10) + '> ')}")
        md_lines.append("")
        md_lines.append(f"### 🤖 Claude Response (`{resp_ts}`):")
        md_lines.append(resp)
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    new_md = "\n".join(md_lines)
    # Compare without the timestamp line to avoid unnecessary writes
    if CLAUDE_MD_PATH.exists():
        old_md = CLAUDE_MD_PATH.read_text(encoding="utf-8")
        old_core = re.sub(r"\*Last Synchronized:.*?\*", "", old_md)
        new_core = re.sub(r"\*Last Synchronized:.*?\*", "", new_md)
        if old_core.strip() == new_core.strip():
            return
    CLAUDE_MD_PATH.write_text(new_md, encoding="utf-8")


def append_claude_turn(user_prompt: str, assistant_response: str):
    """Append a new interaction turn for Claude."""
    turns = load_claude_turns()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_turn = {
        "turn_number": len(turns) + 1,
        "timestamp": now_utc,
        "user_prompt": user_prompt.strip(),
        "assistant_response": assistant_response.strip(),
        "response_timestamp": now_utc
    }
    turns.append(new_turn)
    save_claude_turns(turns)
    logger.info(f"Appended Claude Turn {new_turn['turn_number']} successfully.")
    sync_all()


def load_devin_messages() -> list[dict]:
    """Load cached Devin messages from JSONL."""
    if not DEVIN_JSONL_PATH.exists():
        return []
    msgs = []
    try:
        with open(DEVIN_JSONL_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    msgs.append(json.loads(line))
    except Exception:
        pass
    return msgs


def sync_unified_stream(ag_turns: list[dict], claude_turns: list[dict], devin_msgs: list[dict]):
    """Merge all agent histories into a unified chronological stream."""
    events = []

    # 1. Antigravity events
    for t in ag_turns:
        ts_u = t.get("timestamp") or ""
        events.append({
            "timestamp": ts_u,
            "agent": "Antigravity",
            "sender": "Nick -> Antigravity",
            "content": t.get("user_prompt", "")
        })
        if t.get("assistant_response"):
            ts_r = t.get("response_timestamp") or ts_u
            events.append({
                "timestamp": ts_r,
                "agent": "Antigravity",
                "sender": "Antigravity",
                "content": t.get("assistant_response", "")
            })

    # 2. Claude events
    for t in claude_turns:
        ts_u = t.get("timestamp") or ""
        events.append({
            "timestamp": ts_u,
            "agent": "Claude",
            "sender": "Nick -> Claude",
            "content": t.get("user_prompt", "")
        })
        if t.get("assistant_response"):
            ts_r = t.get("response_timestamp") or ts_u
            events.append({
                "timestamp": ts_r,
                "agent": "Claude",
                "sender": "Claude",
                "content": t.get("assistant_response", "")
            })

    # 3. Devin events
    for m in devin_msgs:
        ts = m.get("timestamp") or ""
        mtype = m.get("type", "")
        sender = "Nick -> Devin" if mtype in ("user_message", "initial_user_message") else "Devin"
        events.append({
            "timestamp": ts,
            "agent": "Devin",
            "sender": sender,
            "content": m.get("message", "")
        })

    # Sort chronologically by timestamp
    events.sort(key=lambda x: x.get("timestamp", ""))

    lines = [
        "# Unified Collaboration Stream: Antigravity + Claude + Devin + Nick",
        f"*Last Synchronized: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
        f"*Total Interleaved Events: {len(events)}*",
        "",
        "> Chronological merged stream of all messages across all agents (Antigravity, Claude, Devin) and Nick.",
        "> Every agent can inspect this single file to see the entire multi-agent workflow in real time.",
        "",
        "---",
        ""
    ]

    # Show the last 120 merged events
    for ev in events[-120:]:
        ts = ev.get("timestamp", "")
        agent = ev.get("agent", "")
        sender = ev.get("sender", "")
        content = ev.get("content", "").strip()

        badge = f"**[{sender}]**"
        lines.append(f"### `[{ts}]` {badge} *(Agent: {agent})*")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    # One common renderer keeps Codex present when this legacy watcher runs.
    from shared_history import write_unified
    write_unified(COLLAB_ROOT)


def sync_all():
    """Run a full multi-agent synchronization pass."""
    ag_turns = extract_antigravity_turns()
    sync_antigravity_files(ag_turns)

    claude_turns = load_claude_turns()
    save_claude_turns(claude_turns)

    devin_msgs = load_devin_messages()

    sync_unified_stream(ag_turns, claude_turns, devin_msgs)
    logger.info(f"Sync complete: {len(ag_turns)} AG turns, {len(claude_turns)} Claude turns, {len(devin_msgs)} Devin messages.")


def send_message(to_agent: str, content: str):
    """Post an explicit note to an agent's inbox."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if to_agent.lower() == "claude":
        target = AG_TO_CLAUDE_PATH
        header = f"\n\n### Update from Antigravity — `{now_str}`\n\n{content}\n"
    else:
        target = CLAUDE_TO_AG_PATH
        header = f"\n\n### Update from Claude — `{now_str}`\n\n{content}\n"

    with open(target, "a", encoding="utf-8") as f:
        f.write(header)
    logger.info(f"Sent message to {to_agent} -> {target.name}")
    sync_all()


def print_status():
    """Print current status of the agent bridge."""
    ag_turns = extract_antigravity_turns()
    claude_turns = load_claude_turns()
    devin_msgs = load_devin_messages()

    print("\n=======================================================")
    print("      MULTI-AGENT BRIDGE STATUS: AG <-> CLAUDE         ")
    print("=======================================================")
    print(f"Antigravity Turns : {len(ag_turns)} turns")
    if ag_turns:
        last_ag = ag_turns[-1]
        print(f"  Last AG Prompt  : {last_ag.get('user_prompt', '')[:80]}...")
        print(f"  Last AG Time    : {last_ag.get('timestamp')}")
    print(f"Claude Turns      : {len(claude_turns)} turns")
    if claude_turns:
        last_cl = claude_turns[-1]
        print(f"  Last CL Prompt  : {last_cl.get('user_prompt', '')[:80]}...")
        print(f"  Last CL Time    : {last_cl.get('timestamp')}")
    print(f"Devin Messages    : {len(devin_msgs)} messages")
    print("Files Synced:")
    print(f"  - {AG_MD_PATH}")
    print(f"  - {CLAUDE_MD_PATH}")
    print(f"  - {UNIFIED_STREAM_PATH}")
    print("=======================================================\n")


def watch_loop(interval: int = 5):
    """Continuously monitor and sync in the background."""
    logger.info(f"Starting perpetual bridge watcher (polling every {interval}s)...")
    last_ag_mtime = 0.0
    last_cl_mtime = 0.0
    last_inbox_mtime = 0.0

    while True:
        try:
            ag_mtime = AG_TRANSCRIPT_PATH.stat().st_mtime if AG_TRANSCRIPT_PATH.exists() else 0.0
            cl_mtime = CLAUDE_MD_PATH.stat().st_mtime if CLAUDE_MD_PATH.exists() else 0.0
            inbox_mtime = CLAUDE_TO_AG_PATH.stat().st_mtime if CLAUDE_TO_AG_PATH.exists() else 0.0

            if ag_mtime != last_ag_mtime or cl_mtime != last_cl_mtime or inbox_mtime != last_inbox_mtime:
                logger.info("Detected change in transcript or Claude files, syncing...")
                sync_all()
                last_ag_mtime = AG_TRANSCRIPT_PATH.stat().st_mtime if AG_TRANSCRIPT_PATH.exists() else 0.0
                last_cl_mtime = CLAUDE_MD_PATH.stat().st_mtime if CLAUDE_MD_PATH.exists() else 0.0
                last_inbox_mtime = CLAUDE_TO_AG_PATH.stat().st_mtime if CLAUDE_TO_AG_PATH.exists() else 0.0
        except Exception as e:
            logger.error(f"Watcher error: {e}")

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Antigravity <-> Claude Multi-Agent Bridge")
    parser.add_argument("--sync", action="store_true", help="Run full synchronization pass")
    parser.add_argument("--watch", action="store_true", help="Start perpetual background watcher")
    parser.add_argument("--status", action="store_true", help="Display current bridge status")
    parser.add_argument("--log-claude", action="store_true", help="Log a turn from Claude")
    parser.add_argument("--prompt", type=str, help="User prompt for Claude turn")
    parser.add_argument("--response", type=str, help="Claude assistant response")
    parser.add_argument("--msg-to-claude", type=str, help="Send message from Antigravity to Claude")
    parser.add_argument("--msg-to-antigravity", type=str, help="Send message from Claude to Antigravity")
    parser.add_argument("--read-antigravity", action="store_true", help="Print recent Antigravity turns")
    parser.add_argument("--read-claude", action="store_true", help="Print recent Claude turns")
    parser.add_argument("--tail", type=int, default=3, help="Number of turns to print (default 3)")

    args = parser.parse_args()

    if args.status:
        print_status()
    elif args.log_claude:
        if not args.prompt or not args.response:
            print("Error: --prompt and --response are required for --log-claude")
            sys.exit(1)
        append_claude_turn(args.prompt, args.response)
    elif args.msg_to_claude:
        send_message("claude", args.msg_to_claude)
    elif args.msg_to_antigravity:
        send_message("antigravity", args.msg_to_antigravity)
    elif args.read_antigravity:
        turns = extract_antigravity_turns()
        for t in turns[-args.tail:]:
            print(f"\n--- Turn {t['turn_number']} ({t['timestamp']}) ---")
            print(f"User: {t['user_prompt']}")
            print(f"Antigravity: {str(t['assistant_response'])[:300]}...")
    elif args.read_claude:
        turns = load_claude_turns()
        for t in turns[-args.tail:]:
            print(f"\n--- Turn {t['turn_number']} ({t['timestamp']}) ---")
            print(f"User: {t['user_prompt']}")
            print(f"Claude: {str(t['assistant_response'])[:300]}...")
    elif args.watch:
        watch_loop()
    else:
        sync_all()
        print_status()


if __name__ == "__main__":
    main()

"""Git Isolation and Concurrent Workspace Protection Guard.

Enforces:
- Branch namespace isolation: `antigravity/<task>` vs `devin/<task>`
- File modification tracking to prevent silent overwrites of each other's work
- Pre-flight workspace checks before applying changes
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
GUARD_STATE = Path(__file__).resolve().parent / "git_guard_state.json"


class GitWorkspaceGuard:
    def __init__(self, repo_root: Optional[Path] = None):
        self.root = repo_root or ROOT
        self.state_path = GUARD_STATE
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"file_manifest": {}, "active_locks": {}}

    def _save_state(self):
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def hash_file(self, path: Path) -> str:
        if not path.is_file():
            return ""
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def acquire_file_lock(self, file_path: str, agent: str) -> Tuple[bool, str]:
        """Request a lock before modifying a file so concurrent agents don't clash."""
        norm_path = str(Path(file_path).resolve())
        current_lock = self.state["active_locks"].get(norm_path)
        if current_lock and current_lock["agent"] != agent:
            return False, f"File locked by {current_lock['agent']} since {current_lock['time']}"

        import datetime
        self.state["active_locks"][norm_path] = {
            "agent": agent,
            "time": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self._save_state()
        return True, "Lock acquired"

    def release_file_lock(self, file_path: str, agent: str) -> bool:
        norm_path = str(Path(file_path).resolve())
        current_lock = self.state["active_locks"].get(norm_path)
        if current_lock and current_lock["agent"] == agent:
            del self.state["active_locks"][norm_path]
            self._save_state()
            return True
        return False

    def check_for_external_edits(self, file_path: Path) -> Tuple[bool, str]:
        """Check if a file was altered externally since last recorded snapshot."""
        norm_path = str(file_path.resolve())
        recorded_hash = self.state["file_manifest"].get(norm_path)
        current_hash = self.hash_file(file_path)

        if recorded_hash and recorded_hash != current_hash:
            return True, f"File {file_path.name} was modified externally! Recorded: {recorded_hash[:8]}, Current: {current_hash[:8]}"
        return False, "File matches record"

    def record_snapshot(self, files: List[Path]):
        for f in files:
            if f.is_file():
                self.state["file_manifest"][str(f.resolve())] = self.hash_file(f)
        self._save_state()

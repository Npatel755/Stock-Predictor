"""Read append-only experiment checkpoints without misreporting liveness."""
import json
from pathlib import Path


def checkpoint_rows(path: Path):
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rows = []
    for index, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if index == len(lines) - 1 and not text.endswith("\n"):
                break  # writer has not finished the final checkpoint line yet
            raise ValueError(f"Invalid checkpoint row {index + 1} in {path.name}") from None
    return rows


from .research_display import search_status, overview_rows, training_overview  # Compatibility for previous callers.

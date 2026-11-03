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


def search_status(directory: Path):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    train = checkpoint_rows(directory / "training.jsonl")
    validation = checkpoint_rows(directory / "validation.jsonl")
    summary_path = directory / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None
    return {"manifest": manifest, "training": train, "validation": validation, "summary": summary}

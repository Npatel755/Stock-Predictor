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
    if "candidate_count" not in manifest:
        manifest["candidate_count"] = len(manifest.get("candidates", []))
    train = checkpoint_rows(directory / "training.jsonl")
    validation = checkpoint_rows(directory / "validation.jsonl")
    summary_path = directory / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None
    return {"manifest": manifest, "training": train, "validation": validation, "summary": summary}


def overview_rows(summary):
    """Read both legacy DVS and independent experiment metrics explicitly."""
    metrics_by_name = dict(summary.get("full_history", {}))
    for name, value in summary.get("evaluation", {}).items():
        if "final_equity" in value:
            metrics_by_name[name] = value
        else:
            for window, metrics in value.items():
                metrics_by_name[f"{name} / {window}"] = metrics
    return [{"scenario": name, "net_pnl": m["final_equity"] - m["initial_capital"],
             "trades": m["entries"], "intrabar_drawdown": m["max_intrabar_drawdown"]}
            for name, m in metrics_by_name.items()]


def training_overview(row):
    folds = row.get("folds")
    values = folds if folds is not None else [row["metrics"]]
    return {"candidate": row["label"], "training_pnl": sum(m["final_equity"]-m["initial_capital"] for m in values),
            "entries": sum(m["entries"] for m in values), "score": row["score"]}

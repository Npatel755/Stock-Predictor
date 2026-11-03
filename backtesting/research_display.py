"""Dashboard adapters, isolated from previously cached checkpoint modules."""
import json
from pathlib import Path


def search_status(directory: Path):
    from .search_results import checkpoint_rows
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest.setdefault("candidate_count", len(manifest.get("candidates", [])))
    summary_path = directory / "summary.json"
    return {"manifest": manifest,
            "training": checkpoint_rows(directory / "training.jsonl"),
            "validation": checkpoint_rows(directory / "validation.jsonl"),
            "summary": json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None}


def overview_rows(summary):
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

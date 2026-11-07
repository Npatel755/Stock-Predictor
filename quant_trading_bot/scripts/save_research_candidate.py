"""Preserve a requested research candidate and its exact curve/trade artifacts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def publish_index():
    lines = ["# Saved MNQ research candidates", "",
        "Exact parameters, metrics, source protocol, full equity curves and trade ledgers are preserved in each candidate folder. "
        "Results use reused 2024–2025 selection data and have no independent forward confirmation. Saving a candidate does not activate trading.", "",
        "| Candidate | Net | Closing DD | Intrabar DD | Trades | Base shutdown | 2×-cost net | 2× shutdown |",
        "|---|---:|---:|---:|---:|---|---:|---|"]
    for path in sorted((ROOT/"reports/saved_candidates").glob("*/candidate.json")):
        saved = json.loads(path.read_text(encoding="utf-8"))
        row = saved["candidate"]
        m, stress = row["metrics"], row["stress"]["2"]
        link = path.relative_to(ROOT/"reports").as_posix()
        lines.append(f"| [{row['candidate_id']}]({link}) | ${m['net_pnl']:,.2f} | ${m['max_drawdown']:,.2f} | ${m['max_intraday_drawdown_bound']:,.2f} | {m['trades']} | {m['permanent_risk_lock']} | ${stress['net_pnl']:,.2f} | {stress['permanent_risk_lock']} |")
    lines += ["", "The saved $5,779.50 result hit its $1,900 internal risk stop at $1,920 measured drawdown and stopped trading early. "
        "Its terminal profit is retained as observed. The $5,022 result completed without a base shutdown, with $1,365 closing drawdown and $1,398 intrabar drawdown. "
        "Both anchors fail the 2×-cost test. A configured loss stop cannot guarantee a future drawdown ceiling because price gaps can overshoot it.", ""]
    (ROOT/"reports/SAVED_CANDIDATES.md").write_text("\n".join(lines), encoding="utf-8")


def save(run, candidate_id):
    run = Path(run).resolve()
    rows = json.loads((run/"MNQ_validation_results.json").read_text())
    row = next(item for item in rows if item["candidate_id"] == candidate_id)
    destination = ROOT/"reports/saved_candidates"/candidate_id
    destination.mkdir(parents=True, exist_ok=False)
    artifacts = {}
    for suffix in ("equity", "trades"):
        source = run/f"MNQ_{candidate_id}_validation_{suffix}.parquet"
        target = destination/source.name
        shutil.copyfile(source, target)
        artifacts[suffix] = dict(path=str(target.relative_to(ROOT)), sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    shutil.copyfile(run/"protocol.json", destination/"source_protocol.json")
    saved = dict(saved_at=datetime.now(timezone.utc).isoformat(), source_run=str(run),
        candidate=row, artifacts=artifacts, saved_for_research=True, live_execution_enabled=False,
        selection_period="2024–2025 reused selection data", independent_confirmation=False,
        user_drawdown_limit=2000,
        below_user_drawdown_limit=row["metrics"]["max_drawdown"] < 2000 and row["metrics"]["max_intraday_drawdown_bound"] < 2000,
        permanent_risk_shutdown=row["metrics"]["permanent_risk_lock"])
    (destination/"candidate.json").write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
    publish_index()
    print(json.dumps(dict(saved=str(destination), candidate_id=candidate_id, net=row["metrics"]["net_pnl"], drawdown=row["metrics"]["max_drawdown"])))
    return saved


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    save(args.run, args.candidate)

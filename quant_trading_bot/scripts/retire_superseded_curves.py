"""Retire reproducible equity curves from this task's superseded market runs.

Keep data, features, trades, models, source snapshots and measured summaries.
The latest campaign (including an in-progress one) is always protected.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
from quant_futures.config import file_hash
from quant_futures.research import json_write

ROOT = Path(__file__).resolve().parents[1]
protocols = sorted((ROOT/"reports").glob("market_campaign_*.json"))
latest = json.loads(protocols[-1].read_text())
protected = {Path(row["path"]).resolve() for row in latest["runs"].values()}
# Both instruments in the latest timestamp are protected even before their
# per-instrument registry has been created by the sequential orchestrator.
stamp = protocols[-1].stem.removeprefix("market_campaign_")
protected.update((ROOT/"runs"/f"{name}_market_{stamp}").resolve() for name in ("mes", "mnq"))
record_path = ROOT/"reports/retired_superseded_curves.json"
record = json.loads(record_path.read_text()) if record_path.exists() else dict(files=[], rationale="Bounded disk budget; keep current campaign and reconstruct superseded curves from retained source/data/config; no raw data deletion")
for protocol_path in protocols[:-1]:
    protocol = json.loads(protocol_path.read_text())
    for row in protocol["runs"].values():
        directory = Path(row["path"]).resolve()
        if directory in protected:
            continue
        if not directory.is_relative_to((ROOT/"runs").resolve()):
            raise ValueError("Unowned run path")
        leaderboard = directory/"leaderboard.json"
        if not leaderboard.exists():
            continue
        for candidate in json.loads(leaderboard.read_text()):
            cid = candidate["candidate_id"]
            if not cid.startswith(("baseline_", "ml_", "meta_", "ensemble_", "regime_")) or Path(cid).name != cid:
                raise ValueError("Invalid candidate identifier")
            path = directory/f"{cid}_equity.parquet"
            if not path.exists():
                continue
            entry = dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=file_hash(path), metrics=str(leaderboard.relative_to(ROOT)),
                retired_at=datetime.now(timezone.utc).isoformat())
            record["files"].append(entry)
            json_write(record_path, record)
            path.unlink()
print(json.dumps(dict(retired=len(record["files"]), total_bytes=sum(row["bytes"] for row in record["files"])) ))

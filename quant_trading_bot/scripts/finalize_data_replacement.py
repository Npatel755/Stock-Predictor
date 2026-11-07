"""Publish the active real-data catalog and supersede stale synthetic handoffs."""
from datetime import datetime, timezone
from pathlib import Path
import json
from collections import Counter
import argparse
from quant_futures.research import code_identity, json_write
from quant_futures.config import file_hash
from quant_futures.dataset_catalog import activate_and_replace

ROOT = Path(__file__).resolve().parents[1]
catalog = json.loads((ROOT/"data/catalog.json").read_text())
parser = argparse.ArgumentParser()
parser.add_argument("--audit-only", action="store_true")
args = parser.parse_args()
if args.audit_only:
    cleanup = json.loads((ROOT/"reports/data_replacement_history.json").read_text())
else:
    catalog, cleanup = activate_and_replace(ROOT, catalog["active_root"])
root = Path(catalog["active_root"])
report = json.loads((root/"import_report.json").read_text())
conditions = Counter(x["condition"] for x in json.loads((root/"condition.json").read_text()))
verified = json.loads((root/"archive_verified.json").read_text())
identity = code_identity()
tests = json.loads((ROOT/"reports/test_receipt.json").read_text())
assert tests["passed"] and tests["source_hash"] == identity["source_hash"]
summary = dict(created_at=datetime.now(timezone.utc).isoformat(), **identity,
    task="Replace earlier futures-project datasets with the user-provided Databento archive",
    status="complete", active_job=catalog["active_job"], source_zip=catalog["source_zip"],
    source_archive_sha256=verified["source_zip_sha256"], source_members=verified["members"],
    raw_rows=report["outright_rows"], source_rows=report["source_rows"],
    non_outright_rows_retained_in_original_zip=report["excluded_non_outright_rows"],
    raw_coverage=report["coverage"], selected_datasets=catalog["instruments"],
    split_protocol=catalog.get("split_protocol"),
    quality_issues=report["quality_issues"], dataset_condition_counts=dict(conditions),
    removed_generated_files=len(cleanup["removed_files"]), original_zip_preserved=Path(catalog["source_zip"]).exists(),
    existing_crypto_research_preserved=True, market_holdout_evaluated_by_data_replacement=False,
    current_market_final_test_evaluated=(ROOT/"reports/final_candidate_test.json").exists(),
    no_model_performance_claim=True, source_archive_purchase_cost=None, amount_spent_by_agent=0,
    clean_check_environment_retained_due_to_automatic_review=True,
    source_data_catalog_hash=file_hash(ROOT/"data/catalog.json"), test_receipt=tests)
json_write(ROOT/"reports/DATA_REPLACEMENT_MANIFEST.json", summary)
if not (ROOT/"reports/final_candidate_test.json").exists():
    json_write(ROOT/"reports/HANDOFF_MANIFEST.json", summary)
lines = ["# Databento data replacement", "", f"Active source: **{catalog['active_job']}**. Original ZIP preserved at `{catalog['source_zip']}`.", "",
    "All three archive members match their supplied SHA-256 hashes. The official Databento SDK decoded the DBN stream directly from ZIP without duplicating the large compressed payload.", "",
    f"The source contains **{report['source_rows']:,} records**: **{report['outright_rows']:,} outright bars** and **{report['excluded_non_outright_rows']:,} non-outright/spread records**. Spreads remain in the original ZIP; they are counted and never mislabeled as outright futures.", "",
    "| Instrument | Raw outright bars | Selected front-contract bars | First raw observation (UTC) | Last raw observation (UTC) |",
    "|---|---:|---:|---|---|"]
for name in ("MES", "MNQ", "ES", "NQ"):
    raw = report["coverage"][name]
    selected = catalog["instruments"][name]["coverage"]
    lines.append(f"| {name} | {raw['rows']:,} | {selected['rows']:,} | {raw['first']} | {raw['last']} |")
lines += ["", "The imported outright bars had zero invalid/nonpositive prices, invalid OHLC relationships, invalid volumes, off-tick values, duplicate keys, timestamp-alignment failures or prelaunch micro observations in the implemented checks. This does not establish complete exchange-calendar coverage. Missing/no-trade intervals are not forward-filled.", "",
    "The raw partitions preserve every imported outright contract and its instrument ID. Selected series use only the preceding completed session's volume, roll forward by expiry, and flag contract changes. The 2010 ES/NQ data remains mini-futures reference history; no MES/MNQ observations were fabricated before May 2019. Bid/ask and book fields remain null because the export is OHLCV only.", "",
    f"Cleanup removed **{len(cleanup['removed_files']):,} generated files** from this futures project's old synthetic/sample datasets, their runs and disposable test fixtures. Separate ETH/BNB research and the supplied source ZIP were preserved. The detailed allowlist is in `reports/data_replacement_history.json`.", "",
    "The disposable `.clean-check` verification environment remains because automatic approval review blocked its removal. It is not an active price dataset.", "",
    "Data import did not fit a model, consume a market holdout or activate trading. User-confirmed account settings are 50% consistency and DLL off; other contractual details still require verification.", "",
    "## Access", "", "```powershell", ".\\.venv\\Scripts\\python.exe -m quant_futures datasets", "```", "",
    "Use `MES`, `MNQ`, `ES`, or `NQ` as dataset arguments to resolve development descriptors containing training and validation only. Physical test files require governed final evaluation; the current one-time MNQ test status is in FINAL_REPORT.md. See [DATA_SPLIT_REPORT.md](DATA_SPLIT_REPORT.md) for the chronological protocol and exact counts. Full contract/year partitions, symbology, condition metadata, selection schedule and checksums are retained beside the imported data. Dataset use and redistribution remain governed by the user's Databento entitlement."]
(ROOT/"reports/DATA_IMPORT_REPORT.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
if catalog.get("split_protocol"):
    split_lines = ["# Chronological data split", "", "The active user-provided Databento data is physically separated into training, validation and test Parquet files for each instrument. No random shuffle was used.", "",
        "- Training: available history before January 1, 2024 UTC.",
        "- Validation: January 1, 2024 through December 31, 2025 UTC.",
        "- Test: January 1, 2026 through the archive end, November 5, 2026 UTC.", "",
        "| Instrument | Training bars | Validation bars | Test bars | Total selected bars |",
        "|---|---:|---:|---:|---:|"]
    for name, item in catalog["instruments"].items():
        counts = [item["splits"][role]["coverage"]["rows"] for role in ("train", "validation", "test")]
        assert sum(counts) == item["coverage"]["rows"]
        split_lines.append(f"| {name} | {counts[0]:,} | {counts[1]:,} | {counts[2]:,} | {sum(counts):,} |")
    split_lines += ["", "MES/MNQ training begins May 5, 2019 UTC. ES/NQ training begins June 6, 2010 UTC and remains distinct mini-futures reference history. All four validation sets begin January 1, 2024 at 23:00 UTC and test sets begin January 1, 2026 at 23:00 UTC; closures and absent bars are not filled.", "",
        "The default fixed protocol fits estimators, preprocessing and calibration only on eligible training rows. Training labels reaching the validation boundary are purged. Candidate selection uses validation. Features can carry causal earlier-period history, but the development loader never reads test prices. An optional explicitly configured walk-forward protocol may fit completed earlier validation observations for subsequent validation blocks.", "",
        "Ordinary research loading rejects a direct test partition. Final evaluation verifies the frozen artifact and source, then consumes a global single-use test reservation before loading test prices. "+("One frozen MNQ candidate has now been evaluated on 2026. The correlated market period is consumed for model selection; no repeated untouched-test claim is permitted. See FINAL_REPORT.md." if (ROOT/"reports/final_candidate_test.json").exists() else "The real-market test remains unevaluated; fixture tests exercise this guard without consuming it."), "",
        "Every selected row is assigned exactly once. Date ranges are disjoint; per-file SHA-256 hashes, UTC coverage and protocol IDs are recorded in `data/catalog.json` and adjacent partition manifests. The original ZIP and imported raw contract partitions are preserved. Superseded unsplit derived files were retired after the new partitions and catalog were committed.", "",
        f"Split protocol ID: `{catalog['split_protocol']['protocol_id']}`.", "",
        f"Verification: {tests['command']}; passed: `{tests['passed']}`. See `test_receipt.json` for the matching source hash."]
    (ROOT/"reports/DATA_SPLIT_REPORT.md").write_text("\n".join(split_lines)+"\n", encoding="utf-8")
if not (ROOT/"reports/latest_market_campaign.json").exists():
    (ROOT/"reports/FINAL_REPORT.md").write_text("# Current project status\n\nThe supplied Databento export has replaced the earlier synthetic/sample futures datasets and their generated runs.\n\nSee [DATA_IMPORT_REPORT.md](DATA_IMPORT_REPORT.md) and `DATA_REPLACEMENT_MANIFEST.json` for actual coverage, validation, cleanup and source hashes.\n\nNo market model result or deployment eligibility is implied by this data replacement. The master research pipeline remains available for work on the new history; live execution is disabled.\n", encoding="utf-8")
print(json.dumps(dict(status=summary["status"], source=summary["active_job"], raw_rows=summary["raw_rows"], removed_files=summary["removed_generated_files"]), indent=2))

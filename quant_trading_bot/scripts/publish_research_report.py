"""Publish measured development results and explicit external dependencies."""
from pathlib import Path
from datetime import datetime, timezone
import json
from quant_futures.research import json_write, code_identity
from quant_futures.config import file_hash, digest
from paper_compatibility import verify_compatibility

ROOT = Path(__file__).resolve().parents[1]
campaign = json.loads((ROOT/"reports/latest_market_campaign.json").read_text())
campaigns = [json.loads(path.read_text()) for path in sorted((ROOT/"reports").glob("final_market_campaign_*m.json"))]
extended = json.loads((ROOT/"reports/latest_extended_study.json").read_text())
receipt = json.loads((ROOT/"reports/test_receipt.json").read_text())
assert receipt["passed"] and receipt["source_hash"] == code_identity()["source_hash"]
catalog = json.loads((ROOT/"data/catalog.json").read_text())
paper = json.loads((ROOT/"reports/market_paper_verification.json").read_text())
splits = json.loads((ROOT/"reports/split_verification.json").read_text())
assert paper["passed"] and splits["passed"]
for item in catalog["instruments"].values():
    key = digest(dict(test_partition=item["splits"]["test"]["dataset_version"]))
    assert not (ROOT/"data/manifests/final_tests"/f"{key}.json").exists()
rows = []
for study in campaigns:
    for instrument, run in study["runs"].items():
        registration = json.loads((Path(run["path"])/"experiment.json").read_text())
        verify_compatibility(Path(run["path"]), registration)
        leaderboard = json.loads((Path(run["path"])/"leaderboard.json").read_text())
        rows.extend(dict(instrument=instrument, timeframe_minutes=study["timeframe_minutes"], **row) for row in leaderboard)
studies = extended["attempts"]
completed = [row for row in studies if row["status"] == "completed"]
failed = [row for row in studies if row["status"] != "completed"]
lines = ["# Measured MES / MNQ research", "", "The implemented bounded campaign found **no deployable trading strategy**. This finding applies to the declared data, costs, features, model budgets and execution assumptions; it does not establish that all possible ML strategies fail.", "",
    "The active source is the user-provided Databento export GLBX-20261106-FX6FM5XWUX. Training uses available micro history from May 2019 through 2023; selection uses 2024–2025; 2026 remains reserved and unevaluated. ES/NQ reference history is separately labeled. The chronological split has no overlapping timestamps and every selected bar is accounted for. See [DATA_SPLIT_REPORT.md](DATA_SPLIT_REPORT.md).", "",
    f"The corrected primary comparisons completed {len(rows)} candidates across MES and MNQ at declared 5- and 15-minute resolutions. The 5-minute sensitivity campaign was registered after the user freed disk space. Estimators, pruning and calibration fit training observations only. Training is capped at the latest 100000 observations per fit, so elapsed training history differs by resolution. Feature, label and holding horizons are bar-based and also scale with resolution. Costs are configurable research assumptions. Model families within each experiment share the same one-contract cap and independent risk limits. Validation blocks restart capital/risk state; the aggregate curves below are attribution curves and must not be described as one continuous funded-account record.", "",
    "| Instrument | Minutes | Candidate | Validation net P&L | Max drawdown | Trades | Profit factor | Eligible |",
    "|---|---:|---|---:|---:|---:|---:|---|"]
for row in sorted(rows, key=lambda row: (row["instrument"], row["timeframe_minutes"], row["candidate_id"])):
    factor = "n/a" if row.get("profit_factor") is None else f"{row['profit_factor']:.3f}"
    lines.append(f"| {row['instrument']} | {row['timeframe_minutes']} | {row['candidate_id']} | ${row['net_pnl']:,.2f} | ${row['max_drawdown']:,.2f} | {row['trades']} | {factor} | {row['research_eligible']} |")
lines += ["", "Flat no-trade results are abstention benchmarks, not trading edges. Negative validation outcomes are retained. A model with fewer losses because it rarely trades has not demonstrated positive expectancy. See each run's calibration, fold, regime/year attribution, bootstrap/Reality Check, cost/latency stress, funded-scenario and Monte Carlo artifacts before interpreting the ranking.", "",
    "## Extended studies", "",
    f"Completed {len(completed)} of {len(studies)} registered extended attempts; {len(failed)} failed attempts remain visible. These exploratory studies include horizon/target alternatives, neural networks, PPO/DQN, training-only nested search and feature diagnostics, causal regime allocation, cross-market features and a shared-account replay. Their budgets and full failures are recorded in `{extended['path']}`. Short neural/RL runs test feasibility and out-of-sample behavior; they do not establish convergence or deployment readiness.", "",
    "| Instrument | Study | Status | Validation net P&L | Trades |",
    "|---|---|---|---:|---:|"]
for row in studies:
    metrics = row.get("result", {}).get("metrics", {})
    pnl = "n/a" if "net_pnl" not in metrics else f"${metrics['net_pnl']:,.2f}"
    lines.append(f"| {row['instrument']} | {row['name']} | {row['status']} | {pnl} | {metrics.get('trades', 'n/a')} |")
lines += ["", "The shared-account EMA diagnostic has one balance and one risk state, gross correlated exposure reservation, no implicit price filling, and explicit timestamp exclusions. It is a continuous diagnostic and differs from the reset-fold comparison. Primary/extended choices and earlier interrupted/corrected runs all contribute selection opportunities; local per-run adjusted p-values do not correct every research decision across the whole campaign.", "",
    "## Verification and limits", "",
    "The current source passes its full automated suite. Actual 2025 market replay also matches batch accounting across an explicit checkpoint restart for both instruments. Replay exposed a Windows checkpoint-file sharing lock; a bounded file-replacement retry fixed it. The original frozen research and model artifacts remain unchanged. `paper_compatibility.json` verifies that this exact storage-only patch is the sole source difference and records the parent artifact and unchanged model-weight hashes; derived paper-verification artifacts carry the new source identity. That historical replay is not forward paper evidence. Physical split checks read test timestamps and hashes for integrity, not test price columns or performance.", "",
    "The initial campaign was superseded after corrections to scheduled-exit timing and label completion timestamps. The final 15-minute campaign explicitly flattens at 16:30 ET, an available bar open before the published 16:45 cutoff; the generic 16:40 setting rounds late at this resolution. These execution corrections are disclosed additional research attempts, not hidden discarded results. An intermediate rerun failed on a 44.4 MiB allocation; its record is retained. Prediction batching, fold-limited inference, releasing completed curves and verified feature-cache reuse resolved the resource issue without changing split boundaries or model settings. Source snapshots and hashes distinguish these versions.", "",
    "To fit the disk budget, reproducible per-bar equity curves from superseded runs were retired after logging their hashes and sizes in `reports/retired_superseded_curves.json`. Their metrics, trades, model artifacts, source snapshots and features remain; the final campaign's curves and all original market data remain available.", "",
    "The provider's customization documentation confirms DLL-off removes the provider daily cap, while 50% evaluation consistency is a purchase add-on. These are the settings confirmed by the user. The independent $300 research daily stop remains a risk choice. See [official customization](https://support.lucidtrading.com/en/articles/16226050-lucidflex-customization) and [official consistency calculation](https://support.lucidtrading.com/en/articles/12945805-lucidflex-consistency-percentage).", "",
    "Operational eligibility remains blocked by the missing authoritative historical session/holiday calendar, verified brokerage costs and integration permissions, complete account-contract details, and sustained authorized forward paper review. The 50% consistency cushion and purchase fee are not guessed. OHLCV cannot establish intrabar sequence, true spread, order-book depth, queue priority or future capacity. See [CME hours and holidays](https://www.cmegroup.com/trading-hours.html), [LIMITATIONS.md](LIMITATIONS.md) and [FUNDED_ACCOUNT_RULES.md](FUNDED_ACCOUNT_RULES.md).", "",
    "The reserved market test was not consumed because no candidate meets the research and operational eligibility gates. Real-money execution remains disabled. No paid download, account purchase or live broker action was made.", ""]
(ROOT/"MODEL_COMPARISON.md").write_text("\n".join(lines), encoding="utf-8")
final = ["# Research handoff", "", "The new Databento data is imported and chronologically split. The bounded real-data baseline/ML campaign and extended studies are complete; no deployable strategy is established. The 2026 test remains reserved.", "",
    f"Primary candidates: {len(rows)}. Extended attempts: {len(studies)} ({len(completed)} completed, {len(failed)} failed). Full measured outcomes and limitations: [MODEL_COMPARISON.md](../MODEL_COMPARISON.md).", "",
    "Implementation includes the event simulator, causal batch/online features, model/target utilities, risk and funded-account simulators, synchronized portfolio replay, checksummed paper recovery, feed watchdog, experiment/source snapshots and local dashboard. Source-matched automated tests and bounded actual-market replay/restart checks pass.", "",
    "External dependencies remain: authoritative historical schedules, confirmed commissions and API/platform permission, complete account-contract terms and sustained forward paper data/review. Windows execution is verified; WSL/Docker and real-feed operation have not been established. No live trading is enabled.", "",
    "The disposable `.clean-check` environment remains because automatic approval review rejected its deletion with “blocked by policy.” It is not an active market dataset.", ""]
(ROOT/"reports/FINAL_REPORT.md").write_text("\n".join(final), encoding="utf-8")
manifest = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(), status="bounded_research_complete_no_deployable_candidate",
    full_master_operational_readiness=False, market_test_evaluated=False, live_execution_enabled=False,
    data_catalog_sha256=file_hash(ROOT/"data/catalog.json"), split_protocol=catalog["split_protocol"],
    primary_campaigns=campaigns, extended_study_path=extended["path"], extended_attempts=len(studies),
    test_receipt=receipt, paper_verification=paper, data_split_verification=splits,
    automatic_review_rejected_environment_cleanup=True,
    external_dependencies=["authoritative historical schedule", "verified costs and broker/platform API authorization", "complete account contract and purchase fee", "sustained forward paper review"])
json_write(ROOT/"reports/HANDOFF_MANIFEST.json", manifest)
print(json.dumps(dict(primary=len(rows), extended=len(studies), failed_extended=len(failed), market_test_evaluated=False), indent=2))

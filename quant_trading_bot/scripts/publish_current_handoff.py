"""Publish factual current transfer results, count, split and final-test status."""
from pathlib import Path
from datetime import datetime, timezone
import json
from quant_futures.research import code_identity, json_write
from quant_futures.config import file_hash, digest
from research_inventory import inventory
from publish_pareto_report import publish as publish_refinement

ROOT = Path(__file__).resolve().parents[1]
receipt = json.loads((ROOT/"reports/test_receipt.json").read_text())
assert receipt["passed"] and receipt["source_hash"] == code_identity()["source_hash"]
counts = inventory(ROOT)
json_write(ROOT/"reports/strategy_counts.json", counts)
minute = json.loads((ROOT/"reports/latest_minute_reference_transfer.json").read_text())
control = json.loads((ROOT/"reports/latest_reference_transfer.json").read_text())
adaptive = json.loads((ROOT/"reports/latest_adaptive_opening_study.json").read_text())
overnight = json.loads((ROOT/"reports/latest_overnight_study.json").read_text())
opening = json.loads((ROOT/"reports/latest_opening_range_study.json").read_text())
session_file = ROOT/"reports/latest_session_window_study.json"
session_study = json.loads(session_file.read_text()) if session_file.exists() else None
gap_file = ROOT/"reports/latest_gap_structure_minutes_study.json"
gap_study = json.loads(gap_file.read_text()) if gap_file.exists() else None
risk_file = ROOT/"reports/latest_risk_expansion_study.json"
risk_study = json.loads(risk_file.read_text()) if risk_file.exists() else None
refinement_file = ROOT/"reports/latest_pareto_refinement.json"
refinement = json.loads(refinement_file.read_text()) if refinement_file.exists() else None
followup_file = ROOT/"reports/latest_profit_drawdown_followup.json"
followup = json.loads(followup_file.read_text()) if followup_file.exists() else None
saved_test_file = ROOT/"reports/saved_version_reused_test.json"
saved_test = json.loads(saved_test_file.read_text()) if saved_test_file.exists() else None
final = json.loads((ROOT/"reports/final_candidate_test.json").read_text())
frozen_final = json.loads((ROOT/final["path"]/"frozen_candidate.json").read_text())
reservation_path = ROOT/"data/manifests/final_tests"/(digest(dict(test_partition=final["test_dataset_version"]))+".json")
reservation = json.loads(reservation_path.read_text())
assert digest(frozen_final["candidate"]) == frozen_final["candidate_hash"] == final["frozen_candidate_hash"] == reservation["model_version"]
assert reservation["dataset_version"] == final["test_dataset_version"]
assert reservation["source_hash"] == final["source_hash"] == code_identity()["source_hash"]
assert reservation["config_hash"] == digest(frozen_final["candidate"]["configuration"])
tests = {name: json.loads((ROOT/"reports"/f"{name}_test_receipt.json").read_text()) for name in ("wsl", "clean") if (ROOT/"reports"/f"{name}_test_receipt.json").exists()}
prior = ROOT/"reports/HISTORICAL_MICRO_COMPARISON.md"
if not prior.exists():
    old = ROOT/"MODEL_COMPARISON.md"
    if old.exists():
        prior.write_text("# Superseded micro-trained comparison record\n\nThis historical report predates the reference-transfer and final-test evaluations. Its test-status statements describe that earlier point in research. Current status is in MODEL_COMPARISON.md and reports/FINAL_REPORT.md.\n\n"+old.read_text(encoding="utf-8"), encoding="utf-8")
lines = ["# Current ES/NQ → MES/MNQ research", "",
    "The research found positive validation backtests below the requested $2,000 drawdown limit, but has **not established a dependable deployable trading edge**. The previously frozen candidate returned only $6.50 in its 2026 final test, with a confidence interval spanning zero. Subsequent improvements use reused selection data and have no independent final confirmation. No live trading is enabled.", "",
    f"Tested **{counts['distinct_strategy_definitions']} distinct strategy/model definitions**, **{counts['unique_parameter_configurations']} parameter/timeframe/feature configurations**, and **{counts['unique_market_configuration_cases']} market/configuration cases**. **{counts['completed_run_attempts']} completed attempts** includes corrected and repeated runs; reruns do not increase the distinct-definition count. Approximate training screens are separately labeled. See [strategy count audit](reports/STRATEGY_COUNTS.md).", "",
    "## Chronological split", "",
    "- Training: actual ES/NQ contract history from June 2010 through 2023. Internal fitting/calibration/selection all remain before 2024.",
    "- Validation: actual MES/MNQ 2024–2025; earlier micro history supplies causal feature warmup only in the transfer studies.",
    "- Final test: one frozen MNQ candidate evaluated once on January–November 5, 2026. ES/NQ/MES test price files remain unread, but the correlated 2026 market period is now consumed for model-selection purposes. No retuning against it may be represented as untouched testing.", "",
    "Original source resolution is one minute. The 15-minute transfer run is a separate control. There is no fabricated pre-2019 micro history, volume mapping, or mini P&L relabeled as micro P&L. All eligible rows enter the one-minute model pipeline without sampling; rolling warmup, missing-feature and invalid forward-event windows are excluded and counted.", "",
    "| Transfer | Original reference training rows | Eligible feature/label rows | Final base-model fitting rows | Calibration rows |",
    "|---|---:|---:|---:|---:|"]
for name, pair in minute["pairs"].items():
    fitted = next(row for row in pair["final_fits"] if row["status"] == "completed")
    lines.append(f"| {name} | {pair['source_rows']:,} | {pair['eligible_rows']:,} | {fitted['fitting_rows']:,} | {fitted['calibration_rows']:,} |")
lines += ["", "Streaming logistic and XGBoost external-memory models use normalized price/structure/time features, with volume/VWAP transfer features excluded. Each model uses the fitting and calibration counts above; the data is not split between the two models. The final one-minute fits use 2010–2022 and calibration uses 2023, following parameter selection on 2022–2023 reference outcomes from earlier fits. See `latest_minute_reference_transfer.json` and its retained shards/artifacts for exact dates and hashes.", "",
    "## Measured micro validation", "",
    "These are continuous one-account 2024–2025 results. Settings were selected using reference training outcomes before actual micro validation. Positive validation is not proof of a future edge. Studies introduced after earlier validation observations are disclosed additional research, not independent confirmation.", "",
    "| Study | Transfer | Candidate | Net P&L | Max DD | Trades | Qualified by all checks |", "|---|---|---|---:|---:|---:|---|"]
studies = [("Original one-minute", minute), ("15-minute control", control), ("One-attempt ORB", opening), ("Overnight", overnight), ("Adaptive ORB", adaptive)]
if session_study:
    studies.append(("Session/calendar — post-final exploratory", session_study))
if gap_study:
    studies.append(("Gap/structure — post-final exploratory", gap_study))
post_rows = [dict(study=label, transfer=pair, **row)
    for label, study in studies if study.get("post_final_test_research")
    for pair, detail in study["pairs"].items() for row in detail["validation_results"] if "metrics" in row]
if post_rows:
    post_rows.sort(key=lambda row: row["metrics"]["net_pnl"], reverse=True)
    leading = post_rows[0]
    annual = {}
    for day, value in leading["metrics"]["daily_pnl"].items():
        annual[day[:4]] = annual.get(day[:4], 0)+value
    post_summary = dict(created_at=datetime.now(timezone.utc).isoformat(),
        studies=[study["path"] for _, study in studies if study.get("post_final_test_research")],
        completed_reference_screens=sum(detail["screen_attempts"] for _, study in studies
            if study.get("post_final_test_research") for detail in study["pairs"].values()),
        distinct_new_rule_families=len({name for _, study in studies if study.get("post_final_test_research") for name in study["rules"]}),
        selected_micro_replays=len(post_rows), economic_qualified=sum(row.get("economic_research_qualified", False) for row in post_rows),
        leading_observed_candidate=leading, leading_annual_pnl=annual, independent_confirmation=False,
        selection_period="Reused actual MES/MNQ 2024–2025", new_test_prices_accessed=False,
        final_test_manifest_unchanged=True, final_test_reservation_sha256=file_hash(reservation_path), live_execution_enabled=False)
    json_write(ROOT/"reports/post_final_research_summary.json", post_summary)
    post_lines = ["# Additional strategy research after the frozen final test", "",
        f"Screened {post_summary['distinct_new_rule_families']} new rule families in {post_summary['completed_reference_screens']} reference-market/configuration cases using ES/NQ 2010–2023. Selected candidates then received {len(post_rows)} actual MES/MNQ 2024–2025 continuous-account replays with cost stress. No new 2026 prices were loaded. The original final-test reservation remains consumed.", "",
        "These are reused selection-period results, not independent out-of-sample confirmation. No candidate passes every economic/confidence check or is enabled for live trading.", "",
        "| Study | Transfer | Candidate | Net | Maximum DD | Trades | 2× costs net | All checks |",
        "|---|---|---|---:|---:|---:|---:|---|"]
    for row in post_rows:
        m = row["metrics"]
        post_lines.append(f"| {row['study']} | {row['transfer']} | {row['candidate_id']} | ${m['net_pnl']:,.2f} | ${m['max_drawdown']:,.2f} | {m['trades']} | ${row['stress']['2']['net_pnl']:,.2f} | {row.get('economic_research_qualified', False)} |")
    post_lines += ["", "## Leading observed candidate", "",
        f"{leading['transfer']} `{leading['candidate_id']}`: `{json.dumps(leading['candidate'], sort_keys=True)}`. Annual selection-period P&L: `{json.dumps(annual, sort_keys=True)}`. Checks: `{json.dumps(leading['checks'], sort_keys=True)}`.", "",
        "The opening-gap continuation rule observes the completed 09:30–09:44 ET opening candles and the previous complete 09:30–15:59 regular session of the same contract. A gap between 0.1 and 0.6 of the prior regular-session range, followed by opening momentum in the gap direction, requests one entry at the next 09:45 opening price. The leading MNQ variant has a 40-point protective stop and 120-point target, exits at the 11:00 opening price, and takes at most one entry attempt per session. Risk limits, adverse fills and per-side commissions are applied by the shared event simulator.", "",
        "Its 2010–2021 NQ screen lost $2,814 using actual mini contract economics, so its long-history training check fails despite positive 2022 and 2023 reference replays. The 2024–2025 block-bootstrap confidence interval spans zero. Historical drawdown below $2,000 does not guarantee a future loss cap. New forward observations are needed for independent confirmation.", "",
        "An initial gap run was invalidated because its opening-window mask included prior-evening bars; retained artifacts are excluded from valid counts. The correction is covered by a full-session regression test. All original data and research artifacts remain retained.", "",
        "[Interactive equity, monthly P&L and drawdown charts](research_charts.html) · [Strategy inventory](STRATEGY_COUNTS.md)", ""]
    (ROOT/"reports/POST_FINAL_RESEARCH.md").write_text("\n".join(post_lines), encoding="utf-8")
for label, study in studies:
    for pair, detail in study["pairs"].items():
        for row in detail["validation_results"]:
            if "metrics" not in row:
                continue
            m = row["metrics"]
            lines.append(f"| {label} | {pair} | {row['candidate_id']} | ${m['net_pnl']:,.2f} | ${m['max_drawdown']:,.2f} | {m['trades']} | {row.get('economic_research_qualified', False)} |")
if session_study or gap_study:
    lines += ["", "The session/calendar and gap/structure batches were introduced after the frozen final test. Each screens eight fixed rule families on ES/NQ training history and reuses actual 2024–2025 micro history as a selection period. They never load 2026 prices, and no result from these batches has independent final confirmation. A positive reused-period result requires new forward data before any deployment decision. An interrupted gap-study run was invalidated after its opening window included prior-evening candles; the corrected run and full-session regression test replace it. Its original artifacts remain diagnostic records and do not count as valid completed strategies."]
if risk_study:
    improved = risk_study["best_selected"]
    rm = improved["metrics"]
    improvement_text = f"Latest MNQ risk/exit research: **${rm['net_pnl']:,.2f} net**, **${rm['max_drawdown']:,.2f} closing-equity drawdown**, **${rm['max_intraday_drawdown_bound']:,.2f} adverse-intrabar bound**, **{rm['trades']} trades**. Improvement over the reproduced $1,635.50 one-contract baseline: **${risk_study['pnl_improvement']:,.2f}**. This is 2024–2025 reused selection data; the 2026 test was not reused."
    lines += ["", "## Latest risk/exit improvement", "", improvement_text, "",
        "[Risk expansion report](reports/RISK_EXPANSION_RESEARCH.md) gives every tested sizing/exit case, permanent-shutdown failures, cost-stress results and the selection rule."]
    risk_lines = ["# Higher-profit risk and exit research", "", improvement_text, "",
        f"Selected parameters: `{json.dumps(improved['candidate'], sort_keys=True)}`. Actual integer fills, prior-volume participation, per-contract commissions, spread/slippage and a size-dependent impact allowance are replayed. Profit was not obtained by multiplying an existing equity curve.", "",
        "The first stage screens 72 NQ risk/exit combinations over the 2010–2023 training history, then freezes reference-ranked candidates plus explicit size/taper anchors before micro replay. The disclosed follow-up combines the longer exit with larger size after inspecting the first stage; it is additional reused-validation optimization. Original entry conditions remain unchanged. The internal drawdown stop is $1,800 in stage one and $1,900 in the follow-up; every selected result must remain below $2,000 for both closing and adverse-intrabar drawdown and must not permanently stop trading in base or 2×-cost replay. Price gaps can exceed configured stops in future trading.", "",
        "The 2024–2025 results are continuous single-account selection-period simulations. The 2026 market period remains consumed by the original frozen test, with no second evaluation here. Long-history, uncertainty and independent-forward confirmation remain separate evidence requirements. No strategy is enabled for live execution.", "",
        "| Candidate | Max contracts | Stop points | Target multiple | Exit ET | Sizing | Net | Max DD | Intrabar DD | 2× net | 2× DD | Permanent lock | Selection checks |",
        "|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|---|"]
    risk_records = []
    if risk_study.get("parent_path"):
        risk_records.extend(json.loads((Path(risk_study["parent_path"])/"results.json").read_text())["validation_results"])
    risk_records.extend(risk_study["validation_results"])
    risk_records = list({row["candidate_id"]:row for row in risk_records}.values())
    for row in sorted(risk_records, key=lambda row:row["metrics"]["net_pnl"], reverse=True):
        p, m, stress = row["candidate"], row["metrics"], row["stress"]["2"]
        risk_lines.append(f"| {row['candidate_id']} | {p['contracts']} | {p['stop_points']} | {p['payoff']} | {p['exit_minute']//60:02d}:{p['exit_minute']%60:02d} | {p['sizing']} | ${m['net_pnl']:,.2f} | ${m['max_drawdown']:,.2f} | ${m['max_intraday_drawdown_bound']:,.2f} | ${stress['net_pnl']:,.2f} | ${stress['max_drawdown']:,.2f} | {m['permanent_risk_lock']} | {row['selection_qualified']} |")
    risk_lines += ["", f"Selected annual P&L: `{json.dumps(improved['annual_pnl'], sort_keys=True)}`. Remaining evidence checks: `{json.dumps(improved['evidence_checks'], sort_keys=True)}`.", "",
        "| Cost multiplier | Net P&L | Max DD | Intrabar DD | Permanent lock |", "|---|---:|---:|---:|---|"]
    for factor, measured in improved["stress"].items():
        risk_lines.append(f"| {factor}× | ${measured['net_pnl']:,.2f} | ${measured['max_drawdown']:,.2f} | ${measured['max_intraday_drawdown_bound']:,.2f} | {measured['permanent_risk_lock']} |")
    risk_lines += ["", "A higher historical return does not establish a durable edge or guarantee a future $2,000 drawdown cap. Retuning against the same selection years adds overfitting risk. A larger order can receive partial fills, and stressed costs can change risk gates and trade acceptance.", "",
        "The first stage completed all fourteen cases; a duplicate keyword prevented only final report serialization. Publication was recovered from the archived frozen parameters, matching source hashes and completed result files without rerunning the search.", "",
        "[Interactive charts](research_charts.html) · [Full machine-readable study](latest_risk_expansion_study.json) · [Published commission schedule](https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions)", ""]
    (ROOT/"reports/RISK_EXPANSION_RESEARCH.md").write_text("\n".join(risk_lines), encoding="utf-8")
if refinement:
    refinement_text = publish_refinement(ROOT, refinement)
    lines += ["", "## Entry-filter and protective-stop refinement", "", refinement_text, "",
        "[Refinement report](reports/PARETO_REFINEMENT.md) records all selected replays, failed selection checks and retained benchmark."]
if followup:
    followup_text = publish_refinement(ROOT, followup)
    lines += ["", "## Higher profit and lower drawdown follow-up", "", followup_text, "",
        "[Follow-up results](reports/PROFIT_DRAWDOWN_FOLLOWUP.md) compare the saved candidates and causal sizing settings."]
best = next(row for row in adaptive["pairs"]["NQ->MNQ"]["validation_results"] if row["candidate_id"] == final["candidate_id"])
lines += ["", "## Frozen candidate and final test", "",
    "The selected conventional strategy uses a completed 30-minute opening range, at most one entry attempt per session, a stop based on four times the prior completed minute's 20-bar simple ATR, and a target three times that stop distance. It can trade long or short, stops new entry decisions at 11:30 ET, and has noon flattening. Entry size is one MNQ contract; the independent risk stop is $1,800 with a $2,000 measured-drawdown rejection limit. Price gaps can overshoot those thresholds.", "",
    f"Validation: **${best['metrics']['net_pnl']:,.2f} net**, **${best['metrics']['max_drawdown']:,.2f} drawdown**, **{best['metrics']['trades']} trades**. At 2× costs: **${best['stress']['2']['net_pnl']:,.2f}**; at 3× costs: **${best['stress']['3']['net_pnl']:,.2f}**. Its training-history qualification and positive confidence-interval checks failed. Validation performance was concentrated in 2024; 2025 lost $164.", "",
    f"After exact validation reproduction, the implementation, parameters, risk configuration, source hashes and test hash were frozen. An exclusive global reservation was created before any test-price columns were loaded. **One-time 2026 final test: ${final['metrics']['net_pnl']:,.2f} net, ${final['metrics']['max_drawdown']:,.2f} closing-equity drawdown, ${final['metrics']['max_intraday_drawdown_bound']:,.2f} adverse-intrabar drawdown bound, {final['metrics']['trades']} trades over {final['metrics']['session_days']} observed sessions.**", "",
    f"Final-test cost sensitivity: 1.5× **${final['stress']['1.5']['net_pnl']:,.2f}**, 2× **${final['stress']['2']['net_pnl']:,.2f}**, 3× **${final['stress']['3']['net_pnl']:,.2f}**. Risk gates change trade acceptance under different costs, so these outcomes need not be monotonic. The confidence interval includes zero and the sample is small. This is a nominal historical profit/drawdown result, not reliable evidence of durable profitability or a future maximum-loss guarantee.", "",
    "The final-test record is [final_candidate_test.json](reports/final_candidate_test.json). It is consumed; do not delete its reservation or test a second tuned candidate on the same 2026 period. Subsequent strategy changes need a genuinely new forward period or an explicitly disclosed protocol reset.", "",
    "## Graphs, verification and limits", "",
    "[Interactive charts](reports/research_charts.html) show available history, training/validation boundaries, strategy counts, earlier comparisons, continuous validation equity/drawdown/months and the final test in a separate chart. The dashboard runs at [localhost:8511](http://127.0.0.1:8511). Earlier micro-trained 5/15-minute results remain in [the historical comparison](reports/HISTORICAL_MICRO_COMPARISON.md).", "",
    "Windows tests, isolated dependency checks and WSL test receipts are retained with source identities. The WSL dependency closure is pinned separately. Models and checkpoints are trusted local artifacts. Paper checkpoint/restart parity is a historical software check, not forward paper evidence.", "",
    "Actual commissions are modeled from Lucid's [published per-side schedule](https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions): $1.75 for minis and $0.50 for micros; unlisted pass-through charges still need confirmation. Spread/slippage and OHLC ambiguity are explicit assumptions. The historical exchange calendar, platform/API authorization, account-contract details and sustained real-feed paper review remain operational dependencies. User-confirmed settings are 50% evaluation consistency and provider DLL off; the research daily stop is independent.", "",
    "Early experiments were superseded after execution/label corrections and after the user changed the training scope to full reference history. A partial morning-search predecessor was stopped because an early holiday close caused permanent gap lockout; that failure was diagnosed and retained. A Windows checkpoint sharing-lock retry is recorded as an infrastructure-only compatibility patch. Every additional selection opportunity increases overfitting risk; bootstrap intervals and nominal adjusted p-values do not remove that uncertainty.", ""]
if saved_test:
    sm = saved_test["metrics"]
    saved_test_text = f"The saved $6,622 development version was frozen and evaluated once, without tuning: **2026 reused-test net ${sm['net_pnl']:,.2f}, closing drawdown ${sm['max_drawdown']:,.2f}, intrabar drawdown ${sm['max_intraday_drawdown_bound']:,.2f}, {sm['trades']} trades**. It failed profitability. The period was already consumed by an earlier candidate, so this is not independent confirmation. Earlier 2024–2025 validation-guided refinements are development results; future selection must use training data only."
    lines[2:2] = [saved_test_text,"","[Frozen saved-version outcome](reports/SAVED_VERSION_TEST.md)",""]
(ROOT/"MODEL_COMPARISON.md").write_text("\n".join(lines), encoding="utf-8")
summary = ["# Current research handoff", "",
    f"**{counts['distinct_strategy_definitions']} strategy/model definitions, {counts['unique_parameter_configurations']} configurations, {counts['unique_market_configuration_cases']} market/configuration cases and {counts['completed_run_attempts']} completed attempts** are recorded. Reruns and training screens are explicitly separated. See [STRATEGY_COUNTS.md](STRATEGY_COUNTS.md).", "",
    "ES/NQ original one-minute reference history from 2010–2023 was used for fitting and internal selection; actual MES/MNQ 2024–2025 was validation. Reference fitting uses all eligible observations, with per-contract shards and external-memory/batched learners. The longer reference history is not relabeled as pre-2019 micro P&L.", "",
    f"Previously selected drawdown-constrained validation: **${best['metrics']['net_pnl']:,.2f} net / ${best['metrics']['max_drawdown']:,.2f} max DD** on MNQ. Frozen single-use 2026 test: **${final['metrics']['net_pnl']:,.2f} net / ${final['metrics']['max_drawdown']:,.2f} max DD / {final['metrics']['trades']} trades**. This meets the nominal historical profit/drawdown target but fails to establish a dependable profitable trading bot. The test period is consumed; no repeated tuning or second untouched-test claim is allowed.", "",
    "[Graphs](research_charts.html), [full measured results](../MODEL_COMPARISON.md), [strategy-count audit](STRATEGY_COUNTS.md), [final-test manifest](final_candidate_test.json). No real-money execution is enabled.", "",
    "Forward paper data/review, exact account charges and platform permissions, and an authoritative historical calendar remain external dependencies. No paid data, account or subscription was purchased. Earlier crypto experiments and the original Databento ZIP remain preserved.", "",
    "Automatic approval review previously rejected removal of the disposable `.clean-check` environment with “blocked by policy.” It remains a verification environment, not an active price dataset.", ""]
if session_study:
    summary += ["Additional post-final-test session/calendar research is recorded in [latest_session_window_study.json](latest_session_window_study.json). Its 2024–2025 results are reused-period exploration; independent confirmation requires new forward data.", ""]
if gap_study:
    summary += ["The additional opening-gap/prior-session-structure batch is recorded in [latest_gap_structure_minutes_study.json](latest_gap_structure_minutes_study.json), under the same post-final-test exploratory restriction.", ""]
if risk_study:
    summary += [improvement_text, "", "The [risk/exit improvement report](RISK_EXPANSION_RESEARCH.md) includes baseline comparisons and rejected risk-shutdown cases.", ""]
if refinement:
    summary += [refinement_text, "", "[Full refinement results](PARETO_REFINEMENT.md).", ""]
if followup:
    summary += [followup_text, "", "[Full follow-up results](PROFIT_DRAWDOWN_FOLLOWUP.md).", ""]
if saved_test:
    summary[2:2] = [saved_test_text,"","[Frozen saved-version outcome](SAVED_VERSION_TEST.md)",""]
(ROOT/"reports/FINAL_REPORT.md").write_text("\n".join(summary), encoding="utf-8")
handoff = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(),
    status="research_completed_nominal_profitable_backtests_no_deployable_edge", original_request_operational_readiness=False,
    strategy_counts={k: counts[k] for k in ("distinct_strategy_definitions", "unique_parameter_configurations", "unique_market_configuration_cases", "completed_run_attempts", "by_method")},
    training="Original one-minute ES/NQ available 2010–2023", validation="Actual MES/MNQ 2024–2025",
    final_test_evaluated_once=True, final_test=final, test_period_consumed_for_model_selection=True,
    saved_version_reused_test=saved_test, total_recorded_test_evaluations=1 if saved_test is None else 2,
    research_policy="No validation/test tuning. Parameter selection must use training history only; prior validation-guided refinements remain disclosed development results.",
    post_final_test_exploratory_study=None if session_study is None else dict(path=session_study["path"], independent_confirmation=False, test_prices_accessed=False),
    post_final_test_gap_study=None if gap_study is None else dict(path=gap_study["path"], independent_confirmation=False, test_prices_accessed=False),
    post_final_test_risk_study=None if risk_study is None else dict(path=risk_study["path"], best_selected=risk_study["best_selected"], independent_confirmation=False, test_prices_accessed=False),
    post_final_test_refinement=None if refinement is None else dict(path=refinement["path"], goal_met=refinement["goal_met"], best_selected=refinement["best_selected"], independent_confirmation=False, test_prices_accessed=False),
    post_final_test_profit_drawdown_followup=None if followup is None else dict(path=followup["path"], goal_met=followup["goal_met"], best_selected=followup["best_selected"], independent_confirmation=False, test_prices_accessed=False),
    minute_training_rows={k: {field: v[field] for field in ("source_rows", "eligible_rows", "initial_fits", "final_fits")} for k, v in minute["pairs"].items()},
    windows_test_receipt=receipt, other_test_receipts=tests,
    dataset_catalog_sha256=file_hash(ROOT/"data/catalog.json"), live_execution_enabled=False,
    future_profit_or_drawdown_guarantee=False, automatically_rejected_environment_cleanup_retained=True)
json_write(ROOT/"reports/HANDOFF_MANIFEST.json", handoff)
print(json.dumps(dict(definitions=counts["distinct_strategy_definitions"], configurations=counts["unique_parameter_configurations"], attempts=counts["completed_run_attempts"], final_test_net=final["metrics"]["net_pnl"], deployment_eligible=False), indent=2))

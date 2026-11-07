"""Count distinct definitions/configurations without counting reruns as new ideas."""
from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def inventory(root):
    root = Path(root)
    records, diagnostics = [], []
    for directory in sorted((root/"runs").iterdir()):
        if not directory.is_dir():
            continue
        interruption = directory/"interruption.json"
        if interruption.exists() and json.loads(interruption.read_text()).get("status") == "invalidated_engineering_diagnostic":
            diagnostics.append(dict(run=directory.name, status="invalidated_engineering_diagnostic", source=str(interruption.relative_to(root))))
            continue
        protocol_path = directory/"protocol.json"
        protocol = json.loads(protocol_path.read_text()) if protocol_path.exists() else {}
        experiment_path = directory/"experiment.json"
        experiment = json.loads(experiment_path.read_text()) if experiment_path.exists() else {}
        kind = directory.name.rsplit("_2026", 1)[0]
        if kind.startswith(("mes_market", "mnq_market")):
            kind = "micro_primary"
        scope = {key: protocol[key] for key in ("session_policy", "trading_protocol", "design", "features", "risk_protocol") if key in protocol}
        if experiment.get("config"):
            scope["engine_configuration"] = {key: experiment["config"].get(key) for key in
                ("label_horizon", "embargo_bars", "validation_mode", "probability_threshold", "calibration", "maximum_training_rows", "costs", "execution", "risk")}
        def add(family, params, market, minutes, method, source, key, status="completed", metrics=None):
            if status != "completed":
                diagnostics.append(dict(run=directory.name, record=key, status=status, source=source))
                return
            definition = str(family)
            configuration = dict(definition=definition, parameters=params, timeframe_minutes=minutes, study_definition=kind, scope=scope)
            records.append(dict(definition=definition, configuration_id=stable(configuration), configuration=configuration,
                market=str(market), market_case_id=stable(dict(configuration=configuration, market=market)),
                method=method, run=directory.name, source=source, record=str(key),
                net_pnl=None if not metrics else metrics.get("net_pnl")))
        attempts_file = directory/"attempts.json"
        if experiment:
            if attempts_file.exists():
                attempts = json.loads(attempts_file.read_text())
            elif (directory/"attempts.jsonl").exists():
                attempts = [json.loads(line) for line in (directory/"attempts.jsonl").read_text().splitlines() if line.strip()]
            else:
                attempts = []
            if experiment.get("synthetic"):
                continue
            for index, row in enumerate(attempts):
                candidate = row["candidate"]
                add(candidate["name"], candidate, experiment["instrument"], experiment["timeframe"], "event_backtest",
                    str((directory/("attempts.json" if attempts_file.exists() else "attempts.jsonl")).relative_to(root)), index, row.get("status"), row.get("metrics"))
        for file in sorted(directory.glob("*_training_attempts.json")) + sorted(directory.glob("*_screen_attempts.json")):
            market = file.name.split("_")[0]
            rows = json.loads(file.read_text())
            for index, row in enumerate(rows):
                candidate = row.get("candidate", {})
                if kind.startswith("adaptive_opening_minutes"):
                    family = "opening_range_atr_once"
                elif kind.startswith("opening_range_minutes"):
                    family = "opening_range_fixed_once"
                elif kind.startswith("overnight_minutes"):
                    family = "overnight_"+candidate.get("direction", "unknown")
                else:
                    family = candidate.get("name", row.get("candidate_id", "unknown"))
                methods = "training_screen" if "screen_attempts" in file.name else "event_backtest"
                minutes = 15 if kind.startswith("reference_transfer") else 5 if kind.startswith("drawdown_search") else 1
                status = row.get("status", "completed")
                add(family, candidate, market, minutes, methods, str(file.relative_to(root)), index, status)
        if kind.startswith("extended_") or directory.name.startswith("extended_"):
            results = directory/"results.json"
            if not results.exists():
                continue
            for index, row in enumerate(json.loads(results.read_text()).get("attempts", [])):
                result, name = row.get("result", {}), row["name"]
                if "metrics" in result:
                    family = "return_regression" if name.startswith("return_h") else "cost_direction" if name.startswith("three_way_h") else "triple_barrier" if name.startswith("triple_barrier") else name
                    add(family, dict(study=name, parent_protocol=protocol.get("planned", {})), row["instrument"], 15,
                        "event_backtest", str(results.relative_to(root)), index, row["status"], result["metrics"])
                elif "trials" in result:
                    family = name.removeprefix("inner_search_")
                    for trial, attempt in enumerate(result["trials"]):
                        add(family, dict(study="inner_search", hyperparameters=attempt["hyperparameters"]), row["instrument"], 15,
                            "inner_optimization", str(results.relative_to(root)), f"{index}/{trial}", row["status"])
                elif name == "feature_ablation":
                    for group, analysis in result.items():
                        for trial, attempt in enumerate(analysis.get("trials", [])):
                            add("logistic", dict(feature_ablation=group, hyperparameters=attempt["hyperparameters"]), row["instrument"], 15,
                                "inner_optimization", str(results.relative_to(root)), f"{index}/{group}/{trial}", row["status"])
                else:
                    diagnostics.append(dict(run=directory.name, record=name, status=row["status"], source=str(results.relative_to(root))))
    definitions = sorted(set(row["definition"] for row in records))
    by_method = {method: len({row["market_case_id"] for row in records if row["method"] == method}) for method in sorted(set(row["method"] for row in records))}
    return dict(created_at=datetime.now(timezone.utc).isoformat(),
        distinct_strategy_definitions=len(definitions), strategy_definitions=definitions,
        unique_parameter_configurations=len(set(row["configuration_id"] for row in records)),
        unique_market_configuration_cases=len(set(row["market_case_id"] for row in records)),
        completed_run_attempts=len(records), failed_or_diagnostic_records=len(diagnostics),
        repeated_completed_attempts=len(records)-len(set(row["market_case_id"] for row in records)),
        by_method=by_method, definitions_note="A definition is a strategy/model rule name; changing market, parameters or rerunning does not create a new definition. Configurations include timeframe, feature-study and execution-session scope. Market cases additionally distinguish the instrument. Historical corrected/interrupted runs are retained. Training screens are approximate and separately labeled; pure model-fit/unit tests and cost-stress reruns are excluded.",
        counted_attempt_scope="Registered primary evaluations, reference candidate screening/selection grids, dedicated training-attempt records and inner optimization records. Selected micro-validation replays, final-test evaluation, cost-stress reruns and historical auxiliary verification without a dedicated attempt record are reported separately and are not added again to this search-attempt total.",
        records=records, diagnostics=diagnostics)


if __name__ == "__main__":
    from quant_futures.research import json_write
    root = Path(__file__).resolve().parents[1]
    report = inventory(root)
    json_write(root/"reports/strategy_counts.json", report)
    summary = {key: report[key] for key in ("distinct_strategy_definitions", "unique_parameter_configurations", "unique_market_configuration_cases", "completed_run_attempts", "by_method")}
    lines = ["# Strategies tested", "", f"Distinct strategy/model definitions: **{report['distinct_strategy_definitions']}**.", "",
        f"Unique parameter/timeframe/feature configurations: **{report['unique_parameter_configurations']}**. Unique market/configuration cases: **{report['unique_market_configuration_cases']}**. Completed recorded attempts including reruns: **{report['completed_run_attempts']}**.", "",
        report["definitions_note"], "", report["counted_attempt_scope"], "", "| Definition | Unique configurations | Unique market cases | Completed attempts |", "|---|---:|---:|---:|"]
    for name in report["strategy_definitions"]:
        rows = [row for row in report["records"] if row["definition"] == name]
        lines.append(f"| {name} | {len(set(row['configuration_id'] for row in rows))} | {len(set(row['market_case_id'] for row in rows))} | {len(rows)} |")
    (root/"reports/STRATEGY_COUNTS.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

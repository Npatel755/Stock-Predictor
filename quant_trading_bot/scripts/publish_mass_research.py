"""Publish the completed training search from saved records, never market prices."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT/"reports"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536),b""):
            value.update(chunk)
    return value.hexdigest()


def atomic_json(path,value):
    path = Path(path)
    temporary = path.with_name(path.name+".tmp")
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    temporary.replace(path)


def run_directory(result):
    path = Path(result["run_path"])
    if not path.is_absolute():
        path = ROOT/path
    path = path.resolve()
    if not path.is_relative_to((ROOT/"runs").resolve()) or not path.is_dir():
        raise ValueError("Research artifacts must be in an existing project runs directory")
    return path


def config_id(row):
    for key in ("config_id","candidate_id","configuration_id","id"):
        if key in row:
            return str(row[key])
    raise ValueError("A configuration record is missing its stable identifier")


def verify_records(result,folder):
    target = int(result["target"])
    completed = int(result["completed"])
    unique = int(result["unique_configs"])
    if target < 10000 or completed < target or unique < target:
        raise ValueError("The 10,000-configuration search is incomplete; do not publish completion")
    for key in ("validation_accessed","test_accessed"):
        alternate = key.replace("_accessed","_prices_accessed")
        if result.get(key,result.get(alternate)) is not False:
            raise ValueError("Explicit no-validation/test-price-access flags are required")
    csv_path,config_path = folder/"ranked.csv",folder/"configurations.jsonl"
    with csv_path.open(encoding="utf-8-sig",newline="") as stream:
        rows = list(csv.DictReader(stream))
    ranked_ids = [config_id(row) for row in rows]
    manifest_ids = []
    with config_path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                manifest_ids.append(config_id(json.loads(line)))
    if len(rows) != completed or len(ranked_ids) != len(set(ranked_ids)):
        raise ValueError("Ranked CSV count/unique IDs do not match completed experiments")
    if len(manifest_ids) != unique or len(manifest_ids) != len(set(manifest_ids)):
        raise ValueError("Configuration manifest count/unique IDs do not match the declared search")
    if set(ranked_ids) != set(manifest_ids):
        raise ValueError("Completed experiment IDs and the frozen configuration manifest differ")
    top = result.get("top10",[])
    if len(top) > 10 or any(config_id(row) not in set(ranked_ids) for row in top):
        raise ValueError("The top-10 list is not a subset of completed experiment IDs")
    if len({config_id(row) for row in top}) != len(top):
        raise ValueError("The frozen shortlist contains duplicate configurations")
    if result.get("fresh_holdout_available") is not False:
        raise ValueError("Previously observed periods cannot be relabeled as fresh holdouts")
    if result.get("validation_status") != "blocked_previously_observed" or result.get("test_status") != "blocked_previously_observed":
        raise ValueError("This publication requires explicit blocked validation/test status")
    return dict(csv_rows=len(rows),unique_ranked_ids=len(set(ranked_ids)),
        manifest_rows=len(manifest_ids),top10_rows=len(top),
        ranked_csv_sha256=sha256(csv_path),configurations_sha256=sha256(config_path))


def text(value):
    return str(value).replace("|","\\|").replace("\r"," ").replace("\n"," ")


def number(value,digits=2):
    if value is None:
        return "—"
    return f"{float(value):,.{digits}f}"


def row_value(row,key,default=None):
    return row.get(key,row.get("metrics",{}).get(key,default))


def render_reports(result,folder,verification):
    qualified = int(result.get("qualified_count",0))
    complete = int(result["completed"])
    relative = Path(os.path.relpath(folder,REPORTS)).as_posix()
    lines = ["# 10,000-configuration training research", "",
        f"**{complete:,} completed configurations; {int(result['unique_configs']):,} unique IDs verified.** "
        f"{qualified:,} met the declared training qualification checks. Validation and final testing are **BLOCKED** because the available later periods have already been observed.","",
        "This is a training research result, not a claim of profitable unseen performance. No market-price data are read by this report publisher. "
        "The search reports that validation and test prices were not opened. Existing split boundaries remain unchanged: training ends before 2024; validation is 2024–2025; testing is 2026. "
        "Repartitioning or forgetting earlier results would not restore an untouched holdout.","",
        "## Protocol and reproducibility", "",
        f"Seed: `{text(result.get('seed','not recorded'))}`. Fixed search target: **{int(result['target']):,}**. "
        "Configuration IDs were reconciled between the ranked CSV and configuration manifest. These checks establish record identity and completeness; equivalence deduplication depends on the search generator's declared canonicalization.","",
        "Split/selection policy:","",f"`{text(json.dumps(result.get('split_policy',{}),sort_keys=True))}`", "",
        "Source identities:","", "```json",json.dumps(result.get("source_hashes",{}),indent=2,sort_keys=True),"```","",
        f"[Ranked results for all configurations]({relative}/ranked.csv) · [Reproducible configuration manifest]({relative}/configurations.jsonl)","",
        "## Training shortlist", "",
        "All values below are training measurements under the recorded contract specifications, costs and account assumptions. "
        "Mini-contract results must not be relabeled as micro-contract history. Training drawdown below $2,000 does not guarantee a future loss ceiling. "
        "Net sums four disjoint fold accounts with capital reset. Drawdowns are worst separate folds. Profit factor pools trade P&L; Sharpe is the mean of fold daily Sharpes. Duration is minutes.","",
        "| Configuration | Instrument | Family | Net | Closing DD | Cash DD | Intrabar DD | Profit factor | Sharpe | Win rate | Expectancy | Trades | Avg duration | Positive folds | Training qualified |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for row in result.get("top10",[]):
        win = row_value(row,"win_rate")
        win_text = "—" if win is None else f"{float(win):.1%}"
        folds = row.get("total_folds",row.get("folds","—"))
        if not isinstance(folds,(int,str)):
            folds = len(folds)
        values = [config_id(row),row.get("instrument","—"),row.get("family","—"),
            "$"+number(row_value(row,"net_pnl")),"$"+number(row_value(row,"max_drawdown")),
            "$"+number(row_value(row,"realized_drawdown")),"$"+number(row_value(row,"intrabar_drawdown")),
            number(row_value(row,"profit_factor")),number(row_value(row,"sharpe")),win_text,
            "$"+number(row_value(row,"expectancy",row_value(row,"expected_value_per_trade"))),
            number(row_value(row,"trades"),0),number(row_value(row,"avg_duration")),
            f"{row.get('positive_folds','—')}/{folds}",bool(row.get("qualified",False))]
        lines.append("| "+" | ".join(text(value) for value in values)+" |")
    if not result.get("top10"):
        lines += ["", "No top-10 candidate list was supplied. Do not infer a passing strategy from completion of the search."]
    lines += ["", "## Event-driven verification", "",
        "Every search configuration uses the sequential JIT event simulator. Frozen finalists reproduce their base run and receive a2× cost stress. Independent ledger arithmetic covers every finalist trade; up to25 evenly spaced trades per fold are also replayed through the separate shared simulator. "
        "These isolated trade checks verify fills and economics. Account-path equivalence is not claimed: the older simulator omits pre-exit adverse bounds and exit-cost reserves. No strategy is promoted automatically.","",
        "| Candidate | Base reproduced | Ledger trades checked | Shared trade replays | 2× cost net | 2× closing DD | 2× intrabar DD | 2× training qualified |",
        "|---|---|---:|---:|---:|---:|---:|---|"]
    for item in result.get('execution_verification',[]):
        checks=item.get('execution_parity',[])
        if not isinstance(checks,list): checks=[]
        stress=item.get('stress_2x',{})
        lines.append('| '+' | '.join(text(v) for v in [item['config_id'],item.get('base_reproduced',False),
            sum(v.get('ledger_trades',0) for v in checks),sum(v.get('shared_simulator_replayed',0) for v in checks),
            '$'+number(stress.get('net_pnl')),'$'+number(stress.get('max_drawdown')),
            '$'+number(stress.get('intrabar_drawdown')),stress.get('qualified',False)])+' |')
    lines += ["",
        "## PASS/FAIL and missing confirmation", "",
        f"- Full training search: **PASS** — {complete:,} completed records reconciled to unique configuration IDs.",
        f"- Declared training qualification: **{'PASS for '+str(qualified)+' configurations' if qualified else 'FAIL — no qualifying configuration'}**.",
        "- Profitability on genuinely unseen validation: **NOT ESTABLISHED — BLOCKED**. Do not claim a pass from earlier reused validation results.",
        "- Drawdown below $2,000 on genuinely unseen validation: **NOT ESTABLISHED — BLOCKED**.",
        "- Final untouched test: **NOT RUN — BLOCKED**. The 2026 period has already been consumed.",
        "- Exact funded-account compliance: **NOT ESTABLISHED** unless separately verified against the actual account agreement, platform permission, charges, trailing-loss mechanics and consistency rules. Configurable assumptions do not establish compliance.",
        "- Live deployment: **FAIL / not eligible**. No live execution is authorized.","",
        "The 50% consistency requirement and every other funded-account rule must remain explicit in the account configuration. "
        "No unverified account-specific term is assumed here. A strategy must pass the complete execution, cost, account and independent-observation checks before any success claim.","",
        "## Artifacts and next legitimate evaluation", "",
        f"[Strategy rules, fold detail, exported curves and trade ledgers]({relative}/RESEARCH_DETAILS.md). "
        f"[Frozen protocol]({relative}/protocol.json) · [Finalist verification]({relative}/finalist_training_checks.json).", "",
        "Equity/drawdown and trade-by-trade artifacts, when generated by event-driven verification, remain under the run directory. "
        "The publisher does not fabricate curves or trades for a vectorized screen. Review the execution-verification records for exact available filenames and unresolved checks.","",
        "[Validation status](MASS_VALIDATION_REPORT.md) · [Final test status](MASS_TEST_REPORT.md) · [Dashboard](http://127.0.0.1:8511)","",
        "A new evaluation requires genuinely untouched forward observations and a frozen shortlist/ranking/evaluation protocol. "
        "Do not tune candidates from validation/test outcomes or repeatedly inspect those periods during continued training research.",""]
    (REPORTS/"MASS_RESEARCH_REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    for kind,title,period in (("VALIDATION","One-time validation report","2024–2025"),("TEST","Final untouched-test report","2026")):
        report = ["# "+title,"", "**BLOCKED — no genuinely untouched period is currently available.**","",
            f"The existing {period} {kind.lower()} period has already been observed in earlier research. "
            "Its boundaries are preserved. A new 60/20/20 split, relabeling, or withholding earlier reports cannot undo that exposure.","",
            "No new price evaluation was performed for this stage of the 10,000-configuration search. "
            "There are no new validation/test P&L, drawdown, curves or trades to report; none are invented.","",
            "Freeze the training-selected shortlist and all selection/evaluation criteria before collecting genuinely new forward data. "
            "Run that predetermined evaluation once; if it fails, report failure without creating validation-driven alternatives.","",
            "Earlier disclosed reused-period evaluations remain separate historical records and are not substituted for this missing independent evaluation.","",
            "[Training research](MASS_RESEARCH_REPORT.md)",""]
        (REPORTS/("MASS_"+kind+"_REPORT.md")).write_text("\n".join(report),encoding="utf-8")


def main():
    result_path = REPORTS/"mass_research_result.json"
    result = read_json(result_path)
    folder = run_directory(result)
    checks = verify_records(result,folder)
    render_reports(result,folder,checks)
    receipt = dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),
        publication_only_no_price_reads=True,strategy_replayed=False,**checks,
        source_result_sha256=sha256(result_path),validation_status="blocked_previously_observed",
        test_status="blocked_previously_observed",independent_confirmation=False,
        live_execution_enabled=False)
    atomic_json(REPORTS/"mass_research_publication_verification.json",receipt)
    print(json.dumps(dict(published=True,completed=result["completed"],qualified=result.get("qualified_count",0),validation="BLOCKED",test="BLOCKED")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()

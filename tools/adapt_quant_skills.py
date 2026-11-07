"""Adapt the user-supplied quant skill pack for Codex without executing its content."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


def adapt(name, content):
    content = content.replace("\r\n", "\n").replace("Devin", "Codex")
    content = content.replace("use when Codex is tasked with full strategy research or 10000+ candidate evaluations.",
        "use for multi-stage trading-strategy research or large training-only configuration searches.")
    content = content.replace("Guarantee reliable point-in-time inputs and reproducibility. Fail closed on unidentified gaps.",
        "Audit point-in-time inputs and reproducibility. Block trading claims when unresolved data faults invalidate the simulation.")
    content = content.replace("signed price change � verified contract multiplier � quantity", "signed price change × verified contract multiplier × quantity")
    if name == "research-orchestrator":
        content = content.replace("No candidate passes predefined gates -> report no credible edge. Do not mine protected data, invent results or keep searching until luck makes something look profitable.",
            "If no candidate passes the predefined gates, report no credible edge. Complete an explicitly requested finite training-search budget even when early candidates fail or succeed; do not stop merely to obtain a favorable result. Never extend a protected validation/test stage or change candidates from its outcomes. Stop a run for missing required data, an unrecoverable execution error, an explicit resource limit, or user instruction; preserve resumable checkpoints.")
        content = content.replace("## Workflow\n", "## Scope and discovery\n\n"
            "Preserve the user's existing split boundaries, research budget, authorization and project instructions. This skill does not authorize new holdout evaluations, purchases, live connections, messages, trades or deployments. Never relabel observed data as untouched. Parameter fitting, feature selection and strategy development use training data only; validation may apply only a ranking rule and shortlist frozen beforehand. If the relevant validation/test period has already been used, record that limitation and require fresh forward observations for independent confirmation.\n\n"
            "Load sibling skills only for the current work. These installed siblings are available in the same parent directory:\n\n"
            "- Data and contract provenance: [data-integrity](../data-integrity/SKILL.md), [futures-contract-lifecycle](../futures-contract-lifecycle/SKILL.md), [cross-contract-transfer](../cross-contract-transfer/SKILL.md).\n"
            "- Strategy development and evidence: [strategy-discovery](../strategy-discovery/SKILL.md), [walk-forward-validation](../walk-forward-validation/SKILL.md), [overfitting-defense](../overfitting-defense/SKILL.md), [negative-control-testing](../negative-control-testing/SKILL.md), [market-regime-analysis](../market-regime-analysis/SKILL.md), [economic-event-research](../economic-event-research/SKILL.md).\n"
            "- Simulation and risk: [backtesting-engine](../backtesting-engine/SKILL.md), [simulator-verification](../simulator-verification/SKILL.md), [execution-optimization](../execution-optimization/SKILL.md), [risk-management](../risk-management/SKILL.md), [risk-of-ruin-monte-carlo](../risk-of-ruin-monte-carlo/SKILL.md), [portfolio-construction](../portfolio-construction/SKILL.md).\n"
            "- Forward operation: [paper-trading-reconciliation](../paper-trading-reconciliation/SKILL.md), [deployment-safety-monitoring](../deployment-safety-monitoring/SKILL.md).\n\n## Workflow\n")
    if name in ("risk-management", "cross-contract-transfer"):
        content += "\nThe specification values above are reference arithmetic, not a current verification receipt. Verify current official contract/account specifications before relying on them for financial decisions; retain user-confirmed settings and unresolved fields separately.\n"
    if name == "economic-event-research":
        content += "\nThe dated links are examples of official source types. Use the historical releases and schedules corresponding to the requested research dates; do not treat a current calendar as evidence of past publication timing.\n"
    if name == "simulator-verification":
        content = content.replace("Adding nonnegative costs to identical fills cannot increase net P&L.",
            "Adding nonnegative costs to an identical fixed trade/fill sequence cannot increase net P&L. When cost changes alter risk gates, quantities or trade acceptance, compare those paths separately rather than enforcing monotonic terminal P&L across different trades.")
    return content.rstrip()+"\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--destination",type=Path,required=True)
    parser.add_argument("--artifact-dir",type=Path,required=True)
    parser.add_argument("--validator",type=Path,required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("skill_validation",args.validator)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    source_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
    artifacts = args.artifact_dir.resolve()
    artifacts.mkdir(parents=True,exist_ok=True)
    stage = artifacts/"quant-skills-codex"
    stage.mkdir(exist_ok=False)
    report = dict(created_at=datetime.now(timezone.utc).isoformat(),source=str(args.source),source_sha256=source_hash,
        destination=str(args.destination),skills=[],validation=[],archive_scripts_executed=False,
        automatic_discovery=True,adaptations=["Codex naming", "Sibling skill links", "Finite search budget and protected-split rules", "No implied live authorization", "Fixed-fill versus changed-path cost checks", "Dated reference caveats"])
    with zipfile.ZipFile(args.source) as archive:
        members = [item for item in archive.infolist() if item.filename.endswith("/SKILL.md")]
        if len(members) != 18:
            raise ValueError("Expected exactly eighteen skills")
        for member in members:
            path = PurePosixPath(member.filename)
            if path.is_absolute() or ".." in path.parts or path.parts[:2] != (".agents","skills") or len(path.parts) != 4:
                raise ValueError("Unexpected archive skill path")
            name = path.parts[-2]
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",name):
                raise ValueError("Invalid skill name")
            text = adapt(name,archive.read(member).decode("utf-8"))
            target = stage/name
            target.mkdir(exist_ok=False)
            (target/"SKILL.md").write_text(text,encoding="utf-8")
            ok,message = validator.validate_skill(target)
            if not ok:
                raise ValueError(name+": "+message)
            if (args.destination/name).exists():
                raise FileExistsError("Existing skill will not be overwritten: "+name)
            installed_bytes=(target/"SKILL.md").read_bytes()
            report["skills"].append(dict(name=name,sha256=hashlib.sha256(installed_bytes).hexdigest(),bytes=len(installed_bytes)))
            report["validation"].append(dict(name=name,passed=ok,message=message))
    # Preflight every skill before the first install. The ZIP's install prompt
    # and readmes are source material only, not executable instructions.
    args.destination.mkdir(parents=True,exist_ok=True)
    for skill in report["skills"]:
        name = skill["name"]
        folder = args.destination/name
        folder.mkdir(exist_ok=False)
        (folder/"SKILL.md").write_bytes((stage/name/"SKILL.md").read_bytes())
        ok,message = validator.validate_skill(folder)
        if not ok:
            raise ValueError("Installed validation failed: "+name+": "+message)
    package = artifacts/"quant-skills-codex.zip"
    with zipfile.ZipFile(package,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage.glob("*/SKILL.md")):
            archive.write(path,path.relative_to(stage).as_posix())
    report["package"] = str(package)
    report["installed"] = len(report["skills"])
    report["all_valid"] = True
    (artifacts/"quant-skills-installation.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(installed=report["installed"],all_valid=True,destination=str(args.destination),package=str(package))))


if __name__ == "__main__":
    main()

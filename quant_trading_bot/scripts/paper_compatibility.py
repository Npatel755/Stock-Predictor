"""Audit a checkpoint-write-only patch without rewriting frozen market research."""
from pathlib import Path
import zipfile
import joblib
from quant_futures.config import file_hash
from quant_futures.research import code_identity, json_write


def verify_compatibility(directory, registration):
    current = code_identity()
    added = sorted(set(current["source_files"])-set(registration["source_files"]))
    removed = set(registration["source_files"])-set(current["source_files"])
    if removed or set(added)-{"transfer.py"}:
        raise ValueError("Source inventory changed")
    changed = [name for name, sha in current["source_files"].items() if name in registration["source_files"] and registration["source_files"][name] != sha]
    if not changed:
        return dict(source_identical=not added, parent_source_hash=registration["source_hash"], current_source_hash=current["source_hash"],
            added_unused_modules=added, scope="Existing source files are identical; any added transfer module is not imported by the historical research or paper path.")
    if changed != ["durable_paper.py"]:
        raise ValueError("Research source changed; no infrastructure-only compatibility migration allowed")
    with zipfile.ZipFile(Path(directory)/"code_snapshot.zip") as archive:
        before = archive.read("quant_futures/durable_paper.py").decode("utf-8")
    after = (Path(__file__).resolve().parents[1]/"src/quant_futures/durable_paper.py").read_text(encoding="utf-8")
    before, after = before.replace("\r\n", "\n"), after.replace("\r\n", "\n")
    retry = """        for attempt in range(12):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if attempt == 11:
                    raise
                time.sleep(min(.025*2**attempt, .5))
"""
    assert before.count("        temporary.replace(path)\n") == 1
    if before.replace("        temporary.replace(path)\n", retry) != after:
        raise ValueError("Checkpoint patch differs from the reviewed bounded file-replacement retry")
    return dict(source_identical=False, parent_source_hash=registration["source_hash"], current_source_hash=current["source_hash"],
        changed_files=changed, added_unused_modules=added,
        scope="Only bounded retries for checkpoint-file replacement and an independent added transfer module. All other historical research/model/features/execution/risk source bytes are identical.")


def paper_bundle(directory, registration):
    directory = Path(directory)
    compatibility = verify_compatibility(directory, registration)
    original = directory/"candidate.joblib"
    bundle = joblib.load(original)
    weights = joblib.hash(bundle["model"])
    if not compatibility["source_identical"]:
        bundle = dict(bundle, source_hash=compatibility["current_source_hash"],
            parent_source_hash=compatibility["parent_source_hash"], parent_model_hash=file_hash(original),
            compatibility_scope="Historical paper verification only; original frozen research artifact remains immutable", deployment_eligible=False)
        assert joblib.hash(bundle["model"]) == weights
        joblib.dump(bundle, directory/"paper_candidate.joblib", compress=3)
    json_write(directory/"paper_compatibility.json", dict(**compatibility, model_weights_hash=weights,
        original_artifact_sha256=file_hash(original), original_frozen_artifact_modified=False))
    return bundle

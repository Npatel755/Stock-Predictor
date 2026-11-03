"""Validate and label frozen research presets independently of chart rendering."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import BacktestResult


def attach_research_profile(result: BacktestResult, configuration: Path):
    """Label a preset only when its exact configuration and Pine hash match."""
    configuration = Path(configuration)
    metadata_path = configuration.with_name(configuration.stem + ".metadata.json")
    if not metadata_path.exists():
        return
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(json.dumps(result.config, sort_keys=True).encode()).hexdigest()
    if digest != metadata.get("configuration_sha256"):
        return
    name = metadata.get("strategy_name")
    if name != "DVS ETH v1.2":
        return
    derivative = configuration.parent.parent / "reference/DVS_ETH_v1_2.pine"
    if not derivative.exists() or hashlib.sha256(derivative.read_bytes()).hexdigest() != metadata.get("pine_sha256"):
        raise ValueError("Saved strategy's Pine derivative does not match its metadata")
    result.provenance.update(research_profile=name + " (experimental)",
                             research_derivative_sha256=metadata["pine_sha256"],
                             base_pine_version=result.config["strategy_version"],
                             historical_gate_passed=metadata.get("passed_predeclared_validation_gate", False))

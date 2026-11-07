"""Predeclared real-data validation comparisons. Never consumes final test."""
import os
for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"
from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import argparse
from threadpoolctl import threadpool_limits
from quant_futures.config import load_config, file_hash
from quant_futures.research import run_research, code_identity, json_write

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--minutes", type=int, choices=[5, 15], default=15)
minutes = parser.parse_args().minutes
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
protocol_path = ROOT/"reports"/f"market_campaign_{stamp}.json"
previous_path = ROOT/"reports/latest_market_campaign.json"
previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
protocol = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(),
    split_protocol=json.loads((ROOT/"data/catalog.json").read_text())["split_protocol"],
    instruments=["MES", "MNQ"], timeframe_minutes=minutes,
    rationale="Declared 5/15-minute resolution supplies multi-year validation with bounded resources. A five-minute sensitivity campaign is registered after the user freed disk, without tuning model parameters from the fifteen-minute results. Same declared costs/risk for all families. Flat cutoff is explicitly 16:30 ET, an available bar open before the published 16:45 deadline. Bar-based feature, label and holding horizons scale with resolution; training is capped at the latest 100000 observations, not identical elapsed training history.",
    objectives=["forward return direction; ridge return regression", "donchian meta-label"],
    comparison="16 conventional baselines, rule regime, equal ensemble, logistic/ridge/tree/LightGBM/XGBoost and breakout meta-model",
    test_policy="No final test evaluation unless a statistically and operationally eligible candidate is established; no such decision is made by this script.",
    fee_status="Illustrative configuration assumptions, not a broker fee quotation", runs={})
protocol["funded_rules_sha256"] = file_hash(ROOT/"configs/lucidflex.yaml")
json_write(protocol_path, protocol)
with threadpool_limits(limits=1):
    for instrument in protocol["instruments"]:
        suffix = "" if minutes == 15 else "_5m"
        config_file = ROOT/"configs"/f"{instrument.lower()}_market{suffix}.yaml"
        cfg = load_config(config_file)
        output = ROOT/"runs"/f"{instrument.lower()}_market_{stamp}"
        protocol["runs"][instrument] = dict(path=str(output), config_sha256=file_hash(config_file), status="running")
        json_write(protocol_path, protocol)
        print(f"Starting {instrument}: {output}", flush=True)
        cache = previous.get("runs", {}).get(instrument, {}).get("path")
        if cache and json.loads((Path(cache)/"experiment.json").read_text())["timeframe"] != minutes:
            cache = None
        run_research(instrument, cfg, output, ROOT/"configs/lucidflex.yaml", feature_cache=cache)
        shutil.copyfile(config_file, output/"research_config.yaml")
        shutil.copyfile(ROOT/"configs/lucidflex.yaml", output/"funded_rules.yaml")
        protocol["runs"][instrument].update(status="complete", summary=json.loads((output/"summary.json").read_text()))
        json_write(protocol_path, protocol)
        print(f"Completed {instrument}", flush=True)
protocol["completed_at"] = datetime.now(timezone.utc).isoformat()
json_write(protocol_path, protocol)
json_write(ROOT/"reports/latest_market_campaign.json", protocol)
json_write(ROOT/"reports"/f"final_market_campaign_{minutes}m.json", protocol)

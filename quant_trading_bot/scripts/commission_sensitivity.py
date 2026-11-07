"""Published-commission counterfactual for preselected development candidates."""
import os
for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "1"
from pathlib import Path
from datetime import datetime, timezone
import json
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import ResearchConfig, file_hash
from quant_futures.research import load_dataset, candidate_signal, json_write, code_identity, _combined
from quant_futures.backtest import run_backtest
from quant_futures.metrics import summarize
from paper_compatibility import verify_compatibility

ROOT = Path(__file__).resolve().parents[1]
source = "https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions"
report = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(), test_accessed=False,
    source=source, accessed_on="2026-11-06", published_commission_per_side=dict(MES=.5, MNQ=.5),
    policy="Preselect the primary ranking's best baseline and frozen candidate; retain models and signals, rerun the same validation folds with the published $0.50 per-side commission as the only explicit cash fee. This is a cost counterfactual, not a new model search or a claim about unlisted pass-through charges. Spread/slippage assumptions remain unchanged.",
    results=[])
json_write(ROOT/"reports/commission_sensitivity_protocol.json", report)
with threadpool_limits(limits=1):
    for protocol_file in sorted((ROOT/"reports").glob("final_market_campaign_*m.json")):
        protocol = json.loads(protocol_file.read_text())
        for instrument, run in protocol["runs"].items():
            directory = Path(run["path"])
            registration = json.loads((directory/"experiment.json").read_text())
            verify_compatibility(directory, registration)
            leaderboard = json.loads((directory/"leaderboard.json").read_text())
            bundle = joblib.load(directory/"candidate.joblib")
            cfg = ResearchConfig.model_validate(bundle["config"])
            alternate = cfg.model_copy(update={"costs": cfg.costs.model_copy(update={"commission_per_side": .5, "exchange_per_side": 0, "regulatory_per_side": 0})})
            bars, _, _ = load_dataset(instrument, minutes=cfg.timeframe_minutes)
            feature_file = directory/"development_features.parquet"
            assert file_hash(feature_file) == registration["feature_set"]
            features = pd.read_parquet(feature_file)
            folds = [np.arange(f["validation"][0], f["validation"][1]+1) for f in registration["validation_folds"]]
            best_baseline = next(row for row in leaderboard if row["family"] == "baseline")
            candidates = [(best_baseline["candidate_id"], dict(family="baseline", name=best_baseline["model"]), None)]
            selected_id = json.loads((directory/"summary.json").read_text())["selected_for_research_only"]
            if selected_id != best_baseline["candidate_id"]:
                candidates.append((selected_id, bundle["candidate"], bundle["model"]))
            for cid, candidate, model in candidates:
                signal = candidate_signal(candidate, bars, features, cfg, model)
                pieces = [run_backtest(bars.iloc[valid].reset_index(drop=True), signal.iloc[valid].reset_index(drop=True), alternate) for valid in folds]
                measured = summarize(_combined(pieces, cfg.initial_balance), cfg.initial_balance, trials=256)
                original = next(row for row in leaderboard if row["candidate_id"] == cid)
                report["results"].append(dict(instrument=instrument, timeframe_minutes=cfg.timeframe_minutes, candidate_id=cid,
                    original_total_cash_fee_per_side=cfg.costs.fee, published_commission_scenario_cash_fee_per_side=.5,
                    original_net_pnl=original["net_pnl"], counterfactual=measured, deployment_eligible=False))
                json_write(ROOT/"reports/commission_sensitivity.json", report)
                print(instrument, cfg.timeframe_minutes, cid, round(measured["net_pnl"], 2), flush=True)
report["completed_at"] = datetime.now(timezone.utc).isoformat()
json_write(ROOT/"reports/commission_sensitivity.json", report)

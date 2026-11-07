"""Train on ES/NQ from 2010; select inside training; validate actual micros later."""
import os
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
from pathlib import Path
from datetime import datetime, timezone
import gc
import json
import shutil
import zipfile
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.transfer import PAIRS, guarded_partition, transfer_features, trading_config, morning_indexes
from quant_futures.features import build_features
from quant_futures.labels import future_returns
from quant_futures.models import fit_model, calibration_metrics
from quant_futures.strategies import baseline
from quant_futures.backtest import run_backtest
from quant_futures.metrics import summarize
from quant_futures.research import code_identity, json_write
from quant_futures.config import file_hash, digest

ROOT = Path(__file__).resolve().parents[1]
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
output = ROOT/"runs"/f"reference_transfer_{stamp}"
output.mkdir(exist_ok=False)
identity = code_identity()
report = dict(created_at=datetime.now(timezone.utc).isoformat(), **identity, script_sha256=file_hash(__file__),
    user_requested_training="ES/NQ available contract history from 2010 through 2023; no micro observations used for fitting",
    protocol=dict(outer_training_end_exclusive="2024-01-01T00:00:00Z",
        inner_model_fit_end_exclusive="2022-01-01T00:00:00Z", inner_selection_years=[2022, 2023],
        actual_micro_validation=["2024-01-01T00:00:00Z", "2026-01-01T00:00:00Z"],
        final_test="Actual MES/MNQ 2026 remains reserved; this script cannot load it", no_random_shuffle=True),
    transfer_assumptions="Normalized price/structure/time features only; volume and VWAP transfer features excluded. Mini and micro retain different symbols, multipliers and commissions. All eligible reference training rows are used; the previous 100000-row fitting cap does not apply.",
    trading_protocol="15-minute completed bars; enter 09:45–11:30 ET and flatten at noon ET. No prices filled. Keep the entire active window and one real flat observation per session for replay efficiency; batch/compact accounting parity is unit tested.",
    risk_protocol="Reference simulations use real 1-mini multipliers and 10x account/risk budget for explicit 1-mini/10-micro notional scaling. No historical micro P&L is invented. Actual micro validation uses one contract, $50000 balance, $1800 hard risk stop and a $2000 measured drawdown rejection threshold. Gaps can overshoot hard thresholds.",
    source_commissions="https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions",
    commission_caveat="Published $1.75 mini / $0.50 micro commissions per side; unlisted pass-through charges are not verified. One-tick spread and adverse slippage are retained; higher-cost stress required.",
    strategies=["ema", "sma", "adx", "donchian", "rsi", "bollinger", "opening_range", "momentum", "slow_trend", "opening_fade"],
    ml_models=["logistic", "ridge", "tree", "lightgbm", "xgboost"], thresholds=[.51, .54],
    regular_variants=[dict(width=width, payoff=payoff, hold=8) for width in (1, 2) for payoff in (2, 3)],
    selection="Freeze top 3 training-ranked candidates per pair before reading micro validation prices. Prefer positive net P&L in both inner years, adequate trades and risk robustness; retain diagnostic top 3 even if no training-qualified candidate exists, clearly labeled.",
    test_accessed=False, live_execution_enabled=False, pairs={})
json_write(output/"protocol.json", report)
shutil.copyfile(__file__, output/"study_script.py")
with zipfile.ZipFile(output/"code_snapshot.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for path in (ROOT/"src/quant_futures").glob("*.py"):
        archive.write(path, "quant_futures/"+path.name)


def execute(reference, micro):
    print("Loading reference training", reference, flush=True)
    bars, metadata, quality = guarded_partition(reference, "train")
    features = build_features(bars, 15)
    features.to_parquet(output/f"{reference}_training_features.parquet", index=False)
    normalized = transfer_features(features)
    labels = future_returns(bars, horizon=5, minutes=15)
    before = pd.Timestamp("2022-01-01T00:00Z")
    fit_ids = np.flatnonzero(bars.timestamp_utc.lt(before) & pd.to_datetime(labels.label_end, utc=True).lt(before) & labels.forward_return.notna())
    print(reference, "training bars", len(bars), "inner model fitting rows", len(fit_ids), flush=True)
    models = {}
    model_attempts = []
    for name in report["ml_models"]:
        try:
            models[name] = fit_model(name, normalized.iloc[fit_ids].reset_index(drop=True), labels.iloc[fit_ids].reset_index(drop=True), bars.iloc[fit_ids].reset_index(drop=True))
            model_attempts.append(dict(name=name, status="completed", rows=len(fit_ids),
                start=str(bars.timestamp_utc.iloc[fit_ids[0]]), end=str(bars.timestamp_utc.iloc[fit_ids[-1]])))
        except (ValueError, RuntimeError, ImportError, MemoryError) as error:
            model_attempts.append(dict(name=name, status="failed", error=str(error)))
        json_write(output/f"{reference}_model_fits.json", model_attempts)
        print(reference, "fit", name, model_attempts[-1]["status"], flush=True)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    minute = local.dt.hour*60+local.dt.minute
    allowed = (minute >= 585) & (minute < 690)
    candidates = [dict(family="rule", name=name, **variant) for name in report["strategies"] for variant in report["regular_variants"]]
    candidates += [dict(family="ml", name=name, threshold=threshold, width=2, payoff=2, hold=8)
        for name in models for threshold in report["thresholds"]]
    def signals(candidate, data, all_features, fitted=None):
        if candidate["family"] == "ml":
            signal = fitted.signal(transfer_features(all_features), candidate["threshold"])
        elif candidate["name"] == "slow_trend":
            signal = np.sign(data.close.rolling(80).mean()-data.close.rolling(240).mean()).fillna(0)
        elif candidate["name"] == "opening_fade":
            signal = pd.Series(np.select([data.close > all_features.opening_high, data.close < all_features.opening_low], [-1, 1], 0), index=data.index)
        else:
            signal = baseline(candidate["name"], data, all_features)
        local_time = data.timestamp_utc.dt.tz_convert("America/New_York")
        clock = local_time.dt.hour*60+local_time.dt.minute
        stop_points = trading_config(data.instrument.iloc[0], candidate["width"]).execution.stop_ticks*.25
        return signal.where((clock >= 585) & (clock < 690) & all_features.atr.between(1, stop_points), 0).fillna(0).astype(int)
    active_ids = morning_indexes(bars)
    year_indexes = {year: active_ids[bars.timestamp_utc.iloc[active_ids].dt.year.to_numpy() == year] for year in (2022, 2023)}
    attempts = []
    for number, candidate in enumerate(candidates):
        cid = candidate["name"]+"_"+digest(candidate)[:10]
        row = dict(candidate_id=cid, candidate=candidate, reference=reference, micro=micro, inner_years={})
        try:
            desired = signals(candidate, bars, features, models.get(candidate["name"]))
            cfg = trading_config(reference, candidate["width"], candidate["payoff"], candidate["hold"])
            for year, ids in year_indexes.items():
                result = run_backtest(bars.iloc[ids].reset_index(drop=True), desired.iloc[ids].reset_index(drop=True), cfg)
                metrics = summarize(result, cfg.initial_balance, trials=256)
                metrics["exit_reasons"] = result["trades"].reason.value_counts().to_dict() if len(result["trades"]) else {}
                row["inner_years"][str(year)] = metrics
            values = list(row["inner_years"].values())
            row["training_qualified"] = all(m["net_pnl"] > 0 and m["max_drawdown"] < 18000 and m["trades"] >= 30 for m in values)
            row["ranking_score"] = min(m["net_pnl"]/(1+m["max_drawdown"]) for m in values)
            row["status"] = "completed"
        except (ValueError, RuntimeError, MemoryError) as error:
            row.update(status="failed", error=str(error), training_qualified=False, ranking_score=-1e99)
        attempts.append(row)
        json_write(output/f"{reference}_training_attempts.json", attempts)
        print(reference, number+1, "/", len(candidates), cid, row["status"], round(row["ranking_score"], 3), flush=True)
        gc.collect()
    ranked = sorted([a for a in attempts if a["status"] == "completed"], key=lambda a: (a["training_qualified"], a["ranking_score"]), reverse=True)[:3]
    frozen = dict(frozen_at=datetime.now(timezone.utc).isoformat(), reference=reference, micro=micro,
        reference_dataset_version=metadata["dataset_version"], source_hash=identity["source_hash"],
        eligible_reference_bars=len(bars), feature_columns=list(normalized),
        selection_basis="ES/NQ 2022/2023 inner outcomes only; no micro validation prices loaded", candidates=ranked)
    final_models = {}
    full_ids = np.flatnonzero(pd.to_datetime(labels.label_end, utc=True).lt(pd.Timestamp("2024-01-01T00:00Z")) & labels.forward_return.notna())
    for row in ranked:
        candidate = row["candidate"]
        if candidate["family"] == "ml" and candidate["name"] not in final_models:
            name = candidate["name"]
            final_models[name] = fit_model(name, normalized.iloc[full_ids].reset_index(drop=True), labels.iloc[full_ids].reset_index(drop=True), bars.iloc[full_ids].reset_index(drop=True))
    artifact = output/f"{reference}_{micro}_transfer_models.joblib"
    joblib.dump(dict(models=final_models, candidates=ranked, **identity,
        training_reference=reference, testing_micro=micro, normalized_features=list(normalized),
        fit_rows=len(full_ids), fit_start=str(bars.timestamp_utc.iloc[full_ids[0]]), fit_end=str(bars.timestamp_utc.iloc[full_ids[-1]]),
        deployment_eligible=False), artifact, compress=3)
    frozen["artifact_sha256"] = file_hash(artifact)
    json_write(output/f"{reference}_frozen_selection.json", frozen)
    # No micro prices are read until reference selection and final model hashes
    # have been written. The actual test alias cannot pass guarded_partition.
    micro_bars, micro_meta, micro_quality = guarded_partition(micro, "validation")
    # Separate micro training data supplies only causal feature warmup, not model
    # fitting. Its dates remain before the validation start.
    from quant_futures.research import load_dataset
    warmup, _, _ = load_dataset(micro+":train", minutes=15)
    warmup = warmup.iloc[-500:].copy()
    combined = pd.concat([warmup, micro_bars], ignore_index=True)
    micro_features = build_features(combined, 15)
    micro_start = len(warmup)
    actual = micro_bars.reset_index(drop=True)
    active = morning_indexes(actual)
    outcomes = []
    for row in ranked:
        candidate, cid = row["candidate"], row["candidate_id"]
        desired = signals(candidate, combined, micro_features, final_models.get(candidate["name"])).iloc[micro_start:].reset_index(drop=True)
        cfg = trading_config(micro, candidate["width"], candidate["payoff"], candidate["hold"])
        active_bars, active_signal = actual.iloc[active].reset_index(drop=True), desired.iloc[active].reset_index(drop=True)
        result = run_backtest(active_bars, active_signal, cfg)
        measured = summarize(result, cfg.initial_balance, trials=256)
        result["curve"].to_parquet(output/f"{micro}_{cid}_validation_equity.parquet", index=False)
        result["trades"].to_parquet(output/f"{micro}_{cid}_validation_trades.parquet", index=False)
        stress = {}
        for factor in (1.5, 2, 3):
            stress[str(factor)] = summarize(run_backtest(active_bars, active_signal, cfg.model_copy(update={"costs": cfg.costs.scaled(factor)})), cfg.initial_balance, trials=256)
        checks = dict(training_qualified=row["training_qualified"], profitable=measured["net_pnl"] > 0,
            max_drawdown_below_2000=measured["max_drawdown"] < 2000,
            intrabar_drawdown_below_2000=measured["max_intraday_drawdown_bound"] < 2000,
            enough_trades=measured["trades"] >= 100,
            positive_confidence_interval=measured["uncertainty"]["mean_ci"][0] is not None and measured["uncertainty"]["mean_ci"][0] > 0,
            positive_at_2x_costs=stress["2"]["net_pnl"] > 0)
        outcomes.append(dict(candidate_id=cid, candidate=candidate, validation_instrument=micro,
            source_training_instrument=reference, metrics=measured, checks=checks,
            economic_research_qualified=all(checks.values()), calendar_verified=micro_quality["calendar_verified"],
            stress=stress, deployment_eligible=False))
        json_write(output/f"{micro}_validation_results.json", outcomes)
        print(reference, "->", micro, cid, "validation PnL", round(measured["net_pnl"], 2), "DD", round(measured["max_drawdown"], 2), flush=True)
    report["pairs"][reference+"->"+micro] = dict(reference_coverage=metadata["coverage"], processed_training_rows=len(bars),
        training_attempts=len(attempts), training_qualified=sum(row["training_qualified"] for row in attempts),
        inner_model_fit_rows=len(fit_ids), final_reference_fit_rows=len(full_ids), actual_validation_version=micro_meta["dataset_version"],
        actual_micro_validation_rows=len(actual), replay_rows=len(active), validation_results=outcomes)
    json_write(output/"results.json", report)


with threadpool_limits(limits=1):
    for reference, micro in PAIRS.items():
        execute(reference, micro)
        gc.collect()
assert code_identity()["source_hash"] == identity["source_hash"], "Source changed during transfer research"
report["completed_at"] = datetime.now(timezone.utc).isoformat()
json_write(output/"results.json", report)
json_write(ROOT/"reports/latest_reference_transfer.json", dict(path=str(output), **report))

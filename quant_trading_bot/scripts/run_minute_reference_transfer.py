"""Original one-minute ES/NQ training, then later actual micro validation."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from datetime import datetime, timezone
import gc
import json
import shutil
import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits
from minute_transfer_support import COLUMNS, build_shards, price_features, train_streaming_logistic, train_external_xgboost, calibrate, predict
from quant_futures.transfer import PAIRS, trading_config, guarded_partition, morning_indexes
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.data import canonical
from quant_futures.config import digest, file_hash
from quant_futures.backtest import run_backtest
from quant_futures.metrics import summarize
from quant_futures.research import json_write, code_identity

ROOT = Path(__file__).resolve().parents[1]
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
output = ROOT/"runs"/f"minute_reference_transfer_{stamp}"
output.mkdir(exist_ok=False)
report = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(), timeframe_minutes=1,
    script_sha256=file_hash(__file__), feature_support_sha256=file_hash(Path(__file__).with_name("minute_transfer_support.py")),
    train="Original ES/NQ one-minute bars 2010–2023. No random row sampling or fitting-row cap; all eligible rows used.",
    inner_protocol="Base model fits 2010–2020, calibration 2021; ES/NQ 2022–2023 selects settings. Refit each model on 2010–2022 and calibrate on 2023 after settings are frozen.",
    validation="Actual MES/MNQ 2024–2025, one account with no resets; micro 2026 final test is never read.",
    features="Separately versioned normalized price/structure/clock features; no volume/VWAP features. Rolling warmup and invalid label windows are excluded, with counts recorded.",
    models=["streaming_logistic", "external_xgboost"], thresholds=[.51, .54],
    rules=["trend", "momentum", "mean_reversion", "donchian", "long_trend"],
    reference_economics="Actual ES/NQ multipliers and $1.75 published per-side commission; 10x account/risk scale is disclosed, never labeled early micro P&L.",
    micro_risk="One contract, $50000 balance, $1800 risk stop, $2000 measured drawdown rejection threshold; price gaps can overshoot. Morning entry 09:45–11:30 ET and noon flattening.",
    external_memory_documentation="https://xgboost.readthedocs.io/en/stable/tutorials/external_memory.html",
    final_test_accessed=False, live_execution_enabled=False, pairs={})
json_write(output/"protocol.json", report)
for script in (Path(__file__), Path(__file__).with_name("minute_transfer_support.py")):
    shutil.copyfile(script, output/script.name)


def cfg_for(symbol, candidate):
    cfg = trading_config(symbol, candidate["width"], payoff=2, hold=60)
    return cfg.model_copy(update={"timeframe_minutes": 1, "execution": cfg.execution.model_copy(update={"max_gap_minutes": 5})})


def desired(candidate, bars, features, probabilities):
    if candidate["family"] == "ml":
        p = probabilities[candidate["name"]]
        signal = np.select([p > candidate["threshold"], p < 1-candidate["threshold"]], [1, -1], 0)
    elif candidate["name"] == "trend":
        signal = np.sign(features.trend_20_120.to_numpy())
    elif candidate["name"] == "long_trend":
        signal = np.maximum(0, np.sign(features.trend_20_120.to_numpy()))
    elif candidate["name"] == "momentum":
        signal = np.sign(features.momentum_20.to_numpy())
    elif candidate["name"] == "mean_reversion":
        z = features.zscore_20.to_numpy()
        signal = np.select([z < -2, z > 2], [1, -1], 0)
    elif candidate["name"] == "donchian":
        signal = np.select([features.high_distance_60 > 0, features.low_distance_60 < 0], [1, -1], 0)
    else:
        raise ValueError("Unregistered candidate")
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    minute = local.dt.hour*60+local.dt.minute
    allowed = (minute >= 585) & (minute < 690) & features.notna().all(axis=1)
    return pd.Series(signal, index=bars.index).where(allowed, 0).fillna(0).astype(int)


def predictions(models, features):
    valid = features.notna().all(axis=1).to_numpy()
    result = {}
    for name, model in models.items():
        p = np.full(len(features), .5)
        p[valid] = predict(model, features.loc[valid].to_numpy(dtype=np.float32))
        result[name] = p
    return result


def fit_models(shards, prefix, fit_end, cal_start, cal_end):
    models, attempts = {}, []
    for name in report["models"]:
        try:
            print(prefix, "fitting", name, "through", fit_end, flush=True)
            model = train_streaming_logistic(shards, fit_end) if name == "streaming_logistic" else train_external_xgboost(shards, fit_end, output/f"{prefix}_{name}_external_cache")
            calibrate(model, shards, cal_start, cal_end)
            models[name] = model
            attempts.append(dict(name=name, status="completed", fitting_rows=model["fitting_rows"], calibration_rows=model["calibration_rows"]))
            joblib.dump(model, output/f"{prefix}_{name}.joblib", compress=3)
        except (ValueError, RuntimeError, MemoryError) as error:
            attempts.append(dict(name=name, status="failed", error=str(error)))
        json_write(output/f"{prefix}_model_fits.json", attempts)
    return models, attempts


def execute(reference, micro):
    source = resolve_dataset(reference+":train")
    shards = build_shards(source, output/(reference+"_one_minute_training_shards"))
    initial_models, initial_fits = fit_models(shards["shards"], reference+"_inner", "2021-01-01T00:00Z", "2021-01-01T00:00Z", "2022-01-01T00:00Z")
    # Read only the declared inner selection years from the raw reference file.
    selection = canonical(pd.read_parquet(source, filters=[("timestamp_utc", ">=", pd.Timestamp("2022-01-01T00:00Z")),
        ("timestamp_utc", "<", pd.Timestamp("2024-01-01T00:00Z"))]))
    features = price_features(selection)
    probability = predictions(initial_models, features)
    candidates = [dict(family="rule", name=name, width=width) for name in report["rules"] for width in (1, 2)]
    candidates += [dict(family="ml", name=name, width=width, threshold=threshold) for name in initial_models
        for width in (1, 2) for threshold in report["thresholds"]]
    active = morning_indexes(selection)
    years = {year: active[selection.timestamp_utc.iloc[active].dt.year.to_numpy() == year] for year in (2022, 2023)}
    attempts = []
    for candidate in candidates:
        cid = candidate["name"]+"_"+digest(candidate)[:10]
        signals = desired(candidate, selection, features, probability)
        cfg = cfg_for(reference, candidate)
        values = {}
        for year, indexes in years.items():
            result = run_backtest(selection.iloc[indexes].reset_index(drop=True), signals.iloc[indexes].reset_index(drop=True), cfg)
            values[str(year)] = summarize(result, cfg.initial_balance, trials=256)
        qualified = all(v["net_pnl"] > 0 and v["max_drawdown"] < 18000 and v["trades"] >= 30 for v in values.values())
        row = dict(candidate_id=cid, candidate=candidate, training_years=values, training_qualified=qualified,
            score=min(v["net_pnl"]/(1+v["max_drawdown"]) for v in values.values()))
        attempts.append(row)
        json_write(output/f"{reference}_training_attempts.json", attempts)
        print(reference, "1m inner", cid, round(row["score"], 3), flush=True)
    selected = sorted(attempts, key=lambda row: (row["training_qualified"], row["score"]), reverse=True)[:3]
    json_write(output/f"{reference}_frozen_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(),
        selected=selected, basis="Reference 2022/2023 only; actual micro validation prices have not been opened", source_dataset_version=shards["source_dataset_version"]))
    del initial_models, probability, features, selection
    gc.collect()
    final_models, final_fits = fit_models(shards["shards"], reference+"_final", "2023-01-01T00:00Z", "2023-01-01T00:00Z", "2024-01-01T00:00Z")
    # Both model types are refitted even when rules win the inner comparison.
    bars, metadata, quality = guarded_partition(micro, "validation", minutes=1)
    warm_source = resolve_dataset(micro+":train")
    with pq.ParquetFile(warm_source) as warm_file:
        warm = warm_file.read_row_group(warm_file.num_row_groups-1).to_pandas().tail(500)
    combined = pd.concat([canonical(warm), bars], ignore_index=True)
    features = price_features(combined)
    probability = predictions(final_models, features)
    first = len(warm)
    actual = combined.iloc[first:].reset_index(drop=True)
    active = morning_indexes(actual)
    outcomes = []
    for row in selected:
        candidate, cid = row["candidate"], row["candidate_id"]
        if candidate["family"] == "ml" and candidate["name"] not in final_models:
            outcomes.append(dict(candidate_id=cid, status="failed_final_refit"))
            continue
        signals = desired(candidate, combined, features, probability).iloc[first:].reset_index(drop=True)
        cfg = cfg_for(micro, candidate)
        replay_bars, replay_signal = actual.iloc[active].reset_index(drop=True), signals.iloc[active].reset_index(drop=True)
        result = run_backtest(replay_bars, replay_signal, cfg)
        measured = summarize(result, cfg.initial_balance, trials=256)
        result["curve"].to_parquet(output/f"{micro}_{cid}_validation_equity.parquet", index=False)
        result["trades"].to_parquet(output/f"{micro}_{cid}_validation_trades.parquet", index=False)
        stress = {str(factor): summarize(run_backtest(replay_bars, replay_signal, cfg.model_copy(update={"costs": cfg.costs.scaled(factor)})), cfg.initial_balance, trials=256) for factor in (1.5, 2, 3)}
        checks = dict(training_qualified=row["training_qualified"], positive_net=measured["net_pnl"] > 0,
            drawdown_below_2000=measured["max_drawdown"] < 2000, intrabar_drawdown_below_2000=measured["max_intraday_drawdown_bound"] < 2000,
            enough_trades=measured["trades"] >= 100,
            positive_confidence=measured["uncertainty"]["mean_ci"][0] is not None and measured["uncertainty"]["mean_ci"][0] > 0,
            positive_at_2x_costs=stress["2"]["net_pnl"] > 0)
        outcomes.append(dict(candidate_id=cid, candidate=candidate, status="completed", metrics=measured, stress=stress,
            checks=checks, economic_research_qualified=all(checks.values()), deployment_eligible=False))
        print(reference, "->", micro, "1m", cid, "PnL", round(measured["net_pnl"], 2), "DD", round(measured["max_drawdown"], 2), flush=True)
        json_write(output/f"{micro}_validation_results.json", outcomes)
    report["pairs"][reference+"->"+micro] = dict(source_rows=shards["input_rows"], eligible_rows=shards["eligible_rows"],
        fitting_row_cap=None, initial_fits=initial_fits, final_fits=final_fits, training_attempts=len(attempts),
        training_qualified=sum(row["training_qualified"] for row in attempts), actual_micro_validation_rows=len(bars),
        actual_validation_dataset_version=metadata["dataset_version"], calendar_verified=quality["calendar_verified"], validation_results=outcomes)
    json_write(output/"results.json", report)


with threadpool_limits(limits=1):
    for reference, micro in PAIRS.items():
        execute(reference, micro)
        gc.collect()
report["completed_at"] = datetime.now(timezone.utc).isoformat()
json_write(output/"results.json", report)
json_write(ROOT/"reports/latest_minute_reference_transfer.json", dict(path=str(output), **report))

"""Training-only strategy selection followed by continuous validation, $2K cap.

This is a finite, fully logged hypothesis batch. It cannot promise future profit.
The 2026 test partition is never read by this script.
"""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from datetime import datetime, timezone
import gc
import json
import argparse
import shutil
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import ResearchConfig, Costs, Execution, RiskLimits, file_hash, digest
from quant_futures.research import load_dataset, json_write, code_identity
from quant_futures.backtest import run_backtest
from quant_futures.metrics import summarize
from quant_futures.models import fit_model
from quant_futures.labels import future_returns
from quant_futures.strategies import baseline

ROOT = Path(__file__).resolve().parents[1]
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
output = ROOT/"runs"/f"drawdown_search_{stamp}"
output.mkdir(exist_ok=False)
protocol = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(),
    script_sha256=file_hash(__file__), user_objective="Positive after-cost validation economics with maximum drawdown below $2000; no future guarantee",
    test_accessed=False, maximum_acceptable_drawdown=2000, risk_kill_drawdown=1800,
    selection="2022 and 2023 training-year simulations only. ML fitting/calibration ends before 2022. Evaluate at most top 3 training-ranked candidates per instrument on continuous 2024–2025 validation, with no capital/risk resets. No selection using 2026 test.",
    caveat="This is additional research after observing prior 2024–2025 failures. Validation remains a reused model-selection period, not unbiased final evidence. Only a future frozen final-test evaluation can address generalization; 2026 remains reserved.",
    session_policy="Morning only: entry decisions 09:45–11:30 ET; flatten at 12:00 ET. A fixed conservative clock avoids the observed early-holiday-close exposure without inferring futures holidays from bank calendars. Unexpected gaps still kill the account. Authoritative holiday calendar remains unverified.",
    strategies=["ema", "sma", "adx", "donchian", "opening_range", "previous_session", "rsi", "bollinger", "vwap", "momentum", "trend_pullback", "long_trend"],
    variants=[dict(width=width, payoff=payoff, hold=hold) for width, payoff, hold in ((1, 2, 24), (1, 3, 78), (2, 2, 24), (2, 3, 78))],
    ml_models=["logistic", "ridge", "lightgbm", "xgboost"], probability_thresholds=[.51, .54],
    cash_commission_per_side=.5, cash_fee_source="https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions",
    fee_caveat="Published commission, no unlisted pass-through fee assumption verified; adverse spread/slippage remain applied", instruments={})
json_write(output/"protocol.json", protocol)
shutil.copyfile(__file__, output/"search_script.py")


def run_instrument(instrument):
    data, manifest, quality = load_dataset(instrument, minutes=5)
    campaign = json.loads((ROOT/"reports/final_market_campaign_5m.json").read_text())
    parent = Path(campaign["runs"][instrument]["path"])
    registration = json.loads((parent/"experiment.json").read_text())
    feature_file = parent/"development_features.parquet"
    if file_hash(feature_file) != registration["feature_set"]:
        raise ValueError("Feature cache checksum mismatch")
    features = pd.read_parquet(feature_file)
    assert len(features) == len(data)
    cfg = ResearchConfig(instrument=instrument, timeframe_minutes=5,
        costs=Costs(commission_per_side=.5, exchange_per_side=0, regulatory_per_side=0),
        execution=Execution(max_gap_minutes=5, session_flat_minute_et=720),
        risk=RiskLimits(max_trade_risk=100, max_open_risk=100, max_daily_loss=200, max_drawdown=1800))
    years = {year: np.flatnonzero(data.timestamp_utc.dt.year == year) for year in (2022, 2023)}
    local = data.timestamp_utc.dt.tz_convert("America/New_York")
    minute = local.dt.hour*60+local.dt.minute
    allowed = (minute >= 585) & (minute < 690)  # Entry decisions 09:45–11:30 ET.
    models = {}
    labels = future_returns(data, horizon=5, cost_points=1, minutes=5)
    boundary = pd.Timestamp("2022-01-01T00:00Z")
    fit_ids = np.flatnonzero((data.timestamp_utc < boundary) & (pd.to_datetime(labels.label_end, utc=True) < boundary))[-100000:]
    for name in protocol["ml_models"]:
        models[name] = fit_model(name, features.iloc[fit_ids].reset_index(drop=True), labels.iloc[fit_ids].reset_index(drop=True), data.iloc[fit_ids].reset_index(drop=True))
    candidates = []
    for strategy in protocol["strategies"]:
        for variant in protocol["variants"]:
            candidates.append(dict(family="rule", name=strategy, **variant))
    for name in protocol["ml_models"]:
        for threshold in protocol["probability_thresholds"]:
            candidates.append(dict(family="ml", name=name, threshold=threshold, width=2, payoff=2, hold=78))
    def settings(candidate):
        stop = (32 if instrument == "MES" else 80)*candidate["width"]
        return cfg.model_copy(update={"execution": cfg.execution.model_copy(update={"stop_ticks": stop,
            "target_ticks": stop*candidate["payoff"], "max_hold_bars": candidate["hold"]})})
    def signal(candidate):
        if candidate["family"] == "ml":
            s = models[candidate["name"]].signal(features, candidate["threshold"])
        elif candidate["name"] == "trend_pullback":
            up = (features.ema_fast > features.ema_slow) & (features.momentum_60 > 0)
            down = (features.ema_fast < features.ema_slow) & (features.momentum_60 < 0)
            s = pd.Series(np.select([up & (features.zscore < -.5), down & (features.zscore > .5)], [1, -1], 0))
        elif candidate["name"] == "long_trend":
            s = baseline("ema", data, features).clip(lower=0)
        else:
            s = baseline(candidate["name"], data, features)
        stop_points = settings(candidate).execution.stop_ticks*.25
        # Filter known, completed volatility; no fitting thresholds on validation.
        return s.where(allowed & features.atr.between(1, stop_points), 0).fillna(0).astype(int)
    attempts = []
    for number, candidate in enumerate(candidates):
        cid = candidate["name"]+"_"+digest(candidate)[:10]
        row = dict(candidate_id=cid, candidate=candidate, training_years={})
        try:
            signals = signal(candidate)
            for year, indexes in years.items():
                result = run_backtest(data.iloc[indexes].reset_index(drop=True), signals.iloc[indexes].reset_index(drop=True), settings(candidate))
                row["training_years"][str(year)] = summarize(result, trials=len(candidates)*2)
                row["training_years"][str(year)]["exit_reasons"] = result["trades"].reason.value_counts().to_dict() if len(result["trades"]) else {}
                locks = [event for event in result["events"] if event["event"] == "account_lockout"]
                row["training_years"][str(year)]["last_risk_lock"] = locks[-1] if locks else None
                del result
            values = list(row["training_years"].values())
            row["training_qualified"] = all(v["net_pnl"] > 0 and v["max_drawdown"] < 1800 and v["trades"] >= 30 for v in values)
            row["selection_score"] = min(v["net_pnl"]/(1+v["max_drawdown"]) for v in values)
            row["status"] = "completed"
        except (ValueError, RuntimeError, MemoryError) as error:
            row.update(status="failed", error=str(error), selection_score=-1e99, training_qualified=False)
        attempts.append(row)
        json_write(output/f"{instrument}_training_attempts.json", attempts)
        print(instrument, number+1, "/", len(candidates), cid, row["status"], round(row["selection_score"], 3), flush=True)
        gc.collect()
    ranked = sorted([row for row in attempts if row["status"] == "completed"], key=lambda row: (row["training_qualified"], row["selection_score"]), reverse=True)
    selected = ranked[:3]
    json_write(output/f"{instrument}_frozen_training_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(),
        dataset_version=manifest["dataset_version"], source_hash=code_identity()["source_hash"], selection_basis="training 2022/2023 only", selected=selected))
    validation = np.flatnonzero(data.timestamp_utc >= pd.Timestamp("2024-01-01T00:00Z"))
    results = []
    for row in selected:
        candidate, cid = row["candidate"], row["candidate_id"]
        s = signal(candidate).iloc[validation].reset_index(drop=True)
        bars = data.iloc[validation].reset_index(drop=True)
        measured = run_backtest(bars, s, settings(candidate))
        metrics = summarize(measured, trials=256)
        measured["curve"].to_parquet(output/f"{instrument}_{cid}_validation_equity.parquet", index=False)
        measured["trades"].to_parquet(output/f"{instrument}_{cid}_validation_trades.parquet", index=False)
        checks = dict(training_qualified=row["training_qualified"], profitable=metrics["net_pnl"] > 0, drawdown_below_2000=metrics["max_drawdown"] < 2000,
            intrabar_drawdown_below_2000=metrics["max_intraday_drawdown_bound"] < 2000,
            trades_at_least_100=metrics["trades"] >= 100,
            confidence_positive=metrics["uncertainty"]["mean_ci"][0] is not None and metrics["uncertainty"]["mean_ci"][0] > 0,
            calendar_verified=quality["calendar_verified"])
        stress = {}
        for factor in (1.5, 2, 3):
            config = settings(candidate)
            stress[str(factor)] = summarize(run_backtest(bars, s, config.model_copy(update={"costs": config.costs.scaled(factor)})), trials=256)
        checks["positive_at_2x_costs"] = stress["2"]["net_pnl"] > 0
        results.append(dict(candidate_id=cid, candidate=candidate, training_qualified=row["training_qualified"], metrics=metrics,
            checks=checks, research_qualified=all(checks.values()), stress=stress, deployment_eligible=False))
        json_write(output/f"{instrument}_validation_results.json", results)
        print(instrument, cid, "validation", round(metrics["net_pnl"], 2), "DD", round(metrics["max_drawdown"], 2), flush=True)
    protocol["instruments"][instrument] = dict(training_attempts=len(attempts), training_qualified=sum(row["training_qualified"] for row in attempts), validation_results=results)
    json_write(output/"results.json", protocol)


with threadpool_limits(limits=1):
    for instrument in ("MES", "MNQ"):
        run_instrument(instrument)
        gc.collect()
protocol["completed_at"] = datetime.now(timezone.utc).isoformat()
json_write(output/"results.json", protocol)
json_write(ROOT/"reports/latest_drawdown_search.json", dict(path=str(output), **protocol))

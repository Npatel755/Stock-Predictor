"""Registered one-attempt-per-day opening-range research on original minutes."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from datetime import datetime, timezone
import json
import gc
import shutil
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.data import canonical
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.transfer import trading_config, morning_indexes, guarded_partition
from quant_futures.execution import Action
from quant_futures.backtest import run_backtest
from quant_futures.metrics import summarize
from quant_futures.config import digest, file_hash
from quant_futures.research import code_identity, json_write


def opening_intents(bars, opening_minutes=30, long_only=False):
    """One attempt per session; HOLD cannot reopen a stopped-out position."""
    if opening_minutes not in (15, 30):
        raise ValueError("Registered opening periods are 15 or 30 minutes")
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    clock = (local.dt.hour*60+local.dt.minute).to_numpy()
    output = np.full(len(bars), Action.HOLD, dtype=object)
    for _, indexes in bars.groupby("session_id", sort=False).indices.items():
        indexes = np.asarray(indexes)
        opening = indexes[(clock[indexes] >= 570) & (clock[indexes] < 570+opening_minutes)]
        if len(opening) != opening_minutes:
            continue  # Missing opening minutes remain missing; no invented range.
        complete = pd.DatetimeIndex(bars.timestamp_utc.iloc[opening])
        if not np.all(np.diff(complete.as_unit("ns").asi8) == 60*10**9):
            continue
        high, low = bars.high.iloc[opening].max(), bars.low.iloc[opening].min()
        attempted = False
        for index in indexes:
            if clock[index] >= 690:
                output[index] = Action.EXIT
                continue
            if clock[index] < 570+opening_minutes or attempted:
                continue
            if bars.close.iloc[index] > high:
                output[index], attempted = Action.LONG, True
            elif not long_only and bars.close.iloc[index] < low:
                output[index], attempted = Action.SHORT, True
    return pd.Series(output, index=bars.index)


def main():
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = root/"runs"/f"opening_range_minutes_{stamp}"
    directory.mkdir(exist_ok=False)
    protocol = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(), script_sha256=file_hash(__file__),
        hypothesis="The earlier NQ opening-range control had a thin positive micro validation result that failed costs/confidence. This is a disclosed follow-up using original minutes and one attempt per day, not independent confirmation of that observed result.",
        training="Actual ES/NQ 2022–2023 within the training period; 2010–2021 provides earlier reference context and ML fitting in the separate full-history transfer study. These rule parameters use no micro validation returns for ranking.",
        validation="Actual MES/MNQ 2024–2025 after selection is frozen; 2026 test reserved.",
        design="15/30-minute completed opening ranges; one entry attempt/day, HOLD after stop/target prevents reentry. Exit decisions at 11:30 ET, fixed noon safety flat. No missing opening bars filled. Actual reference multipliers and explicit 10x risk/account scaling; actual micro P&L uses one micro.",
        candidates=[dict(opening=opening, width=width, payoff=payoff, long_only=long_only)
            for opening in (15, 30) for width in (1, 2) for payoff in (2, 3) for long_only in (False, True)],
        maximum_drawdown=2000, risk_stop=1800, final_test_accessed=False, pairs={})
    json_write(directory/"protocol.json", protocol)
    shutil.copyfile(__file__, directory/"study_script.py")
    for reference, micro in (("ES", "MES"), ("NQ", "MNQ")):
        source = resolve_dataset(reference+":train")
        bars = canonical(pd.read_parquet(source, filters=[("timestamp_utc", ">=", pd.Timestamp("2022-01-01T00:00Z")), ("timestamp_utc", "<", pd.Timestamp("2024-01-01T00:00Z"))]))
        active = morning_indexes(bars)
        years = {year: active[bars.timestamp_utc.iloc[active].dt.year.to_numpy() == year] for year in (2022, 2023)}
        intentions = {(opening, long_only): opening_intents(bars, opening, long_only) for opening in (15, 30) for long_only in (False, True)}
        attempts = []
        for candidate in protocol["candidates"]:
            cfg = trading_config(reference, candidate["width"], candidate["payoff"], hold=90)
            cfg = cfg.model_copy(update={"timeframe_minutes": 1, "execution": cfg.execution.model_copy(update={"max_gap_minutes": 5})})
            signal = intentions[candidate["opening"], candidate["long_only"]]
            scores = {}
            for year, indexes in years.items():
                measured = run_backtest(bars.iloc[indexes].reset_index(drop=True), signal.iloc[indexes].reset_index(drop=True), cfg)
                scores[str(year)] = summarize(measured, cfg.initial_balance, trials=512)
            values = list(scores.values())
            attempts.append(dict(candidate_id="orb_"+digest(candidate)[:10], candidate=candidate, training_years=scores,
                training_qualified=all(value["net_pnl"] > 0 and value["max_drawdown"] < 18000 and value["trades"] >= 30 for value in values),
                score=min(value["net_pnl"]/(1+value["max_drawdown"]) for value in values)))
            json_write(directory/f"{reference}_training_attempts.json", attempts)
            print(reference, "one-attempt ORB", len(attempts), "/", len(protocol["candidates"]), round(attempts[-1]["score"], 3), flush=True)
        selected = sorted(attempts, key=lambda row: (row["training_qualified"], row["score"]), reverse=True)[:2]
        json_write(directory/f"{reference}_frozen_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(), selected=selected,
            selection_basis="Reference training outcomes only; no micro validation prices loaded"))
        del bars, intentions
        gc.collect()
        actual, metadata, quality = guarded_partition(micro, "validation", minutes=1)
        active = morning_indexes(actual)
        outcomes = []
        for row in selected:
            candidate, cid = row["candidate"], row["candidate_id"]
            signal = opening_intents(actual, candidate["opening"], candidate["long_only"])
            cfg = trading_config(micro, candidate["width"], candidate["payoff"], hold=90)
            cfg = cfg.model_copy(update={"timeframe_minutes": 1, "execution": cfg.execution.model_copy(update={"max_gap_minutes": 5})})
            rb, rs = actual.iloc[active].reset_index(drop=True), signal.iloc[active].reset_index(drop=True)
            result = run_backtest(rb, rs, cfg)
            measured = summarize(result, cfg.initial_balance, trials=512)
            result["curve"].to_parquet(directory/f"{micro}_{cid}_validation_equity.parquet", index=False)
            result["trades"].to_parquet(directory/f"{micro}_{cid}_validation_trades.parquet", index=False)
            stress = {str(factor): summarize(run_backtest(rb, rs, cfg.model_copy(update={"costs": cfg.costs.scaled(factor)})), cfg.initial_balance, trials=512) for factor in (1.5, 2, 3)}
            checks = dict(training_qualified=row["training_qualified"], profitable=measured["net_pnl"] > 0,
                drawdown_below_2000=measured["max_drawdown"] < 2000, intrabar_drawdown_below_2000=measured["max_intraday_drawdown_bound"] < 2000,
                enough_trades=measured["trades"] >= 100, positive_confidence=measured["uncertainty"]["mean_ci"][0] is not None and measured["uncertainty"]["mean_ci"][0] > 0,
                positive_at_2x_costs=stress["2"]["net_pnl"] > 0)
            outcomes.append(dict(candidate_id=cid, candidate=candidate, metrics=measured, checks=checks, stress=stress,
                economic_research_qualified=all(checks.values()), deployment_eligible=False))
            print(reference, "->", micro, cid, "PnL", round(measured["net_pnl"], 2), "DD", round(measured["max_drawdown"], 2), flush=True)
            json_write(directory/f"{micro}_validation_results.json", outcomes)
        protocol["pairs"][reference+"->"+micro] = dict(training_attempts=len(attempts), training_qualified=sum(row["training_qualified"] for row in attempts),
            validation_dataset_version=metadata["dataset_version"], calendar_verified=quality["calendar_verified"], validation_results=outcomes)
        json_write(directory/"results.json", protocol)
        gc.collect()
    protocol["completed_at"] = datetime.now(timezone.utc).isoformat()
    json_write(directory/"results.json", protocol)
    json_write(root/"reports/latest_opening_range_study.json", dict(path=str(directory), **protocol))


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()

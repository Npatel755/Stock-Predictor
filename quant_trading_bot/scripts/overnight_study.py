"""Full reference-history overnight screening, then shared-engine verification."""
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
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits
from quant_futures.config import digest, file_hash
from quant_futures.contracts import SPECS
from quant_futures.execution import Action, PaperBroker
from quant_futures.data import canonical
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.transfer import trading_config, guarded_partition
from quant_futures.backtest import run_backtest
from quant_futures.metrics import summarize
from quant_futures.research import code_identity, json_write


def session_frames(path):
    pending = pd.DataFrame()
    with pq.ParquetFile(path) as source:
        for batch in source.iter_batches(batch_size=100000):
            frame = pd.concat([pending, batch.to_pandas()], ignore_index=True)
            last = frame.session_id.iloc[-1]
            for _, group in frame[frame.session_id != last].groupby("session_id", sort=False):
                yield group.reset_index(drop=True)
            pending = frame[frame.session_id == last].reset_index(drop=True)
    if len(pending):
        yield pending


def night_config(symbol, candidate):
    cfg = trading_config(symbol, candidate["width"], candidate["payoff"], hold=900)
    return cfg.model_copy(update={"timeframe_minutes": 1, "execution": cfg.execution.model_copy(update={"max_gap_minutes": 5})})


def night_data(group, history):
    local = group.timestamp_utc.dt.tz_convert("America/New_York")
    minute = (local.dt.hour*60+local.dt.minute).to_numpy()
    mask = (minute >= 1080) | (minute <= 481)
    selected = group.loc[mask]
    trend = int(np.sign(history[-1]-np.mean(history[-20:]))) if len(history) >= 20 else 0
    return dict(time=pd.DatetimeIndex(selected.timestamp_utc).as_unit("ns").asi8, minute=minute[mask],
        open=selected.open.to_numpy(), high=selected.high.to_numpy(), low=selected.low.to_numpy(), close=selected.close.to_numpy(),
        volume=selected.volume.to_numpy(), contract=selected.contract.to_numpy(), trend=trend,
        year=pd.Timestamp(group.session_id.iloc[0]).year, session=str(group.session_id.iloc[0]))


def direction(candidate, trend):
    return 1 if candidate["direction"] == "long" else trend if candidate["direction"] == "trend" else max(0, trend)


def screen_trade(night, candidate, symbol):
    """Training screen only: no claim of continuous account/risk equivalence."""
    side = direction(candidate, night["trend"])
    entries = np.flatnonzero(night["minute"] == candidate["entry"])
    if not side or not len(entries):
        return None
    decision = entries[0]
    start = decision+1
    if start >= len(night["time"]) or night["time"][start]-night["time"][decision] > 5*60*10**9 or night["contract"][start] != night["contract"][decision] or night["volume"][decision] < 100:
        return None
    endings = np.flatnonzero((night["minute"] >= 476) & (night["minute"] < 1080) & (np.arange(len(night["minute"])) > start))
    if not len(endings):
        return None
    end = endings[0]
    cfg, spec = night_config(symbol, candidate), SPECS[symbol]
    broker = PaperBroker(cfg.costs)
    entry = broker.market_price(night["open"][start], side, symbol)
    stop = entry-side*cfg.execution.stop_ticks*spec.tick
    target = entry+side*cfg.execution.target_ticks*spec.tick
    # The scheduled 07:56 opening exit precedes that bar's intrabar path.
    ids = np.arange(start, end)
    gaps = np.diff(night["time"][start-1:end]) > 5*60*10**9
    rolls = night["contract"][ids] != night["contract"][start]
    opening_stop = side*(night["open"][ids]-stop) <= 0
    hit_stop = night["low"][ids] <= stop if side > 0 else night["high"][ids] >= stop
    hit_target = night["high"][ids] >= target+spec.tick if side > 0 else night["low"][ids] <= target-spec.tick
    triggers = np.flatnonzero(gaps | rolls | opening_stop | hit_stop | hit_target)
    reason = "time_exit"
    if len(triggers):
        offset = triggers[0]
        index = ids[offset]
        if rolls[offset]:
            return None  # No old-contract quote: never screen a raw roll-gap profit.
        if gaps[offset]:
            reference, reason = night["open"][index], "gap_or_roll"
        elif opening_stop[offset] or hit_stop[offset]:
            reference = min(night["open"][index], stop) if side > 0 else max(night["open"][index], stop)
            reason = "stop"
        else:
            reference, reason = target, "target"
    else:
        reference = night["open"][end]
    exit_price = spec.round_price(reference) if reason == "target" else broker.market_price(reference, -side, symbol)
    return dict(net_pnl=side*(exit_price-entry)*spec.multiplier-2*cfg.costs.fee,
        year=night["year"], session=night["session"], reason=reason)


def overnight_intents(bars, candidate):
    output = np.full(len(bars), Action.HOLD, dtype=object)
    history = []
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    minute = (local.dt.hour*60+local.dt.minute).to_numpy()
    for _, indexes in bars.groupby("session_id", sort=False).indices.items():
        indexes = np.asarray(indexes)
        trend = int(np.sign(history[-1]-np.mean(history[-20:]))) if len(history) >= 20 else 0
        side = direction(candidate, trend)
        entries = indexes[minute[indexes] == candidate["entry"]]
        if side and len(entries):
            output[entries[0]] = Action.LONG if side > 0 else Action.SHORT
        output[indexes[(minute[indexes] >= 475) & (minute[indexes] < 1080)]] = Action.EXIT
        history.append(float(bars.close.iloc[indexes[-1]]))
    return pd.Series(output, index=bars.index)


def replay_indexes(bars):
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    minute = local.dt.hour*60+local.dt.minute
    mask = ((minute >= 1080) | (minute <= 481)).to_numpy(copy=True)
    mask[np.flatnonzero(~bars.session_id.duplicated())] = True
    return np.flatnonzero(mask)


def main():
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = root/"runs"/f"overnight_minutes_{stamp}"
    folder.mkdir(exist_ok=False)
    report = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(), script_sha256=file_hash(__file__),
        hypothesis="Overnight drift / lagged 20-session trend, one entry per session. Distinct from the morning studies; not assumed profitable.",
        screening="Original one-minute ES/NQ training from 2010–2023, streamed by session. Fast per-trade screening uses actual mini multipliers/costs but does not reproduce account risk state. Candidates must then pass full shared-engine replay on 2022/2023 reference data before economic qualification.",
        validation="Actual MES/MNQ 2024–2025 after frozen reference selection; 2026 reserved.",
        risk="One micro, $1800 hard risk stop, $2000 drawdown rejection. Exit at the next open after the 07:55 completed-bar decision, before ordinary morning news and known 08:15 early-close patterns; authoritative historical calendar still unverified.",
        candidates=[dict(entry=entry, width=width, payoff=payoff, direction=trend)
            for entry in (1095, 1320) for width in (1, 2) for payoff in (2, 3) for trend in ("long", "trend", "long_trend")],
        selection="Prefer positive 2022 and 2023 screen years, positive earlier 2010–2021 aggregate, and low closed-trade drawdown; select top two before any actual micro validation. All attempts retained. Screening drawdown is not maximum intrabar drawdown.",
        final_test_accessed=False, pairs={})
    json_write(folder/"protocol.json", report)
    shutil.copyfile(__file__, folder/"study_script.py")
    for reference, micro in (("ES", "MES"), ("NQ", "MNQ")):
        source = resolve_dataset(reference+":train")
        source_meta = json.loads(source.with_suffix(".manifest.json").read_text())
        if source_meta["split_role"] != "train" or source_meta["instrument"] != reference or file_hash(source) != source_meta["dataset_version"]:
            raise ValueError("Reference provenance mismatch")
        screens = [[] for _ in report["candidates"]]
        history, count = [], 0
        for group in session_frames(source):
            if not group.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
                raise PermissionError("No forward reference observations allowed")
            night = night_data(group, history)
            for index, candidate in enumerate(report["candidates"]):
                result = screen_trade(night, candidate, reference)
                if result:
                    screens[index].append(result)
            history.append(float(group.close.iloc[-1]))
            count += 1
            if count % 500 == 0:
                print(reference, "overnight reference sessions", count, flush=True)
        ranked = []
        for candidate, results in zip(report["candidates"], screens):
            years = {}
            for year in (2022, 2023):
                trades = [row["net_pnl"] for row in results if row["year"] == year]
                equity = np.r_[0, np.cumsum(trades)]
                years[str(year)] = dict(net_pnl=float(equity[-1]), closed_trade_drawdown=float(np.max(np.maximum.accumulate(equity)-equity)), trades=len(trades))
            earlier = sum(row["net_pnl"] for row in results if row["year"] < 2022)
            qualified = earlier > 0 and all(value["net_pnl"] > 0 and value["trades"] >= 30 for value in years.values())
            ranked.append(dict(candidate_id="night_"+digest(candidate)[:10], candidate=candidate, earlier_2010_2021_net=earlier,
                screen_years=years, screen_qualified=qualified, score=min(value["net_pnl"]/(1+value["closed_trade_drawdown"]) for value in years.values())))
        ranked.sort(key=lambda row: (row["screen_qualified"], row["score"]), reverse=True)
        json_write(folder/f"{reference}_screen_attempts.json", ranked)
        selected = ranked[:2]
        json_write(folder/f"{reference}_frozen_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(), selected=selected,
            basis="All reference screening before actual micro validation"))
        reference_bars = canonical(pd.read_parquet(source, filters=[("timestamp_utc", ">=", pd.Timestamp("2021-10-01T00:00Z"))]))
        inner_verification = {}
        for row in selected:
            signal = overnight_intents(reference_bars, row["candidate"])
            keep = replay_indexes(reference_bars)
            values = {}
            for year in (2022, 2023):
                indexes = keep[reference_bars.timestamp_utc.iloc[keep].dt.year.to_numpy() == year]
                cfg = night_config(reference, row["candidate"])
                result = run_backtest(reference_bars.iloc[indexes].reset_index(drop=True), signal.iloc[indexes].reset_index(drop=True), cfg)
                values[str(year)] = summarize(result, cfg.initial_balance, trials=512)
            inner_verification[row["candidate_id"]] = values
        json_write(folder/f"{reference}_event_training_verification.json", inner_verification)
        del reference_bars, screens
        gc.collect()
        actual, meta, quality = guarded_partition(micro, "validation", minutes=1)
        warm = canonical(pd.read_parquet(resolve_dataset(micro+":train"), filters=[("timestamp_utc", ">=", pd.Timestamp("2023-10-01T00:00Z"))]))
        combined = pd.concat([warm, actual], ignore_index=True)
        keep = replay_indexes(actual)
        outcomes = []
        for row in selected:
            candidate, cid = row["candidate"], row["candidate_id"]
            signal = overnight_intents(combined, candidate).iloc[len(warm):].reset_index(drop=True)
            cfg = night_config(micro, candidate)
            rb, rs = actual.iloc[keep].reset_index(drop=True), signal.iloc[keep].reset_index(drop=True)
            result = run_backtest(rb, rs, cfg)
            measured = summarize(result, cfg.initial_balance, trials=512)
            result["curve"].to_parquet(folder/f"{micro}_{cid}_validation_equity.parquet", index=False)
            result["trades"].to_parquet(folder/f"{micro}_{cid}_validation_trades.parquet", index=False)
            stress = {str(factor): summarize(run_backtest(rb, rs, cfg.model_copy(update={"costs": cfg.costs.scaled(factor)})), cfg.initial_balance, trials=512) for factor in (1.5, 2, 3)}
            checks = dict(training_verified=row["screen_qualified"] and all(value["net_pnl"] > 0 and value["max_drawdown"] < 18000 for value in inner_verification[cid].values()),
                profitable=measured["net_pnl"] > 0, drawdown_below_2000=measured["max_drawdown"] < 2000,
                intrabar_drawdown_below_2000=measured["max_intraday_drawdown_bound"] < 2000, enough_trades=measured["trades"] >= 100,
                positive_confidence=measured["uncertainty"]["mean_ci"][0] is not None and measured["uncertainty"]["mean_ci"][0] > 0,
                positive_at_2x_costs=stress["2"]["net_pnl"] > 0)
            outcomes.append(dict(candidate_id=cid, candidate=candidate, metrics=measured, stress=stress, checks=checks,
                economic_research_qualified=all(checks.values()), deployment_eligible=False))
            json_write(folder/f"{micro}_validation_results.json", outcomes)
            print(reference, "->", micro, "overnight", cid, "PnL", round(measured["net_pnl"], 2), "DD", round(measured["max_drawdown"], 2), flush=True)
        report["pairs"][reference+"->"+micro] = dict(reference_sessions=count, screen_attempts=len(ranked), screen_qualified=sum(row["screen_qualified"] for row in ranked),
            reference_source_version=source_meta["dataset_version"], actual_validation_version=meta["dataset_version"], calendar_verified=quality["calendar_verified"], validation_results=outcomes)
        json_write(folder/"results.json", report)
        gc.collect()
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    json_write(folder/"results.json", report)
    json_write(root/"reports/latest_overnight_study.json", dict(path=str(folder), **report))


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()

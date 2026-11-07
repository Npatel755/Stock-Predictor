"""Opening-range entries with causal volatility-scaled stops; reference first."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from datetime import datetime, timezone
import gc
import json
import shutil
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from overnight_study import session_frames
from opening_range_study import opening_intents
from quant_futures.transfer import trading_config, morning_indexes, guarded_partition
from quant_futures.contracts import SPECS
from quant_futures.execution import PaperBroker, Action
from quant_futures.backtest import Simulator
from quant_futures.data import canonical, validate
from quant_futures.config import digest, file_hash
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.metrics import summarize
from quant_futures.research import code_identity, json_write


def known_atr(bars):
    previous = bars.close.shift()
    reset = bars.contract.ne(bars.contract.shift()) | (bars.timestamp_utc.diff() > pd.Timedelta(minutes=5))
    previous = previous.where(~reset)
    tr = pd.concat([bars.high-bars.low, (bars.high-previous).abs(), (bars.low-previous).abs()], axis=1).max(axis=1)
    return tr.groupby(reset.cumsum(), sort=False).transform(lambda group: group.rolling(20).mean())


def adaptive_config(symbol):
    cfg = trading_config(symbol, hold=90)
    scale = 10 if symbol in ("ES", "NQ") else 1
    return cfg.model_copy(update={"timeframe_minutes": 1,
        "execution": cfg.execution.model_copy(update={"max_gap_minutes": 5}),
        "risk": cfg.risk.model_copy(update={"max_trade_risk": 150*scale, "max_open_risk": 150*scale, "max_daily_loss": 300*scale})})


def adaptive_replay(bars, signals, cfg, atr_at_previous_close, multiple, payoff):
    bars, quality = validate(bars, minutes=1)
    if quality["fatal"] or len(bars) != len(signals) or len(bars) != len(atr_at_previous_close):
        raise ValueError("Valid aligned adaptive replay required")
    sim = Simulator(cfg)
    for index, (bar, signal) in enumerate(zip(bars.itertuples(index=False), signals)):
        atr = atr_at_previous_close.iloc[index] if hasattr(atr_at_previous_close, "iloc") else atr_at_previous_close[index]
        # An order executing now uses volatility from the already-completed
        # prior minute. Existing position.stop/target remain fixed after entry.
        ticks = max(4, int(np.ceil(atr*multiple/sim.spec.tick))) if np.isfinite(atr) else 4
        sim.cfg = cfg.model_copy(update={"execution": cfg.execution.model_copy(update={"stop_ticks": ticks, "target_ticks": ticks*payoff})})
        sim.step(bar, signal)
    return sim.finish()


def screen_session(bars, candidate, symbol, minute=None, atr_values=None):
    if minute is None:
        local = bars.timestamp_utc.dt.tz_convert("America/New_York")
        minute = (local.dt.hour*60+local.dt.minute).to_numpy()
    opening = np.flatnonzero((minute >= 570) & (minute < 570+candidate["opening"]))
    if len(opening) != candidate["opening"]:
        return None
    times = pd.DatetimeIndex(bars.timestamp_utc).as_unit("ns").asi8
    if not np.all(np.diff(times[opening]) == 60*10**9):
        return None
    high, low = bars.high.iloc[opening].max(), bars.low.iloc[opening].min()
    direction = np.select([bars.close.to_numpy() > high, (not candidate["long_only"]) & (bars.close.to_numpy() < low)], [1, -1], 0)
    decisions = np.flatnonzero((minute >= 570+candidate["opening"]) & (minute < 690) & (direction != 0))
    if not len(decisions):
        return None
    decision = decisions[0]
    start = decision+1
    if start >= len(bars) or times[start]-times[decision] > 5*60*10**9 or bars.contract.iloc[start] != bars.contract.iloc[decision] or bars.volume.iloc[decision] < 100:
        return None
    atr = known_atr(bars).iloc[decision] if atr_values is None else atr_values[decision]
    if not np.isfinite(atr):
        return None
    cfg, spec = adaptive_config(symbol), SPECS[symbol]
    ticks = max(4, int(np.ceil(atr*candidate["multiple"]/spec.tick)))
    adverse = spec.tick*(cfg.costs.slippage_ticks+cfg.costs.spread_ticks/2+cfg.costs.impact_ticks)
    estimated = ticks*spec.tick*spec.multiplier+2*cfg.costs.fee+(2*adverse+spec.tick)*spec.multiplier
    if estimated > cfg.risk.max_trade_risk:
        return None
    side = direction[decision]
    endings = np.flatnonzero((minute >= 691) & (np.arange(len(bars)) > start))
    if not len(endings):
        return None
    end = min(endings[0], start+90)
    broker = PaperBroker(cfg.costs)
    entry = broker.market_price(bars.open.iloc[start], side, symbol)
    stop, target = entry-side*ticks*spec.tick, entry+side*ticks*spec.tick*candidate["payoff"]
    ids = np.arange(start, end)
    opening_stop = side*(bars.open.to_numpy()[ids]-stop) <= 0
    stop_hit = bars.low.to_numpy()[ids] <= stop if side > 0 else bars.high.to_numpy()[ids] >= stop
    target_hit = bars.high.to_numpy()[ids] >= target+spec.tick if side > 0 else bars.low.to_numpy()[ids] <= target-spec.tick
    gaps = np.diff(times[start-1:end]) > 5*60*10**9
    rolls = bars.contract.to_numpy()[ids] != bars.contract.iloc[start]
    trigger = np.flatnonzero(opening_stop | stop_hit | target_hit | gaps | rolls)
    limit = False
    if len(trigger):
        offset = trigger[0]
        index = ids[offset]
        if rolls[offset]:
            return None
        if gaps[offset]:
            reference = bars.open.iloc[index]
        elif opening_stop[offset] or stop_hit[offset]:
            reference = min(bars.open.iloc[index], stop) if side > 0 else max(bars.open.iloc[index], stop)
        else:
            reference, limit = target, True
    else:
        reference = bars.open.iloc[end]
    exit_price = spec.round_price(reference) if limit else broker.market_price(reference, -side, symbol)
    return dict(year=pd.Timestamp(bars.session_id.iloc[0]).year,
        net_pnl=side*(exit_price-entry)*spec.multiplier-2*cfg.costs.fee)


def main():
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = root/"runs"/f"adaptive_opening_minutes_{stamp}"
    directory.mkdir(exist_ok=False)
    report = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(), script_sha256=file_hash(__file__),
        hypothesis="Fixed point stops may fail across index levels and volatility regimes. Compare prior-minute 20-bar simple ATR multiples with one entry attempt per day. This is an additional disclosed search after earlier validation outcomes, not independent confirmation.",
        screening="All original one-minute ES/NQ reference training sessions 2010–2023; fast per-trade screen followed by mandatory shared-Simulator continuous 2022/2023 risk verification. Screening cash drawdown is not an intrabar risk estimate.",
        validation="Actual MES/MNQ 2024–2025, frozen settings and no capital resets; final micro 2026 reserved.",
        risk="One contract. Micro trade risk budget $150, daily loss circuit breaker $300, drawdown risk stop $1800, measured drawdown rejection $2000. Reference mini budgets explicitly scale 10x; actual micro P&L is never fabricated before 2019.",
        features="ATR uses known completed one-minute true ranges and resets across raw rolls/extended gaps. Stop/target fixed at entry. No future-minute volatility input or missing-price filling.",
        candidates=[dict(opening=opening, multiple=multiple, payoff=payoff, long_only=long_only)
            for opening in (15, 30) for multiple in (2, 4, 8) for payoff in (2, 3) for long_only in (False, True)],
        final_test_accessed=False, pairs={})
    json_write(directory/"protocol.json", report)
    shutil.copyfile(__file__, directory/"study_script.py")
    for reference, micro in (("ES", "MES"), ("NQ", "MNQ")):
        source = resolve_dataset(reference+":train")
        metadata = json.loads(source.with_suffix(".manifest.json").read_text())
        if metadata["split_role"] != "train" or metadata["instrument"] != reference or file_hash(source) != metadata["dataset_version"]:
            raise ValueError("Reference training provenance mismatch")
        screened = [[] for _ in report["candidates"]]
        count = 0
        for group in session_frames(source):
            if not group.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
                raise PermissionError("Training cannot include forward reference prices")
            local = group.timestamp_utc.dt.tz_convert("America/New_York")
            minute = (local.dt.hour*60+local.dt.minute).to_numpy()
            atr_values = known_atr(group).to_numpy()
            for index, candidate in enumerate(report["candidates"]):
                result = screen_session(group, candidate, reference, minute, atr_values)
                if result:
                    screened[index].append(result)
            count += 1
            if count % 500 == 0:
                print(reference, "adaptive reference sessions", count, flush=True)
        rows = []
        for candidate, results in zip(report["candidates"], screened):
            years = {}
            for year in (2022, 2023):
                pnl = [row["net_pnl"] for row in results if row["year"] == year]
                curve = np.r_[0, np.cumsum(pnl)]
                years[str(year)] = dict(net_pnl=float(curve[-1]), closed_trade_drawdown=float(np.max(np.maximum.accumulate(curve)-curve)), trades=len(pnl))
            earlier = sum(row["net_pnl"] for row in results if row["year"] < 2022)
            rows.append(dict(candidate_id="adaptive_"+digest(candidate)[:10], candidate=candidate, screen_years=years,
                earlier_2010_2021_net=earlier, screen_qualified=earlier > 0 and all(row["net_pnl"] > 0 and row["trades"] >= 30 for row in years.values()),
                score=min(row["net_pnl"]/(1+row["closed_trade_drawdown"]) for row in years.values())))
        rows.sort(key=lambda row: (row["screen_qualified"], row["score"]), reverse=True)
        json_write(directory/f"{reference}_screen_attempts.json", rows)
        selected = rows[:2]
        json_write(directory/f"{reference}_frozen_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(), selected=selected,
            basis="Reference screening only, before actual micro validation is loaded"))
        data = canonical(pd.read_parquet(source, filters=[("timestamp_utc", ">=", pd.Timestamp("2021-10-01T00:00Z"))]))
        atr = known_atr(data).shift()
        active = morning_indexes(data)
        verification = {}
        for row in selected:
            candidate = row["candidate"]
            signal = opening_intents(data, candidate["opening"], candidate["long_only"])
            scores = {}
            for year in (2022, 2023):
                indexes = active[data.timestamp_utc.iloc[active].dt.year.to_numpy() == year]
                cfg = adaptive_config(reference)
                result = adaptive_replay(data.iloc[indexes].reset_index(drop=True), signal.iloc[indexes].reset_index(drop=True), cfg,
                    atr.iloc[indexes].reset_index(drop=True), candidate["multiple"], candidate["payoff"])
                scores[str(year)] = summarize(result, cfg.initial_balance, trials=1024)
            verification[row["candidate_id"]] = scores
        json_write(directory/f"{reference}_event_training_verification.json", verification)
        del data, screened
        gc.collect()
        actual, actual_meta, quality = guarded_partition(micro, "validation", minutes=1)
        atr = known_atr(actual).shift()
        active = morning_indexes(actual)
        outcomes = []
        for row in selected:
            candidate, cid = row["candidate"], row["candidate_id"]
            signal = opening_intents(actual, candidate["opening"], candidate["long_only"])
            rb, rs, ra = actual.iloc[active].reset_index(drop=True), signal.iloc[active].reset_index(drop=True), atr.iloc[active].reset_index(drop=True)
            cfg = adaptive_config(micro)
            result = adaptive_replay(rb, rs, cfg, ra, candidate["multiple"], candidate["payoff"])
            metrics = summarize(result, cfg.initial_balance, trials=1024)
            result["curve"].to_parquet(directory/f"{micro}_{cid}_validation_equity.parquet", index=False)
            result["trades"].to_parquet(directory/f"{micro}_{cid}_validation_trades.parquet", index=False)
            stress = {str(factor): summarize(adaptive_replay(rb, rs, cfg.model_copy(update={"costs": cfg.costs.scaled(factor)}), ra,
                candidate["multiple"], candidate["payoff"]), cfg.initial_balance, trials=1024) for factor in (1.5, 2, 3)}
            checks = dict(training_verified=row["screen_qualified"] and all(value["net_pnl"] > 0 and value["max_drawdown"] < 18000 for value in verification[cid].values()),
                profitable=metrics["net_pnl"] > 0, drawdown_below_2000=metrics["max_drawdown"] < 2000,
                intrabar_drawdown_below_2000=metrics["max_intraday_drawdown_bound"] < 2000, enough_trades=metrics["trades"] >= 100,
                positive_confidence=metrics["uncertainty"]["mean_ci"][0] is not None and metrics["uncertainty"]["mean_ci"][0] > 0,
                positive_at_2x_costs=stress["2"]["net_pnl"] > 0)
            outcomes.append(dict(candidate_id=cid, candidate=candidate, metrics=metrics, checks=checks, stress=stress,
                economic_research_qualified=all(checks.values()), deployment_eligible=False))
            json_write(directory/f"{micro}_validation_results.json", outcomes)
            print(reference, "->", micro, "adaptive", cid, "PnL", round(metrics["net_pnl"], 2), "DD", round(metrics["max_drawdown"], 2), flush=True)
        report["pairs"][reference+"->"+micro] = dict(reference_sessions=count, screen_attempts=len(rows), screen_qualified=sum(row["screen_qualified"] for row in rows),
            reference_source_version=metadata["dataset_version"], validation_dataset_version=actual_meta["dataset_version"], calendar_verified=quality["calendar_verified"], validation_results=outcomes)
        json_write(directory/"results.json", report)
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    json_write(directory/"results.json", report)
    json_write(root/"reports/latest_adaptive_opening_study.json", dict(path=str(directory), **report))


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()

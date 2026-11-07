"""New economically motivated session/calendar rules; no consumed-test access."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from datetime import datetime, timezone
import json
import gc
import shutil
from functools import partial
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from overnight_study import session_frames
from quant_futures.transfer import trading_config, guarded_partition
from quant_futures.contracts import SPECS
from quant_futures.execution import PaperBroker, Action
from quant_futures.backtest import run_backtest
from quant_futures.data import canonical
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.metrics import summarize
from quant_futures.config import digest, file_hash
from quant_futures.research import json_write, code_identity

RULES = {
    "europe_open_drift": (120, 180),
    "europe_selloff_reversal": (120, 180),
    "europe_trend_alignment": (120, 180),
    "month_start_drift": (180, 300),
    "week_start_drift": (180, 300),
    "overnight_continuation": (180, 300),
    "us_open_reversal": (585, 630),
    "midmorning_reversal": (630, 690),
}


def config(symbol, candidate):
    cfg = trading_config(symbol, candidate["width"], candidate["payoff"], hold=180)
    return cfg.model_copy(update={"timeframe_minutes": 1,
        "execution": cfg.execution.model_copy(update={"max_gap_minutes": 5})})


def context(group, history):
    local = group.timestamp_utc.dt.tz_convert("America/New_York")
    minute = (local.dt.hour*60+local.dt.minute).to_numpy()
    return dict(minute=minute, time=pd.DatetimeIndex(group.timestamp_utc).as_unit("ns").asi8,
        open=group.open.to_numpy(), high=group.high.to_numpy(), low=group.low.to_numpy(), close=group.close.to_numpy(),
        volume=group.volume.to_numpy(), contract=group.contract.to_numpy(), session=str(group.session_id.iloc[0]),
        date=pd.Timestamp(group.session_id.iloc[0]), prior_return=history[-1]/history[-2]-1 if len(history) >= 2 else np.nan,
        prior_trend=int(np.sign(history[-1]-np.mean(history[-20:]))) if len(history) >= 20 else 0)


def side_at(c, name, decision):
    if name == "europe_open_drift":
        return 1
    if name == "europe_selloff_reversal":
        return 1 if c["prior_return"] < 0 else 0
    if name == "europe_trend_alignment":
        return c["prior_trend"]
    if name == "month_start_drift":
        # Calendar days are known before entry. This is not an assertion of the
        # exact exchange-trading-day turn-of-month definition from the paper.
        return 1 if c["date"].day <= 3 else 0
    if name == "week_start_drift":
        return 1 if c["date"].weekday() <= 1 else 0
    if name == "overnight_continuation":
        opening = np.flatnonzero(c["minute"] == 1080)
        if not len(opening) or opening[0] >= decision:
            return 0
        return int(np.sign(c["close"][decision]-c["open"][opening[0]]))
    start = np.flatnonzero(c["minute"] == 570)
    if not len(start) or start[0] > decision:
        return 0
    # All prices here are at or before the completed decision candle.
    return -int(np.sign(c["close"][decision]-c["open"][start[0]]))


def screen(c, candidate, symbol, *, windows=RULES, side_fn=side_at):
    entry, end_clock = windows[candidate["name"]]
    decisions = np.flatnonzero(c["minute"] == entry-1)
    if not len(decisions):
        return None
    decision = decisions[0]
    side = side_fn(c, candidate["name"], decision)
    start = decision+1
    if not side or start >= len(c["time"]) or c["minute"][start] != entry or c["volume"][decision] < 100:
        return None
    ends = np.flatnonzero((c["minute"] == end_clock) & (np.arange(len(c["minute"])) > start))
    if not len(ends):
        return None  # Approximate screen; event replay must verify missing-exit risk.
    end = ends[0]
    cfg, spec = config(symbol, candidate), SPECS[symbol]
    broker = PaperBroker(cfg.costs)
    price = broker.market_price(c["open"][start], side, symbol)
    stop, target = price-side*cfg.execution.stop_ticks*spec.tick, price+side*cfg.execution.target_ticks*spec.tick
    ids = np.arange(start, end)
    opening_stop = side*(c["open"][ids]-stop) <= 0
    stopped = c["low"][ids] <= stop if side > 0 else c["high"][ids] >= stop
    targeted = c["high"][ids] >= target+spec.tick if side > 0 else c["low"][ids] <= target-spec.tick
    gaps = np.diff(c["time"][start-1:end]) > 5*60*10**9
    rolls = c["contract"][ids] != c["contract"][decision]
    hits = np.flatnonzero(opening_stop | stopped | targeted | gaps | rolls)
    limit = False
    if len(hits):
        offset, bar = hits[0], ids[hits[0]]
        if rolls[offset]:
            return None
        if gaps[offset]:
            reference = c["open"][bar]
        elif opening_stop[offset] or stopped[offset]:
            reference = min(c["open"][bar], stop) if side > 0 else max(c["open"][bar], stop)
        else:
            reference, limit = target, True
    else:
        reference = c["open"][end]
    exit_price = spec.round_price(reference) if limit else broker.market_price(reference, -side, symbol)
    return dict(net_pnl=side*(exit_price-price)*spec.multiplier-2*cfg.costs.fee,
        year=c["date"].year, session=c["session"])


def history_close(group):
    return float(group.close.iloc[-1])


def intents(bars, candidate, *, windows=RULES, context_fn=context, side_fn=side_at, history_value=history_close):
    signal = np.full(len(bars), Action.HOLD, dtype=object)
    history = []
    entry, exit_clock = windows[candidate["name"]]
    for _, indexes in bars.groupby("session_id", sort=False).indices.items():
        indexes = np.asarray(indexes)
        group = bars.iloc[indexes].reset_index(drop=True)
        c = context_fn(group, history)
        decisions = np.flatnonzero(c["minute"] == entry-1)
        if len(decisions):
            decision = decisions[0]
            side = side_fn(c, candidate["name"], decision)
            if side:
                signal[indexes[decision]] = Action.LONG if side > 0 else Action.SHORT
        # Exit is requested at the close immediately before scheduled exit.
        signal[indexes[(c["minute"] >= exit_clock-1) & (c["minute"] < 1080)]] = Action.EXIT
        history.append(history_value(group))
    return pd.Series(signal, index=bars.index)


def keep_indexes(bars, candidate, *, windows=RULES):
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    clock = local.dt.hour*60+local.dt.minute
    entry, exit_clock = windows[candidate["name"]]
    keep = clock.between(entry-1, exit_clock).to_numpy(copy=True)
    keep[np.flatnonzero(~bars.session_id.duplicated())] = True
    return np.flatnonzero(keep)


def main(*, prefix="session_window_minutes", windows=RULES, context_fn=context, side_fn=side_at,
         history_value=history_close, rationale=None, sources=None, driver_path=None):
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = root/"runs"/f"{prefix}_{stamp}"
    folder.mkdir(exist_ok=False)
    report = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(), script_sha256=file_hash(__file__),
        protocol="Post-final-test exploratory research. Original ES/NQ 2010–2023 training, internal 2022–2023 screening and full event verification, then actual MES/MNQ 2024–2025 reused selection-period validation. 2026 is sealed; this script never loads it. Independent confirmation requires new forward data.",
        sources=["https://www.newyorkfed.org/research/staff_reports/sr917", "https://docs.lib.purdue.edu/ciberwp/43/"],
        rationale="Published overnight drift and calendar effects motivate fixed hypotheses; neither publication establishes current MES/MNQ profitability. Prior-session data and completed current candles only. Month-start uses known calendar dates, not future inferred exchange holidays.",
        rules=windows, risk="One micro; $1800 risk stop and $2000 measured drawdown checks; same adverse fills and published cash commissions. Reference mini budgets scale 10x explicitly.",
        screening="Fast independent-trade screen is approximate, followed by mandatory continuous shared-engine reference verification. No prices filled; entries/exit gaps can disqualify a strategy. Earlier 2010–2021 economics must also be positive.",
        candidates=[dict(name=name, width=width, payoff=payoff) for name in windows for width in (1, 2) for payoff in (2, 3)],
        final_test_accessed=False, post_final_test_research=True, pairs={})
    if rationale is not None:
        report["rationale"] = rationale
    if sources is not None:
        report["sources"] = sources
    if driver_path is not None:
        report["driver_sha256"] = file_hash(driver_path)
        shutil.copyfile(driver_path, folder/"strategy_driver.py")
    make_signal = partial(intents, windows=windows, context_fn=context_fn, side_fn=side_fn, history_value=history_value)
    make_screen = partial(screen, windows=windows, side_fn=side_fn)
    keep_window = partial(keep_indexes, windows=windows)
    json_write(folder/"protocol.json", report)
    shutil.copyfile(__file__, folder/"study_script.py")
    for reference, micro in (("ES", "MES"), ("NQ", "MNQ")):
        source = resolve_dataset(reference+":train")
        meta = json.loads(source.with_suffix(".manifest.json").read_text())
        if meta["split_role"] != "train" or meta["instrument"] != reference or file_hash(source) != meta["dataset_version"]:
            raise ValueError("Reference provenance mismatch")
        results = [[] for _ in report["candidates"]]
        history, count = [], 0
        for group in session_frames(source):
            if not group.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
                raise PermissionError("Training includes a future reference observation")
            c = context_fn(group, history)
            for index, candidate in enumerate(report["candidates"]):
                result = make_screen(c, candidate, reference)
                if result:
                    results[index].append(result)
            history.append(history_value(group))
            count += 1
            if count % 500 == 0:
                print(reference, "session-window reference days", count, flush=True)
        attempts = []
        for candidate, trades in zip(report["candidates"], results):
            years = {}
            minimum = 10 if candidate["name"] == "month_start_drift" else 30
            for year in (2022, 2023):
                pnl = [row["net_pnl"] for row in trades if row["year"] == year]
                curve = np.r_[0, np.cumsum(pnl)]
                years[str(year)] = dict(net_pnl=float(curve[-1]), closed_trade_drawdown=float(np.max(np.maximum.accumulate(curve)-curve)), trades=len(pnl))
            earlier = sum(row["net_pnl"] for row in trades if row["year"] < 2022)
            qualified = earlier > 0 and all(row["net_pnl"] > 0 and row["trades"] >= minimum for row in years.values())
            attempts.append(dict(candidate_id="session_"+digest(candidate)[:10], candidate=candidate,
                earlier_2010_2021_net=earlier, screen_years=years, screen_qualified=qualified,
                score=min(row["net_pnl"]/(1+row["closed_trade_drawdown"]) for row in years.values())))
        attempts.sort(key=lambda row: (row["screen_qualified"], row["score"]), reverse=True)
        json_write(folder/f"{reference}_screen_attempts.json", attempts)
        selected = attempts[:3]
        json_write(folder/f"{reference}_frozen_selection.json", dict(frozen_at=datetime.now(timezone.utc).isoformat(), selected=selected,
            basis="Reference screening only, before actual micro validation. 2026 is excluded."))
        training = canonical(pd.read_parquet(source, filters=[("timestamp_utc", ">=", pd.Timestamp("2021-10-01T00:00Z"))]))
        verified = {}
        for row in selected:
            candidate = row["candidate"]
            signal = make_signal(training, candidate)
            keep = keep_window(training, candidate)
            yearly = {}
            for year in (2022, 2023):
                indexes = keep[training.timestamp_utc.iloc[keep].dt.year.to_numpy() == year]
                cfg = config(reference, candidate)
                result = run_backtest(training.iloc[indexes].reset_index(drop=True), signal.iloc[indexes].reset_index(drop=True), cfg)
                yearly[str(year)] = summarize(result, cfg.initial_balance, trials=2048)
            verified[row["candidate_id"]] = yearly
        json_write(folder/f"{reference}_event_training_verification.json", verified)
        del training, results
        gc.collect()
        bars, validation_meta, quality = guarded_partition(micro, "validation", minutes=1)
        warm = canonical(pd.read_parquet(resolve_dataset(micro+":train"), filters=[("timestamp_utc", ">=", pd.Timestamp("2023-10-01T00:00Z"))]))
        combined = pd.concat([warm, bars], ignore_index=True)
        outcomes = []
        for row in selected:
            candidate, cid = row["candidate"], row["candidate_id"]
            signal = make_signal(combined, candidate).iloc[len(warm):].reset_index(drop=True)
            keep = keep_window(bars, candidate)
            rb, rs = bars.iloc[keep].reset_index(drop=True), signal.iloc[keep].reset_index(drop=True)
            cfg = config(micro, candidate)
            result = run_backtest(rb, rs, cfg)
            measured = summarize(result, cfg.initial_balance, trials=2048)
            result["curve"].to_parquet(folder/f"{micro}_{cid}_validation_equity.parquet", index=False)
            result["trades"].to_parquet(folder/f"{micro}_{cid}_validation_trades.parquet", index=False)
            stress = {str(factor): summarize(run_backtest(rb, rs, cfg.model_copy(update={"costs": cfg.costs.scaled(factor)})), cfg.initial_balance, trials=2048) for factor in (1.5, 2, 3)}
            minimum = 30 if candidate["name"] == "month_start_drift" else 100
            checks = dict(training_verified=row["screen_qualified"] and all(value["net_pnl"] > 0 and value["max_drawdown"] < 18000 for value in verified[cid].values()),
                profitable=measured["net_pnl"] > 0, drawdown_below_2000=measured["max_drawdown"] < 2000,
                intrabar_drawdown_below_2000=measured["max_intraday_drawdown_bound"] < 2000, enough_trades=measured["trades"] >= minimum,
                positive_confidence=measured["uncertainty"]["mean_ci"][0] is not None and measured["uncertainty"]["mean_ci"][0] > 0,
                positive_at_2x_costs=stress["2"]["net_pnl"] > 0)
            outcomes.append(dict(candidate_id=cid, candidate=candidate, metrics=measured, checks=checks, stress=stress,
                economic_research_qualified=all(checks.values()), independent_final_confirmation=False, deployment_eligible=False))
            json_write(folder/f"{micro}_validation_results.json", outcomes)
            print(reference, "->", micro, candidate["name"], "PnL", round(measured["net_pnl"], 2), "DD", round(measured["max_drawdown"], 2), flush=True)
        report["pairs"][reference+"->"+micro] = dict(reference_sessions=count, screen_attempts=len(attempts), screen_qualified=sum(row["screen_qualified"] for row in attempts),
            reference_source_version=meta["dataset_version"], validation_dataset_version=validation_meta["dataset_version"], calendar_verified=quality["calendar_verified"], validation_results=outcomes)
        json_write(folder/"results.json", report)
        gc.collect()
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    json_write(folder/"results.json", report)
    output_name = "latest_session_window_study.json" if prefix == "session_window_minutes" else f"latest_{prefix}_study.json"
    json_write(root/"reports"/output_name, dict(path=str(folder), **report))


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()

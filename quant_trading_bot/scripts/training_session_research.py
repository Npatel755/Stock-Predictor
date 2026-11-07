"""Fixed session-rule research that can open only the NQ training partition."""
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key] = "1"
from datetime import datetime,timezone
import gc
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from overnight_study import session_frames
from quant_futures.backtest import Simulator
from quant_futures.config import digest,file_hash
from quant_futures.contracts import SPECS
from quant_futures.data import canonical,validate
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.execution import Action
from quant_futures.metrics import summarize
from quant_futures.research import code_identity,json_write
from quant_futures.transfer import trading_config
from quant_futures.validation import freeze_candidate

ROOT = Path(__file__).resolve().parents[1]
BLOCKS = (("2010_2015",2010,2016),("2016_2019",2016,2020),("2020_2023",2020,2024))


def training_source():
    path = resolve_dataset("NQ:train")
    meta = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if meta.get("instrument") != "NQ" or meta.get("split_role") != "train" or meta.get("raw_contract_prices") is not True or meta.get("synthetic") is not False:
        raise PermissionError("Actual raw-contract NQ training partition required")
    if file_hash(path) != meta["dataset_version"]:
        raise ValueError("Training provenance mismatch")
    return path,meta


def five_minute_session(group):
    """Aggregate only five real contiguous same-contract minute observations."""
    local = group.timestamp_utc.dt.tz_convert("America/New_York")
    minute = local.dt.hour*60+local.dt.minute
    regular = group.loc[minute.between(570,964)].copy()
    if regular.empty:
        return pd.DataFrame()
    regular["bucket"] = regular.timestamp_utc.dt.floor("5min")
    rows = []
    for timestamp,bucket in regular.groupby("bucket",sort=False):
        if len(bucket) != 5 or bucket.contract.nunique() != 1 or bucket.timestamp_utc.iloc[0] != timestamp or not bucket.timestamp_utc.diff().iloc[1:].eq(pd.Timedelta(minutes=1)).all():
            continue
        rows.append(dict(timestamp_utc=timestamp,instrument="NQ",contract=bucket.contract.iloc[0],
            open=float(bucket.open.iloc[0]),high=float(bucket.high.max()),low=float(bucket.low.min()),
            close=float(bucket.close.iloc[-1]),volume=int(bucket.volume.sum())))
    return canonical(pd.DataFrame(rows)) if rows else pd.DataFrame()


def intent_and_ranges(bars,candidate):
    signals = np.full(len(bars),Action.HOLD,dtype=object)
    ranges = np.full(len(bars),np.nan)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    clock = (local.dt.hour*60+local.dt.minute).to_numpy()
    for _,indexes in bars.groupby("session_id",sort=False).indices.items():
        indexes = np.asarray(indexes)
        opening = indexes[(clock[indexes] >= 570) & (clock[indexes] < 600)]
        if len(opening) != 6 or not np.array_equal(clock[opening],np.arange(570,600,5)) or bars.contract.iloc[opening].nunique() != 1:
            continue
        high,low = float(bars.high.iloc[opening].max()),float(bars.low.iloc[opening].min())
        width = high-low
        if width <= 0:
            continue
        # This range becomes known at 10:00, after the 09:55 candle closes.
        ranges[indexes[clock[indexes] >= 595]] = width
        attempts = opening[-1:] if candidate["name"] == "opening_momentum_5m" else indexes[(clock[indexes] >= 600) & (clock[indexes] < 660)]
        for i in attempts:
            close,hi,lo = float(bars.close.iloc[i]),float(bars.high.iloc[i]),float(bars.low.iloc[i])
            if bars.contract.iloc[i] != bars.contract.iloc[opening[-1]]:
                break
            if candidate["name"] == "opening_breakout_5m":
                side = 1 if close > high else -1 if close < low else 0
            elif candidate["name"] == "failed_breakout_5m":
                short,long = hi > high and close < high,lo < low and close > low
                side = 0 if short and long else -1 if short else 1 if long else 0
            elif candidate["name"] == "opening_momentum_5m":
                displacement = close-float(bars.open.iloc[opening[0]])
                side = int(np.sign(displacement)) if abs(displacement) >= .25*width else 0
            else:
                raise ValueError("Unknown frozen rule")
            if side and not (candidate["long_only"] and side < 0):
                signals[i] = Action.LONG if side > 0 else Action.SHORT
                break
        signals[indexes[clock[indexes] >= 715]] = Action.EXIT
    return pd.Series(signals),pd.Series(ranges)


def configuration(candidate,factor=1):
    cfg = trading_config("NQ",hold=24)
    return cfg.model_copy(update={"timeframe_minutes":5,"costs":cfg.costs.scaled(factor),
        "execution":cfg.execution.model_copy(update={"max_gap_minutes":10,"session_flat_minute_et":720,"max_hold_bars":24}),
        "risk":cfg.risk.model_copy(update={"max_trade_risk":1500,"max_open_risk":1500,"max_daily_loss":3000,"max_drawdown":19000})})


def replay(bars,signals,ranges,candidate,factor=1):
    cfg = configuration(candidate,factor)
    sim = Simulator(cfg)
    previous_range = np.nan
    for i,(bar,signal) in enumerate(zip(bars.itertuples(index=False),signals)):
        # Order at this open uses only the preceding completed five-minute range.
        if np.isfinite(previous_range):
            ticks = max(4,int(np.ceil(previous_range*candidate["stop_fraction"]/SPECS["NQ"].tick)))
            sim.cfg = cfg.model_copy(update={"execution":cfg.execution.model_copy(update={"stop_ticks":ticks,"target_ticks":ticks*candidate["payoff"]})})
        sim.step(bar,signal)
        sim.broker.events.clear()
        previous_range = ranges.iloc[i]
    result = sim.finish()
    result.update(permanent_risk_lock=sim.risk.killed,risk_reason=sim.risk.reason)
    return result


def measure(result):
    metrics = summarize(result,500000,trials=24)
    metrics.update(permanent_risk_lock=result["permanent_risk_lock"],risk_reason=result["risk_reason"])
    return metrics


def rank(row,stress=False):
    cases = list(row["base"].values())+ (list(row["stress_2x"].values()) if stress else [])
    positive = sum(m["net_pnl"] > 0 for m in cases)
    no_locks = all(not m["permanent_risk_lock"] for m in cases)
    sufficient = all(m["trades"] >= 60 for m in cases)
    risk_ok = all(max(m["max_drawdown"],m["max_intraday_drawdown_bound"]) < 20000 for m in cases)
    qualified = positive == len(cases) and no_locks and sufficient and risk_ok
    ratios = [m["net_pnl"]/(1+max(m["max_drawdown"],m["max_intraday_drawdown_bound"])) for m in cases]
    return qualified,no_locks,positive,min(ratios),sum(m["net_pnl"] for m in cases),row["candidate_id"]


def main():
    source,meta = training_source()
    folder = ROOT/"runs"/datetime.now(timezone.utc).strftime("training_sessions_%Y%m%dT%H%M%SZ")
    folder.mkdir(exist_ok=False)
    grid = [dict(name=name,long_only=long_only,stop_fraction=stop,payoff=payoff,contracts=1)
        for name in ("opening_breakout_5m","failed_breakout_5m","opening_momentum_5m")
        for long_only in (False,True) for stop in (.5,1.) for payoff in (2,3)]
    protocol = dict(created_at=datetime.now(timezone.utc).isoformat(),**code_identity(),
        training_only=True,validation_prices_accessed=False,test_prices_accessed=False,
        design="24 fixed cases: three session-rule families, both/long-only directions, half/full opening-range stop, 2R/3R target, one NQ contract. Completed five-minute candles. One entry attempt per session, noon flattening. No protective-stop retuning.",
        selection="Evaluate each case continuously within 2010–2015, 2016–2019, 2020–2023 NQ training blocks. Risk/capital reset at block boundaries only. Rank by qualification, no risk shutdown, number of profitable blocks, worst block net/worst drawdown, total net, id. Freeze top four base-ranked cases before 2x training cost stress. Select one qualified base/stress survivor, otherwise no promoted candidate. Minimum 60 trades per block, positive each block, no shutdown, close/intrabar DD <20000 actual NQ dollars. No validation or test replay in this script.",
        limitations="This is in-training research and repeated hypothesis search; internal blocks are not untouched external confirmation. NQ has real mini economics and 10x micro risk budgets, not synthetic early MNQ P&L. The researcher retains prior validation/test knowledge; outcomes cannot remove that contamination. Configured risk stops may be exceeded by gaps.",
        source=str(source),dataset_version=meta["dataset_version"],blocks=BLOCKS,candidates=grid,
        script_hash=file_hash(__file__),session_loader_hash=file_hash(ROOT/"scripts/overnight_study.py"))
    json_write(folder/"protocol.json",protocol)
    shutil.copyfile(__file__,folder/Path(__file__).name)
    shutil.copyfile(ROOT/"scripts/overnight_study.py",folder/"overnight_study.py")
    frames = []
    for n,group in enumerate(session_frames(source),1):
        if not group.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all() or not group.instrument.eq("NQ").all():
            raise PermissionError("Non-training observations blocked")
        frame = five_minute_session(group)
        if len(frame):
            frames.append(frame)
        if n % 750 == 0:
            print("Training sessions aggregated",n,flush=True)
    bars = canonical(pd.concat(frames,ignore_index=True))
    del frames
    _,quality = validate(bars,minutes=5)
    if quality["fatal"] or bars.timestamp_utc.duplicated().any():
        raise ValueError("Invalid five-minute training source")
    bars.to_parquet(folder/"training_5m.parquet",index=False)
    pieces = {label:bars.loc[bars.timestamp_utc.dt.year.between(left,right-1)].reset_index(drop=True) for label,left,right in BLOCKS}
    del bars
    rows = []
    for candidate in grid:
        cid = "session5_"+digest(candidate)[:10]
        row = dict(candidate_id=cid,candidate=candidate,base={})
        for label,block in pieces.items():
            signals,ranges = intent_and_ranges(block,candidate)
            result = replay(block,signals,ranges,candidate)
            row["base"][label] = measure(result)
            del result
        rows.append(row)
        json_write(folder/"NQ_training_attempts.json",[dict(candidate_id=r["candidate_id"],candidate=r["candidate"],status="completed",metrics={"net_pnl":sum(m["net_pnl"] for m in r["base"].values())},blocks=r["base"]) for r in rows])
        print(cid,candidate["name"],"block net",[m["net_pnl"] for m in row["base"].values()],"base qualified",rank(row)[0],flush=True)
        gc.collect()
    shortlisted = sorted(rows,key=rank,reverse=True)[:4]
    json_write(folder/"frozen_training_shortlist.json",dict(frozen_at=datetime.now(timezone.utc).isoformat(),candidates=shortlisted,
        basis="Training base results only, before 2x training cost replay. Validation/test unopened."))
    for row in shortlisted:
        row["stress_2x"] = {}
        for label,block in pieces.items():
            signals,ranges = intent_and_ranges(block,row["candidate"])
            result = replay(block,signals,ranges,row["candidate"],2)
            row["stress_2x"][label] = measure(result)
            del result
        row["qualified"] = bool(rank(row,True)[0])
        json_write(folder/"training_cost_stress.json",shortlisted)
        print("Training stress",row["candidate_id"],"block net",[m["net_pnl"] for m in row["stress_2x"].values()],"qualified",row["qualified"],flush=True)
        gc.collect()
    survivors = sorted([r for r in shortlisted if r["qualified"]],key=lambda r:rank(r,True),reverse=True)
    selected = survivors[0] if survivors else None
    if selected:
        freeze_candidate(folder/"frozen_candidate.json",dict(candidate_id=selected["candidate_id"],parameters=selected["candidate"],
            training_metrics=selected,source_hash=protocol["source_hash"],script_hash=protocol["script_hash"],
            selection_used_validation=False,selection_used_test=False,deployment_eligible=False))
        for label,block in pieces.items():
            signals,ranges = intent_and_ranges(block,selected["candidate"])
            result = replay(block,signals,ranges,selected["candidate"])
            result["curve"].to_parquet(folder/f"selected_{label}_equity.parquet",index=False)
            result["trades"].to_parquet(folder/f"selected_{label}_trades.parquet",index=False)
    report = dict(path=str(folder),completed_at=datetime.now(timezone.utc).isoformat(),protocol=protocol,
        training_cases=len(rows),shortlist=shortlisted,selected=selected,qualified_candidates=len(survivors),
        validation_prices_accessed=False,test_prices_accessed=False,deployment_eligible=False)
    json_write(folder/"results.json",report)
    json_write(ROOT/"reports/training_session_research.json",report)
    print(json.dumps(dict(completed=True,qualified=len(survivors),selected=None if selected is None else selected["candidate_id"],validation_opened=False,test_opened=False)))


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()

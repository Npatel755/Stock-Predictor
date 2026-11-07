"""Prespecified midday/afternoon rules, exclusively on NQ training history."""
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
import training_session_research as base
from quant_futures.backtest import Simulator
from quant_futures.config import digest,file_hash
from quant_futures.data import canonical,validate
from quant_futures.execution import Action
from quant_futures.research import code_identity,json_write
from quant_futures.validation import freeze_candidate

ROOT = base.ROOT


def intent_and_atr(bars,candidate):
    signals = np.full(len(bars),Action.HOLD,dtype=object)
    atrs = np.full(len(bars),np.nan)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    clock = (local.dt.hour*60+local.dt.minute).to_numpy()
    decision_clock = 835 if candidate["name"] == "afternoon_trend_5m" else 715
    for _,indexes in bars.groupby("session_id",sort=False).indices.items():
        indexes = np.asarray(indexes)
        completed = indexes[(clock[indexes] >= 570) & (clock[indexes] <= decision_clock)]
        expected = np.arange(570,decision_clock+1,5)
        # No incomplete morning, contract splice or missing bucket is filled.
        if len(completed) != len(expected) or not np.array_equal(clock[completed],expected) or bars.contract.iloc[completed].nunique() != 1:
            continue
        i = completed[-1]
        high,low = float(bars.high.iloc[completed].max()),float(bars.low.iloc[completed].min())
        width = high-low
        if width <= 0:
            continue
        closes = bars.close.iloc[completed].to_numpy()
        highs,lows = bars.high.iloc[completed].to_numpy(),bars.low.iloc[completed].to_numpy()
        previous = np.r_[float(bars.open.iloc[completed[0]]),closes[:-1]]
        atr = np.maximum.reduce([highs-lows,abs(highs-previous),abs(lows-previous)])[-12:].mean()
        if not np.isfinite(atr) or atr <= 0:
            continue
        displacement = closes[-1]-float(bars.open.iloc[completed[0]])
        if candidate["name"] == "midday_trend_5m":
            side = int(np.sign(displacement)) if abs(displacement) >= .25*width else 0
        elif candidate["name"] == "midday_reversal_5m":
            location = (closes[-1]-low)/width
            side = -1 if displacement > 0 and location >= .8 else 1 if displacement < 0 and location <= .2 else 0
        elif candidate["name"] == "afternoon_trend_5m":
            recent = closes[-1]-closes[-13]
            side = int(np.sign(recent)) if abs(recent) >= atr and np.sign(recent) == np.sign(displacement) else 0
        else:
            raise ValueError("Unknown declared rule")
        if candidate["long_only"] and side < 0:
            side = 0
        atrs[indexes[clock[indexes] >= decision_clock]] = atr
        if side:
            signals[i] = Action.LONG if side > 0 else Action.SHORT
        # Decision at the completed 15:50 candle, execution at 15:55 open.
        signals[indexes[clock[indexes] >= 950]] = Action.EXIT
    return pd.Series(signals),pd.Series(atrs)


def configuration(candidate,factor=1):
    cfg = base.configuration(dict(candidate,stop_fraction=1),factor)
    return cfg.model_copy(update={"execution":cfg.execution.model_copy(update={"session_flat_minute_et":955,"max_hold_bars":48})})


def replay(bars,signals,atrs,candidate,factor=1):
    cfg = configuration(candidate,factor)
    sim = Simulator(cfg)
    previous_atr = np.nan
    for i,(bar,signal) in enumerate(zip(bars.itertuples(index=False),signals)):
        if np.isfinite(previous_atr):
            ticks = max(4,int(np.ceil(previous_atr*candidate["atr_multiple"]/sim.spec.tick)))
            sim.cfg = cfg.model_copy(update={"execution":cfg.execution.model_copy(update={"stop_ticks":ticks,"target_ticks":int(np.ceil(ticks*candidate["payoff"]))})})
        sim.step(bar,signal)
        sim.broker.events.clear()
        previous_atr = atrs.iloc[i]
    result = sim.finish()
    result.update(permanent_risk_lock=sim.risk.killed,risk_reason=sim.risk.reason)
    return result


def load_cache():
    source,meta = base.training_source()
    parent = json.loads((ROOT/"reports/training_session_research.json").read_text())
    if parent["protocol"]["dataset_version"] != meta["dataset_version"] or parent["validation_prices_accessed"] or parent["test_prices_accessed"]:
        raise ValueError("Training cache provenance mismatch")
    path = Path(parent["path"])/"training_5m.parquet"
    bars = canonical(pd.read_parquet(path))
    if not bars.instrument.eq("NQ").all() or not bars.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
        raise PermissionError("Nontraining symbol/date blocked")
    _,quality = validate(bars,minutes=5)
    if quality["fatal"] or bars.timestamp_utc.duplicated().any():
        raise ValueError("Invalid cached training prices")
    return bars,path,meta


def main():
    # The parent report supplies only verified training-cache identity, never
    # validation/test metrics, prices, fitted parameters or selection outcomes.
    bars,cache_path,meta = load_cache()
    folder = ROOT/"runs"/datetime.now(timezone.utc).strftime("training_afternoon_%Y%m%dT%H%M%SZ")
    folder.mkdir(exist_ok=False)
    grid = [dict(name=name,long_only=long_only,atr_multiple=multiple,payoff=payoff,contracts=1)
        for name in ("midday_trend_5m","midday_reversal_5m","afternoon_trend_5m")
        for long_only in (False,True) for multiple in (2,3) for payoff in (1.5,2)]
    protocol = dict(created_at=datetime.now(timezone.utc).isoformat(),**code_identity(),
        training_only=True,validation_prices_accessed=False,test_prices_accessed=False,
        design="24 cases fixed before simulation: midday trend, midday reversal near completed morning extreme, afternoon trend aligned with session direction; both/long-only; 2/3 times prior completed 12-bar true-range mean stops; 1.5R/2R targets; one NQ contract. Midday entry at 12:00, afternoon entry 14:00; flatten 15:55. One attempt per session; no missing candles invented.",
        selection="Same three chronological training blocks and qualification as earlier session batch: positive each block, >=60 trades each, no risk shutdown, closing/intrabar DD <20000 NQ dollars in base and 2x costs. Top four frozen by base training rank before 2x replay. Select one passing survivor; otherwise none. No validation/test access or variants in this driver.",
        limitations="Repeated in-training hypothesis search; the researcher retains prior results, so this is not clean external confirmation. NQ mini economics and 10x risk budgets are not historical MNQ P&L. Block capital/risk resets prevent interpreting sums as a full-history continuous account.",
        source_dataset_version=meta["dataset_version"],training_cache=str(cache_path),training_cache_sha256=file_hash(cache_path),
        blocks=base.BLOCKS,candidates=grid,script_hashes={Path(p).name:file_hash(p) for p in (__file__,base.__file__)})
    for path in (__file__,base.__file__):
        shutil.copyfile(path,folder/Path(path).name)
    json_write(folder/"protocol.json",protocol)
    pieces = {label:bars.loc[bars.timestamp_utc.dt.year.between(left,right-1)].reset_index(drop=True) for label,left,right in base.BLOCKS}
    del bars
    rows = []
    for c in grid:
        cid = "afternoon_"+digest(c)[:10]
        row = dict(candidate_id=cid,candidate=c,base={})
        for label,block in pieces.items():
            signal,atr = intent_and_atr(block,c)
            result = replay(block,signal,atr,c)
            row["base"][label] = base.measure(result)
            del result
        rows.append(row)
        json_write(folder/"NQ_training_attempts.json",[dict(candidate_id=r["candidate_id"],candidate=r["candidate"],status="completed",blocks=r["base"],metrics={"net_pnl":sum(m["net_pnl"] for m in r["base"].values())}) for r in rows])
        print(cid,c["name"],"base net",[m["net_pnl"] for m in row["base"].values()],"qualified",base.rank(row)[0],flush=True)
        gc.collect()
    shortlisted = sorted(rows,key=base.rank,reverse=True)[:4]
    json_write(folder/"frozen_training_shortlist.json",dict(frozen_at=datetime.now(timezone.utc).isoformat(),candidates=shortlisted,
        basis="Base training only; frozen before training stress. Validation/test unopened."))
    for row in shortlisted:
        row["stress_2x"] = {}
        for label,block in pieces.items():
            signal,atr = intent_and_atr(block,row["candidate"])
            result = replay(block,signal,atr,row["candidate"],2)
            row["stress_2x"][label] = base.measure(result)
            del result
        row["qualified"] = bool(base.rank(row,True)[0])
        json_write(folder/"training_cost_stress.json",shortlisted)
        print("Afternoon stress",row["candidate_id"],[m["net_pnl"] for m in row["stress_2x"].values()],"qualified",row["qualified"],flush=True)
        gc.collect()
    survivors = sorted([r for r in shortlisted if r["qualified"]],key=lambda r:base.rank(r,True),reverse=True)
    selected = survivors[0] if survivors else None
    if selected:
        freeze_candidate(folder/"frozen_candidate.json",dict(candidate_id=selected["candidate_id"],parameters=selected["candidate"],
            training_metrics=selected,source_hash=protocol["source_hash"],script_hashes=protocol["script_hashes"],
            selection_used_validation=False,selection_used_test=False,deployment_eligible=False))
        for label,block in pieces.items():
            signal,atr = intent_and_atr(block,selected["candidate"])
            result = replay(block,signal,atr,selected["candidate"])
            result["curve"].to_parquet(folder/f"selected_{label}_equity.parquet",index=False)
            result["trades"].to_parquet(folder/f"selected_{label}_trades.parquet",index=False)
    report = dict(path=str(folder),completed_at=datetime.now(timezone.utc).isoformat(),protocol=protocol,
        training_cases=len(rows),shortlist=shortlisted,selected=selected,qualified_candidates=len(survivors),
        validation_prices_accessed=False,test_prices_accessed=False,deployment_eligible=False)
    json_write(folder/"results.json",report)
    json_write(ROOT/"reports/training_afternoon_research.json",report)
    print(json.dumps(dict(completed=True,qualified=len(survivors),selected=None if selected is None else selected["candidate_id"],validation_opened=False,test_opened=False)))


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()

"""Checkpointed 10,000-case search over existing physical TRAIN partitions only."""
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key] = "1"
import argparse
from collections import Counter
from datetime import datetime,timezone
import gc
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time
import csv
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from mass_configurations import generate,metadata,SEED,INSTRUMENTS,TARGET
from mass_execution import execute,TRADE_REASONS
from mass_features import features,signal_for
from mass_metrics import summarize_execution
from mass_verify import verify_execution
from quant_futures.config import file_hash,digest
from quant_futures.contracts import SPECS
from quant_futures.data import canonical,validate
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.research import json_write,code_identity

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/"runs/mass_training_v2"
FEATURE_KEYS = ("family","lookback","threshold")
CSV_FIELDS = ("rank","config_id","instrument","family","qualified","score","net_pnl","max_drawdown",
    "realized_drawdown","intrabar_drawdown","profit_factor","sharpe","win_rate","expectancy","trades",
    "avg_duration","positive_folds","total_folds","worst_fold_net","maximum_consistency_ratio",
    "locks","funded_breaches","positive_months","total_months","top_trade_share","signal_fingerprint",
    "behaviorally_unique","parameters","monthly_pnl","regime_pnl","fold_metrics")


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sources():
    return [Path(__file__),*(ROOT/"scripts"/name for name in
        ("mass_configurations.py","mass_execution.py","mass_features.py","mass_metrics.py","mass_verify.py"))]


def train_identity(instrument):
    path = resolve_dataset(instrument+":train")
    meta = read(path.with_suffix(".manifest.json"))
    if meta.get("split_role") != "train" or meta.get("instrument") != instrument:
        raise PermissionError("Only matching physical TRAIN partitions may be loaded")
    if meta.get("synthetic") is not False or meta.get("raw_contract_prices") is not True:
        raise ValueError("Verified actual raw-contract prices required")
    if file_hash(path) != meta["dataset_version"]:
        raise ValueError("Training source hash mismatch")
    return path,meta


def load_training(instrument,folder):
    path,meta = train_identity(instrument)
    target = folder/"cache"/(instrument+"_15m.parquet")
    manifest = target.with_suffix(".json")
    if target.exists() and manifest.exists():
        cached = read(manifest)
        if cached["source_sha256"] != meta["dataset_version"] or file_hash(target) != cached["cache_sha256"]:
            raise ValueError("Training cache identity changed")
        bars = canonical(pd.read_parquet(target))
    else:
        import duckdb
        connection = duckdb.connect()
        try:
            connection.execute("SET threads=1")
            connection.execute("SET memory_limit='256MB'")
            connection.execute("SET enable_progress_bar=false")
            # Full physical training file only. Count, distinctness and exact
            # endpoints prove all 15 consecutive source minutes are present.
            query = """SELECT time_bucket(INTERVAL '15 minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
                instrument, contract, session_id, arg_min(open,timestamp_utc) AS open,
                max(high) AS high, min(low) AS low, arg_max(close,timestamp_utc) AS close, sum(volume)::DOUBLE AS volume
                FROM read_parquet(?) GROUP BY 1,instrument,contract,session_id
                HAVING COUNT(*)=15 AND COUNT(DISTINCT timestamp_utc)=15
                AND MIN(CAST(timestamp_utc AS TIMESTAMPTZ))=time_bucket(INTERVAL '15 minutes',MIN(CAST(timestamp_utc AS TIMESTAMPTZ)))
                AND MAX(CAST(timestamp_utc AS TIMESTAMPTZ))-MIN(CAST(timestamp_utc AS TIMESTAMPTZ))=INTERVAL '14 minutes'
                ORDER BY 1"""
            bars = canonical(connection.execute(query,[str(path)]).fetch_df())
        finally:
            connection.close()
        target.parent.mkdir(parents=True,exist_ok=True)
        bars.to_parquet(target,index=False)
        json_write(manifest,dict(source_sha256=meta["dataset_version"],source_rows=meta["coverage"]["rows"],
            cache_sha256=file_hash(target),bars=len(bars),minutes=15,exact_contiguous_source_minutes=True))
    _,quality = validate(bars,minutes=15)
    if quality["fatal"] or bars.timestamp_utc.duplicated().any() or not bars.instrument.eq(instrument).all():
        raise ValueError("Invalid training cache")
    if not bars.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
        raise PermissionError("Observation crossed the fixed external training boundary")
    return bars,meta


def arrays(bars):
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    dates = pd.to_datetime(bars.session_id)
    return dict(timestamp=pd.DatetimeIndex(bars.timestamp_utc).as_unit("ns").asi8,
        session=pd.factorize(bars.session_id,sort=False)[0].astype(np.int64),
        minute=(local.dt.hour*60+local.dt.minute).to_numpy(dtype=np.int64),
        month=(dates.dt.year*100+dates.dt.month).to_numpy(dtype=np.int64),
        year=dates.dt.year.to_numpy(dtype=np.int64),contract=pd.factorize(bars.contract,sort=False)[0].astype(np.int64),
        **{name:bars[name].to_numpy(dtype=np.float64) for name in ("open","high","low","close","volume")})


def fold_slices(bars,instrument):
    periods = [(2016,2018),(2018,2020),(2020,2022),(2022,2024)] if instrument in ("ES","NQ") else [(2020,2021),(2021,2022),(2022,2023),(2023,2024)]
    result = []
    for left,right in periods:
        indexes = np.flatnonzero(bars.timestamp_utc.ge(pd.Timestamp(f"{left}-01-01T00:00Z")) & bars.timestamp_utc.lt(pd.Timestamp(f"{right}-01-01T00:00Z")))
        if len(indexes) <= 128:
            raise ValueError("Insufficient chronological training fold")
        result.append(dict(label=f"{left}_{right-1}",start=int(indexes[0]),stop=int(indexes[-1])+1,
            history_end_exclusive=f"{left}-01-01T00:00Z",evaluation_end_exclusive=f"{right}-01-01T00:00Z",
            embargo_bars=96,purge_bars=16))
    return result


def execution_cfg(c,factor=1):
    symbol = c["instrument"]
    return dict(initial_balance=50000,tick=SPECS[symbol].tick,multiplier=SPECS[symbol].multiplier,
        commission_per_side=1.75 if symbol in ("ES","NQ") else .5,exchange_per_side=0,regulatory_per_side=0,
        spread_ticks=1,slippage_ticks=1,impact_ticks=.25*(c["max_contracts"]-1),factor=factor,
        maxqty=c["max_contracts"],risk_per_trade=150,max_open_risk=150,daily_loss=300,hard_drawdown=1800,
        stop_atr=c["stop_atr"],target_ratio=c["target_r"],hold_bars=c["hold_bars"],
        entry_start=c["session_start"]-15,entry_end=c["session_end"]-30,
        flat_minute=min(c["session_end"],955),max_gap_minutes=20,participation=.01,
        trailing_atr=c["trailing_atr"],max_consecutive_losses=5,funded_drawdown=2000,funded_cap=50100)


def masked_signal(bars,c,f):
    signal = signal_for(c,f).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    decision = (local.dt.hour*60+local.dt.minute+15).to_numpy()
    valid = (decision >= c["session_start"]) & (decision < c["session_end"]) & (local.dt.weekday.to_numpy() < 5)
    return np.where(valid,signal,0).astype(np.int8)


def entry_regimes(trend):
    prior=np.r_[np.nan,np.asarray(trend,dtype=float)[:-1]]
    return np.where(np.isfinite(prior),np.where(abs(prior)>=.5,1,0),-1)


def evaluate_configuration(c,bars,data,folds,f,signal,factor=1,save=False,folder=None):
    fold_metrics = []
    known_regimes=entry_regimes(f['trend'])
    for fold in folds:
        start,stop = fold["start"],fold["stop"]
        d = {key:values[start:stop] for key,values in data.items()}
        s = signal[start:stop].copy()
        s[:fold["embargo_bars"]] = 0
        s[-fold["purge_bars"]:] = 0
        result = execute(d,s,f["atr"][start:stop],execution_cfg(c,factor))
        regimes = known_regimes[start:stop]
        d["regime"] = regimes
        measured = summarize_execution(result,d)
        measured["label"] = fold["label"]
        # Month/regime/fold statistics persist for all10k. Detailed daily
        # paths are retained for the frozen finalists without duplicating
        # millions of idle-session entries in the ranking/checkpoints.
        if not save:
            measured.pop("daily_pnl")
        if save and factor == 1:
            measured["execution_verification"] = verify_execution(bars.iloc[start:stop].reset_index(drop=True),d,s,f["atr"][start:stop],c,execution_cfg(c,factor),result)
        fold_metrics.append(measured)
        if save:
            name = c["config_id"]+"_"+fold["label"]+("_stress" if factor != 1 else "")
            curve = pd.DataFrame(dict(timestamp_utc=pd.to_datetime(d["timestamp"],unit="ns",utc=True),session=d["session"],
                equity=result["equity"],cash=result["cash"],intrabar_worst_bound=result["worst"],quantity=result["quantity"],funded_floor=result["funded_floor"]))
            curve.to_parquet(folder/(name+"_equity.parquet"),index=False)
            trades = pd.DataFrame(dict(entry_time=pd.to_datetime(d["timestamp"][result["trade_entry"]],unit="ns",utc=True),
                exit_time=pd.to_datetime(d["timestamp"][result["trade_exit"]],unit="ns",utc=True),side=result["trade_side"],
                quantity=result["trade_qty"],entry_price=result["trade_entryprice"],exit_price=result["trade_exitprice"],
                net_pnl=result["trade_net"],fees=result["trade_fees"],reason=[TRADE_REASONS[int(r)] for r in result["trade_reason"]]))
            trades.to_parquet(folder/(name+"_trades.parquet"),index=False)
    return fold_metrics


def aggregate(c,folds,signal):
    count=len(folds)
    net=sum(m["net_pnl"] for m in folds)
    trades=sum(m["trades"] for m in folds)
    positive=sum(m["net_pnl"]>0 for m in folds)
    worst=max(m["max_drawdown"] for m in folds)
    intrabar=max(m["intrabar_drawdown"] for m in folds)
    realized=max(m["realized_drawdown"] for m in folds)
    locks=sum(bool(m["killed"]) for m in folds)
    breaches=sum(bool(m["funded_failed"]) for m in folds)
    consistency=max((m["consistency"] if m["consistency"] is not None else 999) for m in folds)
    minimum_trades=min(m["trades"] for m in folds)
    qualified=positive==count and worst<2000 and intrabar<2000 and realized<2000 and locks==breaches==0 and minimum_trades>=30 and consistency<=.5
    ratios=[m["net_pnl"]/(1+max(m["max_drawdown"],m["intrabar_drawdown"])) for m in folds]
    # Frozen composite; only training internal-fold values are used.
    score=(10000 if qualified else 0)+100*positive/count-100*locks-100*breaches+min(ratios)+np.log1p(max(net,0))/10
    monthly,regimes={},{}
    for m in folds:
        monthly.update({str(k):v for k,v in m["monthly_pnl"].items()})
        for k,v in m["regime_pnl"].items(): regimes[str(k)]=regimes.get(str(k),0)+v
    weights=np.array([m["trades"] for m in folds],dtype=float)
    def average(key):
        vals=np.array([m[key] if m[key] is not None else 0 for m in folds],dtype=float)
        return float(np.dot(vals,weights)/weights.sum()) if weights.sum() else 0.
    return dict(config_id=c["config_id"],instrument=c["instrument"],family=c["family"],qualified=qualified,score=float(score),
        net_pnl=net,max_drawdown=worst,realized_drawdown=realized,intrabar_drawdown=intrabar,
        profit_factor=(sum(m['positive_trade_pnl'] for m in folds)/abs(sum(m['negative_trade_pnl'] for m in folds))) if sum(m['negative_trade_pnl'] for m in folds) else None,
        sharpe=float(np.mean([m["sharpe"] or 0 for m in folds])),
        win_rate=average("win_rate"),expectancy=net/trades if trades else 0,trades=trades,avg_duration=average("avg_duration"),
        positive_folds=positive,total_folds=count,worst_fold_net=min(m["net_pnl"] for m in folds),maximum_consistency_ratio=consistency,
        locks=locks,funded_breaches=breaches,positive_months=sum(v>0 for v in monthly.values()),total_months=len(monthly),
        top_trade_share=max((m["top_trade_share"] or 0) for m in folds),
        signal_fingerprint=hashlib.sha256(signal.tobytes()).hexdigest(),parameters=c,monthly_pnl=monthly,regime_pnl=regimes,fold_metrics=folds)


def setup(folder,seed):
    folder.mkdir(parents=True,exist_ok=True)
    rows=generate(seed)
    universe=metadata(rows,seed)
    source_hashes={p.name:file_hash(p) for p in sources()}
    core_identity=code_identity()
    assumptions_hash=file_hash(ROOT/'configs/lucidflex.yaml')
    path=folder/"protocol.json"
    if path.exists():
        protocol=read(path)
        if protocol["universe"]["universe_sha256"]!=universe["universe_sha256"] or protocol["source_hashes"]!=source_hashes:
            raise ValueError("Frozen universe/code changed; do not resume with different experiments")
        if protocol['source_hash']!=core_identity['source_hash'] or protocol['assumptions_sha256']!=assumptions_hash:
            raise ValueError('Frozen core dependencies or assumptions changed')
    else:
        protocol=dict(created_at=now(),seed=seed,target=TARGET,universe=universe,source_hashes=source_hashes,
            **core_identity,assumptions_sha256=assumptions_hash,split_policy="Existing physical training before2024, validation2024–2025, testing2026 unchanged. Only TRAIN may be loaded.",
            execution="15-minute completed contiguous raw-contract OHLCV; causal indicators; next-open market entries; prior-volume 1% IOC participation; fee/spread/slippage/size impact; tick rounding; strict target trade-through; stop-first ambiguity; adverse gap fills; daily/maximum-loss locks; EOD-funded floor and 50% consistency diagnostics. All markets use actual $50k, $150 risk/trade, $1800 internal stop; no mini-to-micro P&L relabeling.",
            fee_assumption="Per-side cash fees minis1.75/micros0.50 from existing sourced project snapshot. Exchange/regulatory breakdown and current actual all-in charges unverified; no exact compliance claim. Base1tick spread+1tick slippage; impact.25ticks per maximum extra contract.",
            walkforward="Fixed rule configurations assessed over four disjoint chronological training evaluation blocks. Mini history before2016 provides earlier warmup; micro2019 provides earlier warmup. Indicators use preceding training observations only, never fitted on full evaluation statistics. Suppress first96 and last16 entry bars per fold for warmup embargo/purge. Capital/risk reset between folds; aggregate net is a sum, maximum DD worst fold, not a continuous full-history account. This is training-only rolling-origin-style evaluation and ex-post training selection, not untouched external evidence.",
            ranking="Qualification requires positive each fold, >=30 trades each fold, no risk/funded failure, closing/intrabar DD<2000 and maximum daily-profit/total-profit<=50%. Composite=10000*qualified+100*positive_fold_fraction-100*locks-100*funded_breaches+worst(net/(1+maxDD))+log1p(positive total net)/10. Never rank using protected data. Top10 frozen after ALL10000, then training-only2x costs and event verification; no protected-price stage while fresh data unavailable.",
            unknowns=["authoritative historical holiday schedule","actual all-in fees","account rule effective version","minimum days","consistency cushion formula","platform/API permission"],
            validation_accessed=False,test_accessed=False,no_live_execution=True,
            runtime="CPU JIT for sequential path state. GPU not beneficial for this small sequential per-path model; no GPU training. Single worker avoids memory duplication. SQLite checkpoints commit25 experiments; resume by unique config id.")
        json_write(path,protocol)
        with (folder/"configurations.jsonl").open("x",encoding="utf-8") as stream:
            for row in rows: stream.write(json.dumps(row,sort_keys=True)+"\n")
        snapshot=folder/"code"
        snapshot.mkdir(exist_ok=False)
        for p in sources(): shutil.copyfile(p,snapshot/p.name)
        shutil.copytree(ROOT/'src/quant_futures',snapshot/'quant_futures',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(ROOT/"configs/lucidflex.yaml",snapshot/"lucidflex_snapshot.yaml")
    connection=sqlite3.connect(folder/"checkpoints.sqlite")
    connection.execute("CREATE TABLE IF NOT EXISTS results (config_id TEXT PRIMARY KEY,instrument TEXT NOT NULL,payload TEXT NOT NULL)")
    return rows,protocol,connection


def progress(folder,connection,phase):
    counts=dict(connection.execute("SELECT instrument,COUNT(*) FROM results GROUP BY instrument").fetchall())
    total=sum(counts.values())
    p=dict(run_path=str(folder),target=TARGET,completed=total,unique_configs=total,phase=phase,per_market=counts,
        updated_at=now(),validation_accessed=False,test_accessed=False)
    json_write(ROOT/"reports/mass_research_progress.json",p)
    print(json.dumps(p),flush=True)


def write_ranked(folder,rows):
    ordered=sorted(rows,key=lambda r:(r["score"],r["config_id"]),reverse=True)
    # Identical signal paths aren't independent discoveries. Report this
    # grouping; retain distinct executable stop/exit/sizing configurations.
    seen=set()
    for i,row in enumerate(ordered,1):
        row["rank"]=i
        behavior=digest(dict(signal=row["signal_fingerprint"],stop=row["parameters"]["stop_atr"],target=row["parameters"]["target_r"],
            hold=row["parameters"]["hold_bars"],qty=row["parameters"]["max_contracts"],trail=row["parameters"]["trailing_atr"]))
        row["behaviorally_unique"]=behavior not in seen
        seen.add(behavior)
    temp=folder/"ranked.csv.tmp"
    with temp.open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in ordered:
            values={key:row.get(key) for key in CSV_FIELDS}
            for key in ("parameters","monthly_pnl","regime_pnl","fold_metrics"): values[key]=json.dumps(values[key],allow_nan=False)
            writer.writerow(values)
    temp.replace(folder/"ranked.csv")
    return ordered


def run(folder=RUN,seed=SEED):
    rows,protocol,connection=setup(folder,seed)
    completed={row[0] for row in connection.execute("SELECT config_id FROM results")}
    for symbol in INSTRUMENTS:
        pending=[c for c in rows if c["instrument"]==symbol and c["config_id"] not in completed]
        if not pending: continue
        progress(folder,connection,"loading training "+symbol)
        bars,meta=load_training(symbol,folder)
        json_write(folder/(symbol+"_source.json"),meta)
        data=arrays(bars)
        folds=fold_slices(bars,symbol)
        json_write(folder/(symbol+"_folds.json"),folds)
        for lookback,configs in __import__('itertools').groupby(sorted(pending,key=lambda c:c["lookback"]),key=lambda c:c["lookback"]):
            f=features(bars,lookback)
            for c in configs:
                signal=masked_signal(bars,c,f)
                fm=evaluate_configuration(c,bars,data,folds,f,signal)
                row=aggregate(c,fm,signal)
                payload=json.dumps(row,allow_nan=False)
                connection.execute("INSERT INTO results VALUES (?,?,?)",(c["config_id"],symbol,payload))
                completed.add(c["config_id"])
                if len(completed)%25==0:
                    connection.commit()
                if len(completed)%100==0: progress(folder,connection,"training search "+symbol)
            del f
            gc.collect()
        connection.commit()
        del bars,data
        gc.collect()
    progress(folder,connection,"ranking complete training search")
    all_rows=[json.loads(row[0]) for row in connection.execute("SELECT payload FROM results")]
    if len(all_rows)!=TARGET or len({r["config_id"] for r in all_rows})!=TARGET:
        raise RuntimeError("Incomplete search; do not freeze finalists")
    ordered=write_ranked(folder,all_rows)
    top10=ordered[:10]
    shortlist=folder/"frozen_top10.json"
    frozen=dict(frozen_at=now(),configurations=top10,ranked_csv_sha256=file_hash(folder/"ranked.csv"),
        configuration_manifest_sha256=file_hash(folder/"configurations.jsonl"),source_hashes=protocol["source_hashes"],
        selection_basis="All10000 completed; training-only predetermined composite",validation_accessed=False,test_accessed=False)
    if shortlist.exists():
        prior=read(shortlist)
        if prior["ranked_csv_sha256"]!=frozen["ranked_csv_sha256"]: raise ValueError("Frozen ranking changed")
    else:
        json_write(shortlist,frozen)
    verification=[]
    for c_row in top10:
        c=c_row["parameters"]
        progress(folder,connection,"training finalist checks "+c["config_id"])
        bars,_=load_training(c["instrument"],folder)
        data=arrays(bars)
        fs=fold_slices(bars,c["instrument"])
        f=features(bars,c["lookback"])
        signal=masked_signal(bars,c,f)
        metrics=evaluate_configuration(c,bars,data,fs,f,signal,save=True,folder=folder)
        stress=evaluate_configuration(c,bars,data,fs,f,signal,factor=2,save=True,folder=folder)
        stress_row=aggregate(c,stress,signal)
        for old,new in zip(c_row["fold_metrics"],metrics):
            for key in ("net_pnl","max_drawdown","intrabar_drawdown","trades"):
                if old[key]!=new[key]: raise ValueError("Finalist reproduction failed")
        verified=dict(config_id=c["config_id"],base_reproduced=True,stress_2x=stress_row,
            execution_parity=[m["execution_verification"] for m in metrics],operational_eligibility=False)
        verification.append(verified)
        json_write(folder/"finalist_training_checks.json",verification)
        del bars,data,f,metrics,stress,signal
        gc.collect()
    qualified=sum(r["qualified"] for r in ordered)
    result=dict(run_path=str(folder),target=TARGET,completed=TARGET,unique_configs=TARGET,
        qualified_count=qualified,top10=top10,seed=seed,source_hashes=protocol["source_hashes"],
        validation_accessed=False,test_accessed=False,fresh_holdout_available=False,
        validation_status="blocked_previously_observed",test_status="blocked_previously_observed",
        split_policy=protocol["split_policy"],execution_verification=verification,
        funded_status="INCOMPLETE: unverified contractual details and platform permission; only labeled scenario checks",
        profitability_status="TRAINING_ONLY; external performance unconfirmed",total_is_configurations_not_families=True,
        finished_at=now())
    json_write(folder/"results.json",result)
    json_write(ROOT/"reports/mass_research_result.json",result)
    progress(folder,connection,"training complete; independent validation/test blocked")
    connection.close()


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",type=Path,default=RUN)
    parser.add_argument("--seed",type=int,default=SEED)
    args=parser.parse_args()
    with threadpool_limits(limits=1): run(args.run.resolve(),args.seed)

"""Another 200,000 unique TRAIN configurations alongside Gemini's reserved 500k.

No validation/test datasets or outcome files are resolved or read. Only immutable
training manifests are used for exclusions. All selections/count rules are frozen
before this run loads market prices. No third-party model response is assumed.
"""
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import csv
import gc
import json
from pathlib import Path
import random
import shutil
import sqlite3
import numpy as np
from threadpoolctl import threadpool_limits
import mass_research as engine
from mass_configurations import INSTRUMENTS, FAMILIES, LOOKBACKS, OPENING_LOOKBACKS, THRESHOLDS, SESSIONS, STOP_ATR, TARGET_R, HOLD_BARS, MAX_CONTRACTS, TRAILING_ATR, config_id
from training_500k_universe import create_bitset, config_to_index, set_bit, is_bit_set
from training_500k_policy import aggregate
from training_search_100k import folds_for, session_masks, cached_signal
from quant_futures.config import file_hash
from quant_futures.research import json_write, code_identity

ROOT = engine.ROOT
RUN = ROOT/'runs/collaborative_200k_v1'
TARGET = 200000
SEED = 20270101
PRIOR = ('mass_training_v2', 'mass_training_continuation_v1', 'training_search_50k_v2', 'training_search_100k_v1', 'training_search_200k_v1', 'training_search_500k_v1')
DD_FIELDS = ('realized_drawdown', 'max_drawdown', 'intrabar_drawdown')


def positive_under_limit(row):
    return bool(row['net_pnl'] > 0 and all(row[k] < 2000 for k in DD_FIELDS))


def sources():
    return [Path(__file__), *(Path(__file__).with_name(n) for n in ('training_500k_universe.py', 'training_500k_policy.py', 'training_search_100k.py', 'training_100k_policy.py', 'mass_continuation_configurations.py')), ROOT/'configs/user_account_phase_policy.json', *engine.sources()]


def setup(folder=RUN):
    folder.mkdir(parents=True, exist_ok=True)
    identity = {p.name: file_hash(p) for p in sources()}
    original = engine.read(ROOT/'runs/mass_training_v2/protocol.json')
    if code_identity()['source_hash'] != original['source_hash']:
        raise ValueError('Frozen core simulator changed')
    for p in engine.sources():
        if file_hash(p) != original['source_hashes'][p.name]:
            raise ValueError('Frozen execution dependency changed')
    protocol_path = folder/'protocol.json'
    db = sqlite3.connect(folder/'checkpoints.sqlite')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=NORMAL')
    db.execute('CREATE TABLE IF NOT EXISTS configs(config_id TEXT PRIMARY KEY, experiment_order INTEGER UNIQUE, lookback INTEGER, instrument TEXT, payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS results(config_id TEXT PRIMARY KEY, instrument TEXT, payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS checks(config_id TEXT PRIMARY KEY, payload TEXT)')
    if protocol_path.exists():
        protocol = engine.read(protocol_path)
        if protocol['source_hashes'] != identity or file_hash(folder/'configurations.jsonl') != protocol['configuration_sha256']:
            raise ValueError('Frozen collaborative search changed')
        for p, expected in protocol['exclusion_manifest_hashes'].items():
            if file_hash(p) != expected:
                raise ValueError('Reserved prior manifest changed')
        if db.execute('SELECT COUNT(*) FROM configs').fetchone()[0] != TARGET:
            raise ValueError('Frozen configuration database incomplete')
        return protocol, db
    if db.execute('SELECT COUNT(*) FROM results').fetchone()[0]:
        raise ValueError('Unfrozen results forbidden')
    # A partial pre-price manifest creation may safely be rebuilt on resume.
    db.execute('DELETE FROM configs')
    seen = create_bitset(); prior_count = 0; hashes = {}
    for run in PRIOR:
        p = ROOT/'runs'/run/'configurations.jsonl'
        hashes[str(p)] = file_hash(p)
        with p.open(encoding='utf-8') as stream:
            for line in stream:
                idx = config_to_index(json.loads(line))
                if is_bit_set(seen, idx):
                    raise ValueError(f'Duplicate active prior configuration in {run}')
                set_bit(seen, idx); prior_count += 1
    if prior_count != 870000:
        raise ValueError(f'Expected 870000 prior completed or Gemini-reserved configurations, got {prior_count}')
    order = 0
    with (folder/'configurations.jsonl').open('w', encoding='utf-8') as stream:
        for batch in range(20):
            rng = random.Random(SEED + batch)
            records = []
            for family in FAMILIES:
                for _ in range(250):
                    for symbol in INSTRUMENTS:
                        while True:
                            start, end = rng.choice(SESSIONS)
                            c = dict(instrument=symbol, family=family, lookback=rng.choice(OPENING_LOOKBACKS if family == 'opening_range' else LOOKBACKS), threshold=rng.choice(THRESHOLDS[family]), stop_atr=rng.choice(STOP_ATR), target_r=rng.choice(TARGET_R), hold_bars=rng.choice(HOLD_BARS), session_start=start, session_end=end, max_contracts=rng.choice(MAX_CONTRACTS), trailing_atr=rng.choice(TRAILING_ATR))
                            idx = config_to_index(c)
                            if not is_bit_set(seen, idx):
                                set_bit(seen, idx); break
                        order += 1
                        c.update(config_id=config_id(c), experiment_order=order)
                        payload = json.dumps(c, sort_keys=True)
                        stream.write(payload+'\n')
                        records.append((c['config_id'], order, c['lookback'], symbol, payload))
            db.executemany('INSERT INTO configs VALUES(?,?,?,?,?)', records); db.commit()
    if order != TARGET:
        raise ValueError('Incomplete fixed search universe')
    db.execute('CREATE INDEX IF NOT EXISTS config_schedule ON configs(instrument,lookback,config_id)'); db.commit()
    protocol = dict(created_at=engine.now(), target=TARGET, seed=SEED, classification='RESEARCH_ONLY', source_hashes=identity, core_source_hash=original['source_hash'], configuration_sha256=file_hash(folder/'configurations.jsonl'), exclusion_manifest_hashes=hashes, prior_completed_configurations=370000, gemini_reserved_configurations=500000, new_unique_configurations=TARGET, total_reserved_unique=1070000,
        authorization='User requests collaboration with Antigravity Gemini, another200000 strategies, and count positive net P&L with DD strictly below2000. Existing500k job preserved. No validation/test stage authorized.',
        hypothesis='Continue the original ten interpretable signal families and unchanged parameter domains. Broad seeded TRAIN exploration, unchanged execution and account assumptions. No development informed by protected outcomes.',
        count_rule='Positive sum of net P&L after modeled costs across2020-2023 annual accounts AND each of cash,closing,intrabar worst-fold drawdown strictly<2000. Risk locks do not remove cases from this requested two-condition count; report them separately.',
        research_gate='Existing500k quality diagnostic: no permanent locks/funded breaches;3/4 positive folds;PF>=1.30;80-800 trades;positive net;allDD<2000. 50% consistency applies only to evaluation account phase and is separately reported.',
        selection='Rank research-qualified cases by training net descending, intrabarDD ascending, configID. Verify and2x cost stress in order until first survives. Also report highest net among the requested two-condition count without claiming it qualifies.',
        calendar='Fixed physical TRAIN only before2024. Four separate annual2020,2021,2022,2023 accounts reset50k; sum net and worst annualDD, not continuous four-yearDD. First96/last16 entrybars embargo/purge; past-only indicators. Include all opening-range horizons15..120, not only ordinary lookbacks.',
        execution=original['execution'], fee_assumption=original['fee_assumption'], unknowns=original['unknowns'], phase_policy=engine.read(ROOT/'configs/user_account_phase_policy.json'), validation_accessed=False, test_accessed=False, protected_result_files_read=False, no_live_execution=True, independent_confirmation=False, early_stop=False,
        collaboration='Gemini500k job and reserved manifest observed. Shared handoff reports/CODEX_GEMINI_COORDINATION.md. Gemini acknowledgement/review must be recorded separately; not assumed.')
    json_write(protocol_path, protocol)
    snapshot = folder/'code'; snapshot.mkdir(exist_ok=True)
    for p in sources():
        shutil.copyfile(p, snapshot/p.name)
    shutil.copytree(ROOT/'runs/mass_training_v2/code/quant_futures', snapshot/'quant_futures', dirs_exist_ok=True)
    (folder/'cache').mkdir(exist_ok=True)
    for symbol in INSTRUMENTS:
        for ext in ('.json', '.parquet'):
            p = ROOT/'runs/training_search_100k_v1/cache'/(symbol+'_15m'+ext)
            shutil.copyfile(p, folder/'cache'/p.name)
    return protocol, db


def progress(folder, db, phase):
    counts = dict(db.execute('SELECT instrument,COUNT(*) FROM results GROUP BY instrument'))
    record = dict(run_path=str(folder), target=TARGET, completed=sum(counts.values()), per_market=counts, phase=phase, validation_accessed=False, test_accessed=False, protected_result_files_read=False, updated_at=engine.now())
    json_write(ROOT/'reports/COLLABORATIVE_200K_progress.json', record)
    print(json.dumps(record), flush=True)


def verify(row, bars, data, folds, features, signal, folder, db):
    cid = row['config_id']
    saved = db.execute('SELECT payload FROM checks WHERE config_id=?',(cid,)).fetchone()
    if saved:
        return json.loads(saved[0])
    c = row['parameters']
    measured = engine.evaluate_configuration(c, bars, data, folds, features, signal, save=True, folder=folder)
    for a, b in zip(row['fold_metrics'], measured):
        for key in ('net_pnl', *DD_FIELDS, 'trades'):
            if a[key] != b[key]:
                raise ValueError('Saved candidate failed reproduction')
    stress = aggregate(c, engine.evaluate_configuration(c,bars,data,folds,features,signal,factor=2,save=True,folder=folder), signal)
    check = dict(config_id=cid, base=row, stress_2x=stress, base_reproduced=True, execution_parity=[m['execution_verification'] for m in measured], stress_qualified=bool(stress['qualified']), validation_accessed=False, test_accessed=False)
    json_write(folder/('check_'+cid+'.json'), check)
    db.execute('INSERT INTO checks VALUES(?,?)', (cid, json.dumps(check,allow_nan=False))); db.commit()
    return check


def finish(folder, protocol, db):
    requested = "json_extract(payload,'$.net_pnl')>0 AND json_extract(payload,'$.realized_drawdown')<2000 AND json_extract(payload,'$.max_drawdown')<2000 AND json_extract(payload,'$.intrabar_drawdown')<2000"
    groups = {}
    for symbol in INSTRUMENTS:
        clauses = {'evaluated':'1', 'positive_under_2000':requested, 'positive_under_2000_no_locks':requested+" AND json_extract(payload,'$.locks')=0 AND json_extract(payload,'$.funded_breaches')=0", 'research_qualified':"json_extract(payload,'$.qualified')=1", 'evaluation_phase_qualified':"json_extract(payload,'$.evaluation_phase_qualified')=1"}
        groups[symbol] = {k:db.execute(f'SELECT COUNT(*) FROM results WHERE instrument=? AND ({condition})',(symbol,)).fetchone()[0] for k,condition in clauses.items()}
    totals = {k:sum(g[k] for g in groups.values()) for k in next(iter(groups.values()))}
    if totals['evaluated'] != TARGET:
        raise ValueError('Cannot publish partial budget as completed')
    ordering = "json_extract(payload,'$.net_pnl') DESC,json_extract(payload,'$.intrabar_drawdown') ASC,config_id"
    best = db.execute(f'SELECT payload FROM results WHERE {requested} ORDER BY {ordering} LIMIT 1').fetchone()
    winner = None
    # Fixed research qualification and profit ranking, no protected-period input.
    for (payload,) in db.execute(f"SELECT payload FROM results WHERE json_extract(payload,'$.qualified')=1 ORDER BY {ordering}").fetchall():
        row = json.loads(payload); c = row['parameters']
        progress(folder,db,'Verifying TRAIN profit-ranked candidate '+c['config_id'])
        bars,_ = engine.load_training(c['instrument'],folder); data=engine.arrays(bars); folds=folds_for(bars)
        features=engine.features(bars,c['lookback']); signal=cached_signal(c,features,session_masks(bars),{})
        check=verify(row,bars,data,folds,features,signal,folder,db)
        del bars,data,features,signal; gc.collect()
        if check['stress_qualified']:
            winner=check; break
    fields=[*engine.CSV_FIELDS,'evaluation_phase_qualified','robustness_score','positive_under_2000']
    with (folder/'ranked.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader()
        for rank,(payload,) in enumerate(db.execute(f'SELECT payload FROM results ORDER BY {ordering}'),1):
            row=json.loads(payload); row['rank']=rank; row['positive_under_2000']=positive_under_limit(row)
            out={k:row.get(k) for k in fields}
            for k in ('parameters','monthly_pnl','regime_pnl','fold_metrics'):
                out[k]=json.dumps(out[k],allow_nan=False)
            writer.writerow(out)
    for p,expected in protocol['exclusion_manifest_hashes'].items():
        if file_hash(p)!=expected:
            raise ValueError('Prior manifest modified during research')
    result=dict(completed=TARGET,totals=totals,by_market=groups,highest_net_requested_filter=json.loads(best[0]) if best else None,winner=winner,configuration_sha256=protocol['configuration_sha256'],ranked_sha256=file_hash(folder/'ranked.csv'),validation_accessed=False,test_accessed=False,protected_result_files_read=False,independent_confirmation=False,finished_at=engine.now())
    json_write(folder/'results.json',result); json_write(ROOT/'reports/COLLABORATIVE_200K_result.json',result)
    progress(folder,db,'200000_new_configurations_completed')


def run(folder=RUN,prepare_only=False):
    protocol,db=setup(folder)
    try:
        if prepare_only or (folder/'results.json').exists():
            print(json.dumps(dict(prepared=True,already_complete=(folder/'results.json').exists()))); return
        done={r[0] for r in db.execute('SELECT config_id FROM results')}
        for symbol in INSTRUMENTS:
            pending=db.execute('SELECT COUNT(*) FROM configs c WHERE instrument=? AND NOT EXISTS(SELECT 1 FROM results r WHERE r.config_id=c.config_id)',(symbol,)).fetchone()[0]
            if not pending: continue
            progress(folder,db,'Loading verified physical TRAIN '+symbol)
            bars,meta=engine.load_training(symbol,folder); data=engine.arrays(bars); folds=folds_for(bars)
            json_write(folder/(symbol+'_source.json'),meta); json_write(folder/(symbol+'_folds.json'),folds)
            masks=session_masks(bars)
            horizons=[r[0] for r in db.execute('SELECT DISTINCT lookback FROM configs WHERE instrument=? ORDER BY lookback',(symbol,))]
            for lookback in horizons:
                configs=[json.loads(r[0]) for r in db.execute('SELECT payload FROM configs WHERE instrument=? AND lookback=? ORDER BY config_id',(symbol,lookback)) if json.loads(r[0])['config_id'] not in done]
                if not configs: continue
                features=engine.features(bars,lookback); signal_cache={}
                for c in configs:
                    signal=cached_signal(c,features,masks,signal_cache)
                    measured=engine.evaluate_configuration(c,bars,data,folds,features,signal)
                    row=aggregate(c,measured,signal)
                    db.execute('INSERT INTO results VALUES(?,?,?)',(c['config_id'],symbol,json.dumps(row,allow_nan=False))); done.add(c['config_id'])
                    if len(done)%250==0: db.commit()
                    if len(done)%1000==0: progress(folder,db,f'TRAIN {symbol}, lookback{lookback}')
                db.commit(); del features,signal_cache,configs; gc.collect()
            del bars,data,masks; gc.collect()
        finish(folder,protocol,db)
    finally:
        db.close()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--prepare-only',action='store_true'); args=parser.parse_args()
    with threadpool_limits(limits=1): run(prepare_only=args.prepare_only)

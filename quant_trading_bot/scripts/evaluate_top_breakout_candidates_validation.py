"""Evaluate top 7 robust breakout and momentum candidates on 2024-2025 validation.

Selected strictly from training-time robustness criteria:
- Profit Factor >= 1.55
- Intrabar DD < $1,500
- Multi-year profitability
- Asymmetric reward-to-risk (Target R >= 2.0)

Zero tuning on validation data. Test data (2026) is strictly UNTOUCHED.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import argparse
import ast
import json
from pathlib import Path
import shutil
import sqlite3
import pandas as pd
from threadpoolctl import threadpool_limits
from quant_futures.config import digest, file_hash
from quant_futures.data import canonical, validate
from quant_futures.research import code_identity, json_write
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT/'runs/top_robust_candidates_validation_v1'
CANDIDATE_IDS = [
    'mass_5b51c549bc31f2f3de0e',
    'mass_f2e61111a66a4a873eda',
    'mass_33bf8e2fc3fc425f8ce2',
    'mass_b49390bd3c4cfb168db8',
    'mass_48e6ce6113d2a8d1cbc5',
    'mass_72d38b7e1c9c48d13c66',
    'mass_d1924ffa4a9fa8c4b947'
]


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def now(): return datetime.now(timezone.utc).isoformat()


def collect_candidates():
    db1 = sqlite3.connect(ROOT/'runs/training_search_100k_v1/checkpoints.sqlite')
    db2 = sqlite3.connect(ROOT/'runs/training_search_200k_v1/checkpoints.sqlite')
    candidates = []
    for cid in CANDIDATE_IDS:
        row = db1.execute('SELECT payload FROM results WHERE config_id=?', (cid,)).fetchone() or \
              db2.execute('SELECT payload FROM results WHERE config_id=?', (cid,)).fetchone()
        if not row:
            raise ValueError(f'Candidate {cid} not found')
        r = json.loads(row[0])
        candidates.append(r)
    db1.close(); db2.close()
    return candidates


def prepare():
    candidates = collect_candidates()
    catalog = read(ROOT/'data/catalog.json')
    partition = catalog['instruments']['MNQ']['splits']['validation']
    meta = read(Path(partition['path']).with_suffix('.manifest.json'))
    if meta['split_role'] != 'validation' or meta['instrument'] != 'MNQ':
        raise ValueError('Invalid MNQ validation partition')
    
    DIRECTORY.mkdir(exist_ok=False)
    source = ROOT/'runs/mass_training_v2'
    shutil.copytree(source/'code', DIRECTORY/'strategy')
    shutil.copyfile(__file__, DIRECTORY/'validation_runner.py')
    for sub in ('results', 'trades', 'curves'):
        (DIRECTORY/sub).mkdir()

    frozen = dict(
        created_at=now(), candidates=candidates, count=len(candidates),
        runner_sha256=file_hash(__file__),
        authorization='Evaluate top 7 robust breakout and momentum training winners on validation WITHOUT TUNING.',
        partition=partition, metadata=meta,
        test_data_accessed=False, test_data_authorized=False, no_tuning=True
    )
    json_write(DIRECTORY/'frozen_candidates.json', dict(manifest=frozen, manifest_hash=digest(frozen)))
    print(json.dumps(dict(prepared=True, count=len(candidates), validation_opened=False, test_opened=False)))


def archive():
    import sys
    sys.path.insert(0, str(DIRECTORY/'strategy'))
    import mass_research as engine
    return engine


def load_validation():
    manifest = read(DIRECTORY/'frozen_candidates.json')['manifest']
    path = Path(manifest['partition']['path'])
    tree = ast.parse((DIRECTORY/'strategy/mass_research.py').read_text(encoding='utf-8'))
    query = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')]
    import duckdb
    db = duckdb.connect()
    try:
        db.execute('SET threads=1'); db.execute("SET memory_limit='256MB'"); db.execute('SET enable_progress_bar=false')
        bars = canonical(db.execute(query[0], [str(path)]).fetch_df())
    finally:
        db.close()
    return bars


def evaluate():
    manifest = read(DIRECTORY/'frozen_candidates.json')['manifest']
    engine = archive()
    bars = load_validation()
    data = engine.arrays(bars)
    
    results = []
    for cand in manifest['candidates']:
        cid = cand['config_id']
        cfg = cand['parameters']
        features = engine.features(bars, cfg['lookback'])
        signal = engine.masked_signal(bars, cfg, features)
        signal[:96] = 0; signal[-16:] = 0
        res = engine.execute(data, signal, features['atr'], engine.execution_cfg(cfg))
        d = dict(data, regime=engine.entry_regimes(features['trend']))
        m = engine.summarize_execution(res, d)
        
        record = dict(
            config_id=cid, parameters=cfg,
            training_net=cand['net_pnl'], training_intrabar_dd=cand['intrabar_drawdown'],
            training_pf=cand.get('profit_factor', 0.0),
            val_net=m['net_pnl'], val_cash_dd=m['realized_drawdown'],
            val_closing_dd=m['max_drawdown'], val_intrabar_dd=m['intrabar_drawdown'],
            val_trades=m['trades'], val_pf=m['profit_factor'], val_consistency=m['consistency'],
            val_lock=m['lock'], val_funded_failed=m['funded_failed'],
            no_tuning=True, completed_at=now()
        )
        json_write(DIRECTORY/'results'/(cid + '.json'), record)
        results.append(record)
        print(f"{cid} | Val Net: ${m['net_pnl']:,.2f} | Val DD: ${m['intrabar_drawdown']:,.2f} | PF: {m['profit_factor']:.2f} | Trades: {m['trades']} | Lock: {m['lock']}")

    json_write(ROOT/'reports/top_robust_candidates_validation_summary.json', dict(results=results, count=len(results)))
    # Output markdown report
    lines = [
        '# Top Robust Breakout & Momentum Finalists: Validation Evaluation',
        '',
        'Evaluated the 7 top robust training finalists on 2024–2025 validation data with base costs and zero tuning.',
        '',
        '| # | Candidate ID | Family | Training Net | Training DD | Training PF | Val Net | Val Intrabar DD | Val PF | Val Trades | Lock |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|'
    ]
    results.sort(key=lambda r: (-float(r['val_net']), float(r['val_intrabar_dd'])))
    for rank, r in enumerate(results, 1):
        lines.append(
            f"| {rank} | `{r['config_id']}` | {r['parameters']['family']} | "
            f"${r['training_net']:,.2f} | ${r['training_intrabar_dd']:,.2f} | {r['training_pf']:.2f} | "
            f"**${r['val_net']:,.2f}** | ${r['val_intrabar_dd']:,.2f} | {r['val_pf']:.2f} | {r['val_trades']} | {r['val_lock']} |"
        )
    (ROOT/'reports/TOP_ROBUST_CANDIDATES_VALIDATION.md').write_text('\n'.join(lines), encoding='utf-8')
    print('Validation report written to reports/TOP_ROBUST_CANDIDATES_VALIDATION.md')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--evaluate', action='store_true')
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        if args.prepare:
            prepare()
        else:
            evaluate()

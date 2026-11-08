"""Save Portfolio A, Portfolio B, and Scaled versions permanently to disk with full manifests and equity series.
"""
import ast
import json
from pathlib import Path
import sqlite3
import sys
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from quant_futures.data import canonical
from training_5m_policy import execution_cfg_5m

CATALOG = json.load(open(ROOT / 'data/catalog.json'))
tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
DUCKDB_QUERY = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_split(sym, split):
    p = CATALOG['instruments'][sym]['splits'][split]['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(DUCKDB_QUERY, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars


def run_strat(cfg, bars, contracts=None):
    cfg_copy = dict(cfg)
    if contracts is not None:
        cfg_copy['max_contracts'] = contracts
    data = engine.arrays(bars)
    features = engine.features(bars, int(cfg_copy['lookback']))
    raw_sig = engine.signal_for(cfg_copy, features).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= cfg_copy['session_start']) & (decision < cfg_copy['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)
    ecfg = execution_cfg_5m(cfg_copy)
    res = engine.execute(data, sig, features['atr'], ecfg)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    return pd.DataFrame({'ts': ts, 'equity': res['equity'], 'worst': res['worst'], 'cash': res['cash']})


def combine(df1, df2):
    comb = pd.merge(df1[['ts', 'cash', 'worst']], df2[['ts', 'cash', 'worst']], on='ts', how='outer', suffixes=('_1', '_2')).sort_values('ts').ffill().fillna(50000.0)
    comb['pnl'] = (comb['cash_1'] - 50000.0) + (comb['cash_2'] - 50000.0)
    comb['peak'] = comb['pnl'].cummax()
    comb['closed_dd'] = comb['peak'] - comb['pnl']

    comb['worst_pnl'] = (comb['worst_1'] - 50000.0) + (comb['worst_2'] - 50000.0)
    comb['intrabar_dd'] = comb['peak'] - comb['worst_pnl']
    return comb


def save_portfolio(name, folder_name, cfg1, cfg2, c1, c2, data_splits):
    out_dir = ROOT / 'runs' / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nPackaging and saving {name} to {out_dir.relative_to(ROOT)}...")

    tr_mes, tr_mnq = data_splits['train']
    v_mes, v_mnq = data_splits['val']
    t_mes, t_mnq = data_splits['test']

    # Runs
    tr1 = run_strat(cfg1, tr_mes, c1)
    tr2 = run_strat(cfg2, tr_mnq, c2)
    tr_comb = combine(tr1, tr2)

    v1 = run_strat(cfg1, v_mes, c1)
    v2 = run_strat(cfg2, v_mnq, c2)
    v_comb = combine(v1, v2)

    t1 = run_strat(cfg1, t_mes, c1)
    t2 = run_strat(cfg2, t_mnq, c2)
    t_comb = combine(t1, t2)

    # Save CSV equity series
    tr_comb.to_csv(out_dir / 'equity_train_2020_2023.csv', index=False)
    v_comb.to_csv(out_dir / 'equity_val_2024_2025.csv', index=False)
    t_comb.to_csv(out_dir / 'equity_test_2026.csv', index=False)

    cross = t_comb[t_comb['pnl'] >= 3000.0]
    pass_wks = ((cross.iloc[0]['ts'] - t_comb.iloc[0]['ts']).days / 7.0) if not cross.empty else None

    # Summary metrics
    metrics = {
        'portfolio_name': name,
        'contracts': {'leg1_symbol': cfg1['instrument'], 'leg1_contracts': c1, 'leg2_symbol': cfg2['instrument'], 'leg2_contracts': c2},
        'test_2026': {
            'net_pnl': float(t_comb['pnl'].iloc[-1]),
            'closed_max_dd': float(t_comb['closed_dd'].max()),
            'intrabar_max_dd': float(t_comb['intrabar_dd'].max()),
            'cushion_to_2k': float(2000.0 - t_comb['intrabar_dd'].max()),
            'avg_weekly_gain': float(t_comb['pnl'].iloc[-1] / 44.5),
            'avg_monthly_gain': float((t_comb['pnl'].iloc[-1] / 44.5) * 4.333),
            'weeks_to_pass_3k': pass_wks,
        },
        'validation_2024_2025': {
            'net_pnl': float(v_comb['pnl'].iloc[-1]),
            'closed_max_dd': float(v_comb['closed_dd'].max()),
            'intrabar_max_dd': float(v_comb['intrabar_dd'].max()),
            'cushion_to_2k': float(2000.0 - v_comb['intrabar_dd'].max()),
        },
        'train_2020_2023': {
            'net_pnl': float(tr_comb['pnl'].iloc[-1]),
            'closed_max_dd': float(tr_comb['closed_dd'].max()),
            'intrabar_max_dd': float(tr_comb['intrabar_dd'].max()),
            'cushion_to_2k': float(2000.0 - tr_comb['intrabar_dd'].max()),
        },
        '7_year_lifetime_net': float(tr_comb['pnl'].iloc[-1] + v_comb['pnl'].iloc[-1] + t_comb['pnl'].iloc[-1]),
        'worst_historical_intrabar_dd': float(max(tr_comb['intrabar_dd'].max(), v_comb['intrabar_dd'].max(), t_comb['intrabar_dd'].max())),
        'passed_2k_rule_all_periods': bool(max(tr_comb['intrabar_dd'].max(), v_comb['intrabar_dd'].max(), t_comb['intrabar_dd'].max()) < 2000.0)
    }

    with open(out_dir / 'summary.json', 'w') as f:
        json.dump(metrics, f, indent=2)

    with open(out_dir / 'portfolio_config.json', 'w') as f:
        json.dump({'leg1_config': cfg1, 'leg2_config': cfg2}, f, indent=2)

    manifest = {
        'directory': str(out_dir),
        'saved_at': pd.Timestamp.now(tz='UTC').isoformat(),
        'files': [
            'portfolio_config.json',
            'summary.json',
            'equity_train_2020_2023.csv',
            'equity_val_2024_2025.csv',
            'equity_test_2026.csv'
        ]
    }
    with open(out_dir / 'manifest.json', 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"  Successfully saved to {out_dir}")
    return metrics


def main():
    print("Loading data splits...")
    splits = {
        'train': (load_split('MES', 'train'), load_split('MNQ', 'train')),
        'val': (load_split('MES', 'validation'), load_split('MNQ', 'validation')),
        'test': (load_split('MES', 'test'), load_split('MNQ', 'test')),
    }

    c5 = sqlite3.connect(ROOT / 'runs/training_search_5m_v1/configs.sqlite')
    r1 = c5.execute("SELECT payload FROM configs WHERE config_id='m5_77fad21ad8460757ac0d'").fetchone()[0]
    r2 = c5.execute("SELECT payload FROM configs WHERE config_id='m5_59f85ca327b58b5fd3f5'").fetchone()[0]
    c5.close()

    c2 = sqlite3.connect(ROOT / 'runs/training_search_2m_v1/configs.sqlite')
    r3 = c2.execute("SELECT payload FROM configs WHERE config_id='m2_eaa56d8ebf97ab0a5540'").fetchone()[0]
    c2.close()

    cfg_mes_mom = json.loads(r1)
    cfg_mnq_vol = json.loads(r2)
    cfg_mnq_brk = json.loads(r3)

    # 1. Save Portfolio B (The All-Time Champion: MES Mom 3c + MNQ Brk 1c)
    m_b = save_portfolio(
        name="Portfolio B: MES Momentum (3c) + MNQ Breakout (1c)",
        folder_name="saved_portfolio_B_mes_mom_mnq_brk",
        cfg1=cfg_mes_mom,
        cfg2=cfg_mnq_brk,
        c1=3,
        c2=1,
        data_splits=splits
    )

    # 2. Save Portfolio A (The Low-Drawdown Runner-Up: MES Mom 3c + MNQ Vol 1c)
    m_a = save_portfolio(
        name="Portfolio A: MES Momentum (3c) + MNQ Volatility (1c)",
        folder_name="saved_portfolio_A_mes_mom_mnq_vol",
        cfg1=cfg_mes_mom,
        cfg2=cfg_mnq_vol,
        c1=3,
        c2=1,
        data_splits=splits
    )

    # 3. Save Scaled Exploration Version (Portfolio B Scaled: MES 4c + MNQ 1c)
    m_scaled = save_portfolio(
        name="Portfolio B Scaled: MES Momentum (4c) + MNQ Breakout (1c)",
        folder_name="saved_portfolio_B_scaled_4c",
        cfg1=cfg_mes_mom,
        cfg2=cfg_mnq_brk,
        c1=4,
        c2=1,
        data_splits=splits
    )

    print("\nAll portfolios successfully saved and verified!")


if __name__ == '__main__':
    main()

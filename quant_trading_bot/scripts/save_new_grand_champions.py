"""Save Grand Champion Portfolio C and Robust Challenger Portfolio D permanently to disk.
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
from training_3m_policy import execution_cfg_3m

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


def run_strat(cfg, bars):
    data = engine.arrays(bars)
    features = engine.features(bars, int(cfg['lookback']))
    raw_sig = engine.signal_for(cfg, features).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= cfg['session_start']) & (decision < cfg['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)
    ecfg = execution_cfg_3m(cfg)
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


def save_portfolio(name, folder_name, cfg1, cfg2, data_splits):
    out_dir = ROOT / 'runs' / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nPackaging and saving {name} to {out_dir.relative_to(ROOT)}...")

    tr_mes, tr_mnq = data_splits['train']
    v_mes, v_mnq = data_splits['val']
    t_mes, t_mnq = data_splits['test']

    tr1 = run_strat(cfg1, tr_mes)
    tr2 = run_strat(cfg2, tr_mnq)
    tr_comb = combine(tr1, tr2)

    v1 = run_strat(cfg1, v_mes)
    v2 = run_strat(cfg2, v_mnq)
    v_comb = combine(v1, v2)

    t1 = run_strat(cfg1, t_mes)
    t2 = run_strat(cfg2, t_mnq)
    t_comb = combine(t1, t2)

    tr_comb.to_csv(out_dir / 'equity_train_2020_2023.csv', index=False)
    v_comb.to_csv(out_dir / 'equity_val_2024_2025.csv', index=False)
    t_comb.to_csv(out_dir / 'equity_test_2026.csv', index=False)

    cross = t_comb[t_comb['pnl'] >= 3000.0]
    pass_wks = ((cross.iloc[0]['ts'] - t_comb.iloc[0]['ts']).days / 7.0) if not cross.empty else None

    metrics = {
        'portfolio_name': name,
        'contracts': {'leg1_symbol': cfg1['instrument'], 'leg1_contracts': cfg1['max_contracts'], 'leg2_symbol': cfg2['instrument'], 'leg2_contracts': cfg2['max_contracts']},
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
        'files': ['portfolio_config.json', 'summary.json', 'equity_train_2020_2023.csv', 'equity_val_2024_2025.csv', 'equity_test_2026.csv']
    }
    with open(out_dir / 'manifest.json', 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"  Successfully saved to {out_dir}")
    return metrics


def main():
    splits = {
        'train': (load_split('MES', 'train'), load_split('MNQ', 'train')),
        'val': (load_split('MES', 'validation'), load_split('MNQ', 'validation')),
        'test': (load_split('MES', 'test'), load_split('MNQ', 'test')),
    }

    saved_b = json.load(open(ROOT / 'runs/saved_portfolio_B_mes_mom_mnq_brk/portfolio_config.json'))
    champ_mes = saved_b['leg1_config']

    c3 = sqlite3.connect(ROOT / 'runs/training_search_3m_champion_v1/configs.sqlite')
    p1 = c3.execute("SELECT payload FROM configs WHERE config_id='m3_860fb8d2ce89f6436d28'").fetchone()[0]
    p2 = c3.execute("SELECT payload FROM configs WHERE config_id='m3_e168699bdcff4720a66c'").fetchone()[0]
    c3.close()

    new_mnq_hybrid = json.loads(p1)
    new_mnq_breakout = json.loads(p2)

    # 1. Save Grand Champion (Portfolio C)
    save_portfolio(
        name="Portfolio C (Grand Champion): MES Momentum (3c) + MNQ Hybrid m3_860fb (2c, 5.0R)",
        folder_name="saved_portfolio_C_grand_champion_mes_mom_mnq_hyb",
        cfg1=champ_mes,
        cfg2=new_mnq_hybrid,
        data_splits=splits
    )

    # 2. Save Robust Challenger (Portfolio D)
    save_portfolio(
        name="Portfolio D (Robust Challenger): MES Momentum (3c) + MNQ Breakout m3_e1686 (2c, 2.25R)",
        folder_name="saved_portfolio_D_robust_challenger_mes_mom_mnq_brk",
        cfg1=champ_mes,
        cfg2=new_mnq_breakout,
        data_splits=splits
    )

    print("\nAll new champions permanently saved to disk!")


if __name__ == '__main__':
    main()

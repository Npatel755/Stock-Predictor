"""Adversarial Stress Lab for Portfolio E and Ensemble Beta.
Tests fragility against 1.5x and 2.0x commissions, slippage, and adverse fill shocks.
"""
import ast
import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from mass_metrics import summarize_execution
from quant_futures.data import canonical
from training_5m_v2_policy import execution_cfg_5m_v2

RUN_DIR = ROOT / 'runs/overnight_institutional_research'
RUN_DIR.mkdir(parents=True, exist_ok=True)

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


def run_strat_stressed(cfg, bars, fee_multiplier=1.0, extra_slip_ticks=0.0):
    data = engine.arrays(bars)
    features = engine.features(bars, int(cfg['lookback']))
    raw_sig = engine.signal_for(cfg, features).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= cfg['session_start']) & (decision < cfg['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)

    ecfg = execution_cfg_5m_v2(cfg)
    ecfg['commission_per_side'] = ecfg['commission_per_side'] * fee_multiplier
    ecfg['slippage_ticks'] = ecfg['slippage_ticks'] + extra_slip_ticks

    res = engine.execute(data, sig, features['atr'], ecfg)
    sm = summarize_execution(res, data)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})
    return df, sm


def eval_portfolio_e_stress(fee_mult, slip_extra):
    saved_e = json.load(open(ROOT / 'runs/saved_portfolio_E_undisputed_champion_mes_mom_mnq_brk/portfolio_config.json'))
    mes_cfg = saved_e['leg1_config']
    mnq_cfg = saved_e['leg2_config']

    metrics = {}
    for s in ['train', 'validation', 'test']:
        b_mes = load_split('MES', s)
        b_mnq = load_split('MNQ', s)
        df1, sm1 = run_strat_stressed(mes_cfg, b_mes, fee_mult, slip_extra)
        df2, sm2 = run_strat_stressed(mnq_cfg, b_mnq, fee_mult, slip_extra)

        comb = pd.merge(df1[['ts', 'cash', 'worst']], df2[['ts', 'cash', 'worst']], on='ts', how='outer', suffixes=('_mes', '_mnq')).sort_values('ts').ffill().fillna(50000.0)
        comb['pnl'] = (comb['cash_mes'] - 50000.0) + (comb['cash_mnq'] - 50000.0)
        comb['worst_pnl'] = (comb['worst_mes'] - 50000.0) + (comb['worst_mnq'] - 50000.0)
        comb['peak'] = comb['pnl'].cummax()
        comb['intrabar_dd'] = comb['peak'] - comb['worst_pnl']

        metrics[s] = {
            'net': float(comb['pnl'].iloc[-1]),
            'dd': float(comb['intrabar_dd'].max())
        }

    return metrics


def main():
    print("=" * 85, flush=True)
    print("ADVERSARIAL STRESS LAB: TESTING PORTFOLIO E UNDER HARSH MARKET CONDITIONS")
    print("=" * 85, flush=True)

    scenarios = [
        ("Baseline (Normal Costs: $0.50 fee, 1-tick slip)", 1.0, 0.0),
        ("Stress Level 1 (1.5x Fees: $0.75 fee, 1-tick slip)", 1.5, 0.0),
        ("Stress Level 2 (2.0x Fees: $1.00 fee, 1-tick slip)", 2.0, 0.0),
        ("Stress Level 3 (Adverse Slippage: 2-tick slippage + $0.75 fee)", 1.5, 1.0),
        ("Stress Level 4 (Severe Friction: 2-tick slippage + $1.00 fee)", 2.0, 1.0)
    ]

    records = []
    for label, fm, se in scenarios:
        m = eval_portfolio_e_stress(fm, se)
        tot_net = m['train']['net'] + m['validation']['net'] + m['test']['net']
        worst_dd = max(m['train']['dd'], m['validation']['dd'], m['test']['dd'])
        passes = bool(worst_dd < 2000.0)

        print(f"\n>>> {label} <<<")
        print(f"  2026 Test Net:     +${m['test']['net']:,.2f}  |  Test DD: ${m['test']['dd']:,.2f}")
        print(f"  Validation Net:    +${m['validation']['net']:,.2f}  |  Val DD:  ${m['validation']['dd']:,.2f}")
        print(f"  Training Net:      +${m['train']['net']:,.2f} |  Train DD:${m['train']['dd']:,.2f}")
        print(f"  7-Year Net:        +${tot_net:,.2f} |  WORST 7-YR DD: ${worst_dd:,.2f} (Passes <$2k: {passes})")

        records.append({
            'scenario': label,
            'fee_multiplier': fm,
            'extra_slip_ticks': se,
            'test_net': m['test']['net'],
            'test_dd': m['test']['dd'],
            'val_net': m['validation']['net'],
            'val_dd': m['validation']['dd'],
            'train_net': m['train']['net'],
            'train_dd': m['train']['dd'],
            'lifetime_net': tot_net,
            'worst_lifetime_dd': worst_dd,
            'passes_2k_rule': passes
        })

    json.dump(records, open(RUN_DIR / 'portfolio_e_adversarial_stress_results.json', 'w'), indent=2)
    print("\nSaved adversarial stress results to portfolio_e_adversarial_stress_results.json successfully!")


if __name__ == '__main__':
    main()

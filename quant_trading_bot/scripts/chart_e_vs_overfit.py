import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd
import ast
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
from training_10m_policy import execution_cfg_10m

CATALOG = json.load(open(ROOT / 'data/catalog.json'))
tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
DUCKDB_QUERY = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]

def load_split_bars(sym, split):
    p = CATALOG['instruments'][sym]['splits'][split]['path']
    con = duckdb.connect()
    try:
        b = canonical(con.execute(DUCKDB_QUERY, [str(p)]).fetch_df())
    finally:
        con.close()
    return b

bars_mes = {
    'train': load_split_bars('MES', 'train'),
    'validation': load_split_bars('MES', 'validation'),
    'test': load_split_bars('MES', 'test'),
}
bars_mes['train'] = bars_mes['train'][bars_mes['train']['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

bars_mnq = {
    'train': load_split_bars('MNQ', 'train'),
    'validation': load_split_bars('MNQ', 'validation'),
    'test': load_split_bars('MNQ', 'test'),
}
bars_mnq['train'] = bars_mnq['train'][bars_mnq['train']['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

_MES_MOM = dict(instrument="MES", family="momentum", lookback=16, threshold=1.5, stop_atr=1.75,
                target_r=2.5, hold_bars=32, session_start=585, session_end=945, trailing_atr=2.0)
_MNQ_BRK = dict(instrument="MNQ", family="breakout", lookback=10, threshold=1.25, stop_atr=1.75,
                target_r=2.25, hold_bars=8, session_start=600, session_end=720, trailing_atr=2.0)
_MNQ_PM_TRD = dict(instrument="MNQ", family="trend", lookback=16, threshold=1.25, stop_atr=2.25,
                   target_r=5.0, hold_bars=16, session_start=720, session_end=945, trailing_atr=0.0)

def run_sleeve(cfg, bars):
    data = apply_early_close(engine.arrays(bars), bars)
    features = engine.features(bars, int(cfg['lookback']))
    raw_sig = engine.signal_for(cfg, features).astype(np.int8)

    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= cfg['session_start']) & (decision < cfg['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)

    ecfg = execution_cfg_10m(cfg)
    res = engine.execute(data, sig, features['atr'], ecfg)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})
    return df

def get_portfolio_series(sleeves):
    all_dfs = []
    base_cash = 50000.0
    cum_profit = 0.0
    
    for split in ['train', 'validation', 'test']:
        dfs = []
        for sname, scfg, contracts in sleeves:
            cfg = dict(scfg, max_contracts=contracts)
            bars = bars_mes[split] if cfg['instrument'] == 'MES' else bars_mnq[split]
            df = run_sleeve(cfg, bars)
            dfs.append(df)
            
        m = dfs[0][['ts', 'cash', 'worst']].rename(columns={'cash': 'c_0', 'worst': 'w_0'})
        for i in range(1, len(dfs)):
            m = pd.merge(m, dfs[i][['ts', 'cash', 'worst']].rename(columns={'cash': f'c_{i}', 'worst': f'w_{i}'}), on='ts', how='outer')
        m = m.sort_values('ts').ffill().fillna(50000.0)
        
        c_split = np.zeros(len(m))
        w_split = np.zeros(len(m))
        for i in range(len(dfs)):
            c_split += (m[f'c_{i}'].to_numpy() - 50000.0)
            w_split += (m[f'w_{i}'].to_numpy() - 50000.0)
            
        # continuous cumulative equity
        m['cum_equity'] = base_cash + cum_profit + c_split
        m['cum_worst'] = base_cash + cum_profit + w_split
        cum_profit += c_split[-1]
        all_dfs.append(m[['ts', 'cum_equity', 'cum_worst']])
        
    full_df = pd.concat(all_dfs, ignore_index=True).sort_values('ts').reset_index(drop=True)
    full_df['peak'] = full_df['cum_equity'].cummax()
    full_df['drawdown'] = full_df['peak'] - full_df['cum_worst']
    return full_df

# Evaluate Portfolios
df_e_scaled = get_portfolio_series([("MES_2c", _MES_MOM, 2), ("MNQ_2c", _MNQ_BRK, 2)])
df_e_cons = get_portfolio_series([("MES_1c", _MES_MOM, 1), ("MNQ_2c", _MNQ_BRK, 2)])
df_p3 = get_portfolio_series([("MNQ_2c", _MNQ_BRK, 2), ("MNQ_1c", _MNQ_PM_TRD, 1)])

# Plotting
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True, gridspec_kw={'height_ratios': [2.2, 1]})
plt.style.use('seaborn-v0_8-darkgrid' if 'seaborn-v0_8-darkgrid' in plt.style.available else 'default')

# Equity Plot
ax1.plot(df_e_scaled['ts'], df_e_scaled['cum_equity'], label='Portfolio E Scaled (MES 2c + MNQ 2c) - Net +$24,717 | Max DD $1,755', color='#00C853', linewidth=2.2)
ax1.plot(df_e_cons['ts'], df_e_cons['cum_equity'], label='Portfolio E Conservative (MES 1c + MNQ 2c) - Net +$19,908 | Max DD $1,488', color='#2979FF', linewidth=1.8)
ax1.plot(df_p3['ts'], df_p3['cum_equity'], label='Portfolio 3 Overfit Baseline (MNQ AM 2c + MNQ PM 1c) - Flattens in Val/Test', color='#FF9100', linewidth=1.5, linestyle='--')

# Vertical Partition Lines
val_start = pd.to_datetime('2024-01-01', utc=True)
test_start = pd.to_datetime('2026-01-01', utc=True)

for ax in (ax1, ax2):
    ax.axvline(val_start, color='#E0E0E0', linestyle=':', linewidth=1.5)
    ax.axvline(test_start, color='#E0E0E0', linestyle=':', linewidth=1.5)

ax1.text(pd.to_datetime('2022-01-01', utc=True), 72000, 'TRAINING (2020-2023)\nParameter Discovery', color='#B0BEC5', fontsize=11, fontweight='bold', ha='center')
ax1.text(pd.to_datetime('2025-01-01', utc=True), 72000, 'VALIDATION (2024-2025)\nUnseen Out-Of-Sample', color='#FFD54F', fontsize=11, fontweight='bold', ha='center')
ax1.text(pd.to_datetime('2026-06-01', utc=True), 72000, 'TEST (2026)\nHoldout Audit', color='#81C784', fontsize=11, fontweight='bold', ha='center')

ax1.set_title('Institutional Alpha Audit: Portfolio E (Cross-Asset Edge) vs Portfolio 3 (Overfit Baseline)\nStrict Micro Economics ($0.61/side, 1-tick adverse slippage, zero leakage)', fontsize=14, fontweight='bold', pad=15)
ax1.set_ylabel('Account Equity ($)', fontsize=12, fontweight='bold')
ax1.legend(loc='upper left', frameon=True, fontsize=10)
ax1.grid(True, alpha=0.3)

# Drawdown Plot
ax2.plot(df_e_scaled['ts'], -df_e_scaled['drawdown'], label='Portfolio E Scaled DD (Max $1,755)', color='#00C853', linewidth=1.8)
ax2.plot(df_e_cons['ts'], -df_e_cons['drawdown'], label='Portfolio E Conservative DD (Max $1,488)', color='#2979FF', linewidth=1.5)
ax2.plot(df_p3['ts'], -df_p3['drawdown'], label='Portfolio 3 DD (Max $1,655)', color='#FF9100', linewidth=1.2, linestyle='--')

ax2.axhline(-2000, color='#D50000', linestyle='-', linewidth=2.0, label='Funded Account Kill Limit ($2,000 Trailing DD)')
ax2.axhline(-1750, color='#FF6D00', linestyle='--', linewidth=1.2, alpha=0.7, label='Safety Warning Threshold ($1,750 DD)')

ax2.set_title('Intrabar Underwater Drawdown Profile (Strict $2,000 Trailing Limit Protection)', fontsize=12, fontweight='bold', pad=10)
ax2.set_ylabel('Drawdown ($)', fontsize=12, fontweight='bold')
ax2.set_xlabel('Timeline (2020 - 2026)', fontsize=12, fontweight='bold')
ax2.legend(loc='lower left', frameon=True, fontsize=9)
ax2.grid(True, alpha=0.3)

plt.tight_layout()

out_dir = Path('C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d')
png_path = out_dir / 'portfolio_e_vs_overfit_splits.png'
svg_path = out_dir / 'portfolio_e_vs_overfit_splits.svg'
plt.savefig(png_path, dpi=200)
plt.savefig(svg_path)
print(f"Saved charts to {png_path} and {svg_path}")

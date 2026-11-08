import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd
import ast
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

import mass_research as engine
from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close

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

mes_train = load_split_bars('MES', 'train')
mes_train = mes_train[mes_train['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
mes_val = load_split_bars('MES', 'validation')
bars_mes_6y = pd.concat([mes_train, mes_val], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

mnq_train = load_split_bars('MNQ', 'train')
mnq_train = mnq_train[mnq_train['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
mnq_val = load_split_bars('MNQ', 'validation')
bars_mnq_6y = pd.concat([mnq_train, mnq_val], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

def run_sleeve(cfg, bars, fee=0.61):
    data = apply_early_close(engine.arrays(bars), bars)
    features = engine.features(bars, int(cfg['lookback']))
    sig = engine.masked_signal(bars, cfg, features)
    ecfg = engine.execution_cfg(cfg)
    ecfg['commission_per_side'] = fee
    res = engine.execute(data, sig, features['atr'], ecfg)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    pnl = res['cash'] - ecfg['initial_balance']
    worst_pnl = res['worst'] - ecfg['initial_balance']
    return pd.DataFrame({'ts': ts, 'pnl': pnl, 'worst_pnl': worst_pnl})

# Sleeves
s_mes_mom = dict(instrument="MES", family="momentum", lookback=6, threshold=2.0, stop_atr=1.5,
                 target_r=2.25, hold_bars=20, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)
s_mes_trd = dict(instrument="MES", family="trend", lookback=6, threshold=1.0, stop_atr=1.5,
                 target_r=1.75, hold_bars=6, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)
s_mnq_trd = dict(instrument="MNQ", family="trend", lookback=6, threshold=1.0, stop_atr=1.75,
                 target_r=2.25, hold_bars=6, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0)
s_mnq_brk = dict(instrument="MNQ", family="breakout", lookback=20, threshold=1.25, stop_atr=1.5,
                 target_r=2.5, hold_bars=8, session_start=600, session_end=720, max_contracts=1, trailing_atr=0.0)

# Old baseline (Portfolio E 1c baseline)
s_mes_old = dict(instrument="MES", family="momentum", lookback=16, threshold=1.5, stop_atr=1.75,
                 target_r=2.5, hold_bars=32, session_start=585, session_end=945, max_contracts=1, trailing_atr=2.0)
s_mnq_old = dict(instrument="MNQ", family="breakout", lookback=10, threshold=1.25, stop_atr=1.75,
                 target_r=2.25, hold_bars=8, session_start=600, session_end=720, max_contracts=1, trailing_atr=2.0)

df_mes_mom = run_sleeve(s_mes_mom, bars_mes_6y)
df_mes_trd = run_sleeve(s_mes_trd, bars_mes_6y)
df_mnq_trd = run_sleeve(s_mnq_trd, bars_mnq_6y)
df_mnq_brk = run_sleeve(s_mnq_brk, bars_mnq_6y)
df_mes_old = run_sleeve(s_mes_old, bars_mes_6y)
df_mnq_old = run_sleeve(s_mnq_old, bars_mnq_6y)

def combine(dfs):
    m = dfs[0][['ts', 'pnl', 'worst_pnl']].rename(columns={'pnl': 'pnl_0', 'worst_pnl': 'w_0'})
    for i in range(1, len(dfs)):
        df_i = dfs[i][['ts', 'pnl', 'worst_pnl']].rename(columns={'pnl': f'pnl_{i}', 'worst_pnl': f'w_{i}'})
        m = pd.merge(m, df_i, on='ts', how='outer')
    m = m.sort_values('ts').ffill().fillna(0.0)
    m['pnl_comb'] = sum(m[f'pnl_{i}'] for i in range(len(dfs)))
    peak_pnl = m['pnl_comb'].cummax()
    m['open_draw'] = sum((m[f'pnl_{i}'] - m[f'w_{i}']) for i in range(len(dfs)))
    m['intrabar_dd'] = (peak_pnl - (m['pnl_comb'] - m['open_draw']))
    return m

c_duo = combine([df_mes_mom, df_mnq_trd])
c_tri = combine([df_mes_trd, df_mnq_brk, df_mnq_trd])
c_pure = combine([df_mnq_trd])
c_old = combine([df_mes_old, df_mnq_old])

# Plotting
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True, gridspec_kw={'height_ratios': [2.2, 1.2]})

ax1.plot(c_tri['ts'], c_tri['pnl_comb'], label='Portfolio Tri-Alpha (MES Trd + MNQ Brk + MNQ Trd) [+$16,925]', color='#10b981', lw=2.2)
ax1.plot(c_duo['ts'], c_duo['pnl_comb'], label='Portfolio Duo-Momentum (MES Mom + MNQ Trd) [+$10,168]', color='#3b82f6', lw=2.0)
ax1.plot(c_pure['ts'], c_pure['pnl_comb'], label='Pure Single Sleeve: MNQ Trend 1c [+$7,700]', color='#8b5cf6', lw=1.8)
ax1.plot(c_old['ts'], c_old['pnl_comb'], label='Previous 1c Baseline (Portfolio E 1c) [+$5,584]', color='#ef4444', lw=1.5, ls='--')

# Vertical split line between Train and Validation
val_start = pd.Timestamp('2024-01-01', tz='UTC')
ax1.axvline(val_start, color='#64748b', ls=':', lw=1.8, label='Train / Validation Cutoff (2024-01-01)')
ax2.axvline(val_start, color='#64748b', ls=':', lw=1.8)

ax1.set_title('Robust In-Sample Formed Futures Strategies vs Out-of-Sample Validation (2020-2025)\nStrict Micro Economics ($0.61 Commission, 1-Tick Adverse Slippage, 1-Tick Spread, Early Close Flattening)', fontsize=13, fontweight='bold', pad=12)
ax1.set_ylabel('Cumulative Net P&L ($)', fontsize=11, fontweight='bold')
ax1.grid(True, alpha=0.25, ls='--')
ax1.legend(loc='upper left', frameon=True, framealpha=0.9)

# Drawdown chart
ax2.plot(c_tri['ts'], -c_tri['intrabar_dd'], label='Tri-Alpha Max DD: -$1,370', color='#10b981', lw=1.5)
ax2.plot(c_duo['ts'], -c_duo['intrabar_dd'], label='Duo-Momentum Max DD: -$962', color='#3b82f6', lw=1.5)
ax2.plot(c_pure['ts'], -c_pure['intrabar_dd'], label='Pure MNQ Trend Max DD: -$632', color='#8b5cf6', lw=1.5)
ax2.plot(c_old['ts'], -c_old['intrabar_dd'], label='Old Baseline Max DD: -$943', color='#ef4444', lw=1.2, ls='--')

ax2.axhline(-2000, color='#dc2626', lw=2.0, ls='-', label='Funded Account Breach Limit (-$2,000)')
ax2.set_ylabel('Intraday Drawdown ($)', fontsize=11, fontweight='bold')
ax2.set_xlabel('Date (America/New_York)', fontsize=11, fontweight='bold')
ax2.grid(True, alpha=0.25, ls='--')
ax2.legend(loc='lower left', frameon=True, framealpha=0.9, ncol=2)
ax2.set_ylim(-2200, 100)

plt.tight_layout()
out_dir = Path("C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d")
out_png = out_dir / "robust_champion_portfolios_vs_validation.png"
out_svg = out_dir / "robust_champion_portfolios_vs_validation.svg"
plt.savefig(out_png, dpi=300)
plt.savefig(out_svg)
print(f"Saved charts to:\n{out_png}\n{out_svg}")

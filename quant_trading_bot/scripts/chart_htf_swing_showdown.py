import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd
import ast
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.htf_engine import load_resampled_bars, generalized_arrays, compute_htf_features

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

print("Loading data for showdown charts...")
# 15m old baseline
mes_train_15m = load_split_bars('MES', 'train')
mes_train_15m = mes_train_15m[mes_train_15m['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
mes_val_15m = load_split_bars('MES', 'validation')
bars_mes_15m = pd.concat([mes_train_15m, mes_val_15m], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

mnq_train_15m = load_split_bars('MNQ', 'train')
mnq_train_15m = mnq_train_15m[mnq_train_15m['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
mnq_val_15m = load_split_bars('MNQ', 'validation')
bars_mnq_15m = pd.concat([mnq_train_15m, mnq_val_15m], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

# HTF data
mnq_train_60m = load_resampled_bars('MNQ', 'train', '60 minutes')
mnq_val_60m = load_resampled_bars('MNQ', 'validation', '60 minutes', start_date=None)
bars_mnq_60m = pd.concat([mnq_train_60m, mnq_val_60m], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

mes_train_30m = load_resampled_bars('MES', 'train', '30 minutes')
mes_val_30m = load_resampled_bars('MES', 'validation', '30 minutes', start_date=None)
bars_mes_30m = pd.concat([mes_train_30m, mes_val_30m], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

mnq_train_30m = load_resampled_bars('MNQ', 'train', '30 minutes')
mnq_val_30m = load_resampled_bars('MNQ', 'validation', '30 minutes', start_date=None)
bars_mnq_30m = pd.concat([mnq_train_30m, mnq_val_30m], ignore_index=True).sort_values('timestamp_utc').reset_index(drop=True)

# Simulate Old 15m baseline
s_mes_old = dict(instrument="MES", family="momentum", lookback=16, threshold=1.5, stop_atr=1.75,
                 target_r=2.5, hold_bars=32, session_start=585, session_end=945, max_contracts=1, trailing_atr=2.0)
s_mnq_old = dict(instrument="MNQ", family="breakout", lookback=10, threshold=1.25, stop_atr=1.75,
                 target_r=2.25, hold_bars=8, session_start=600, session_end=720, max_contracts=1, trailing_atr=2.0)

import mass_research as engine
def run_15m_sleeve(cfg, bars):
    data = apply_early_close(engine.arrays(bars), bars)
    features = engine.features(bars, int(cfg['lookback']))
    sig = engine.masked_signal(bars, cfg, features)
    ecfg = engine.execution_cfg(cfg)
    ecfg['commission_per_side'] = 0.61
    res = engine.execute(data, sig, features['atr'], ecfg)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    pnl = res['cash'] - ecfg['initial_balance']
    worst = res['worst'] - ecfg['initial_balance']
    return pd.DataFrame({'ts': ts, 'pnl': pnl, 'worst': worst})

df_mes_old = run_15m_sleeve(s_mes_old, bars_mes_15m)
df_mnq_old = run_15m_sleeve(s_mnq_old, bars_mnq_15m)

# Simulate HTF sleeves
data_mnq_60m = apply_early_close(generalized_arrays(bars_mnq_60m), bars_mnq_60m)
data_mes_30m = apply_early_close(generalized_arrays(bars_mes_30m), bars_mes_30m)
data_mnq_30m = apply_early_close(generalized_arrays(bars_mnq_30m), bars_mnq_30m)

feat_mnq_60m = compute_htf_features(bars_mnq_60m, 12, 60)
raw_sig_60m = np.where(np.abs(feat_mnq_60m['trend']) >= 0.75, np.sign(feat_mnq_60m['trend']), 0.0)
local_60m = bars_mnq_60m.timestamp_utc.dt.tz_convert('America/New_York')
dec_60m = (local_60m.dt.hour * 60 + local_60m.dt.minute + 60).to_numpy()
sig_60m = np.where((dec_60m >= 600) & (dec_60m < 720) & (local_60m.dt.weekday.to_numpy() < 5), raw_sig_60m, 0).astype(np.int8)
ecfg_60m = dict(initial_balance=50000.0, tick=0.25, multiplier=2.0, commission_per_side=0.61, exchange_per_side=0.0, regulatory_per_side=0.0, spread_ticks=1, slippage_ticks=1, impact_ticks=0.0, factor=1, maxqty=1, risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, stop_atr=1.25, target_ratio=4.0, hold_bars=8, entry_start=570, entry_end=915, flat_minute=955, max_gap_minutes=120, participation=0.01, trailing_atr=0.0, max_consecutive_losses=5, funded_drawdown=2000.0, funded_cap=50100.0)
res_60m = me.execute(data_mnq_60m, sig_60m, feat_mnq_60m['atr'], ecfg_60m)
df_mnq_60m = pd.DataFrame({'ts': pd.to_datetime(data_mnq_60m['timestamp'], unit='ns', utc=True), 'pnl': res_60m['cash'] - 50000.0, 'worst': res_60m['worst'] - 50000.0})

feat_mes_30m = compute_htf_features(bars_mes_30m, 8, 30)
raw_sig_mes30 = np.where(np.abs(feat_mes_30m['trend']) >= 1.0, np.sign(feat_mes_30m['trend']), 0.0)
local_mes30 = bars_mes_30m.timestamp_utc.dt.tz_convert('America/New_York')
dec_mes30 = (local_mes30.dt.hour * 60 + local_mes30.dt.minute + 30).to_numpy()
sig_mes30 = np.where((dec_mes30 >= 585) & (dec_mes30 < 945) & (local_mes30.dt.weekday.to_numpy() < 5), raw_sig_mes30, 0).astype(np.int8)
ecfg_mes30 = dict(initial_balance=50000.0, tick=0.25, multiplier=5.0, commission_per_side=0.61, exchange_per_side=0.0, regulatory_per_side=0.0, spread_ticks=1, slippage_ticks=1, impact_ticks=0.0, factor=1, maxqty=1, risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, stop_atr=1.25, target_ratio=2.5, hold_bars=12, entry_start=570, entry_end=915, flat_minute=955, max_gap_minutes=60, participation=0.01, trailing_atr=0.0, max_consecutive_losses=5, funded_drawdown=2000.0, funded_cap=50100.0)
res_mes30 = me.execute(data_mes_30m, sig_mes30, feat_mes_30m['atr'], ecfg_mes30)
df_mes_30m = pd.DataFrame({'ts': pd.to_datetime(data_mes_30m['timestamp'], unit='ns', utc=True), 'pnl': res_mes30['cash'] - 50000.0, 'worst': res_mes30['worst'] - 50000.0})

feat_mnq_30m = compute_htf_features(bars_mnq_30m, 16, 30)
bh = feat_mnq_30m['breakout_high'] + 2.0 * feat_mnq_30m['atr']
bl = feat_mnq_30m['breakout_low'] - 2.0 * feat_mnq_30m['atr']
raw_sig_mnq30 = np.where(feat_mnq_30m['close'] > bh, 1.0, np.where(feat_mnq_30m['close'] < bl, -1.0, 0.0))
local_mnq30 = bars_mnq_30m.timestamp_utc.dt.tz_convert('America/New_York')
dec_mnq30 = (local_mnq30.dt.hour * 60 + local_mnq30.dt.minute + 30).to_numpy()
sig_mnq30 = np.where((dec_mnq30 >= 600) & (dec_mnq30 < 720) & (local_mnq30.dt.weekday.to_numpy() < 5), raw_sig_mnq30, 0).astype(np.int8)
ecfg_mnq30 = dict(initial_balance=50000.0, tick=0.25, multiplier=2.0, commission_per_side=0.61, exchange_per_side=0.0, regulatory_per_side=0.0, spread_ticks=1, slippage_ticks=1, impact_ticks=0.0, factor=1, maxqty=1, risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, stop_atr=1.5, target_ratio=2.5, hold_bars=12, entry_start=570, entry_end=915, flat_minute=955, max_gap_minutes=60, participation=0.01, trailing_atr=0.0, max_consecutive_losses=5, funded_drawdown=2000.0, funded_cap=50100.0)
res_mnq30 = me.execute(data_mnq_30m, sig_mnq30, feat_mnq_30m['atr'], ecfg_mnq30)
df_mnq_30m = pd.DataFrame({'ts': pd.to_datetime(data_mnq_30m['timestamp'], unit='ns', utc=True), 'pnl': res_mnq30['cash'] - 50000.0, 'worst': res_mnq30['worst'] - 50000.0})

def combine(dfs):
    m = dfs[0].rename(columns={'pnl': 'p0', 'worst': 'w0'})
    for i in range(1, len(dfs)):
        m = pd.merge(m, dfs[i].rename(columns={'pnl': f'p{i}', 'worst': f'w{i}'}), on='ts', how='outer')
    m = m.sort_values('ts').ffill().fillna(0.0)
    m['pnl_comb'] = sum(m[f'p{i}'] for i in range(len(dfs)))
    peak = m['pnl_comb'].cummax()
    open_draw = sum((m[f'p{i}'] - m[f'w{i}']) for i in range(len(dfs)))
    m['intrabar_dd'] = peak - (m['pnl_comb'] - open_draw)
    return m

c_old = combine([df_mes_old, df_mnq_old])
c_duo_htf = combine([df_mnq_60m, df_mes_30m])
c_tri_htf = combine([df_mnq_30m, df_mnq_60m, df_mes_30m])
c_pure_60m = combine([df_mnq_60m])

# Plotting
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True, gridspec_kw={'height_ratios': [2.2, 1.2]})

ax1.plot(c_tri_htf['ts'], c_tri_htf['pnl_comb'], label='Swing Tri-Core (30m Brk + 60m Trd + 30m MES) [+$17,526 | Exp: $34.77/tr]', color='#059669', lw=2.4)
ax1.plot(c_duo_htf['ts'], c_duo_htf['pnl_comb'], label='Swing Duo-Trend (MNQ 60m Trd + MES 30m Trd) [+$11,540 | Exp: $29.74/tr]', color='#2563eb', lw=2.2)
ax1.plot(c_pure_60m['ts'], c_pure_60m['pnl_comb'], label='Pure 1-Hour Sleeve: MNQ 60m Trend 1c [+$7,025 | Exp: $40.14/tr]', color='#9333ea', lw=2.0)
ax1.plot(c_old['ts'], c_old['pnl_comb'], label='Old 15m Baseline (Portfolio E 1c) [+$5,584 | Exp: $11.83/tr]', color='#ef4444', lw=1.5, ls='--')

val_start = pd.Timestamp('2024-01-01', tz='UTC')
ax1.axvline(val_start, color='#64748b', ls=':', lw=1.8, label='Train / Validation Cutoff (2024-01-01)')
ax2.axvline(val_start, color='#64748b', ls=':', lw=1.8)

ax1.set_title('Higher-Timeframe Swing & Anti-Scalping Models (30m & 60m Bars) vs Old 15m Scalping Baseline\nHigh-Expectancy Exits ($30-$40+/trade), Negligible Friction, Zero Validation Tuning (2020-2025)', fontsize=13, fontweight='bold', pad=12)
ax1.set_ylabel('Cumulative Net P&L ($)', fontsize=11, fontweight='bold')
ax1.grid(True, alpha=0.25, ls='--')
ax1.legend(loc='upper left', frameon=True, framealpha=0.9)

# Drawdown chart
ax2.plot(c_tri_htf['ts'], -c_tri_htf['intrabar_dd'], label='Tri-Core Max DD: -$1,465 (Cushion: +$535)', color='#059669', lw=1.5)
ax2.plot(c_duo_htf['ts'], -c_duo_htf['intrabar_dd'], label='Duo-Trend Max DD: -$1,093 (Cushion: +$907)', color='#2563eb', lw=1.5)
ax2.plot(c_pure_60m['ts'], -c_pure_60m['intrabar_dd'], label='Pure 60m Max DD: -$775 (Cushion: +$1,225)', color='#9333ea', lw=1.5)
ax2.plot(c_old['ts'], -c_old['intrabar_dd'], label='Old Baseline Max DD: -$943', color='#ef4444', lw=1.2, ls='--')

ax2.axhline(-2000, color='#dc2626', lw=2.0, ls='-', label='Funded Account Breach Limit (-$2,000)')
ax2.set_ylabel('Intraday Drawdown ($)', fontsize=11, fontweight='bold')
ax2.set_xlabel('Date (America/New_York)', fontsize=11, fontweight='bold')
ax2.grid(True, alpha=0.25, ls='--')
ax2.legend(loc='lower left', frameon=True, framealpha=0.9, ncol=2)
ax2.set_ylim(-2200, 100)

plt.tight_layout()
out_dir = Path("C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d")
out_png = out_dir / "htf_swing_anti_scalping_showdown.png"
out_svg = out_dir / "htf_swing_anti_scalping_showdown.svg"
plt.savefig(out_png, dpi=300)
plt.savefig(out_svg)
print(f"Saved charts to:\n{out_png}\n{out_svg}")

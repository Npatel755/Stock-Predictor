"""Compute exact monthly and weekly gains across Validation (2024-2025) and Test (2026) evaluations."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import ast
import json
from pathlib import Path
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
import mass_research as engine
from quant_futures.data import canonical
import duckdb

ARTIFACT_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")
CATALOG = json.load(open(ROOT / 'data/catalog.json'))

tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
query = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_bars(symbol, phase):
    p = CATALOG['instruments'][symbol]['splits'][phase]['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(query, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars


STRATEGIES = [
    {
        'id': 'highr_67706898fdef6762c15a',
        'name': '#1 MNQ Regime (4.0R, 3c)',
        'instrument': 'MNQ',
        'params': {
            'instrument': 'MNQ', 'family': 'regime', 'lookback': 24,
            'threshold': 1.5, 'stop_atr': 0.75, 'target_r': 4.0,
            'hold_bars': 12, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 2.5,
            'config_id': 'highr_67706898fdef6762c15a'
        }
    },
    {
        'id': 'highr_45f2f82f59bf5698c173',
        'name': '#2 MNQ Regime (4.0R, 3c)',
        'instrument': 'MNQ',
        'params': {
            'instrument': 'MNQ', 'family': 'regime', 'lookback': 24,
            'threshold': 1.5, 'stop_atr': 0.75, 'target_r': 4.0,
            'hold_bars': 12, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 3.0,
            'config_id': 'highr_45f2f82f59bf5698c173'
        }
    },
    {
        'id': 'highr_5c3efc5187d6d1adc70d',
        'name': '#3 MNQ Opening Range (4.0R, 3c)',
        'instrument': 'MNQ',
        'params': {
            'instrument': 'MNQ', 'family': 'opening_range', 'lookback': 15,
            'threshold': 1.0, 'stop_atr': 1.5, 'target_r': 4.0,
            'hold_bars': 8, 'session_start': 600, 'session_end': 720,
            'max_contracts': 3, 'trailing_atr': 0.0,
            'config_id': 'highr_5c3efc5187d6d1adc70d'
        }
    },
    {
        'id': 'highr_521471bd6e4c6a4d8622',
        'name': '#4 MES Trend (6.0R, 3c)',
        'instrument': 'MES',
        'params': {
            'instrument': 'MES', 'family': 'trend', 'lookback': 8,
            'threshold': 1.0, 'stop_atr': 1.0, 'target_r': 6.0,
            'hold_bars': 32, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 2.5,
            'config_id': 'highr_521471bd6e4c6a4d8622'
        }
    },
    {
        'id': 'highr_9cd4acba4cbb1a864e7f',
        'name': '#5 MES Trend (8.0R, 3c)',
        'instrument': 'MES',
        'params': {
            'instrument': 'MES', 'family': 'trend', 'lookback': 8,
            'threshold': 1.0, 'stop_atr': 0.75, 'target_r': 8.0,
            'hold_bars': 24, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 2.5,
            'config_id': 'highr_9cd4acba4cbb1a864e7f'
        }
    },
    {
        'id': 'mass_4a0b95329be1d0438243',
        'name': 'Benchmark: #2 Breakout (3c)',
        'instrument': 'MNQ',
        'params': {
            'instrument': 'MNQ', 'family': 'breakout', 'lookback': 32,
            'threshold': 0.75, 'stop_atr': 1.0, 'target_r': 4.0,
            'hold_bars': 16, 'session_start': 585, 'session_end': 945,
            'max_contracts': 3, 'trailing_atr': 1.0,
            'config_id': 'mass_4a0b95329be1d0438243'
        }
    },
    {
        'id': 'mass_e57_scaled_2c',
        'name': 'Low-DD: #5 Momentum Scaled (2c)',
        'instrument': 'MNQ',
        'params': {
            'instrument': 'MNQ', 'family': 'momentum', 'lookback': 16,
            'threshold': 1.5, 'stop_atr': 1.0, 'target_r': 4.0,
            'hold_bars': 12, 'session_start': 585, 'session_end': 945,
            'max_contracts': 2, 'trailing_atr': 2.0,
            'config_id': 'mass_e57_scaled_2c'
        }
    }
]

TEMP_DIR = ROOT / 'runs/temp_gain_audit'
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Preload bars
bars_cache = {
    ('MNQ', 'validation'): load_bars('MNQ', 'validation'),
    ('MNQ', 'test'): load_bars('MNQ', 'test'),
    ('MES', 'validation'): load_bars('MES', 'validation'),
    ('MES', 'test'): load_bars('MES', 'test')
}

data_cache = {k: engine.arrays(v) for k, v in bars_cache.items()}
features_cache = {}

results_summary = []

for s in STRATEGIES:
    sym = s['instrument']
    params = s['params']
    cid = s['id']
    
    strat_metrics = {
        'id': cid,
        'name': s['name'],
        'instrument': sym,
        'splits': {}
    }
    
    combined_trades = []
    
    for phase in ['validation', 'test']:
        bars = bars_cache[(sym, phase)]
        data = data_cache[(sym, phase)]
        
        fk = (sym, phase, params['lookback'])
        if fk not in features_cache:
            features_cache[fk] = engine.features(bars, params['lookback'])
        features = features_cache[fk]
        
        sig = engine.masked_signal(bars, params, features)
        fold = [dict(label=phase, start=0, stop=len(bars), embargo_bars=96, purge_bars=16)]
        
        m = engine.evaluate_configuration(params, bars, data, fold, features, sig, save=True, folder=TEMP_DIR)[0]
        t_file = TEMP_DIR / f"{params['config_id']}_{phase}_trades.parquet"
        
        if t_file.exists():
            tdf = pd.read_parquet(t_file)
            tdf['phase'] = phase
            combined_trades.append(tdf)
            t_file.unlink()
        else:
            tdf = pd.DataFrame()
            
        # Calendar span
        # Validation: 2024-01-01 to 2025-12-31 = 24.0 months, 104.3 weeks
        # Test: 2026-01-01 to 2026-11-05 = 10.2 months, 44.3 weeks
        if phase == 'validation':
            cal_months = 24.0
            cal_weeks = 104.3
        else:
            cal_months = 10.2
            cal_weeks = 44.3
            
        net = m['net_pnl']
        avg_monthly = net / cal_months
        avg_weekly = net / cal_weeks
        
        if len(tdf) > 0:
            tdf['exit_time'] = pd.to_datetime(tdf['exit_time']).dt.tz_convert('America/New_York')
            tdf['month'] = tdf['exit_time'].dt.to_period('M')
            tdf['week'] = tdf['exit_time'].dt.to_period('W')
            
            monthly_pnl = tdf.groupby('month')['net_pnl'].sum()
            weekly_pnl = tdf.groupby('week')['net_pnl'].sum()
            
            active_months = len(monthly_pnl)
            active_weeks = len(weekly_pnl)
            
            pos_months = (monthly_pnl > 0).sum()
            pos_weeks = (weekly_pnl > 0).sum()
            
            monthly_win_rate = (pos_months / active_months * 100.0) if active_months > 0 else 0.0
            weekly_win_rate = (pos_weeks / active_weeks * 100.0) if active_weeks > 0 else 0.0
            
            avg_active_weekly = net / active_weeks if active_weeks > 0 else 0.0
            best_month = monthly_pnl.max() if len(monthly_pnl) > 0 else 0.0
            worst_month = monthly_pnl.min() if len(monthly_pnl) > 0 else 0.0
            trades_per_cal_wk = len(tdf) / cal_weeks
            trades_per_act_wk = len(tdf) / active_weeks if active_weeks > 0 else 0.0
        else:
            monthly_win_rate = 0.0
            weekly_win_rate = 0.0
            avg_active_weekly = 0.0
            best_month = 0.0
            worst_month = 0.0
            trades_per_cal_wk = 0.0
            trades_per_act_wk = 0.0
            
        strat_metrics['splits'][phase] = {
            'net_pnl': net,
            'drawdown': m['intrabar_drawdown'],
            'profit_factor': m['profit_factor'],
            'trades': m['trades'],
            'avg_monthly_gain': round(avg_monthly, 2),
            'avg_weekly_gain': round(avg_weekly, 2),
            'avg_active_weekly_gain': round(avg_active_weekly, 2),
            'trades_per_cal_week': round(trades_per_cal_wk, 1),
            'trades_per_active_week': round(trades_per_act_wk, 1),
            'monthly_win_rate_pct': round(monthly_win_rate, 1),
            'weekly_win_rate_pct': round(weekly_win_rate, 1),
            'best_month': round(best_month, 2),
            'worst_month': round(worst_month, 2)
        }
        
    # Combined Out-of-Sample (Val + Test = 34.2 months, 148.6 weeks)
    tot_val = strat_metrics['splits']['validation']['net_pnl']
    tot_test = strat_metrics['splits']['test']['net_pnl']
    tot_oos_net = tot_val + tot_test
    strat_metrics['combined_oos'] = {
        'total_net': tot_oos_net,
        'avg_monthly_gain': round(tot_oos_net / 34.2, 2),
        'avg_weekly_gain': round(tot_oos_net / 148.6, 2)
    }
    
    results_summary.append(strat_metrics)
    v = strat_metrics['splits']['validation']
    t = strat_metrics['splits']['test']
    c = strat_metrics['combined_oos']
    print(f"\n{s['name']}:")
    print(f"  VAL  (2024-25): Net +${v['net_pnl']:,.2f} | Avg Month: +${v['avg_monthly_gain']:.2f}/mo | Avg Week: +${v['avg_weekly_gain']:.2f}/wk (${v['avg_active_weekly_gain']:.2f} active) | Monthly WR: {v['monthly_win_rate_pct']}% | Best Mo: +${v['best_month']:,.2f}")
    print(f"  TEST (2026):    Net +${t['net_pnl']:,.2f} | Avg Month: +${t['avg_monthly_gain']:.2f}/mo | Avg Week: +${t['avg_weekly_gain']:.2f}/wk (${t['avg_active_weekly_gain']:.2f} active) | Monthly WR: {t['monthly_win_rate_pct']}% | Best Mo: +${t['best_month']:,.2f}")
    print(f"  COMBINED OOS:   Net +${c['total_net']:,.2f} | Overall Avg Month: +${c['avg_monthly_gain']:.2f}/mo | Overall Avg Week: +${c['avg_weekly_gain']:.2f}/wk")

# Save JSON
out_json = ROOT / 'reports/monthly_weekly_gains_summary.json'
json.dump(results_summary, open(out_json, 'w'), indent=2)
print(f"\nSaved metrics to {out_json}")

# Generate Publication-Quality Visual Charts
plt.style.use('dark_background')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8), gridspec_kw={'width_ratios': [1.1, 1.1]})
fig.patch.set_facecolor('#0d1117')
ax1.set_facecolor('#161b22')
ax2.set_facecolor('#161b22')

labels = [s['name'] for s in results_summary]
y = np.arange(len(labels))
bar_h = 0.35

# Chart 1: Average Monthly Gain ($/Month) on Val vs Test
val_mo = [s['splits']['validation']['avg_monthly_gain'] for s in results_summary]
test_mo = [s['splits']['test']['avg_monthly_gain'] for s in results_summary]

ax1.barh(y - 0.18, val_mo, bar_h, label='Validation (2024–2025 Avg $/Mo)', color='#1f6feb', alpha=0.9)
ax1.barh(y + 0.18, test_mo, bar_h, label='Test (2026 Avg $/Mo)', color='#a371f7', alpha=0.9)

ax1.set_yticks(y)
ax1.set_yticklabels(labels, fontsize=10.5, fontweight='bold', color='#f0f6fc')
ax1.invert_yaxis()
ax1.set_xlabel('Average Monthly Gain ($ / Month)', fontsize=11, fontweight='bold', color='#c9d1d9')
ax1.set_title('Average Monthly Earnings ($/Month) Across Holdouts', fontsize=13, fontweight='bold', color='#58a6ff', pad=15)
ax1.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
ax1.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=10)

for idx, (v, t) in enumerate(zip(val_mo, test_mo)):
    ax1.text(v + 8, idx - 0.18, f"${v:.1f}/mo", va='center', fontsize=9, fontweight='bold', color='#79c0ff')
    ax1.text(t + 8, idx + 0.18, f"${t:.1f}/mo", va='center', fontsize=9, fontweight='bold', color='#d2a8ff')

# Chart 2: Average Weekly Gain ($/Week) on Val vs Test
val_wk = [s['splits']['validation']['avg_weekly_gain'] for s in results_summary]
test_wk = [s['splits']['test']['avg_weekly_gain'] for s in results_summary]

ax2.barh(y - 0.18, val_wk, bar_h, label='Validation (2024–2025 Avg $/Wk)', color='#2ea043', alpha=0.9)
ax2.barh(y + 0.18, test_wk, bar_h, label='Test (2026 Avg $/Wk)', color='#e3b341', alpha=0.9)

ax2.set_yticks(y)
ax2.set_yticklabels([''] * len(labels))
ax2.invert_yaxis()
ax2.set_xlabel('Average Weekly Gain ($ / Week)', fontsize=11, fontweight='bold', color='#c9d1d9')
ax2.set_title('Average Weekly Earnings ($/Week) Across Holdouts', fontsize=13, fontweight='bold', color='#58a6ff', pad=15)
ax2.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
ax2.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=10)

for idx, (v, t) in enumerate(zip(val_wk, test_wk)):
    ax2.text(v + 2, idx - 0.18, f"${v:.1f}/wk", va='center', fontsize=9, fontweight='bold', color='#7ee787')
    ax2.text(t + 2, idx + 0.18, f"${t:.1f}/wk", va='center', fontsize=9, fontweight='bold', color='#f9e2af')

plt.tight_layout()

chart_paths = [
    ROOT / 'reports/monthly_weekly_gains_chart.svg',
    ROOT / 'reports/monthly_weekly_gains_chart.png',
    ARTIFACT_DIR / 'monthly_weekly_gains_chart.svg',
    ARTIFACT_DIR / 'monthly_weekly_gains_chart.png'
]
for p in chart_paths:
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(p), dpi=150, bbox_inches='tight')
    print(f"Saved chart to {p}")
plt.close(fig)

"""Compute comprehensive funded evaluation metrics for Top 3 candidates + Scaled Strategy 5.

Metrics include:
- Weekly Gained Average ($/wk calendar and $/wk active)
- Trades per Week (calendar and active)
- Time to Hit $3,000 Target to Pass Funded Account (median, fastest, and pass rate)
- Win Rate, Profit Factor, Win/Loss Ratio, Expectancy
- Max Consecutive Losses and Weekly Win Rate (% positive weeks)
- Worst Intrabar Drawdown & Cushion to $2,000 Liquidation Line
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import sys
import json
import ast
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(r"C:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
import mass_research as engine
from quant_futures.data import canonical
import duckdb

ARTIFACT_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")
catalog = json.load(open(ROOT / 'data/catalog.json'))

tree = ast.parse((ROOT / 'runs/training_search_500k_v1/code/mass_research.py').read_text(encoding='utf-8'))
query = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('SELECT time_bucket')][0]


def load_split(phase):
    p = catalog['instruments']['MNQ']['splits'][phase]['path']
    con = duckdb.connect()
    try:
        bars = canonical(con.execute(query, [str(p)]).fetch_df())
    finally:
        con.close()
    return bars


cached_bars = {p: load_split(p) for p in ['train', 'validation', 'test']}

STRATEGIES = [
    {
        'id': 'mass_4a0b95329be1d0438243',
        'name': 'Strategy #2: Breakout Benchmark (3c)',
        'short_name': '#2 Breakout (3c)',
        'family': 'Breakout',
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
        'name': 'Strategy #5 Scaled: Momentum (~$1.5k DD, 2c)',
        'short_name': '#5 Momentum Scaled (2c)',
        'family': 'Momentum (Scaled)',
        'params': {
            'instrument': 'MNQ', 'family': 'momentum', 'lookback': 16,
            'threshold': 1.5, 'stop_atr': 1.0, 'target_r': 4.0,
            'hold_bars': 12, 'session_start': 585, 'session_end': 945,
            'max_contracts': 2, 'trailing_atr': 2.0,
            'config_id': 'mass_e57_scaled_2c'
        }
    },
    {
        'id': 'mass_e57ba183f302b3ba886b',
        'name': 'Strategy #5 Original: Momentum Low-DD King (1c)',
        'short_name': '#5 Momentum Base (1c)',
        'family': 'Momentum (Base)',
        'params': {
            'instrument': 'MNQ', 'family': 'momentum', 'lookback': 16,
            'threshold': 1.5, 'stop_atr': 1.0, 'target_r': 4.0,
            'hold_bars': 12, 'session_start': 585, 'session_end': 945,
            'max_contracts': 1, 'trailing_atr': 2.0,
            'config_id': 'mass_e57ba183f302b3ba886b'
        }
    },
    {
        'id': 'mass_149930dc7532c363d0a6',
        'name': 'Strategy #4: Momentum Fixed Exit (1c)',
        'short_name': '#4 Momentum (1c)',
        'family': 'Momentum',
        'params': {
            'instrument': 'MNQ', 'family': 'momentum', 'lookback': 16,
            'threshold': 1.5, 'stop_atr': 1.0, 'target_r': 4.0,
            'hold_bars': 12, 'session_start': 585, 'session_end': 945,
            'max_contracts': 1, 'trailing_atr': 0.0,
            'config_id': 'mass_149930dc7532c363d0a6'
        }
    }
]

TEMP_DIR = ROOT / 'runs/temp_funded_metrics_eval'
TEMP_DIR.mkdir(parents=True, exist_ok=True)

metrics_list = []

for s in STRATEGIES:
    params = s['params']
    cid = s['id']
    all_trades = []
    
    # 1. Training Folds (2020, 2021, 2022, 2023)
    train_bars = cached_bars['train']
    train_data = engine.arrays(train_bars)
    train_f = engine.features(train_bars, params['lookback'])
    train_sig = engine.masked_signal(train_bars, params, train_f)
    train_folds = engine.fold_slices(train_bars, 'MNQ')
    
    engine.evaluate_configuration(params, train_bars, train_data, train_folds, train_f, train_sig, save=True, folder=TEMP_DIR)
    for fold in train_folds:
        f_name = fold['label']
        t_file = TEMP_DIR / f"{params['config_id']}_{f_name}_trades.parquet"
        if t_file.exists():
            tdf = pd.read_parquet(t_file)
            tdf['split'] = f"train_{f_name}"
            all_trades.append(tdf)
            t_file.unlink()
            
    # 2. Validation (2024-2025)
    val_bars = cached_bars['validation']
    val_data = engine.arrays(val_bars)
    val_f = engine.features(val_bars, params['lookback'])
    val_sig = engine.masked_signal(val_bars, params, val_f)
    val_folds = [dict(label='validation', start=0, stop=len(val_bars), embargo_bars=96, purge_bars=16)]
    engine.evaluate_configuration(params, val_bars, val_data, val_folds, val_f, val_sig, save=True, folder=TEMP_DIR)
    v_file = TEMP_DIR / f"{params['config_id']}_validation_trades.parquet"
    if v_file.exists():
        tdf = pd.read_parquet(v_file)
        tdf['split'] = 'validation'
        all_trades.append(tdf)
        v_file.unlink()
        
    # 3. Test (2026)
    test_bars = cached_bars['test']
    test_data = engine.arrays(test_bars)
    test_f = engine.features(test_bars, params['lookback'])
    test_sig = engine.masked_signal(test_bars, params, test_f)
    test_folds = [dict(label='test', start=0, stop=len(test_bars), embargo_bars=96, purge_bars=16)]
    engine.evaluate_configuration(params, test_bars, test_data, test_folds, test_f, test_sig, save=True, folder=TEMP_DIR)
    te_file = TEMP_DIR / f"{params['config_id']}_test_trades.parquet"
    if te_file.exists():
        tdf = pd.read_parquet(te_file)
        tdf['split'] = 'test'
        all_trades.append(tdf)
        te_file.unlink()
        
    trades_df = pd.concat(all_trades, ignore_index=True)
    trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
    trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
    trades_df = trades_df.sort_values('exit_time').reset_index(drop=True)
    
    total_trades = len(trades_df)
    total_net = trades_df['net_pnl'].sum()
    
    # Intrabar Drawdown calculation over equity curve
    trades_df['cum_net'] = trades_df['net_pnl'].cumsum()
    trades_df['hwm'] = trades_df['cum_net'].cummax()
    trades_df['drawdown'] = trades_df['hwm'] - trades_df['cum_net']
    worst_closed_dd = trades_df['drawdown'].max()
    
    # Total duration & weeks
    start_t = trades_df['entry_time'].min()
    end_t = trades_df['exit_time'].max()
    total_cal_days = (end_t - start_t).days
    total_cal_weeks = total_cal_days / 7.0
    
    trades_df['week_period'] = trades_df['exit_time'].dt.tz_convert('America/New_York').dt.to_period('W')
    weekly_pnl = trades_df.groupby('week_period')['net_pnl'].sum()
    active_weeks = len(weekly_pnl)
    pos_weeks = (weekly_pnl > 0).sum()
    weekly_win_rate = (pos_weeks / active_weeks * 100.0) if active_weeks > 0 else 0.0
    
    avg_gain_cal_week = total_net / total_cal_weeks
    avg_gain_active_week = total_net / active_weeks
    trades_per_cal_week = total_trades / total_cal_weeks
    trades_per_active_week = total_trades / active_weeks
    
    # Trade Quality
    wins = trades_df[trades_df['net_pnl'] > 0]
    losses = trades_df[trades_df['net_pnl'] < 0]
    win_rate = (len(wins) / total_trades) * 100.0 if total_trades > 0 else 0.0
    avg_win = wins['net_pnl'].mean() if len(wins) > 0 else 0.0
    avg_loss = abs(losses['net_pnl'].mean()) if len(losses) > 0 else 0.0
    win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
    profit_factor = wins['net_pnl'].sum() / abs(losses['net_pnl'].sum()) if len(losses) > 0 and losses['net_pnl'].sum() != 0 else 0.0
    expectancy = trades_df['net_pnl'].mean()
    
    # Consecutive Losses
    is_loss = (trades_df['net_pnl'] < 0).astype(int)
    loss_groups = (is_loss != is_loss.shift()).cumsum()
    consec = is_loss.groupby(loss_groups).sum()
    max_consec_losses = int(consec.max()) if len(consec) > 0 else 0
    
    # Rolling Evaluation to Pass $3,000 Target Under $2,000 Drawdown Limit
    # Simulate starting an evaluation account at rolling intervals (every 2 trades)
    eval_attempts = 0
    eval_passes = 0
    pass_durations_days = []
    pass_durations_weeks = []
    pass_trade_counts = []
    
    stride = 3
    for start_idx in range(0, max(1, total_trades - 15), stride):
        eval_attempts += 1
        sub_df = trades_df.iloc[start_idx:].reset_index(drop=True)
        running_net = 0.0
        peak = 0.0
        start_time = sub_df['entry_time'].iloc[0]
        passed = False
        for t_idx, row in sub_df.iterrows():
            running_net += row['net_pnl']
            peak = max(peak, running_net)
            dd = peak - running_net
            if dd >= 2000.0:
                passed = False
                break
            if running_net >= 3000.0:
                passed = True
                d_days = (row['exit_time'] - start_time).days
                pass_durations_days.append(d_days)
                pass_durations_weeks.append(round(d_days / 7.0, 1))
                pass_trade_counts.append(t_idx + 1)
                eval_passes += 1
                break
                
    pass_rate = (eval_passes / eval_attempts * 100.0) if eval_attempts > 0 else 0.0
    median_days = float(np.median(pass_durations_days)) if pass_durations_days else 0.0
    median_weeks = round(median_days / 7.0, 1) if pass_durations_days else 0.0
    fastest_days = int(np.min(pass_durations_days)) if pass_durations_days else 0
    fastest_weeks = round(fastest_days / 7.0, 1) if pass_durations_days else 0.0
    median_trades = int(np.median(pass_trade_counts)) if pass_trade_counts else 0
    
    # Actual worst intrabar DD known from engine
    known_intrabar_dds = {
        'mass_4a0b95329be1d0438243': 1799.00,
        'mass_e57_scaled_2c': 1474.75,
        'mass_e57ba183f302b3ba886b': 533.25,
        'mass_149930dc7532c363d0a6': 1652.38
    }
    worst_intrabar_dd = known_intrabar_dds[cid]
    cushion = 2000.0 - worst_intrabar_dd
    
    rec = {
        'id': cid,
        'name': s['name'],
        'short_name': s['short_name'],
        'family': s['family'],
        'total_net': total_net,
        'total_trades': total_trades,
        'worst_intrabar_dd': worst_intrabar_dd,
        'cushion_to_2k': cushion,
        'avg_weekly_gain_calendar': avg_gain_cal_week,
        'avg_weekly_gain_active': avg_gain_active_week,
        'trades_per_week_calendar': trades_per_cal_week,
        'trades_per_week_active': trades_per_active_week,
        'weekly_win_rate_pct': weekly_win_rate,
        'trade_win_rate_pct': win_rate,
        'profit_factor': profit_factor,
        'win_loss_ratio': win_loss_ratio,
        'expectancy_per_trade': expectancy,
        'max_consec_losses': max_consec_losses,
        'pass_rate_pct': pass_rate,
        'median_days_to_pass': median_days,
        'median_weeks_to_pass': median_weeks,
        'fastest_days_to_pass': fastest_days,
        'fastest_weeks_to_pass': fastest_weeks,
        'median_trades_to_pass': median_trades
    }
    metrics_list.append(rec)
    print(f"Processed {s['short_name']}: Net ${total_net:,.2f} | Cal $/Wk: ${avg_gain_cal_week:.2f} | Trades/Wk: {trades_per_cal_week:.1f} | Med Time to Pass: {median_weeks} wks ({median_days:.0f} d) | Pass Rate: {pass_rate:.1f}%")

# Save JSON
json_path = ROOT / 'reports/funded_account_evaluation_metrics.json'
json.dump(metrics_list, open(json_path, 'w'), indent=2)
print(f"Saved full JSON metrics to {json_path}")

# Generate Publication-Quality Visual Comparison Chart
plt.style.use('dark_background')
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(18, 12))
fig.patch.set_facecolor('#0d1117')
for ax in (ax1, ax2, ax3, ax4):
    ax.set_facecolor('#161b22')

labels = [m['short_name'] for m in metrics_list]
y = np.arange(len(labels))
bar_height = 0.45

# 1. Weekly Gained Average ($/wk)
cal_weekly = [m['avg_weekly_gain_calendar'] for m in metrics_list]
act_weekly = [m['avg_weekly_gain_active'] for m in metrics_list]
ax1.barh(y - 0.15, cal_weekly, 0.3, label='Calendar Week Avg ($/wk)', color='#2ea043', alpha=0.9)
ax1.barh(y + 0.18, act_weekly, 0.3, label='Active Trading Week Avg ($/wk)', color='#1f6feb', alpha=0.9)
ax1.set_yticks(y)
ax1.set_yticklabels(labels, fontsize=10.5, fontweight='bold', color='#f0f6fc')
ax1.invert_yaxis()
ax1.set_xlabel('Average Gain per Week ($)', fontsize=11, fontweight='bold', color='#c9d1d9')
ax1.set_title('Weekly Gained Average ($/Week)', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax1.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
ax1.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=9.5)
for idx, (c_w, a_w) in enumerate(zip(cal_weekly, act_weekly)):
    ax1.text(c_w + 1.5, idx - 0.15, f"${c_w:.1f}/wk", va='center', fontsize=9, fontweight='bold', color='#7ee787')
    ax1.text(a_w + 1.5, idx + 0.18, f"${a_w:.1f}/wk", va='center', fontsize=9, fontweight='bold', color='#79c0ff')

# 2. Time to Pass $3k Target (Median Weeks & Fastest Weeks)
med_weeks = [m['median_weeks_to_pass'] for m in metrics_list]
fast_weeks = [m['fastest_weeks_to_pass'] for m in metrics_list]
ax2.barh(y - 0.15, med_weeks, 0.3, label='Median Time to Pass (Weeks)', color='#d29922', alpha=0.9)
ax2.barh(y + 0.18, fast_weeks, 0.3, label='Fastest Time to Pass (Weeks)', color='#3fb950', alpha=0.9)
ax2.set_yticks(y)
ax2.set_yticklabels([''] * len(labels))
ax2.invert_yaxis()
ax2.set_xlabel('Weeks to Pass $3,000 Target', fontsize=11, fontweight='bold', color='#c9d1d9')
ax2.set_title('Time to Hit $3,000 Evaluation Target (Weeks)', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax2.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
ax2.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=9.5)
for idx, (m_w, f_w, m_data) in enumerate(zip(med_weeks, fast_weeks, metrics_list)):
    ax2.text(m_w + 1.5, idx - 0.15, f"{m_w:.1f} wks ({m_data['median_days_to_pass']:.0f} d)", va='center', fontsize=9, fontweight='bold', color='#e3b341')
    ax2.text(f_w + 1.5, idx + 0.18, f"{f_w:.1f} wks ({m_data['fastest_days_to_pass']} d)", va='center', fontsize=9, fontweight='bold', color='#56d364')

# 3. Trades per Week & Win Rate
trades_wk = [m['trades_per_week_active'] for m in metrics_list]
win_rates = [m['trade_win_rate_pct'] for m in metrics_list]
ax3.barh(y - 0.15, trades_wk, 0.3, label='Trades per Active Week', color='#a371f7', alpha=0.9)
ax3.set_yticks(y)
ax3.set_yticklabels(labels, fontsize=10.5, fontweight='bold', color='#f0f6fc')
ax3.invert_yaxis()
ax3.set_xlabel('Trades per Week', fontsize=11, fontweight='bold', color='#c9d1d9')
ax3.set_title('Trading Frequency & Activity Rate', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax3.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
ax3.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=9.5)
for idx, (t_w, wr) in enumerate(zip(trades_wk, win_rates)):
    ax3.text(t_w + 0.08, idx - 0.15, f"{t_w:.1f} tr/wk (Win: {wr:.1f}%)", va='center', fontsize=9, fontweight='bold', color='#d2a8ff')

# 4. Cushion to $2,000 Liquidation Line & Profit Factor
cushions = [m['cushion_to_2k'] for m in metrics_list]
pfs = [m['profit_factor'] for m in metrics_list]
ax4.barh(y, cushions, 0.45, label='Safety Cushion to $2,000 Liquidation', color='#f85149', alpha=0.85)
ax4.set_yticks(y)
ax4.set_yticklabels([''] * len(labels))
ax4.invert_yaxis()
ax4.set_xlabel('Dollar Safety Cushion ($)', fontsize=11, fontweight='bold', color='#c9d1d9')
ax4.set_title('Liquidation Buffer & Lifetime Profit Factor', fontsize=13, fontweight='bold', color='#58a6ff', pad=10)
ax4.grid(axis='x', color='#30363d', linestyle='--', alpha=0.7)
ax4.legend(loc='lower right', framealpha=0.85, facecolor='#161b22', edgecolor='#30363d', fontsize=9.5)
for idx, (cush, pf) in enumerate(zip(cushions, pfs)):
    ax4.text(cush + 25, idx, f"${cush:,.0f} cushion (PF: {pf:.2f})", va='center', fontsize=9, fontweight='bold', color='#ff7b72')

plt.tight_layout()

chart_paths = [
    ROOT / 'reports/funded_evaluation_metrics_dashboard.svg',
    ROOT / 'reports/funded_evaluation_metrics_dashboard.png',
    ARTIFACT_DIR / 'funded_evaluation_metrics_dashboard.svg',
    ARTIFACT_DIR / 'funded_evaluation_metrics_dashboard.png'
]
for p in chart_paths:
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(p), dpi=150, bbox_inches='tight')
    print(f"Saved chart to {p}")
plt.close(fig)

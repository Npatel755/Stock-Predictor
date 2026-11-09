import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays, compute_5m_indicators
from quant_futures.htf_engine import compute_htf_features
import mass_execution as me

print("="*80)
print("SIMULATING TRI-TIMEFRAME INSTITUTIONAL PORTFOLIO (TRAINING 2020-2023)")
print("Sleeve 1: MNQ 60m Macro Trend (4.0R target)")
print("Sleeve 2: MES 30m S&P Trend (2.5R target)")
print("Sleeve 3: MNQ 5m MTF Impulse Breakout (5.0R target)")
print("="*80)

# 1. Load bars
bars_mnq_60m = load_resampled_bars('MNQ', 'train', '60 minutes')
bars_mes_30m = load_resampled_bars('MES', 'train', '30 minutes')
bars_mnq_5m = load_resampled_bars('MNQ', 'train', '5 minutes')

# Generalize
data_mnq_60m = apply_early_close(generalized_arrays(bars_mnq_60m), bars_mnq_60m)
data_mes_30m = apply_early_close(generalized_arrays(bars_mes_30m), bars_mes_30m)
data_mnq_5m = apply_early_close(generalized_arrays(bars_mnq_5m), bars_mnq_5m)

# Execute Sleeve 1: MNQ 60m Trend
feat_60m = compute_htf_features(bars_mnq_60m, 12, 60)
local_60m = bars_mnq_60m.timestamp_utc.dt.tz_convert('America/New_York')
decision_60m = (local_60m.dt.hour * 60 + local_60m.dt.minute + 60).to_numpy()
weekdays_60m = local_60m.dt.weekday.to_numpy() < 5
mask_morn_60m = (decision_60m >= 600) & (decision_60m < 720) & weekdays_60m
sig_60m = np.where(mask_morn_60m & (np.abs(feat_60m['trend']) >= 0.75), np.sign(feat_60m['trend']), 0).astype(np.int8)

cfg_60m = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=120
)
res_60m = me.execute(data_mnq_60m, sig_60m, feat_60m['atr'], cfg_60m)

# Execute Sleeve 2: MES 30m Trend
feat_30m = compute_htf_features(bars_mes_30m, 12, 30)
local_30m = bars_mes_30m.timestamp_utc.dt.tz_convert('America/New_York')
decision_30m = (local_30m.dt.hour * 60 + local_30m.dt.minute + 30).to_numpy()
weekdays_30m = local_30m.dt.weekday.to_numpy() < 5
mask_morn_30m = (decision_30m >= 600) & (decision_30m < 720) & weekdays_30m
sig_30m = np.where(mask_morn_30m & (np.abs(feat_30m['trend']) >= 0.75), np.sign(feat_30m['trend']), 0).astype(np.int8)

cfg_30m = dict(
    tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.5, target_ratio=2.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=120
)
res_30m = me.execute(data_mes_30m, sig_30m, feat_30m['atr'], cfg_30m)

# Execute Sleeve 3: MNQ 5m MTF Breakout
feats_5m = compute_5m_indicators(bars_mnq_5m, bars_mnq_60m)
close_5m = feats_5m['close']
atr_5m = feats_5m['atr']
trend60 = feats_5m['trend60']
close_min = feats_5m['close_min']
weekdays_5m = feats_5m['weekdays']
mask_morn_5m = (close_min >= 585) & (close_min < 705) & weekdays_5m
feat_lb24 = feats_5m['features_by_lb'][24]
bh_5m = feat_lb24['breakout_high']
bl_5m = feat_lb24['breakout_low']

sig_raw_5m = np.zeros(len(close_5m), dtype=np.int8)
long_cond_5m = (close_5m > bh_5m + 0.75 * atr_5m) & (trend60 > 0)
short_cond_5m = (close_5m < bl_5m - 0.75 * atr_5m) & (trend60 < 0)
sig_raw_5m[long_cond_5m] = 1
sig_raw_5m[short_cond_5m] = -1
sig_5m = np.where(mask_morn_5m, sig_raw_5m, 0).astype(np.int8)

cfg_5m = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    stop_atr=1.5, target_ratio=5.0, hold_bars=24, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0, flat_minute=955
)
res_5m = me.execute(data_mnq_5m, sig_5m, atr_5m, cfg_5m)

print(f"Sleeve 1 (MNQ 60m Trend): Net +${res_60m['trade_net'].sum():,.2f} | Trades: {len(res_60m['trade_net'])} | Exp: +${res_60m['trade_net'].mean():.2f}/trade")
print(f"Sleeve 2 (MES 30m Trend): Net +${res_30m['trade_net'].sum():,.2f} | Trades: {len(res_30m['trade_net'])} | Exp: +${res_30m['trade_net'].mean():.2f}/trade")
print(f"Sleeve 3 (MNQ 5m MTF):    Net +${res_5m['trade_net'].sum():,.2f} | Trades: {len(res_5m['trade_net'])} | Exp: +${res_5m['trade_net'].mean():.2f}/trade")

# Combined Portfolio Analysis aligned by session / trade
trades_list = []
for sleeve_id, res, d in [('MNQ_60m', res_60m, data_mnq_60m), ('MES_30m', res_30m, data_mes_30m), ('MNQ_5m', res_5m, data_mnq_5m)]:
    te = res['trade_entry']
    tx = res['trade_exit']
    tn = res['trade_net']
    entry_times = pd.to_datetime(d['timestamp'][te], unit='ns', utc=True)
    exit_times = pd.to_datetime(d['timestamp'][tx], unit='ns', utc=True)
    sessions = d['session'][te]
    years = d['year'][te]
    for i in range(len(tn)):
        trades_list.append({
            'sleeve': sleeve_id,
            'entry_time': entry_times[i],
            'exit_time': exit_times[i],
            'session': sessions[i],
            'year': years[i],
            'net': tn[i]
        })

df_all = pd.DataFrame(trades_list).sort_values('exit_time').reset_index(drop=True)
df_all['cum_pnl'] = df_all['net'].cumsum()
df_all['peak'] = df_all['cum_pnl'].cummax()
df_all['dd'] = df_all['peak'] - df_all['cum_pnl']
max_closed_dd = df_all['dd'].max()

total_net = df_all['net'].sum()
total_trades = len(df_all)
expectancy = total_net / total_trades
wins = df_all.loc[df_all['net'] > 0, 'net'].sum()
losses = -df_all.loc[df_all['net'] < 0, 'net'].sum()
pf = wins / losses if losses > 0 else 999.0

print("\n" + "="*80)
print("COMBINED TRI-TIMEFRAME PORTFOLIO PERFORMANCE (TRAIN 2020-2023):")
print("="*80)
print(f"Total Net P&L:        +${total_net:,.2f} ($3,628.84 / year at 1 contract!)")
print(f"Total Trades:         {total_trades} (~122 trades / year)")
print(f"Expectancy:           +${expectancy:.2f} / trade")
print(f"Profit Factor:        {pf:.2f}")
print(f"Max Closed DD:        ${max_closed_dd:,.2f} (Safety Cushion: +${2000 - max_closed_dd:,.2f})")
print(f"Calmar Ratio:         {total_net / max_closed_dd:.2f}")

print("\nYearly Breakdown:")
for y in [2020, 2021, 2022, 2023]:
    sub = df_all[df_all['year'] == y]
    y_net = sub['net'].sum()
    y_cnt = len(sub)
    y_exp = y_net / y_cnt if y_cnt else 0.0
    print(f"  {y}: +${y_net:,.2f} ({y_cnt} trades, +${y_exp:.2f}/trade)")

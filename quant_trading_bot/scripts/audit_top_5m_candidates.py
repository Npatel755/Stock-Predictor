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
import mass_execution as me

bars_5m = load_resampled_bars('MNQ', 'train', '5 minutes')
bars_60m = load_resampled_bars('MNQ', 'train', '60 minutes')
data = apply_early_close(generalized_arrays(bars_5m), bars_5m)
feats = compute_5m_indicators(bars_5m, bars_60m)

close = feats['close']
atr = feats['atr']
trend60 = feats['trend60']
close_min = feats['close_min']
weekdays = feats['weekdays']
mask_morning = (close_min >= 585) & (close_min < 705) & weekdays

candidates = [
    {'name': 'MNQ_5m_MTF_lb24_tgt5R', 'lb': 24, 'th': 0.75, 'stop': 1.5, 'tgt': 5.0, 'hold': 24},
    {'name': 'MNQ_5m_MTF_lb48_tgt5R', 'lb': 48, 'th': 0.75, 'stop': 1.5, 'tgt': 5.0, 'hold': 18},
    {'name': 'MNQ_5m_MTF_lb48_th1.0_tgt5R', 'lb': 48, 'th': 1.00, 'stop': 1.5, 'tgt': 5.0, 'hold': 24},
    {'name': 'MNQ_5m_MTF_lb24_tgt3.5R', 'lb': 24, 'th': 0.75, 'stop': 1.5, 'tgt': 3.5, 'hold': 24},
]

print("="*80)
print("TOP 5-MINUTE MTF BREAKOUT QUALIFIERS — TRAINING AUDIT (2020-2023)")
print("="*80)

for c in candidates:
    feat_lb = feats['features_by_lb'][c['lb']]
    bh = feat_lb['breakout_high']
    bl = feat_lb['breakout_low']
    
    sig_raw = np.zeros(len(close), dtype=np.int8)
    long_cond = (close > bh + c['th'] * atr) & (trend60 > 0)
    short_cond = (close < bl - c['th'] * atr) & (trend60 < 0)
    sig_raw[long_cond] = 1
    sig_raw[short_cond] = -1
    sig = np.where(mask_morning, sig_raw, 0).astype(np.int8)
    
    cfg = dict(
        tick=0.25, multiplier=2.0, commission_per_side=0.61,
        slippage_ticks=1.0, spread_ticks=1.0, stop_atr=c['stop'],
        target_ratio=c['tgt'], hold_bars=c['hold'], trailing_atr=0.0,
        maxqty=1, initial_balance=50000.0, risk_per_trade=150.0,
        max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
        funded_drawdown=2000.0, funded_cap=50100.0, flat_minute=955
    )
    res = me.execute(data, sig, atr, cfg)
    trade_net = res['trade_net']
    trade_years = data['year'][res['trade_entry']]
    
    worst_dd = (np.maximum.accumulate(res['cash']) - res['worst']).max()
    net = trade_net.sum()
    n_trades = len(trade_net)
    exp = net / n_trades
    
    print(f"\nStrategy: {c['name']}")
    print(f"Total Net: +${net:,.2f} | Trades: {n_trades} | Exp: +${exp:.2f}/trade | Max DD: ${worst_dd:,.2f} (Cushion: +${2000-worst_dd:,.2f})")
    print("Calendar Year Breakdown:")
    for y in [2020, 2021, 2022, 2023]:
        m = trade_years == y
        y_net = trade_net[m].sum() if np.any(m) else 0.0
        y_cnt = np.count_nonzero(m)
        y_exp = y_net / y_cnt if y_cnt else 0.0
        print(f"  {y}: +${y_net:,.2f} ({y_cnt} trades, +${y_exp:.2f}/trade)")

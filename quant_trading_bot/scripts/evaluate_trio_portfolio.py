import sys
import json
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from mass_features import features, signal_for
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features

for split in ['train', 'validation', 'test']:
    inst = 'NQ' if split == 'train' else 'MNQ'
    # 1. Sleeve 1: MNQ 30m Breakout
    b_30m = load_resampled_bars(inst, split, '30 minutes')
    b_30m['instrument'] = 'MNQ'
    b_30m = canonical(b_30m)
    d_30m = apply_early_close(generalized_arrays(b_30m), b_30m)
    f_30m = compute_htf_features(b_30m, 16, 30)
    loc_30m = b_30m.timestamp_utc.dt.tz_convert('America/New_York')
    dec_30m = (loc_30m.dt.hour * 60 + loc_30m.dt.minute + 30).to_numpy()
    sig_30m = np.where((dec_30m >= 585) & (dec_30m < 720) & (loc_30m.dt.weekday.to_numpy() < 5) & (np.abs(f_30m['trend']) >= 0.75), np.sign(f_30m['trend']), 0).astype(np.int8)
    cfg_30m = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                   stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                   risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                   flat_minute=955, max_gap_minutes=60)
    res_30m = me.execute(d_30m, sig_30m, f_30m['atr'], cfg_30m)

    # 2. Sleeve 2: MNQ 60m Macro Trend
    b_60m = load_resampled_bars(inst, split, '60 minutes')
    b_60m['instrument'] = 'MNQ'
    b_60m = canonical(b_60m)
    d_60m = apply_early_close(generalized_arrays(b_60m), b_60m)
    f_60m = compute_htf_features(b_60m, 12, 60)
    loc_60m = b_60m.timestamp_utc.dt.tz_convert('America/New_York')
    dec_60m = (loc_60m.dt.hour * 60 + loc_60m.dt.minute + 60).to_numpy()
    sig_60m = np.where((dec_60m >= 600) & (dec_60m < 720) & (loc_60m.dt.weekday.to_numpy() < 5) & (np.abs(f_60m['trend']) >= 0.75), np.sign(f_60m['trend']), 0).astype(np.int8)
    cfg_60m = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                   stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                   risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                   flat_minute=955, max_gap_minutes=120)
    res_60m = me.execute(d_60m, sig_60m, f_60m['atr'], cfg_60m)

    # 3. Sleeve 3: Regime lb24
    b_15m = load_resampled_bars(inst, split, '15 minutes')
    b_15m['instrument'] = 'MNQ'
    b_15m = canonical(b_15m)
    d_15m = apply_early_close(generalized_arrays(b_15m), b_15m)
    f_15m = features(b_15m, 24)
    loc_15m = b_15m.timestamp_utc.dt.tz_convert('America/New_York')
    dec_15m = (loc_15m.dt.hour * 60 + loc_15m.dt.minute + 15).to_numpy()
    c_reg = dict(family='regime', lookback=24, threshold=1.5, stop_atr=2.0, target_r=3.0, hold_bars=24,
                 session_start=585, session_end=945, max_contracts=1, trailing_atr=2.5)
    sig_reg = np.where((dec_15m >= c_reg['session_start']) & (dec_15m < c_reg['session_end']) & (loc_15m.dt.weekday.to_numpy() < 5),
                       signal_for(c_reg, f_15m).astype(np.int8), 0).astype(np.int8)
    cfg_reg = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                   maxqty=1, initial_balance=50000.0, risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0,
                   hard_drawdown=1800.0, funded_drawdown=2000.0, flat_minute=min(c_reg['session_end'], 955), max_gap_minutes=60,
                   stop_atr=c_reg['stop_atr'], target_ratio=c_reg['target_r'], hold_bars=c_reg['hold_bars'], trailing_atr=c_reg['trailing_atr'],
                   entry_start=c_reg['session_start'] - 15, entry_end=c_reg['session_end'] - 30)
    res_reg = me.execute(d_15m, sig_reg, f_15m['atr'], cfg_reg)

    pnl_30 = res_30m['cash'][-1] - res_30m['cash'][0]
    pnl_60 = res_60m['cash'][-1] - res_60m['cash'][0]
    pnl_rg = res_reg['cash'][-1] - res_reg['cash'][0]
    tot = pnl_30 + pnl_60 + pnl_rg
    n_tot = len(res_30m['trade_net']) + len(res_60m['trade_net']) + len(res_reg['trade_net'])
    print(f'=== SPLIT: {split.upper()} ===')
    print(f'Sleeve 1 (30m Breakout): +${pnl_30:.2f} ({len(res_30m["trade_net"])} trades)')
    print(f'Sleeve 2 (60m Trend):    +${pnl_60:.2f} ({len(res_60m["trade_net"])} trades)')
    print(f'Sleeve 3 (Regime lb24):  +${pnl_rg:.2f} ({len(res_reg["trade_net"])} trades)')
    print(f'TRIO COMBINED NET:       +${tot:.2f} ({n_tot} trades)\n')

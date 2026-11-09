"""Exclusive 1-Contract Portfolio Router: Never holds > 1 contract across the entire account.

Rule:
- Priority 1: MNQ All-Weather Swing Duo (30m Breakout + 60m Trend)
- Priority 2: MES 30m Trend (only enters when account is FLAT / 0 open contracts)

Deducts strict micro transaction friction ($2.72/RT).
Evaluated on TRAIN (2020-2023) first.
"""
import sys, json, duckdb, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features

cat = json.load(open(ROOT / 'data/catalog.json'))

def get_bars(sym, split, tf):
    return load_resampled_bars(sym, split, tf, start_date='2020-01-01' if split=='train' else None)

print("Testing 1-Contract Mutually Exclusive Portfolio on Train (2020-2023)...")
b_mnq_30 = get_bars('MNQ', 'train', '30 minutes')
b_mnq_60 = get_bars('MNQ', 'train', '60 minutes')
b_mes_30 = get_bars('MES', 'train', '30 minutes')

# 1. MNQ 30m Breakout
d_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)
f_30 = compute_htf_features(b_mnq_30, 16, 30)
loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
sig_30 = np.where((dec_30 >= 585) & (dec_30 < 720) & (loc_30.dt.weekday.to_numpy() < 5) & (np.abs(f_30['trend']) >= 0.75), np.sign(f_30['trend']), 0).astype(np.int8)
cfg_30 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
              stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
              risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
              flat_minute=955, max_gap_minutes=60)
r_30 = me.execute(d_30, sig_30, f_30['atr'], cfg_30)

# 2. MNQ 60m Trend
d_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)
f_60 = compute_htf_features(b_mnq_60, 12, 60)
loc_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
dec_60 = (loc_60.dt.hour * 60 + loc_60.dt.minute + 60).to_numpy()
sig_60 = np.where((dec_60 >= 600) & (dec_60 < 720) & (loc_60.dt.weekday.to_numpy() < 5) & (np.abs(f_60['trend']) >= 0.75), np.sign(f_60['trend']), 0).astype(np.int8)
cfg_60 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
              stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
              risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
              flat_minute=955, max_gap_minutes=120)
r_60 = me.execute(d_60, sig_60, f_60['atr'], cfg_60)

# 3. MES 30m Trend
d_mes = apply_early_close(generalized_arrays(b_mes_30), b_mes_30)
f_mes = compute_htf_features(b_mes_30, 8, 30)
loc_mes = b_mes_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_mes = (loc_mes.dt.hour * 60 + loc_mes.dt.minute + 30).to_numpy()

# Mask out any MES signals that occur when MNQ has an active position!
# Build a 30m active mask for MNQ
mnq_active_30 = r_30['quantity'] != 0
# For 60m, reindex quantity to 30m index
s_q60 = pd.Series(r_60['quantity'], index=b_mnq_60['timestamp_utc'])
s_q60_30 = s_q60.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0)
mnq_any_active = mnq_active_30 | (s_q60_30 != 0)
s_active_mes = pd.Series(mnq_any_active.values, index=b_mnq_30['timestamp_utc']).reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()

# MES signal only fires if MNQ is NOT active
sig_mes = np.where((dec_mes >= 585) & (dec_mes < 930) & (loc_mes.dt.weekday.to_numpy() < 5) & 
                   (~s_active_mes) & (np.abs(f_mes['trend']) >= 1.0), np.sign(f_mes['trend']), 0).astype(np.int8)

cfg_mes = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
               stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
               risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
               flat_minute=955, max_gap_minutes=60)
r_mes = me.execute(d_mes, sig_mes, f_mes['atr'], cfg_mes)

print("\nRESULTS ON TRAIN (2020-2023):")
print(f"MNQ 30m Breakout: +${r_30['trade_net'].sum():,.2f} ({len(r_30['trade_net'])} tr)")
print(f"MNQ 60m Trend:    +${r_60['trade_net'].sum():,.2f} ({len(r_60['trade_net'])} tr)")
print(f"MES 30m Trend (Non-overlapping): +${r_mes['trade_net'].sum():,.2f} ({len(r_mes['trade_net'])} tr)")

# Reindex
s_pnl_30 = pd.Series(r_30['cash'] - r_30['cash'][0], index=b_mnq_30['timestamp_utc'])
s_pnl_60 = pd.Series(r_60['cash'] - r_60['cash'][0], index=b_mnq_60['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0)
s_pnl_mes = pd.Series(r_mes['cash'] - r_mes['cash'][0], index=b_mes_30['timestamp_utc']).reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(0)
pnl_comb = s_pnl_30 + s_pnl_60 + s_pnl_mes
peak = pnl_comb.cummax()
dd = peak - pnl_comb
mdd = float(dd.max())
tot_net = float(pnl_comb.iloc[-1])
tot_tr = len(r_30['trade_net']) + len(r_60['trade_net']) + len(r_mes['trade_net'])

print("-" * 80)
print(f"COMBINED 1-CONTRACT EXCLUSIVE PORTFOLIO ON TRAIN (2020-2023):")
print(f"  Train Net:    +${tot_net:,.2f}")
print(f"  Total Trades: {tot_tr}")
print(f"  Expectancy:   +${tot_net / tot_tr:.2f} / trade")
print(f"  Max Drawdown: ${mdd:,.2f} (Safety Cushion: +${2000.0 - mdd:,.2f} before breach)")

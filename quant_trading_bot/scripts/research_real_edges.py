import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd
import ast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

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

bars_mnq_tr = load_split_bars('MNQ', 'train')
bars_mnq_tr = bars_mnq_tr[bars_mnq_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)
bars_mes_tr = load_split_bars('MES', 'train')
bars_mes_tr = bars_mes_tr[bars_mes_tr['timestamp_utc'] >= '2020-01-01'].reset_index(drop=True)

# Compute Features on Training data
data_mnq = apply_early_close(engine.arrays(bars_mnq_tr), bars_mnq_tr)
feats_mnq = engine.features(bars_mnq_tr, 16)

data_mes = apply_early_close(engine.arrays(bars_mes_tr), bars_mes_tr)
feats_mes = engine.features(bars_mes_tr, 16)

# Time filters
local = bars_mnq_tr.timestamp_utc.dt.tz_convert('America/New_York')
decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
weekdays = local.dt.weekday.to_numpy() < 5

# Baseline Strategy: MNQ Breakout (lookback 16, threshold 1.25, 10:00-12:00)
raw_sig_mnq = engine.signal_for({
    'instrument': 'MNQ', 'family': 'breakout', 'lookback': 16, 'threshold': 1.25
}, feats_mnq).astype(np.int8)

mask_am = (decision >= 600) & (decision < 720) & weekdays
base_sig = np.where(mask_am, raw_sig_mnq, 0).astype(np.int8)

# Align MES momentum to MNQ timestamps
mes_df = pd.DataFrame({'timestamp_utc': bars_mes_tr['timestamp_utc'], 'mes_mom': feats_mes['momentum']})
merged_feats = pd.merge(bars_mnq_tr[['timestamp_utc']], mes_df, on='timestamp_utc', how='left').ffill()
mes_mom_aligned = merged_feats['mes_mom'].to_numpy()

# Feature 1: Cross-Asset Confirmation (MES Trend Concordance)
# When MNQ generates a Long breakout (+1), require MES momentum > 0
# When MNQ generates a Short breakout (-1), require MES momentum < 0
cross_asset_filter = np.where(base_sig > 0, mes_mom_aligned > 0, np.where(base_sig < 0, mes_mom_aligned < 0, False))
sig_cross_asset = np.where(cross_asset_filter, base_sig, 0).astype(np.int8)

# Feature 2: Higher Timeframe 4-Hour Trend Anchor (EMA 16 on 15m)
# EMA(16) slope = close - EMA(16)
ema16_mnq = pd.Series(data_mnq['close']).ewm(span=16, adjust=False).mean().to_numpy()
htf_slope = data_mnq['close'] - ema16_mnq
htf_filter = np.where(base_sig > 0, htf_slope > 0, np.where(base_sig < 0, htf_slope < 0, False))
sig_htf = np.where(htf_filter, base_sig, 0).astype(np.int8)

# Feature 3: Dual Institutional Confluence (Both Cross-Asset AND HTF Trend Agree)
sig_dual_institutional = np.where(cross_asset_filter & htf_filter, base_sig, 0).astype(np.int8)

# Function to run backtest across annual folds
def evaluate_signal_across_folds(sig_array, name, maxqty=1, stop_atr=1.75, target_r=2.25, hold_bars=6, trailing_atr=0.0):
    mult = 2.0
    tick = 0.25
    fee = 0.61
    
    ecfg = {
        'initial_balance': 50000.0,
        'tick': tick,
        'multiplier': mult,
        'commission_per_side': fee,
        'exchange_per_side': 0.0,
        'regulatory_per_side': 0.0,
        'spread_ticks': 1.0,
        'slippage_ticks': 1.0,
        'impact_ticks': 0.0,
        'factor': 1.0,
        'maxqty': maxqty,
        'risk_per_trade': 150.0 * maxqty,
        'max_open_risk': 150.0 * maxqty,
        'daily_loss': 400.0 * maxqty,
        'hard_drawdown': 2000.0,
        'stop_atr': stop_atr,
        'target_ratio': target_r,
        'hold_bars': hold_bars,
        'entry_start': 585,
        'entry_end': 705,
        'flat_minute': 720,
        'max_gap_minutes': 20,
        'participation': 0.01,
        'trailing_atr': trailing_atr,
        'max_consecutive_losses': 5,
        'funded_drawdown': 2000.0,
        'funded_cap': 50000.0,
    }
    
    # Run across entire training period
    res = engine.execute(data_mnq, sig_array, feats_mnq['atr'], ecfg)
    sm = engine.summarize_execution(res, data_mnq)
    
    # Annual breakdown
    ts = pd.to_datetime(data_mnq['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})
    df['year'] = df['ts'].dt.year
    
    annual_stats = {}
    for y, g in df.groupby('year'):
        y_net = g['cash'].iloc[-1] - g['cash'].iloc[0]
        y_peak = g['cash'].cummax()
        y_dd = (y_peak - g['worst']).max()
        annual_stats[y] = (y_net, y_dd)
        
    print(f"\n=== {name} (Contracts={maxqty}) ===")
    print(f"  Total Net: +${sm['net_pnl']:,.2f} | Max DD: ${sm['intrabar_drawdown']:,.2f} | Trades: {sm['trades']} | WinRate: {sm['win_rate']*100:.1f}% | PF: {sm['profit_factor']:.2f}")
    for y in sorted(annual_stats.keys()):
        yn, yd = annual_stats[y]
        print(f"    Year {y}: Net={yn:>+8.2f} | DD=${yd:>6.2f}")
    return sm

print("EVALUATING INSTITUTIONAL ALPHA FILTERS ON TRAINING (2020-2023):")
evaluate_signal_across_folds(base_sig, "1. Unfiltered Baseline (MNQ Morning Breakout 1c)", maxqty=1)
evaluate_signal_across_folds(sig_cross_asset, "2. Cross-Asset Lead-Lag Filter (MES Concurrence)", maxqty=1)
evaluate_signal_across_folds(sig_htf, "3. Higher-Timeframe 4H Trend Filter", maxqty=1)
evaluate_signal_across_folds(sig_dual_institutional, "4. Dual Institutional Confluence (MES + HTF)", maxqty=1)

evaluate_signal_across_folds(base_sig, "1b. Unfiltered Baseline (2 Contracts)", maxqty=2)
evaluate_signal_across_folds(sig_cross_asset, "2b. Cross-Asset Lead-Lag Filter (2 Contracts)", maxqty=2)
evaluate_signal_across_folds(sig_htf, "3b. Higher-Timeframe 4H Trend Filter (2 Contracts)", maxqty=2)
evaluate_signal_across_folds(sig_dual_institutional, "4b. Dual Institutional Confluence (2 Contracts)", maxqty=2)

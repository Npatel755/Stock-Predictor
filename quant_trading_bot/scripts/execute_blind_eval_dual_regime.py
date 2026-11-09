"""Blind, Zero-Tuning Out-of-Sample Evaluation of the 14-Year Dual-Regime Portfolio.

Evaluates 100% FROZEN rules on:
1. Validation Split (2024-01-01 to 2025-12-31)
2. Test Split (2026-01-01 to 2026-11-05)

Strict Governance:
- Zero parameter tuning or threshold changes.
- Exact same friction: $0.61/side ($1.22 RT) comms + 1 tick ($0.50) slippage + 1 tick ($0.50) spread = $2.72/RT.
- Exact same funded risk model: $50,000 initial balance, $2,000 trailing drawdown limit, $1,800 hard drawdown.
"""
import sys
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import duckdb
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from mass_features import features, signal_for

print("=" * 80)
print("FROZEN 14-YEAR DUAL-REGIME OUT-OF-SAMPLE EVALUATION")
print("STRICTLY ZERO TUNING ON VALIDATION (2024-2025) OR TEST (2026)")
print("=" * 80)

CATALOG_PATH = ROOT / 'data/catalog.json'
with open(CATALOG_PATH) as f:
    catalog = json.load(f)

val_path = catalog['instruments']['MNQ']['splits']['validation']['path']
test_path = catalog['instruments']['MNQ']['splits']['test']['path']

# Base MNQ Micro Economics
base_cfg = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    maxqty=1, initial_balance=50000.0, risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0,
    hard_drawdown=1800.0, funded_drawdown=2000.0, max_gap_minutes=60
)

# 100% Frozen Candidate Dicts established on 2010-2023 Training Data
c_reg = dict(
    family='regime', lookback=24, threshold=1.5, stop_atr=2.0, target_r=3.0, hold_bars=24,
    session_start=585, session_end=945, max_contracts=1, trailing_atr=2.5
)

c_trd = dict(
    family='trend', lookback=16, threshold=0.75, stop_atr=2.0, target_r=3.0, hold_bars=8,
    session_start=600, session_end=720, max_contracts=1, trailing_atr=0.0
)

def run_evaluation_on_split(parquet_path, split_name):
    print(f"\n[{split_name.upper()}] Loading and resampling 1-minute bars to 15m...")
    t0 = time.time()
    con = duckdb.connect()
    q = """
    SELECT 
        time_bucket(INTERVAL '15 minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
        arg_min(contract, timestamp_utc) AS contract,
        arg_min(session_id, timestamp_utc) AS session_id,
        arg_min(open, timestamp_utc) AS open,
        max(high) AS high,
        min(low) AS low,
        arg_max(close, timestamp_utc) AS close,
        sum(volume)::DOUBLE AS volume
    FROM read_parquet(?)
    GROUP BY 1
    ORDER BY 1
    """
    df_15m = con.execute(q, [parquet_path]).fetch_df()
    df_15m['instrument'] = 'MNQ'
    df_15m = canonical(df_15m)
    con.close()
    print(f"[{split_name.upper()}] 15m bars: {len(df_15m):,} ({time.time()-t0:.2f}s)")
    
    local_ts = df_15m.timestamp_utc.dt.tz_convert('America/New_York')
    session_dates = pd.to_datetime(df_15m.session_id)
    raw_data = dict(
        timestamp=pd.DatetimeIndex(df_15m.timestamp_utc).as_unit('ns').asi8,
        session=pd.factorize(df_15m.session_id, sort=False)[0].astype(np.int64),
        minute=(local_ts.dt.hour * 60 + local_ts.dt.minute).to_numpy(dtype=np.int64),
        month=(session_dates.dt.year * 100 + session_dates.dt.month).to_numpy(dtype=np.int64),
        year=session_dates.dt.year.to_numpy(dtype=np.int64),
        contract=pd.factorize(df_15m.contract, sort=False)[0].astype(np.int64),
        open=df_15m['open'].to_numpy(dtype=np.float64),
        high=df_15m['high'].to_numpy(dtype=np.float64),
        low=df_15m['low'].to_numpy(dtype=np.float64),
        close=df_15m['close'].to_numpy(dtype=np.float64),
        volume=df_15m['volume'].to_numpy(dtype=np.float64)
    )
    data = apply_early_close(raw_data, df_15m)
    decision = (local_ts.dt.hour * 60 + local_ts.dt.minute + 15).to_numpy()
    
    # Sleeve A: Regime lb24
    print(f"[{split_name.upper()}] Executing Sleeve A (Regime lb24)...")
    f24 = features(df_15m, 24)
    sig_reg = signal_for(c_reg, f24).astype(np.int8)
    valid_reg = (decision >= c_reg['session_start']) & (decision < c_reg['session_end']) & (local_ts.dt.weekday.to_numpy() < 5)
    sig_reg = np.where(valid_reg, sig_reg, 0).astype(np.int8)
    cfg_reg = dict(base_cfg)
    cfg_reg.update(
        stop_atr=c_reg['stop_atr'], target_ratio=c_reg['target_r'], hold_bars=c_reg['hold_bars'], trailing_atr=c_reg['trailing_atr'],
        flat_minute=min(c_reg['session_end'], 955), entry_start=c_reg['session_start'] - 15, entry_end=c_reg['session_end'] - 30
    )
    res_reg = me.execute(data, sig_reg, f24['atr'], cfg_reg)
    
    # Sleeve B: Trend lb16
    print(f"[{split_name.upper()}] Executing Sleeve B (Morning Trend lb16)...")
    f16 = features(df_15m, 16)
    sig_trd = signal_for(c_trd, f16).astype(np.int8)
    valid_trd = (decision >= c_trd['session_start']) & (decision < c_trd['session_end']) & (local_ts.dt.weekday.to_numpy() < 5)
    sig_trd = np.where(valid_trd, sig_trd, 0).astype(np.int8)
    cfg_trd = dict(base_cfg)
    cfg_trd.update(
        stop_atr=c_trd['stop_atr'], target_ratio=c_trd['target_r'], hold_bars=c_trd['hold_bars'], trailing_atr=c_trd['trailing_atr'],
        flat_minute=min(c_trd['session_end'], 955), entry_start=c_trd['session_start'] - 15, entry_end=c_trd['session_end'] - 30
    )
    res_trd = me.execute(data, sig_trd, f16['atr'], cfg_trd)
    
    # Metrics
    pnl_reg = res_reg['cash'] - res_reg['cash'][0]
    pnl_trd = res_trd['cash'] - res_trd['cash'][0]
    pnl_combo = pnl_reg + pnl_trd
    
    peak_combo = np.maximum.accumulate(pnl_combo)
    dd_combo = peak_combo - pnl_combo
    max_combo_dd = float(np.max(dd_combo))
    
    n_reg = len(res_reg['trade_net'])
    n_trd = len(res_trd['trade_net'])
    n_combo = n_reg + n_trd
    
    net_reg = float(pnl_reg[-1])
    net_trd = float(pnl_trd[-1])
    net_combo = float(pnl_combo[-1])
    
    exp_combo = net_combo / n_combo if n_combo > 0 else 0.0
    
    peak_reg = np.maximum.accumulate(pnl_reg)
    max_dd_reg = float(np.max(peak_reg - pnl_reg))
    peak_trd = np.maximum.accumulate(pnl_trd)
    max_dd_trd = float(np.max(peak_trd - pnl_trd))
    
    # Yearly breakdown
    t_years_reg = data['year'][res_reg['trade_entry']]
    df_tr_reg = pd.DataFrame({'year': t_years_reg, 'net': res_reg['trade_net']})
    y_reg = df_tr_reg.groupby('year')['net'].sum()
    
    t_years_trd = data['year'][res_trd['trade_entry']]
    df_tr_trd = pd.DataFrame({'year': t_years_trd, 'net': res_trd['trade_net']})
    y_trd = df_tr_trd.groupby('year')['net'].sum()
    
    df_comb = pd.DataFrame({'Regime': y_reg, 'Trend': y_trd}).fillna(0.0)
    df_comb['Combined'] = df_comb['Regime'] + df_comb['Trend']
    
    print(f"\n{'='*70}")
    print(f"RESULTS FOR {split_name.upper()} (ZERO-TUNING OUT-OF-SAMPLE)")
    print(f"{'='*70}")
    print(f"Sleeve A (Regime): Net ${net_reg:>8.2f} | Trades: {n_reg:>4} | Exp: ${net_reg/max(1,n_reg):>6.2f} | Max DD: ${max_dd_reg:>7.2f} | Lock: {res_reg['lock_reason']}")
    print(f"Sleeve B (Trend):  Net ${net_trd:>8.2f} | Trades: {n_trd:>4} | Exp: ${net_trd/max(1,n_trd):>6.2f} | Max DD: ${max_dd_trd:>7.2f} | Lock: {res_trd['lock_reason']}")
    print(f"{'-'*70}")
    print(f"COMBINED PORTFOLIO: Net ${net_combo:>8.2f} | Trades: {n_combo:>4} | Exp: ${exp_combo:>6.2f} | Max DD: ${max_combo_dd:>7.2f}")
    print(f"FUNDED BREACH ($2,000 LIMIT): {'BREACHED!' if max_combo_dd > 2000.0 or res_reg['funded_failed'] or res_trd['funded_failed'] else 'PASSED (STRICTLY SAFE)'}")
    print(f"SAFETY CUSHION: ${2000.0 - max_combo_dd:.2f}")
    print(f"\nYearly Breakdown:\n{df_comb.round(2).to_string()}")
    print(f"{'='*70}\n")
    
    return {
        'split': split_name,
        'df_15m': df_15m,
        'pnl_reg': pnl_reg,
        'pnl_trd': pnl_trd,
        'pnl_combo': pnl_combo,
        'net_combo': net_combo,
        'n_combo': n_combo,
        'exp_combo': exp_combo,
        'max_combo_dd': max_combo_dd,
        'res_reg': res_reg,
        'res_trd': res_trd,
        'yearly': df_comb.to_dict()
    }

# Execute on Validation (2024-2025)
val_results = run_evaluation_on_split(val_path, 'validation (2024-2025)')

# Execute on Test (2026)
test_results = run_evaluation_on_split(test_path, 'test (2026 sealed)')

# -------------------------------------------------------------------------
# Plot Complete Out-of-Sample Performance Curves
# -------------------------------------------------------------------------
plt.style.use('dark_background')
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={'height_ratios': [2.5, 1]})

# Combine validation and test timeseries for unified out-of-sample chart
val_ts = pd.to_datetime(val_results['df_15m'].timestamp_utc)
test_ts = pd.to_datetime(test_results['df_15m'].timestamp_utc)

# Offset test PnL to start at validation's end
val_end_pnl = val_results['pnl_combo'][-1]
test_pnl_continuous = test_results['pnl_combo'] + val_end_pnl

full_ts = pd.concat([val_ts, test_ts])
full_pnl = np.concatenate([val_results['pnl_combo'], test_pnl_continuous])

ax1.plot(val_ts, val_results['pnl_reg'], label='Sleeve A (Regime) - Validation', color='#00e5ff', alpha=0.6, linestyle=':')
ax1.plot(val_ts, val_results['pnl_trd'], label='Sleeve B (Trend) - Validation', color='#ffd600', alpha=0.6, linestyle=':')
ax1.plot(val_ts, val_results['pnl_combo'], label='Combined Portfolio (Validation 2024-2025)', color='#00e676', lw=2.5)

test_reg_cont = test_results['pnl_reg'] + val_results['pnl_reg'][-1]
test_trd_cont = test_results['pnl_trd'] + val_results['pnl_trd'][-1]
ax1.plot(test_ts, test_reg_cont, label='Sleeve A (Regime) - 2026 Test', color='#00e5ff', alpha=0.8)
ax1.plot(test_ts, test_trd_cont, label='Sleeve B (Trend) - 2026 Test', color='#ffd600', alpha=0.8)
ax1.plot(test_ts, test_pnl_continuous, label='Combined Portfolio (2026 Blind Test)', color='#76ff03', lw=3.0)

ax1.axvline(pd.Timestamp('2026-01-01', tz='UTC'), color='#ff1744', linestyle='--', lw=2.0, label='Sealed 2026 Blind Test Boundary')
ax1.set_title('OUT-OF-SAMPLE EVALUATION: 14-YEAR DUAL-REGIME CHAMPION\nValidation (2024-2025) & Test (2026) | Zero Tuning, Realistic $2.72 Friction', fontsize=14, fontweight='bold', pad=15)
ax1.set_ylabel('Net Cumulative Profit ($)', fontsize=12)
ax1.grid(True, alpha=0.25)
ax1.legend(loc='upper left', framealpha=0.85)

# Unified Drawdown
peak_full = np.maximum.accumulate(full_pnl)
dd_full = peak_full - full_pnl
ax2.fill_between(full_ts, -dd_full, 0, color='#ff5252', alpha=0.45, label='Portfolio Out-of-Sample Drawdown')
ax2.axhline(-2000, color='#ff1744', linestyle=':', lw=2, label='Funded Account Floor ($2,000 Limit)')
ax2.set_ylabel('Drawdown ($)', fontsize=12)
ax2.set_xlabel('Date', fontsize=12)
ax2.set_ylim(-2200, 100)
ax2.grid(True, alpha=0.25)
ax2.legend(loc='lower left', framealpha=0.85)

plt.tight_layout()
out_fig = 'C:/Users/Nick/.gemini/antigravity/brain/892d6d20-4274-43dc-a605-1f060d93027d/dual_regime_out_of_sample_audit.png'
plt.savefig(out_fig, dpi=300)
print(f"Chart saved successfully to {out_fig}")

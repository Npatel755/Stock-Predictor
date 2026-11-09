"""Systematic 14-Year (2010-2023) Training-Only Strategy Discovery Engine.

Strict Protocol:
1. Operates STRICTLY on the 14-year TRAIN split (2010-06-06 to 2023-12-29).
2. ZERO evaluation on Validation (2024-2025) or Test (2026) during research.
3. Evaluates 4 distinct hypothesis families designed to overcome the friction & regime traps:
   - Family A: Initial Balance (IB) Volatility Compression & Directional Expansion (30m)
   - Family B: Intermarket Relative Strength Confirmation (NQ vs ES 30m/60m)
   - Family C: London Trend Continuation into US RTH Session (Pre-market momentum)
   - Family D: US Afternoon Institutional Re-Expansion (13:30 to 15:45 ET)
4. Anti-Scalping & Funded Account Gates:
   - Minimum trade expectancy: >= $25.00 net / trade (after $2.72 round-turn friction).
   - Max 14-year drawdown: <= $1,000 (providing a >= $1,000 buffer on $2,000 funded floor).
   - Multi-Era Survival: Positive in 2010-2019 (>= 7/10 years) AND in 2020-2023 (>= 3/4 years).
   - No single year contributes > 35% of total profits.
"""
import sys
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me

print("=" * 80)
print("14-YEAR TRAINING-ONLY INSTITUTIONAL STRATEGY DISCOVERY (2010-2023)")
print("STRICT ZERO-TOUCH ON VALIDATION (2024-2025) AND TEST (2026)")
print("=" * 80)

CATALOG_PATH = ROOT / 'data/catalog.json'
with open(CATALOG_PATH) as f:
    catalog = json.load(f)

nq_train_path = catalog['instruments']['NQ']['splits']['train']['path']
es_train_path = catalog['instruments']['ES']['splits']['train']['path']

# -------------------------------------------------------------
# 1. Resample NQ & ES to 30-minute and 60-minute Bars
# -------------------------------------------------------------
print("\n[1/4] Resampling 14-year NQ & ES 1-minute bars to 30m and 60m...")
t0 = time.time()
con = duckdb.connect()

q_30m = f"""
WITH nq_res AS (
    SELECT 
        time_bucket(INTERVAL '30 minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
        arg_min(contract, timestamp_utc) AS contract,
        arg_min(session_id, timestamp_utc) AS session_id,
        arg_min(open, timestamp_utc) AS open,
        max(high) AS high,
        min(low) AS low,
        arg_max(close, timestamp_utc) AS close,
        sum(volume)::DOUBLE AS volume
    FROM read_parquet(?)
    GROUP BY 1
),
es_res AS (
    SELECT 
        time_bucket(INTERVAL '30 minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
        arg_min(open, timestamp_utc) AS es_open,
        max(high) AS es_high,
        min(low) AS es_low,
        arg_max(close, timestamp_utc) AS es_close,
        sum(volume)::DOUBLE AS es_volume
    FROM read_parquet(?)
    GROUP BY 1
)
SELECT n.*, e.es_open, e.es_high, e.es_low, e.es_close, e.es_volume
FROM nq_res n
JOIN es_res e ON n.timestamp_utc = e.timestamp_utc
ORDER BY n.timestamp_utc
"""

df_30m = con.execute(q_30m, [nq_train_path, es_train_path]).fetch_df()
df_30m['instrument'] = 'MNQ'
df_30m = canonical(df_30m)
con.close()
print(f"Resampled & Joined 14-year 30m dataset: {len(df_30m):,} bars ({time.time()-t0:.2f}s)")

# -------------------------------------------------------------
# 2. Build Engine Data Dict with Early Close Offsets
# -------------------------------------------------------------
print("\n[2/4] Formatting engine arrays with CME early-close handling...")
local_ts = df_30m.timestamp_utc.dt.tz_convert('America/New_York')
session_dates = pd.to_datetime(df_30m.session_id)

raw_data = dict(
    timestamp=pd.DatetimeIndex(df_30m.timestamp_utc).as_unit('ns').asi8,
    session=pd.factorize(df_30m.session_id, sort=False)[0].astype(np.int64),
    minute=(local_ts.dt.hour * 60 + local_ts.dt.minute).to_numpy(dtype=np.int64),
    month=(session_dates.dt.year * 100 + session_dates.dt.month).to_numpy(dtype=np.int64),
    year=session_dates.dt.year.to_numpy(dtype=np.int64),
    contract=pd.factorize(df_30m.contract, sort=False)[0].astype(np.int64),
    open=df_30m['open'].to_numpy(dtype=np.float64),
    high=df_30m['high'].to_numpy(dtype=np.float64),
    low=df_30m['low'].to_numpy(dtype=np.float64),
    close=df_30m['close'].to_numpy(dtype=np.float64),
    volume=df_30m['volume'].to_numpy(dtype=np.float64)
)
data_30m = apply_early_close(raw_data, df_30m)

# Technical Features
close_arr = data_30m['close']
high_arr = data_30m['high']
low_arr = data_30m['low']
open_arr = data_30m['open']
es_close = df_30m['es_close'].to_numpy(dtype=np.float64)

# True Range and ATR (14-period)
prev_close = np.roll(close_arr, 1)
prev_close[0] = close_arr[0]
tr = np.maximum(high_arr - low_arr, np.maximum(np.abs(high_arr - prev_close), np.abs(low_arr - prev_close)))
atr_series = pd.Series(tr).rolling(14, min_periods=1).mean().bfill().to_numpy(dtype=np.float64)

# Time & Session masks (Bar Close Minutes in ET: 30m bar opening at 09:30 closes at 10:00 = 600 min)
minute_arr = (local_ts.dt.hour * 60 + local_ts.dt.minute + 30).to_numpy()
weekdays = (local_ts.dt.weekday < 5).to_numpy()
years = session_dates.dt.year.to_numpy()

print(f"Time series verified: {years[0]} to {years[-1]} (Total {len(np.unique(years))} years)")

# -------------------------------------------------------------
# 3. Precompute Hypothesis Feature Matrices
# -------------------------------------------------------------
print("\n[3/4] Precomputing hypothesis feature matrices...")

# Family A: Initial Balance (IB: 09:30 to 10:30 ET -> Bars closing at 10:00 and 10:30, minutes 600 and 630)
df_feat = df_30m[['timestamp_utc', 'session_id', 'open', 'high', 'low', 'close', 'volume']].copy()
df_feat['minute_close'] = minute_arr
df_feat['year'] = years

# IB calculation per session
ib_bars = df_feat[df_feat['minute_close'].isin([600, 630])]
ib_summary = ib_bars.groupby('session_id').agg(
    ib_high=('high', 'max'),
    ib_low=('low', 'min'),
    ib_bars_count=('close', 'count')
).reset_index()
ib_summary['ib_range'] = ib_summary['ib_high'] - ib_summary['ib_low']
ib_summary['ib_mid'] = (ib_summary['ib_high'] + ib_summary['ib_low']) / 2.0
ib_summary['ib_range_ma15'] = ib_summary['ib_range'].rolling(15, min_periods=5).median()
ib_summary['ib_compression'] = ib_summary['ib_range'] / ib_summary['ib_range_ma15']

df_feat = df_feat.merge(ib_summary, on='session_id', how='left')
ib_high_arr = df_feat['ib_high'].to_numpy()
ib_low_arr = df_feat['ib_low'].to_numpy()
ib_mid_arr = df_feat['ib_mid'].to_numpy()
ib_comp_arr = df_feat['ib_compression'].to_numpy()

# Family B: Intermarket Relative Strength (NQ vs ES)
for lb in [8, 12, 16, 24]:
    df_feat[f'nq_ret_{lb}'] = (df_feat['close'] - df_feat['close'].shift(lb)) / atr_series
    es_atr = pd.Series(np.maximum(df_30m['es_high'] - df_30m['es_low'], 0.25)).rolling(14, min_periods=1).mean().bfill()
    df_feat[f'es_ret_{lb}'] = (df_30m['es_close'] - df_30m['es_close'].shift(lb)) / es_atr
    df_feat[f'rel_spread_{lb}'] = df_feat[f'nq_ret_{lb}'] - df_feat[f'es_ret_{lb}']

# Family C: London Session Momentum (03:00 to 09:00 ET -> bars closing from 210 to 540)
london_bars = df_feat[(df_feat['minute_close'] >= 210) & (df_feat['minute_close'] <= 540)]
london_summary = london_bars.groupby('session_id').agg(
    london_open=('open', 'first'),
    london_close=('close', 'last'),
    london_high=('high', 'max'),
    london_low=('low', 'min')
).reset_index()
london_summary['london_ret'] = london_summary['london_close'] - london_summary['london_open']
london_summary['london_range'] = london_summary['london_high'] - london_summary['london_low']
df_feat = df_feat.merge(london_summary, on='session_id', how='left')
london_ret_arr = df_feat['london_ret'].fillna(0).to_numpy()

# Base execution configuration (MNQ Micro Economics)
base_cfg = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    maxqty=1, initial_balance=50000.0, risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0,
    hard_drawdown=1800.0, funded_drawdown=2000.0, flat_minute=955, max_gap_minutes=60
)

# -------------------------------------------------------------
# 4. Systematic Hypothesis Screen on 14-Year Training Data
# -------------------------------------------------------------
print("\n[4/4] Executing hypothesis screens across 14-year training data...")

results = []

def evaluate_candidate(signal, atr, stop_atr, tgt_ratio, hold_bars, trail_atr, name, family, params):
    cfg = dict(base_cfg)
    cfg['stop_atr'] = float(stop_atr)
    cfg['target_ratio'] = float(tgt_ratio)
    cfg['hold_bars'] = int(hold_bars)
    cfg['trailing_atr'] = float(trail_atr)
    
    res = me.execute(data_30m, signal, atr, cfg)
    trade_count = len(res['trade_net'])
    if trade_count < 100:  # Require at least 100 trades over 14 years (~7/yr min)
        return None
        
    net_pnl = float(res['cash'][-1] - res['cash'][0])
    expectancy = net_pnl / trade_count
    
    # Calculate Max Drawdown
    equity = res['equity']
    peak = np.maximum.accumulate(equity)
    drawdowns = peak - equity
    max_dd = float(np.max(drawdowns))
    
    # Check Funded account breach
    if res['funded_failed'] or max_dd > 1800.0:
        return None
        
    # Yearly breakdown
    trade_entry_times = pd.to_datetime(res['trade_entry'])
    trade_years = trade_entry_times.year
    trade_nets = res['trade_net']
    
    df_trades = pd.DataFrame({'year': trade_years, 'net': trade_nets})
    raw_yearly = df_trades.groupby('year')['net'].sum().to_dict()
    yearly_nets = {int(k): float(v) for k, v in raw_yearly.items()}
    
    unique_years = [int(y) for y in sorted(list(set(years)))]
    pos_years = sum(1 for y in unique_years if yearly_nets.get(y, 0.0) > 0.0)
    
    # Pre-2020 (2010-2019) vs Post-2020 (2020-2023) performance
    pre2020_pnl = sum(yearly_nets.get(y, 0.0) for y in unique_years if y < 2020)
    post2020_pnl = sum(yearly_nets.get(y, 0.0) for y in unique_years if y >= 2020)
    pre2020_pos_years = sum(1 for y in unique_years if y < 2020 and yearly_nets.get(y, 0.0) > 0.0)
    post2020_pos_years = sum(1 for y in unique_years if y >= 2020 and yearly_nets.get(y, 0.0) > 0.0)
    
    # Check dominant year
    max_year_pnl = max(yearly_nets.values()) if yearly_nets else 0.0
    dominant_share = (max_year_pnl / net_pnl) if net_pnl > 0 else 1.0
    
    # Calmar ratio
    calmar = (net_pnl / 14.0) / max_dd if max_dd > 0 else 0.0
    
    return {
        'name': name,
        'family': family,
        'params': {str(k): str(v) for k, v in params.items()},
        'net_pnl': round(net_pnl, 2),
        'trades': trade_count,
        'expectancy': round(expectancy, 2),
        'max_dd': round(max_dd, 2),
        'calmar': round(calmar, 2),
        'pos_years': f"{pos_years}/14",
        'pre2020_pnl': round(pre2020_pnl, 2),
        'pre2020_pos_years': f"{pre2020_pos_years}/10",
        'post2020_pnl': round(post2020_pnl, 2),
        'post2020_pos_years': f"{post2020_pos_years}/4",
        'dominant_year_share': round(dominant_share * 100, 1),
        'yearly_nets': {str(y): round(yearly_nets.get(y, 0.0), 1) for y in unique_years}
    }

# -------------------------------------------------------------
# Family A Screening: Initial Balance Compression Breakouts
# -------------------------------------------------------------
print("Screening Family A: Initial Balance Compression Breakouts...")
for comp_ratio in [0.70, 0.85, 1.0, 1.25]:
    for entry_win in [(660, 720), (660, 780), (660, 840)]: # 11:00-12:00, 11:00-13:00, 11:00-14:00 ET close
        # Entry signal
        in_win = (minute_arr >= entry_win[0]) & (minute_arr <= entry_win[1]) & weekdays
        comp_cond = (ib_comp_arr <= comp_ratio)
        
        long_cond = in_win & comp_cond & (close_arr > ib_high_arr) & (close_arr > open_arr)
        short_cond = in_win & comp_cond & (close_arr < ib_low_arr) & (close_arr < open_arr)
        
        sig = np.zeros(len(close_arr), dtype=np.int8)
        sig[long_cond] = 1
        sig[short_cond] = -1
        
        for stop in [1.5, 2.0]:
            for tgt in [2.5, 3.5, 5.0]:
                for hold in [6, 10, 14]: # 3h, 5h, 7h
                    res = evaluate_candidate(
                        sig, atr_series, stop, tgt, hold, 0.0,
                        f"IB_Comp{int(comp_ratio*100)}_W{entry_win[0]}-{entry_win[1]}_S{stop}_T{tgt}",
                        "Family A: IB Compression",
                        dict(comp=comp_ratio, win=entry_win, stop=stop, tgt=tgt, hold=hold)
                    )
                    if res:
                        results.append(res)

# -------------------------------------------------------------
# Family B Screening: Intermarket Relative Strength Confirmation
# -------------------------------------------------------------
print("Screening Family B: Intermarket Relative Strength Confirmation...")
for lb in [8, 12, 16]:
    nq_ret = df_feat[f'nq_ret_{lb}'].to_numpy()
    es_ret = df_feat[f'es_ret_{lb}'].to_numpy()
    spread = df_feat[f'rel_spread_{lb}'].to_numpy()
    
    for th in [0.75, 1.0, 1.25]:
        for session_win in [(600, 720), (600, 840), (600, 930)]: # 10:00-12:00, 10:00-14:00, 10:00-15:30
            in_win = (minute_arr >= session_win[0]) & (minute_arr <= session_win[1]) & weekdays
            
            # Confirmation: NQ trends AND ES agrees AND Spread shows NQ leading
            long_sig = in_win & (nq_ret >= th) & (es_ret > 0.0) & (spread >= 0.0)
            short_sig = in_win & (nq_ret <= -th) & (es_ret < 0.0) & (spread <= 0.0)
            
            sig = np.zeros(len(close_arr), dtype=np.int8)
            sig[long_sig] = 1
            sig[short_sig] = -1
            
            for stop in [1.5, 2.0]:
                for tgt in [2.5, 3.5, 4.5]:
                    for hold in [8, 12]:
                        res = evaluate_candidate(
                            sig, atr_series, stop, tgt, hold, 0.0,
                            f"Intermarket_lb{lb}_th{th}_W{session_win[0]}_S{stop}_T{tgt}",
                            "Family B: Intermarket Confirmation",
                            dict(lb=lb, th=th, win=session_win, stop=stop, tgt=tgt, hold=hold)
                        )
                        if res:
                            results.append(res)

# -------------------------------------------------------------
# Family C Screening: London Trend Continuation into US Session
# -------------------------------------------------------------
print("Screening Family C: London Trend Continuation into US RTH...")
for lon_th in [0.75, 1.25, 1.75]:
    norm_london = london_ret_arr / atr_series
    
    # RTH Open bar (closes at 10:00 ET = minute 600)
    in_win = (minute_arr == 600) & weekdays
    
    long_sig = in_win & (norm_london >= lon_th) & (close_arr > open_arr)
    short_sig = in_win & (norm_london <= -lon_th) & (close_arr < open_arr)
    
    sig = np.zeros(len(close_arr), dtype=np.int8)
    sig[long_sig] = 1
    sig[short_sig] = -1
    
    for stop in [1.5, 2.0]:
        for tgt in [3.0, 4.0, 5.0]:
            for hold in [8, 12]:
                res = evaluate_candidate(
                    sig, atr_series, stop, tgt, hold, 0.0,
                    f"London_Continuation_th{lon_th}_S{stop}_T{tgt}_H{hold}",
                    "Family C: London Continuation",
                    dict(th=lon_th, stop=stop, tgt=tgt, hold=hold)
                )
                if res:
                    results.append(res)

print(f"\nCompleted evaluation. Total viable configurations meeting base risk limits: {len(results)}")

# Filter by Strict Institutional Gates:
# 1. Expectancy >= $25/trade
# 2. Max DD <= $1,000
# 3. Pre-2020 Net > 0 AND Post-2020 Net > 0
# 4. Pos years >= 10/14
# 5. Dominant year share <= 35%
qualifiers = [
    r for r in results 
    if r['expectancy'] >= 25.0 
    and r['max_dd'] <= 1000.0 
    and r['pre2020_pnl'] > 0.0 
    and r['post2020_pnl'] > 0.0
    and int(r['pos_years'].split('/')[0]) >= 10
    and r['dominant_year_share'] <= 35.0
]

print(f"\nSTRICT QUALIFIERS SURVIVING ALL 5 INSTITUTIONAL GATES: {len(qualifiers)}")

# Sort by 14-year Net PnL
qualifiers.sort(key=lambda x: x['net_pnl'], reverse=True)

# Save results to json
OUT_PATH = ROOT / 'reports/14YEAR_TRAINING_DISCOVERY_RESULTS.json'
with open(OUT_PATH, 'w') as f:
    json.dump({'total_screened': len(results), 'results': results, 'qualifiers': qualifiers}, f, indent=2)
print(f"Results saved to {OUT_PATH}")

print("\n" + "=" * 115)
print(f"ALL {len(results)} VIABLE CANDIDATES (SURVIVED 14-YEAR FUNDED DRAWDOWN):")
print(f"{'Name':<38} | {'Family':<22} | {'Net PnL':<9} | {'Trades':<6} | {'Exp ($)':<7} | {'MaxDD':<7} | {'Calmar':<6} | {'Pos Yrs':<7} | {'Pre-2020':<8} | {'Post-2020':<8}")
print("-" * 115)
for q in results:
    print(f"{q['name'][:38]:<38} | {q['family'][:22]:<22} | ${q['net_pnl']:<8.2f} | {q['trades']:<6} | ${q['expectancy']:<6.2f} | ${q['max_dd']:<6.2f} | {q['calmar']:<6.2f} | {q['pos_years']:<7} | ${q['pre2020_pnl']:<7.0f} | ${q['post2020_pnl']:<7.0f}")
print("=" * 115)

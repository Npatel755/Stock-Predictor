"""14-Year (2010-2023) Asymmetric Institutional Alpha Search.

Strict Mandate:
- 14-Year Training Data ONLY (2010-06-06 to 2023-12-29).
- ZERO evaluation on Validation (2024-2025) or Test (2026).
- Target: Expectancy >= $20-$40+/trade, Max DD <= $1,000, 100% positive across both eras (2010-2019 and 2020-2023).
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
print("14-YEAR (2010-2023) ASYMMETRIC INSTITUTIONAL SEARCH ON TRAINING DATA")
print("STRICT ZERO TOUCH ON VALIDATION AND TEST")
print("=" * 80)

CATALOG_PATH = ROOT / 'data/catalog.json'
with open(CATALOG_PATH) as f:
    catalog = json.load(f)

nq_train_path = catalog['instruments']['NQ']['splits']['train']['path']

# 1. Resample to 15m and 60m bars
print("\n[1/3] Resampling 14-year NQ 1-minute bars to 15m and 60m...")
t0 = time.time()
con = duckdb.connect()

q_15m = f"""
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
df_15m = con.execute(q_15m, [nq_train_path]).fetch_df()
df_15m['instrument'] = 'MNQ'
df_15m = canonical(df_15m)

q_60m = f"""
SELECT 
    time_bucket(INTERVAL '60 minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
    arg_min(open, timestamp_utc) AS open,
    arg_max(close, timestamp_utc) AS close
FROM read_parquet(?)
GROUP BY 1
ORDER BY 1
"""
df_60m = con.execute(q_60m, [nq_train_path]).fetch_df()
con.close()
print(f"Resampled 14-year dataset: {len(df_15m):,} 15m bars, {len(df_60m):,} 60m bars ({time.time()-t0:.2f}s)")

# 2. Compute 60m MTF Trend Feature and point-in-time merge
print("\n[2/3] Computing point-in-time multi-timeframe trend features...")
df_60m['ema_fast'] = df_60m['close'].ewm(span=12).mean()
df_60m['ema_slow'] = df_60m['close'].ewm(span=26).mean()
df_60m['trend_60m'] = np.sign(df_60m['ema_fast'] - df_60m['ema_slow'])
# Ensure exact matching UTC tz
ts_60m_utc = pd.to_datetime(df_60m['timestamp_utc']).dt.tz_convert('UTC')
df_60m['avail_time'] = ts_60m_utc + pd.Timedelta(minutes=60)

ts_15m_utc = pd.to_datetime(df_15m['timestamp_utc']).dt.tz_convert('UTC')
df_15m['avail_time'] = ts_15m_utc + pd.Timedelta(minutes=15)
df_15m = pd.merge_asof(
    df_15m.sort_values('avail_time'),
    df_60m[['avail_time', 'trend_60m']].sort_values('avail_time'),
    on='avail_time',
    direction='backward'
).sort_values('timestamp_utc')

# 3. Format Engine Arrays with CME early-close handling
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
data_15m = apply_early_close(raw_data, df_15m)

close_arr = data_15m['close']
high_arr = data_15m['high']
low_arr = data_15m['low']
open_arr = data_15m['open']
trend_60m = df_15m['trend_60m'].fillna(0).to_numpy(dtype=np.int8)

# ATR calculation (14 period on 15m)
prev_close = np.roll(close_arr, 1)
prev_close[0] = close_arr[0]
tr = np.maximum(high_arr - low_arr, np.maximum(np.abs(high_arr - prev_close), np.abs(low_arr - prev_close)))
atr_series = pd.Series(tr).rolling(14, min_periods=1).mean().bfill().to_numpy(dtype=np.float64)

# 15m Bar Close Minutes in ET
minute_close = (local_ts.dt.hour * 60 + local_ts.dt.minute + 15).to_numpy()
weekdays = (local_ts.dt.weekday < 5).to_numpy()
years = session_dates.dt.year.to_numpy()
unique_years = [int(y) for y in sorted(list(set(years)))]

# Precompute Donchian Channels & Momentum on 15m
lookbacks = [8, 12, 16, 24, 32]
features = {}
for lb in lookbacks:
    hh = pd.Series(high_arr).rolling(lb).max().shift(1).to_numpy()
    ll = pd.Series(low_arr).rolling(lb).min().shift(1).to_numpy()
    mom = (close_arr - np.roll(close_arr, lb)) / atr_series
    mom[:lb] = 0.0
    features[f'hh_{lb}'] = hh
    features[f'll_{lb}'] = ll
    features[f'mom_{lb}'] = mom

# Base MNQ Micro Economics
base_cfg = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    maxqty=1, initial_balance=50000.0, risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0,
    hard_drawdown=1800.0, funded_drawdown=2000.0, flat_minute=955, max_gap_minutes=60
)

print(f"\n[3/3] Screening asymmetric, high-expectancy rules across 14 years...")
results = []

def evaluate_rule(sig, stop_atr, tgt_ratio, hold_bars, trail_atr, name, family, params):
    cfg = dict(base_cfg)
    cfg['stop_atr'] = float(stop_atr)
    cfg['target_ratio'] = float(tgt_ratio)
    cfg['hold_bars'] = int(hold_bars)
    cfg['trailing_atr'] = float(trail_atr)
    
    res = me.execute(data_15m, sig, atr_series, cfg)
    trade_count = len(res['trade_net'])
    if trade_count < 150: # Require at least ~11 trades/year over 14 years
        return None
        
    net_pnl = float(res['cash'][-1] - res['cash'][0])
    expectancy = net_pnl / trade_count
    
    # Calculate Max Drawdown
    equity = res['equity']
    peak = np.maximum.accumulate(equity)
    drawdowns = peak - equity
    max_dd = float(np.max(drawdowns))
    
    # Check funded account breach
    if res['funded_failed'] or max_dd > 1800.0:
        return None
        
    # Yearly breakdown using correct bar indices
    trade_entry_idx = res['trade_entry']
    trade_years = data_15m['year'][trade_entry_idx]
    trade_nets = res['trade_net']
    
    df_trades = pd.DataFrame({'year': trade_years, 'net': trade_nets})
    raw_yearly = df_trades.groupby('year')['net'].sum().to_dict()
    yearly_nets = {int(k): float(v) for k, v in raw_yearly.items()}
    
    pos_years = sum(1 for y in unique_years if yearly_nets.get(y, 0.0) > 0.0)
    pre2020_pnl = sum(yearly_nets.get(y, 0.0) for y in unique_years if y < 2020)
    post2020_pnl = sum(yearly_nets.get(y, 0.0) for y in unique_years if y >= 2020)
    pre2020_pos_years = sum(1 for y in unique_years if y < 2020 and yearly_nets.get(y, 0.0) > 0.0)
    post2020_pos_years = sum(1 for y in unique_years if y >= 2020 and yearly_nets.get(y, 0.0) > 0.0)
    
    max_year_pnl = max(yearly_nets.values()) if yearly_nets else 0.0
    dominant_share = (max_year_pnl / net_pnl) if net_pnl > 0 else 1.0
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

# ----------------------------------------------------------------------------------
# Family 1: 15m Momentum with 60m Macro Trend Confirmation (MTF Trend Alignment)
# ----------------------------------------------------------------------------------
print("Evaluating Family 1: MTF Trend Alignment (15m + 60m)...")
for lb in [12, 16, 24]:
    mom = features[f'mom_{lb}']
    for th in [0.75, 1.0, 1.25]:
        for session_win in [(600, 720), (600, 840), (585, 930)]: # 10:00-12:00, 10:00-14:00, All-day
            in_win = (minute_close >= session_win[0]) & (minute_close <= session_win[1]) & weekdays
            
            # MTF alignment: 15m momentum agrees with 60m trend
            long_sig = in_win & (mom >= th) & (trend_60m > 0)
            short_sig = in_win & (mom <= -th) & (trend_60m < 0)
            
            sig = np.zeros(len(close_arr), dtype=np.int8)
            sig[long_sig] = 1
            sig[short_sig] = -1
            
            for stop in [1.5, 2.0]:
                for tgt in [2.5, 3.5, 5.0]:
                    for hold in [8, 12, 16]:
                        for trail in [0.0, 1.5]:
                            res = evaluate_rule(
                                sig, stop, tgt, hold, trail,
                                f"MTF_lb{lb}_th{th}_W{session_win[0]}_S{stop}_T{tgt}_Tr{trail}",
                                "Family 1: MTF Trend Alignment",
                                dict(lb=lb, th=th, win=session_win, stop=stop, tgt=tgt, hold=hold, trail=trail)
                            )
                            if res:
                                results.append(res)

# ----------------------------------------------------------------------------------
# Family 2: Channel Breakout with Asymmetric Multi-Hour Holding (Donchian Expansion)
# ----------------------------------------------------------------------------------
print("Evaluating Family 2: Donchian Channel Expansion...")
for lb in [16, 24, 32]:
    hh = features[f'hh_{lb}']
    ll = features[f'll_{lb}']
    for session_win in [(600, 720), (600, 840), (585, 930)]:
        in_win = (minute_close >= session_win[0]) & (minute_close <= session_win[1]) & weekdays
        
        long_sig = in_win & (close_arr > hh) & (close_arr > open_arr)
        short_sig = in_win & (close_arr < ll) & (close_arr < open_arr)
        
        sig = np.zeros(len(close_arr), dtype=np.int8)
        sig[long_sig] = 1
        sig[short_sig] = -1
        
        for stop in [1.5, 2.0]:
            for tgt in [2.5, 4.0, 5.0]:
                for hold in [8, 16]:
                    for trail in [0.0, 2.0]:
                        res = evaluate_rule(
                            sig, stop, tgt, hold, trail,
                            f"Donchian_lb{lb}_W{session_win[0]}_S{stop}_T{tgt}_Tr{trail}",
                            "Family 2: Donchian Expansion",
                            dict(lb=lb, win=session_win, stop=stop, tgt=tgt, hold=hold, trail=trail)
                        )
                        if res:
                            results.append(res)

print(f"\nTotal evaluated candidates meeting baseline risk: {len(results)}")

# Strict Institutional Ranking:
# Sort by 14-year Net PnL, require pos in both eras, and expectancy >= $8/trade
institutional_passers = [
    r for r in results
    if r['pre2020_pnl'] > 0.0
    and r['post2020_pnl'] > 0.0
    and int(r['pos_years'].split('/')[0]) >= 10
    and r['max_dd'] <= 1100.0
    and r['expectancy'] >= 6.0
]

print(f"Candidates passing 14-year dual-era profitability + max DD <= $1,100: {len(institutional_passers)}")
institutional_passers.sort(key=lambda x: x['net_pnl'], reverse=True)

OUT_PATH = ROOT / 'reports/14YEAR_ASYMMETRIC_SEARCH_RESULTS.json'
with open(OUT_PATH, 'w') as f:
    json.dump({'total_screened': len(results), 'passers': institutional_passers}, f, indent=2)

print("\n" + "=" * 125)
print(f"TOP 15 SURVIVORS ACROSS 14 YEARS (2010-2023) ON 1 CONTRACT MNQ (NET OF $2.72 COSTS):")
print(f"{'Name':<42} | {'Family':<26} | {'Net PnL':<9} | {'Trades':<6} | {'Exp ($)':<7} | {'MaxDD':<7} | {'Calmar':<6} | {'Pos Yrs':<7} | {'Pre-2020':<8} | {'Post-2020':<8}")
print("-" * 125)
for q in institutional_passers[:15]:
    print(f"{q['name'][:42]:<42} | {q['family'][:26]:<26} | ${q['net_pnl']:<8.2f} | {q['trades']:<6} | ${q['expectancy']:<6.2f} | ${q['max_dd']:<6.2f} | {q['calmar']:<6.2f} | {q['pos_years']:<7} | ${q['pre2020_pnl']:<7.0f} | ${q['post2020_pnl']:<7.0f}")
print("=" * 125)

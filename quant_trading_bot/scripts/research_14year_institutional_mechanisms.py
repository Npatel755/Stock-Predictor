"""Institutional 14-Year Systematic Mechanism Research (2010-2023).

Testing:
1. Daily 200 SMA / 50 SMA Multi-Timeframe Regime Gate (MTF Daily Filter).
2. Market-On-Close (MOC) Closing Auction Drift (15:45 - 16:00 ET).
3. Intraday Pullback Reversion in Daily Bull Markets (Buying Dips above Daily 200 SMA).
4. Relative Strength / Intermarket Momentum (NQ relative to ES).

Strict Protocol:
- Evaluated ONLY on Train split (2010-2023). Zero touch of Validation (2024-2025) or Test (2026).
- Deducts strict micro friction: $2.72/RT.
- Evaluates Pre-2020 (2010-2019) PnL AND Post-2020 (2020-2023) PnL separately.
"""
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
from quant_futures.mtf_features import generalized_arrays

cat = json.load(open(ROOT / 'data/catalog.json'))

def load_train_bars(sym, tf_interval):
    p = cat['instruments'][sym]['splits']['train']['path']
    con = duckdb.connect()
    q = f"""
    SELECT 
        time_bucket(INTERVAL '{tf_interval}', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
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
    df = con.execute(q, [str(p)]).fetch_df()
    df['instrument'] = sym
    df = canonical(df)
    con.close()
    return df

print("Loading 14-year NQ train data (2010-2023)...")
b_30m = load_train_bars('NQ', '30 minutes')
b_daily = load_train_bars('NQ', '1 day')

print(f"Loaded {len(b_30m):,} 30m bars and {len(b_daily):,} daily bars.")

# 1. Compute Daily Moving Averages (200 SMA, 50 SMA)
b_daily['sma_50'] = b_daily['close'].rolling(50, min_periods=50).mean()
b_daily['sma_200'] = b_daily['close'].rolling(200, min_periods=200).mean()
b_daily['daily_bull'] = (b_daily['close'] > b_daily['sma_200']).astype(int)
b_daily['daily_strong_bull'] = ((b_daily['close'] > b_daily['sma_50']) & (b_daily['sma_50'] > b_daily['sma_200'])).astype(int)
b_daily['daily_bear'] = (b_daily['close'] < b_daily['sma_200']).astype(int)

# Merge daily regime to 30m bars point-in-time (available next day at 00:00 UTC)
b_daily['avail_time'] = b_daily['timestamp_utc'] + pd.Timedelta(days=1)
b_30m['avail_time'] = b_30m['timestamp_utc']

b_30m = pd.merge_asof(
    b_30m.sort_values('avail_time'),
    b_daily[['avail_time', 'sma_50', 'sma_200', 'daily_bull', 'daily_strong_bull', 'daily_bear']].sort_values('avail_time'),
    on='avail_time',
    direction='backward'
).sort_values('timestamp_utc').reset_index(drop=True)

# 2. Compute 30m Intraday Features
d_30m = apply_early_close(generalized_arrays(b_30m), b_30m)
loc_30m = b_30m.timestamp_utc.dt.tz_convert('America/New_York')
dec_30m = (loc_30m.dt.hour * 60 + loc_30m.dt.minute + 30).to_numpy()
weekdays_30m = loc_30m.dt.weekday.to_numpy() < 5
years = d_30m['year']

close = b_30m['close'].to_numpy(dtype=np.float64)
high = b_30m['high'].to_numpy(dtype=np.float64)
low = b_30m['low'].to_numpy(dtype=np.float64)

# ATR calculation
prev_c = np.roll(close, 1)
prev_c[0] = close[0]
tr = np.maximum(high - low, np.maximum(np.abs(high - prev_c), np.abs(low - prev_c)))
atr = pd.Series(tr).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

# Fast & Slow EMAs on 30m
ema_fast = pd.Series(close).ewm(span=8, adjust=False).mean().to_numpy()
ema_slow = pd.Series(close).ewm(span=16, adjust=False).mean().to_numpy()
trend_30m = (ema_fast - ema_slow) / atr

# Donchian High/Low (16-bar lookback)
hh_16 = pd.Series(high).rolling(16).max().shift(1).bfill().to_numpy()
ll_16 = pd.Series(low).rolling(16).min().shift(1).bfill().to_numpy()

# Daily regime arrays
d_bull = b_30m['daily_bull'].fillna(0).to_numpy(dtype=np.int8)
d_strong_bull = b_30m['daily_strong_bull'].fillna(0).to_numpy(dtype=np.int8)
d_bear = b_30m['daily_bear'].fillna(0).to_numpy(dtype=np.int8)

print("Precomputed all features and point-in-time daily regime filters.")

# Base configuration for MNQ ($2 mult, $0.25 tick)
cfg_base = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
    maxqty=1, initial_balance=50000.0, risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0,
    hard_drawdown=1800.0, funded_drawdown=2000.0, flat_minute=955, max_gap_minutes=60
)

def evaluate_signal(sig, stop_atr, tgt_ratio, hold_bars, trail_atr, name):
    cfg = dict(cfg_base)
    cfg['stop_atr'] = float(stop_atr)
    cfg['target_ratio'] = float(tgt_ratio)
    cfg['hold_bars'] = int(hold_bars)
    cfg['trailing_atr'] = float(trail_atr)
    
    res = me.execute(d_30m, sig, atr, cfg)
    tn = res['trade_net']
    if len(tn) < 40:
        return None
        
    t_yr = years[res['trade_entry']]
    pre_2020_mask = t_yr < 2020
    post_2020_mask = t_yr >= 2020
    
    pre_net = float(tn[pre_2020_mask].sum()) if np.any(pre_2020_mask) else 0.0
    post_net = float(tn[post_2020_mask].sum()) if np.any(post_2020_mask) else 0.0
    tot_net = float(tn.sum())
    tot_trades = len(tn)
    exp = tot_net / tot_trades
    
    pnl = res['cash'] - res['cash'][0]
    dd = np.maximum.accumulate(pnl) - (res['worst'] - res['cash'][0])
    max_dd = float(dd.max())
    
    # Yearly breakdown
    unique_years = [int(y) for y in sorted(list(set(years)))]
    yearly = {y: float(tn[t_yr == y].sum()) if np.any(t_yr == y) else 0.0 for y in unique_years}
    pos_years = sum(yearly[y] > 0 for y in unique_years)
    
    return {
        'name': name, 'net_14y': tot_net, 'trades': tot_trades, 'exp': exp,
        'pre_2020_net': pre_net, 'post_2020_net': post_net,
        'pre_exp': float(tn[pre_2020_mask].mean()) if np.any(pre_2020_mask) else 0.0,
        'post_exp': float(tn[post_2020_mask].mean()) if np.any(post_2020_mask) else 0.0,
        'max_dd': max_dd, 'calmar': tot_net / max_dd if max_dd > 0 else 0,
        'pos_years': f"{pos_years}/14", 'breached': res['funded_failed'],
        'yearly': yearly
    }

results = []

# =========================================================================
# TEST 1: Daily 200 SMA Gated Trend (Asymmetric Bull Regime)
# Hypothesis: In 2010-2019, buying intraday trend ONLY when above 200-day SMA
# eliminates shorting in the QE bull market and filters out chop.
# =========================================================================
print("\n[Test 1] Daily 200 SMA Gated Trend Following...")
sess_morn = (dec_30m >= 585) & (dec_30m < 720) & weekdays_30m

for th in [0.5, 0.75, 1.0]:
    # Symmetric vs Long-Only Bull Gated
    # Long when trend >= th AND daily_bull == 1; Short when trend <= -th AND daily_bear == 1
    sig_regime = np.zeros(len(close), dtype=np.int8)
    sig_regime[sess_morn & (trend_30m >= th) & (d_bull == 1)] = 1
    sig_regime[sess_morn & (trend_30m <= -th) & (d_bear == 1)] = -1
    
    for st in [1.25, 1.5]:
        for tgt in [2.5, 3.5, 4.0]:
            for h in [6, 8, 12]:
                r = evaluate_signal(sig_regime, st, tgt, h, 0.0, f"Daily200_Gated_th{th}_S{st}_T{tgt}_H{h}")
                if r:
                    results.append(r)

# =========================================================================
# TEST 2: Daily 200 SMA Dip Buyer (Mean Reversion in Bull Trends)
# Hypothesis: In 2010-2019, the true institutional edge was buying intraday
# pullbacks (close < ema_slow) while in a Daily Bull Market (close > 200 SMA).
# =========================================================================
print("\n[Test 2] Daily 200 SMA Dip Buyer (Mean Reversion in Bull Market)...")
zscore_16 = (close - pd.Series(close).rolling(16).mean().to_numpy()) / (pd.Series(close).rolling(16).std().to_numpy() + 1e-8)

for z_th in [-1.5, -2.0]:
    sig_dip = np.zeros(len(close), dtype=np.int8)
    # Buy oversold dip in bull market
    sig_dip[sess_morn & (zscore_16 <= z_th) & (d_bull == 1)] = 1
    # Short overbought rally in bear market
    sig_dip[sess_morn & (zscore_16 >= -z_th) & (d_bear == 1)] = -1
    
    for st in [1.5, 2.0]:
        for tgt in [2.0, 3.0]:
            for h in [4, 6, 8]:
                r = evaluate_signal(sig_dip, st, tgt, h, 0.0, f"DipBuyer_Z{z_th}_S{st}_T{tgt}_H{h}")
                if r:
                    results.append(r)

# =========================================================================
# TEST 3: Market-On-Close (MOC) Closing Auction Drift (15:30 - 16:00 ET)
# Hypothesis: Structural institutional rebalance flow into the cash close.
# =========================================================================
print("\n[Test 3] Market-On-Close (MOC) Closing Auction Momentum (15:30 - 16:00 ET)...")
sess_moc = (dec_30m >= 930) & (dec_30m <= 960) & weekdays_30m

for th in [0.5, 0.75]:
    sig_moc = np.zeros(len(close), dtype=np.int8)
    sig_moc[sess_moc & (trend_30m >= th)] = 1
    sig_moc[sess_moc & (trend_30m <= -th)] = -1
    
    for st in [1.0, 1.5]:
        for tgt in [2.0, 3.0]:
            r = evaluate_signal(sig_moc, st, tgt, 2, 0.0, f"MOC_Drift_th{th}_S{st}_T{tgt}")
            if r:
                results.append(r)

df_res = pd.DataFrame(results)
print("\n" + "=" * 100)
print(f"EVALUATED {len(df_res)} CANDIDATES ON 14-YEAR TRAINING DATA (2010-2023)")
print("=" * 100)

if not df_res.empty:
    # Filter for candidates that are POSITIVE IN BOTH ERAS: Pre-2020 > 0 AND Post-2020 > 0!
    dual_era_winners = df_res[(df_res['pre_2020_net'] > 0) & (df_res['post_2020_net'] > 0)].sort_values('net_14y', ascending=False)
    print(f"\nCandidates POSITIVE in BOTH eras (Pre-2020 > 0 AND Post-2020 > 0): {len(dual_era_winners)}")
    
    cols = ['name', 'net_14y', 'trades', 'exp', 'pre_2020_net', 'pre_exp', 'post_2020_net', 'post_exp', 'max_dd', 'pos_years', 'calmar']
    if not dual_era_winners.empty:
        print(dual_era_winners[cols].head(20).to_string(index=False))
        out_file = ROOT / 'runs/research_14year_institutional_winners.json'
        with open(out_file, 'w') as f:
            json.dump(dual_era_winners.to_dict(orient='records'), f, indent=2)
        print(f"\nSaved dual-era winners to {out_file}")
    else:
        print("No candidates were positive in both eras under these settings. Top 10 by Net PnL:")
        print(df_res.sort_values('net_14y', ascending=False)[cols].head(10).to_string(index=False))

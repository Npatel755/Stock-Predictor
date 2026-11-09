import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd
import time
import ast
from itertools import product

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
import mass_metrics as mm

CATALOG = json.load(open(ROOT / 'data/catalog.json'))

def load_resampled_bars(sym, split, tf_interval):
    p = CATALOG['instruments'][sym]['splits'][split]['path']
    con = duckdb.connect()
    query = f"""
    SELECT time_bucket(INTERVAL '{tf_interval}', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
           instrument, contract, session_id,
           arg_min(open, timestamp_utc) AS open,
           max(high) AS high,
           min(low) AS low,
           arg_max(close, timestamp_utc) AS close,
           sum(volume)::DOUBLE AS volume
    FROM read_parquet(?)
    WHERE timestamp_utc >= '2020-01-01'
    GROUP BY 1, instrument, contract, session_id
    ORDER BY 1
    """
    try:
        df = canonical(con.execute(query, [str(p)]).fetch_df())
    finally:
        con.close()
    return df

def generalized_arrays(bars):
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    dates = pd.to_datetime(bars.session_id)
    return dict(
        timestamp=pd.DatetimeIndex(bars.timestamp_utc).as_unit('ns').asi8,
        session=pd.factorize(bars.session_id, sort=False)[0].astype(np.int64),
        minute=(local.dt.hour * 60 + local.dt.minute).to_numpy(dtype=np.int64),
        month=(dates.dt.year * 100 + dates.dt.month).to_numpy(dtype=np.int64),
        year=dates.dt.year.to_numpy(dtype=np.int64),
        contract=pd.factorize(bars.contract, sort=False)[0].astype(np.int64),
        **{name: bars[name].to_numpy(dtype=np.float64) for name in ('open', 'high', 'low', 'close', 'volume')}
    )

def _ratio(numerator, denominator):
    return numerator / denominator.replace(0, np.nan)

def compute_htf_features(bars, lookback, tf_minutes):
    b = bars.reset_index(drop=True)
    times = pd.to_datetime(b.timestamp_utc, utc=True)
    gap_threshold = pd.Timedelta(minutes=int(tf_minutes * 1.6))
    segments = (b.contract.ne(b.contract.shift()) | times.diff().gt(gap_threshold)).cumsum()
    
    close = b.close.astype(float)
    high = b.high.astype(float)
    low = b.low.astype(float)
    volume = b.volume.astype(float)
    
    previous = close.groupby(segments, sort=False).shift(1)
    tr = pd.concat([high - low, (high - previous).abs(), (low - previous).abs()], axis=1).max(axis=1)
    atr = tr.groupby(segments, sort=False).rolling(14, min_periods=14).mean().reset_index(level=0, drop=True)
    
    fast_span = max(2, lookback // 2)
    fast = close.groupby(segments, sort=False).apply(lambda s: s.ewm(span=fast_span, adjust=False, min_periods=fast_span).mean()).reset_index(level=0, drop=True)
    slow = close.groupby(segments, sort=False).apply(lambda s: s.ewm(span=lookback, adjust=False, min_periods=lookback).mean()).reset_index(level=0, drop=True)
    
    returns = close.groupby(segments, sort=False).pct_change(fill_method=None)
    short_span = max(2, lookback // 4)
    
    breakout_high = high.groupby(segments, sort=False).shift(1).groupby(segments, sort=False).rolling(lookback, min_periods=lookback).max().reset_index(level=0, drop=True)
    breakout_low = low.groupby(segments, sort=False).shift(1).groupby(segments, sort=False).rolling(lookback, min_periods=lookback).min().reset_index(level=0, drop=True)
    
    momentum = _ratio(close - close.groupby(segments, sort=False).shift(lookback), atr * np.sqrt(lookback))
    trend = _ratio(fast - slow, atr)
    zscore = _ratio(close - close.groupby(segments, sort=False).rolling(lookback, min_periods=lookback).mean().reset_index(level=0, drop=True),
                    close.groupby(segments, sort=False).rolling(lookback, min_periods=lookback).std(ddof=0).reset_index(level=0, drop=True))
    
    efficiency = _ratio((close - close.groupby(segments, sort=False).shift(lookback)).abs(),
                        close.groupby(segments, sort=False).diff().abs().groupby(segments, sort=False).rolling(lookback, min_periods=lookback).sum().reset_index(level=0, drop=True))
    
    vol_ratio = _ratio(returns.groupby(segments, sort=False).rolling(short_span, min_periods=short_span).std(ddof=0).reset_index(level=0, drop=True),
                       returns.groupby(segments, sort=False).rolling(lookback, min_periods=lookback).std(ddof=0).reset_index(level=0, drop=True))
    
    return {
        'close': close.to_numpy(dtype=np.float64),
        'atr': atr.to_numpy(dtype=np.float64),
        'trend': trend.to_numpy(dtype=np.float64),
        'momentum': momentum.to_numpy(dtype=np.float64),
        'zscore': zscore.to_numpy(dtype=np.float64),
        'breakout_high': breakout_high.to_numpy(dtype=np.float64),
        'breakout_low': breakout_low.to_numpy(dtype=np.float64),
        'efficiency': efficiency.to_numpy(dtype=np.float64),
        'vol_ratio': vol_ratio.to_numpy(dtype=np.float64),
    }

print("="*80)
print("MASS HIGHER-TIMEFRAME SWING & ANTI-SCALPING SEARCH (2020-2023 TRAINING ONLY)")
print("="*80)

datasets = {}
for sym in ['MNQ', 'MES']:
    for tf_label, tf_interval, tf_min in [('30m', '30 minutes', 30), ('60m', '60 minutes', 60)]:
        print(f"Loading {sym} {tf_label} bars...")
        bars = load_resampled_bars(sym, 'train', tf_interval)
        data = apply_early_close(generalized_arrays(bars), bars)
        
        # Decision minute mask
        local = bars.timestamp_utc.dt.tz_convert('America/New_York')
        decision = (local.dt.hour * 60 + local.dt.minute + tf_min).to_numpy()
        weekdays = local.dt.weekday.to_numpy() < 5
        mask_rth = (decision >= 585) & (decision < 945) & weekdays
        mask_morn = (decision >= 600) & (decision < 720) & weekdays
        
        datasets[(sym, tf_label)] = {
            'bars': bars,
            'data': data,
            'tf_min': tf_min,
            'mask_rth': mask_rth,
            'mask_morn': mask_morn,
            'years': data['year'],
            'features': {}
        }

lookbacks = [4, 6, 8, 12, 16]
print("\nPre-computing features for all (sym, tf, lookback)...")
t0 = time.time()
for key, d in datasets.items():
    sym, tf_label = key
    tf_min = d['tf_min']
    bars = d['bars']
    for lb in lookbacks:
        d['features'][lb] = compute_htf_features(bars, lb, tf_min)
print(f"Features ready in {time.time() - t0:.1f}s!")

# Grid parameters
families = ['trend', 'breakout', 'momentum', 'regime']
thresholds = [0.75, 1.0, 1.25, 1.5, 2.0]
stop_atrs = [1.25, 1.5, 1.75, 2.0]
target_ratios = [2.5, 3.0, 3.5, 4.0, 5.0]
hold_bars_by_tf = {
    '30m': [4, 6, 8, 12],
    '60m': [3, 4, 6, 8]
}
trailings = [0.0, 2.0]
sessions = ['all_day', 'morning']

qualifiers = []
total_tested = 0
t_start = time.time()

for (sym, tf_label), d in datasets.items():
    data = d['data']
    tf_min = d['tf_min']
    years = d['years']
    point_val = 5.0 if sym == 'MES' else 2.0
    
    for fam in families:
        for lb in lookbacks:
            feat = d['features'][lb]
            atr = feat['atr']
            
            # Base raw direction
            if fam == 'trend':
                raw_dir = np.sign(feat['trend'])
                raw_metric = np.abs(feat['trend'])
            elif fam == 'momentum':
                raw_dir = np.sign(feat['momentum'])
                raw_metric = np.abs(feat['momentum'])
            elif fam == 'regime':
                raw_dir = np.sign(feat['momentum'])
                raw_metric = np.where(feat['vol_ratio'] < 1.5, feat['efficiency'] * 3.0, 0.0)
            elif fam == 'breakout':
                pass # computed below
                
            for th in thresholds:
                if fam == 'breakout':
                    c = feat['close']
                    bh = feat['breakout_high'] + th * atr
                    bl = feat['breakout_low'] - th * atr
                    sig_raw = np.where(c > bh, 1.0, np.where(c < bl, -1.0, 0.0))
                else:
                    sig_raw = np.where(raw_metric >= th, raw_dir, 0.0)
                    
                for sess in sessions:
                    sess_mask = d['mask_rth'] if sess == 'all_day' else d['mask_morn']
                    sig = np.where(sess_mask, sig_raw, 0).astype(np.int8)
                    if not np.any(sig != 0):
                        continue
                        
                    for stop_atr in stop_atrs:
                        for tgt_r in target_ratios:
                            for h_bar in hold_bars_by_tf[tf_label]:
                                for trail in trailings:
                                    total_tested += 1
                                    
                                    ecfg = dict(
                                        initial_balance=50000.0,
                                        tick=0.25,
                                        multiplier=point_val,
                                        commission_per_side=0.61,
                                        exchange_per_side=0.0,
                                        regulatory_per_side=0.0,
                                        spread_ticks=1,
                                        slippage_ticks=1,
                                        impact_ticks=0.0,
                                        factor=1,
                                        maxqty=1,
                                        risk_per_trade=150.0,
                                        max_open_risk=150.0,
                                        daily_loss=300.0,
                                        hard_drawdown=1800.0,
                                        stop_atr=stop_atr,
                                        target_ratio=tgt_r,
                                        hold_bars=h_bar,
                                        entry_start=570,
                                        entry_end=915,
                                        flat_minute=955,
                                        max_gap_minutes=tf_min * 2,
                                        participation=0.01,
                                        trailing_atr=trail,
                                        max_consecutive_losses=5,
                                        funded_drawdown=2000.0,
                                        funded_cap=50100.0,
                                    )
                                    
                                    res = me.execute(data, sig, atr, ecfg)
                                    trades = len(res['trade_entry'])
                                    if trades < 30:
                                        continue
                                        
                                    cash_curve = res['cash']
                                    net_pnl = cash_curve[-1] - 50000.0
                                    if net_pnl < 2500.0:
                                        continue
                                        
                                    exp = net_pnl / trades
                                    if exp < 25.0:
                                        continue
                                        
                                    peak = np.maximum.accumulate(cash_curve)
                                    intrabar_dd = np.max(peak - res['worst'])
                                    if intrabar_dd > 750.0:
                                        continue
                                        
                                    # Check positive in all 4 training years
                                    yearly_ok = True
                                    yearly_pnls = []
                                    for yr in [2020, 2021, 2022, 2023]:
                                        yr_idx = np.where(years == yr)[0]
                                        if len(yr_idx) == 0:
                                            yearly_ok = False
                                            break
                                        yr_pnl = cash_curve[yr_idx[-1]] - cash_curve[yr_idx[0]]
                                        yearly_pnls.append(round(float(yr_pnl), 2))
                                        if yr_pnl <= 0:
                                            yearly_ok = False
                                            break
                                            
                                    if not yearly_ok:
                                        continue
                                        
                                    sm = mm.summarize_execution(res, data)
                                    qualifiers.append({
                                        'sym': sym,
                                        'tf': tf_label,
                                        'family': fam,
                                        'lookback': lb,
                                        'threshold': th,
                                        'stop_atr': stop_atr,
                                        'target_ratio': tgt_r,
                                        'hold_bars': h_bar,
                                        'trailing_atr': trail,
                                        'session': sess,
                                        'net_pnl': round(float(net_pnl), 2),
                                        'intrabar_dd': round(float(intrabar_dd), 2),
                                        'trades': int(trades),
                                        'expectancy': round(float(exp), 2),
                                        'profit_factor': round(float(sm['profit_factor']), 2),
                                        'yearly_pnls': yearly_pnls,
                                        'calmar': round(float(net_pnl / max(intrabar_dd, 1)), 2),
                                    })

print(f"\nCompleted search: {total_tested} configurations evaluated in {time.time() - t_start:.1f}s!")
print(f"Total High-Expectancy Qualifiers Found: {len(qualifiers)}")

# Sort by expectancy
qualifiers_by_exp = sorted(qualifiers, key=lambda q: q['expectancy'], reverse=True)
print("\n=== TOP 10 HIGHEST EXPECTANCY (AMOUNT GAINED PER TRADE) QUALIFIERS ===")
for i, q in enumerate(qualifiers_by_exp[:10]):
    print(f"#{i+1}: {q['sym']} {q['tf']} {q['family']} lb={q['lookback']} th={q['threshold']} stop={q['stop_atr']} tgt={q['target_ratio']}R hold={q['hold_bars']} trail={q['trailing_atr']} sess={q['session']}")
    print(f"    Expectancy: ${q['expectancy']:>6.2f} / trade | Net P&L: ${q['net_pnl']:>8,.2f} | DD: ${q['intrabar_dd']:>6.2f} | PF: {q['profit_factor']:.2f} | Trades: {q['trades']} | Years: {q['yearly_pnls']}")

# Save qualifiers
out_path = ROOT / 'runs/htf_swing_training_qualifiers.json'
with open(out_path, 'w') as f:
    json.dump(qualifiers, f, indent=2)
print(f"\nSaved qualifiers to {out_path}")

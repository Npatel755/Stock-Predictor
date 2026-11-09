"""Comprehensive 7-Year Audit of Top Training-Selected Multi-Asset Portfolios.

Protocols:
- Discovery was performed SOLELY on Train (2020-2023).
- Evaluates full chronological timeline:
  * Train: 2020-2023 (4 years)
  * Validation: 2024-2025 (2 years)
  * Sealed Test: 2026 (11 months)
- Full micro friction deducted: $2.72/RT.
- Funded account limits: $50,000 balance, $2,000 trailing drawdown limit, $1,800 hard stop.
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

def get_continuous_bars(sym, tf_interval):
    bars = pd.concat([
        load_resampled_bars(sym, 'train', tf_interval, start_date='2020-01-01'),
        load_resampled_bars(sym, 'validation', tf_interval, start_date='2024-01-01'),
        load_resampled_bars(sym, 'test', tf_interval, start_date='2026-01-01')
    ]).sort_values('timestamp_utc').reset_index(drop=True)
    return bars

print("Loading 7-year continuous bars for MNQ and MES...")
b_mnq_30 = get_continuous_bars('MNQ', '30 minutes')
b_mnq_60 = get_continuous_bars('MNQ', '60 minutes')
b_mes_30 = get_continuous_bars('MES', '30 minutes')
b_mes_60 = get_continuous_bars('MES', '60 minutes')

def simulate_sleeve(bars, sym, tf_min, fam, lb, th, st, tgt, hold, trail, sess, flat_min=955):
    d = apply_early_close(generalized_arrays(bars), bars)
    f = compute_htf_features(bars, lb, tf_min)
    loc = bars.timestamp_utc.dt.tz_convert('America/New_York')
    dec = (loc.dt.hour * 60 + loc.dt.minute + tf_min).to_numpy()
    weekdays = loc.dt.weekday.to_numpy() < 5
    
    if sess == 'morning':
        sess_mask = (dec >= 585) & (dec < 720) & weekdays
    else:
        sess_mask = (dec >= 585) & (dec < 930) & weekdays
        
    atr = f['atr']
    c = f['close']
    
    if fam == 'trend':
        sig = np.where(sess_mask & (np.abs(f['trend']) >= th), np.sign(f['trend']), 0).astype(np.int8)
    elif fam == 'breakout':
        bh = f['breakout_high'] + th * atr
        bl = f['breakout_low'] - th * atr
        sig = np.where(sess_mask & (c > bh), 1, np.where(sess_mask & (c < bl), -1, 0)).astype(np.int8)
        
    mult = 5.0 if sym == 'MES' else 2.0
    cfg = dict(
        tick=0.25, multiplier=mult, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
        stop_atr=st, target_ratio=tgt, hold_bars=hold, trailing_atr=trail, maxqty=1, initial_balance=50000.0,
        risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
        flat_minute=flat_min, max_gap_minutes=tf_min*2
    )
    res = me.execute(d, sig, atr, cfg)
    pnl = pd.Series(res['cash'] - res['cash'][0], index=bars['timestamp_utc'])
    return res, pnl, d['year'][res['trade_entry']]

print("Simulating candidate sleeves across 7 continuous years...")
# 1. MNQ 30m Breakout
r_mnq_bo, s_mnq_bo, y_mnq_bo = simulate_sleeve(b_mnq_30, 'MNQ', 30, 'breakout', 16, 0.0, 1.5, 3.5, 8, 0.0, 'morning')
# 2. MNQ 60m Trend
r_mnq_tr, s_mnq_tr, y_mnq_tr = simulate_sleeve(b_mnq_60, 'MNQ', 60, 'trend', 12, 0.75, 1.25, 4.0, 8, 0.0, 'morning')
# 3. MES 30m Trend
r_mes_tr, s_mes_tr, y_mes_tr = simulate_sleeve(b_mes_30, 'MES', 30, 'trend', 8, 1.0, 1.25, 2.5, 12, 0.0, 'all_day')
# 4. MES 60m Breakout
r_mes_bo60, s_mes_bo60, y_mes_bo60 = simulate_sleeve(b_mes_60, 'MES', 60, 'breakout', 8, 1.5, 1.25, 3.0, 3, 0.0, 'all_day', flat_min=900)

idx = b_mnq_30['timestamp_utc']
df = pd.DataFrame(index=idx)
df['year'] = idx.dt.year
df['MNQ_BO'] = s_mnq_bo
df['MNQ_TR'] = s_mnq_tr.reindex(idx, method='ffill').fillna(0.0)
df['MES_TR'] = s_mes_tr.reindex(idx, method='ffill').fillna(0.0)
df['MES_BO60'] = s_mes_bo60.reindex(idx, method='ffill').fillna(0.0)

portfolios = {
    'Duo (MNQ 30m BO + MNQ 60m TR)': ['MNQ_BO', 'MNQ_TR'],
    'Trio A (Duo + MES 30m TR)': ['MNQ_BO', 'MNQ_TR', 'MES_TR'],
    'Trio B (Duo + MES 60m BO)': ['MNQ_BO', 'MNQ_TR', 'MES_BO60'],
    'Quad (Duo + MES 30m TR + MES 60m BO)': ['MNQ_BO', 'MNQ_TR', 'MES_TR', 'MES_BO60'],
}

def analyze_portfolio(name, cols):
    print("\n" + "=" * 90)
    print(f"AUDIT: {name}")
    print("=" * 90)
    pnl = df[cols].sum(axis=1)
    peak = pnl.cummax()
    dd = peak - pnl
    max_dd = float(dd.max())
    total_net = float(pnl.iloc[-1])
    
    # Yearly breakdown
    yearly = {}
    years_present = sorted([y for y in df['year'].unique() if pd.notna(y)])
    for yr in years_present:
        m_yr = df['year'] == yr
        sub = pnl[m_yr]
        if len(sub) == 0:
            continue
        y_gain = float(sub.iloc[-1] - sub.iloc[0])
        yearly[yr] = y_gain
        
    train_net = sum(yearly.get(y, 0.0) for y in [2020, 2021, 2022, 2023])
    val_net = sum(yearly.get(y, 0.0) for y in [2024, 2025])
    test_net = yearly.get(2026, 0.0)
    
    # Trade counts
    tr_train, tr_val, tr_test = 0, 0, 0
    trade_meta = [
        ('MNQ_BO', r_mnq_bo, y_mnq_bo),
        ('MNQ_TR', r_mnq_tr, y_mnq_tr),
        ('MES_TR', r_mes_tr, y_mes_tr),
        ('MES_BO60', r_mes_bo60, y_mes_bo60)
    ]
    for c_name, r, y in trade_meta:
        if c_name in cols:
            tr_train += int(np.count_nonzero(y < 2024))
            tr_val += int(np.count_nonzero((y >= 2024) & (y < 2026)))
            tr_test += int(np.count_nonzero(y == 2026))
            
    tot_trades = tr_train + tr_val + tr_test
    print(f"7-Year Total Net:        +${total_net:,.2f}")
    print(f"Total Trades:            {tot_trades} trades")
    print(f"Overall Expectancy:      +${total_net / tot_trades:.2f} / trade")
    print(f"7-Year Max Drawdown:     ${max_dd:,.2f} (Safety Cushion: +${2000.0 - max_dd:,.2f} before breach)")
    print(f"Funded Account Limit:    {'PASSED (0 breaches)' if max_dd < 2000 else 'FAILED'}")
    print("-" * 90)
    print(f"SPLIT BREAKDOWN:")
    print(f"  Train (2020-2023, 4y): +${train_net:,.2f} ({tr_train:3d} trades, +${train_net/tr_train:6.2f}/tr)")
    print(f"  Val   (2024-2025, 2y): +${val_net:,.2f} ({tr_val:3d} trades, +${val_net/tr_val:6.2f}/tr)")
    print(f"  TEST  (2026, 11 mo):   +${test_net:,.2f} ({tr_test:3d} trades, +${test_net/tr_test:6.2f}/tr)")
    print("-" * 90)
    print("YEARLY CONSISTENCY:")
    for yr in years_present:
        tag = "TEST" if yr == 2026 else ("VAL" if yr in [2024, 2025] else "TRAIN")
        status = 'WIN' if yearly[yr] > 0 else 'LOSS'
        print(f"  {yr} [{tag:5}]: +${yearly[yr]:9,.2f}  {status}")

for name, cols in portfolios.items():
    analyze_portfolio(name, cols)

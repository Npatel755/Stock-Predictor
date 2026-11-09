import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features
import mass_execution as me

# Load 7-year continuous bars for MNQ and MES across 30m and 60m
datasets = {}
for sym in ['MNQ', 'MES']:
    for tf_label, tf_interval, tf_min in [('30m', '30 minutes', 30), ('60m', '60 minutes', 60)]:
        bars = pd.concat([
            load_resampled_bars(sym, 'train', tf_interval, start_date='2020-01-01'),
            load_resampled_bars(sym, 'validation', tf_interval, start_date='2024-01-01'),
            load_resampled_bars(sym, 'test', tf_interval, start_date='2026-01-01')
        ]).sort_values('timestamp_utc').reset_index(drop=True)
        
        data = apply_early_close(generalized_arrays(bars), bars)
        local = bars.timestamp_utc.dt.tz_convert('America/New_York')
        dec = (local.dt.hour * 60 + local.dt.minute + tf_min).to_numpy()
        weekdays = local.dt.weekday.to_numpy() < 5
        mask_morn = (dec >= 600) & (dec < 720) & weekdays
        mask_all = (dec >= 585) & (dec < 945) & weekdays
        
        datasets[(sym, tf_label)] = {
            'bars': bars, 'data': data, 'tf_min': tf_min,
            'mask_morn': mask_morn, 'mask_all': mask_all,
            'years': data['year'], 'features': {},
            'tick': 0.25, 'mult': 5.0 if sym == 'MES' else 2.0,
            'fee': 0.61
        }
        for lb in [4, 6, 8, 12, 16]:
            datasets[(sym, tf_label)]['features'][lb] = compute_htf_features(bars, lb, tf_min)

print("Pre-computed 7-year continuous features.")

# Load training qualifiers
qualifiers = json.load(open(ROOT / 'runs/htf_swing_training_qualifiers.json'))
print(f"Auditing {len(qualifiers)} training qualifiers on 2026 Test and full 7-year history...")

results = []
for q in qualifiers:
    sym = q['sym']
    tf_label = q['tf']
    fam = q['family']
    lb = q['lookback']
    th = q['threshold']
    stop_atr = q['stop_atr']
    tgt = q['target_ratio']
    hold = q['hold_bars']
    sess = q['session']
    
    d = datasets[(sym, tf_label)]
    feat = d['features'][lb]
    atr = feat['atr']
    c = feat['close']
    data = d['data']
    years = d['years']
    
    if fam == 'trend':
        raw_dir = np.sign(feat['trend'])
        raw_metric = np.abs(feat['trend'])
        sig_raw = np.where(raw_metric >= th, raw_dir, 0.0)
    elif fam == 'momentum':
        raw_dir = np.sign(feat['momentum'])
        raw_metric = np.abs(feat['momentum'])
        sig_raw = np.where(raw_metric >= th, raw_dir, 0.0)
    elif fam == 'breakout':
        bh = feat['breakout_high'] + th * atr
        bl = feat['breakout_low'] - th * atr
        sig_raw = np.where(c > bh, 1.0, np.where(c < bl, -1.0, 0.0))
    elif fam == 'regime':
        raw_dir = np.sign(feat['momentum'])
        raw_metric = np.where(feat['vol_ratio'] < 1.5, feat['efficiency'] * 3.0, 0.0)
        sig_raw = np.where(raw_metric >= th, raw_dir, 0.0)
        
    sess_mask = d['mask_all'] if sess == 'all_day' else d['mask_morn']
    sig = np.where(sess_mask, sig_raw, 0).astype(np.int8)
    
    cfg = dict(
        tick=d['tick'], multiplier=d['mult'], commission_per_side=d['fee'],
        slippage_ticks=1.0, spread_ticks=1.0, stop_atr=stop_atr,
        target_ratio=tgt, hold_bars=hold, trailing_atr=0.0,
        maxqty=1, initial_balance=50000.0, risk_per_trade=150.0,
        max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
        funded_drawdown=2000.0, funded_cap=50100.0, flat_minute=955,
        max_gap_minutes=120 if tf_label == '60m' else 60
    )
    
    res = me.execute(data, sig, atr, cfg)
    tn = res['trade_net']
    if len(tn) < 50:
        continue
    
    trade_years = years[res['trade_entry']]
    
    # 2026 Test PnL
    test_mask = trade_years == 2026
    test_net = tn[test_mask].sum() if np.any(test_mask) else 0.0
    test_trades = np.count_nonzero(test_mask)
    
    # Yearly PnLs
    yearly = {y: float(tn[trade_years == y].sum()) if np.any(trade_years == y) else 0.0 for y in range(2020, 2027)}
    pos_years = sum(yearly[y] > 0 for y in range(2020, 2027))
    
    worst_dd = float((np.maximum.accumulate(res['cash']) - res['worst']).max())
    net_7y = float(tn.sum())
    
    if test_net > 0 and pos_years >= 6 and worst_dd <= 1200.0:
        results.append({
            'sym': sym, 'tf': tf_label, 'family': fam, 'lb': lb, 'th': th,
            'stop': stop_atr, 'tgt': tgt, 'hold': hold, 'sess': sess,
            'net_7y': net_7y, 'trades_7y': len(tn), 'exp_7y': net_7y / len(tn),
            'test_2026_net': test_net, 'test_2026_trades': test_trades,
            'max_dd_7y': worst_dd, 'pos_years': pos_years, 'yearly': yearly,
            'calmar_7y': net_7y / worst_dd if worst_dd > 0 else 999.0
        })

df_res = pd.DataFrame(results)
print(f"\nTotal Qualifiers POSITIVE in 2026 Test, >=6/7 Positive Years, and DD <= $1,200: {len(df_res)}")
if not df_res.empty:
    df_res = df_res.sort_values('calmar_7y', ascending=False)
    cols = ['sym', 'tf', 'family', 'lb', 'th', 'stop', 'tgt', 'hold', 'net_7y', 'test_2026_net', 'exp_7y', 'max_dd_7y', 'pos_years', 'calmar_7y']
    print(df_res[cols].head(15).to_string(index=False))

out_file = ROOT / 'runs/bulletproof_7y_qualifiers.json'
with open(out_file, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved bulletproof qualifiers to {out_file}")

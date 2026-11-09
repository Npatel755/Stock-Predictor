import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import time
from itertools import product

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays, compute_5m_indicators
import mass_execution as me
import mass_metrics as mm

CATALOG = json.load(open(ROOT / 'data/catalog.json'))

print("="*80, flush=True)
print("MASS 5-MINUTE & MULTI-TIMEFRAME (MTF) ANTI-SCALPING SEARCH", flush=True)
print("STRICTLY 2020-2023 TRAINING DATA ONLY — ZERO VALIDATION / TEST TOUCH", flush=True)
print("="*80, flush=True)

datasets = {}
for sym in ['MNQ', 'MES']:
    print(f"\nLoading {sym} bars (5m and 60m) for Training (2020-2023)...", flush=True)
    bars_5m = load_resampled_bars(sym, 'train', '5 minutes')
    bars_60m = load_resampled_bars(sym, 'train', '60 minutes')
    data = apply_early_close(generalized_arrays(bars_5m), bars_5m)
    
    print(f"Computing causal 5m indicators and MTF 60m trend for {sym}...", flush=True)
    t0 = time.time()
    feats = compute_5m_indicators(bars_5m, bars_60m)
    print(f"{sym} features computed in {time.time() - t0:.1f}s.", flush=True)
    
    # Session timing masks in Eastern Time
    close_min = feats['close_min']
    weekdays = feats['weekdays']
    
    # Morning: 09:45 to 11:45 ET (close_min between 585 and 705)
    mask_morning = (close_min >= 585) & (close_min < 705) & weekdays
    # Afternoon: 13:00 to 14:45 ET (close_min between 780 and 885)
    mask_afternoon = (close_min >= 780) & (close_min < 885) & weekdays
    # All-day RTH: 09:45 to 15:15 ET (close_min between 585 and 915)
    mask_all_day = (close_min >= 585) & (close_min < 915) & weekdays
    # ORB entry window: 10:00 to 11:30 ET (close_min between 600 and 690)
    mask_orb = (close_min >= 600) & (close_min < 690) & weekdays
    
    datasets[sym] = {
        'bars_5m': bars_5m,
        'data': data,
        'feats': feats,
        'mask_morning': mask_morning,
        'mask_afternoon': mask_afternoon,
        'mask_all_day': mask_all_day,
        'mask_orb': mask_orb,
        'years': data['year'],
        'point_val': 5.0 if sym == 'MES' else 2.0,
        'tick': 0.25,
        'mult': 5.0 if sym == 'MES' else 2.0,
        'adverse_ticks': 1.5, # 1 tick adverse slippage + 0.5 tick spread
        'fee': 0.61 # commission per side
    }

print("\nStarting search across 5-minute strategy families...")

qualifiers = []
total_tested = 0
t_start = time.time()

# Predeclared gates
MIN_TRADES = 80
MIN_PF = 1.70
MIN_NET = 3000.0
MAX_DD = 750.0 # Cushion >= $1,250 on $2,000 trailing limit
MIN_EXPECTANCY = 25.0 # Anti-scalping minimum ($25/trade)

for sym, d in datasets.items():
    data = d['data']
    feats = d['feats']
    years = d['years']
    close = feats['close']
    atr = feats['atr']
    trend60 = feats['trend60']
    vol_ratio = feats['vol_ratio']
    orb_high = feats['orb_high']
    orb_low = feats['orb_low']
    
    # -------------------------------------------------------------
    # Family 1: 5m MTF Breakout (Donchian Breakout + 60m Trend Alignment)
    # -------------------------------------------------------------
    for lb in [12, 18, 24, 36, 48]:
        feat_lb = feats['features_by_lb'][lb]
        bh = feat_lb['breakout_high']
        bl = feat_lb['breakout_low']
        
        for th in [0.25, 0.5, 1.0]:
            sig_raw = np.zeros(len(close), dtype=np.int8)
            long_cond = (close > bh + th * atr) & (trend60 > 0)
            short_cond = (close < bl - th * atr) & (trend60 < 0)
            sig_raw[long_cond] = 1
            sig_raw[short_cond] = -1
            
            for sess_name, sess_mask in [('morning', d['mask_morning']), ('all_day', d['mask_all_day']), ('afternoon', d['mask_afternoon'])]:
                sig = np.where(sess_mask, sig_raw, 0).astype(np.int8)
                if not np.any(sig != 0):
                    continue
                
                for stop_atr in [1.5, 2.0]:
                    for tgt in [2.5, 3.0, 3.5, 4.0, 5.0]:
                        for hold in [12, 18, 24, 36]:
                            total_tested += 1
                            
                            cfg = dict(
                                tick=d['tick'], multiplier=d['mult'], commission_per_side=d['fee'],
                                slippage_ticks=1.0, spread_ticks=1.0, stop_atr=stop_atr,
                                target_ratio=tgt, hold_bars=hold, trailing_atr=0.0,
                                maxqty=1, initial_balance=50000.0, risk_per_trade=150.0,
                                max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                                funded_drawdown=2000.0, funded_cap=50100.0, flat_minute=955
                            )
                            
                            res = me.execute(data, sig, atr, cfg)
                            n_trades = len(res['trade_entry'])
                            if n_trades < MIN_TRADES or res['lock'] != 0 or res['funded_failed']:
                                continue
                            
                            trade_net = res['trade_net']
                            net = trade_net.sum()
                            if net < MIN_NET:
                                continue
                            
                            exp = net / n_trades
                            if exp < MIN_EXPECTANCY:
                                continue
                            
                            wins = trade_net[trade_net > 0].sum()
                            losses = -trade_net[trade_net < 0].sum()
                            pf = wins / losses if losses > 0 else 999.0
                            if pf < MIN_PF:
                                continue
                            
                            peak = 50000.0
                            worst_dd = 0.0
                            for c in res['worst']:
                                peak = max(peak, c)
                                worst_dd = max(worst_dd, peak - c)
                                
                            if worst_dd > MAX_DD:
                                continue
                            
                            # Check positive calendar years 2020-2023
                            trade_years = years[res['trade_entry']]
                            pos_years = sum(trade_net[trade_years == y].sum() > 0 for y in [2020, 2021, 2022, 2023])
                            if pos_years < 4:
                                continue
                            
                            qualifiers.append({
                                'sym': sym,
                                'tf': '5m',
                                'family': 'mtf_breakout',
                                'lb': lb,
                                'th': th,
                                'stop_atr': stop_atr,
                                'target_ratio': tgt,
                                'hold_bars': hold,
                                'trailing_atr': 0.0,
                                'session': sess_name,
                                'net': float(net),
                                'trades': int(n_trades),
                                'expectancy': float(exp),
                                'pf': float(pf),
                                'max_dd': float(worst_dd),
                                'pos_years': int(pos_years),
                                'calmar': float(net / worst_dd) if worst_dd > 0 else 999.0
                            })

    # -------------------------------------------------------------
    # Family 2: 5m MTF Trend & Momentum (EWMA / Momentum + 60m Trend Alignment)
    # -------------------------------------------------------------
    for lb in [12, 18, 24, 36, 48]:
        feat_lb = feats['features_by_lb'][lb]
        trend5 = feat_lb['trend']
        
        for th in [0.75, 1.0, 1.25, 1.5]:
            sig_raw = np.zeros(len(close), dtype=np.int8)
            long_cond = (trend5 > th) & (trend60 > 0)
            short_cond = (trend5 < -th) & (trend60 < 0)
            sig_raw[long_cond] = 1
            sig_raw[short_cond] = -1
            
            for sess_name, sess_mask in [('morning', d['mask_morning']), ('all_day', d['mask_all_day'])]:
                sig = np.where(sess_mask, sig_raw, 0).astype(np.int8)
                if not np.any(sig != 0):
                    continue
                
                for stop_atr in [1.5, 2.0]:
                    for tgt in [2.5, 3.0, 3.5, 4.0, 5.0]:
                        for hold in [12, 18, 24, 36]:
                            total_tested += 1
                            
                            cfg = dict(
                                tick=d['tick'], multiplier=d['mult'], commission_per_side=d['fee'],
                                slippage_ticks=1.0, spread_ticks=1.0, stop_atr=stop_atr,
                                target_ratio=tgt, hold_bars=hold, trailing_atr=0.0,
                                maxqty=1, initial_balance=50000.0, risk_per_trade=150.0,
                                max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                                funded_drawdown=2000.0, funded_cap=50100.0, flat_minute=955
                            )
                            
                            res = me.execute(data, sig, atr, cfg)
                            n_trades = len(res['trade_entry'])
                            if n_trades < MIN_TRADES or res['lock'] != 0 or res['funded_failed']:
                                continue
                            
                            trade_net = res['trade_net']
                            net = trade_net.sum()
                            if net < MIN_NET:
                                continue
                            
                            exp = net / n_trades
                            if exp < MIN_EXPECTANCY:
                                continue
                            
                            wins = trade_net[trade_net > 0].sum()
                            losses = -trade_net[trade_net < 0].sum()
                            pf = wins / losses if losses > 0 else 999.0
                            if pf < MIN_PF:
                                continue
                            
                            peak = 50000.0
                            worst_dd = 0.0
                            for c in res['worst']:
                                peak = max(peak, c)
                                worst_dd = max(worst_dd, peak - c)
                                
                            if worst_dd > MAX_DD:
                                continue
                            
                            trade_years = years[res['trade_entry']]
                            pos_years = sum(trade_net[trade_years == y].sum() > 0 for y in [2020, 2021, 2022, 2023])
                            if pos_years < 4:
                                continue
                            
                            qualifiers.append({
                                'sym': sym,
                                'tf': '5m',
                                'family': 'mtf_trend',
                                'lb': lb,
                                'th': th,
                                'stop_atr': stop_atr,
                                'target_ratio': tgt,
                                'hold_bars': hold,
                                'trailing_atr': 0.0,
                                'session': sess_name,
                                'net': float(net),
                                'trades': int(n_trades),
                                'expectancy': float(exp),
                                'pf': float(pf),
                                'max_dd': float(worst_dd),
                                'pos_years': int(pos_years),
                                'calmar': float(net / worst_dd) if worst_dd > 0 else 999.0
                            })

    # -------------------------------------------------------------
    # Family 3: 5m Opening Range Breakout (ORB)
    # -------------------------------------------------------------
    for th in [0.0, 0.25, 0.5, 1.0]:
        sig_raw = np.zeros(len(close), dtype=np.int8)
        long_cond = (close > orb_high + th * atr) & (trend60 > 0)
        short_cond = (close < orb_low - th * atr) & (trend60 < 0)
        sig_raw[long_cond] = 1
        sig_raw[short_cond] = -1
        
        sig = np.where(d['mask_orb'], sig_raw, 0).astype(np.int8)
        if not np.any(sig != 0):
            continue
            
        for stop_atr in [1.5, 2.0]:
            for tgt in [2.5, 3.0, 3.5, 4.0, 5.0]:
                for hold in [12, 18, 24, 36]:
                    total_tested += 1
                    
                    cfg = dict(
                        tick=d['tick'], multiplier=d['mult'], commission_per_side=d['fee'],
                        slippage_ticks=1.0, spread_ticks=1.0, stop_atr=stop_atr,
                        target_ratio=tgt, hold_bars=hold, trailing_atr=0.0,
                        maxqty=1, initial_balance=50000.0, risk_per_trade=150.0,
                        max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                        funded_drawdown=2000.0, funded_cap=50100.0, flat_minute=955
                    )
                    
                    res = me.execute(data, sig, atr, cfg)
                    n_trades = len(res['trade_entry'])
                    if n_trades < MIN_TRADES or res['lock'] != 0 or res['funded_failed']:
                        continue
                    
                    trade_net = res['trade_net']
                    net = trade_net.sum()
                    if net < MIN_NET:
                        continue
                    
                    exp = net / n_trades
                    if exp < MIN_EXPECTANCY:
                        continue
                    
                    wins = trade_net[trade_net > 0].sum()
                    losses = -trade_net[trade_net < 0].sum()
                    pf = wins / losses if losses > 0 else 999.0
                    if pf < MIN_PF:
                        continue
                    
                    peak = 50000.0
                    worst_dd = 0.0
                    for c in res['worst']:
                        peak = max(peak, c)
                        worst_dd = max(worst_dd, peak - c)
                        
                    if worst_dd > MAX_DD:
                        continue
                    
                    trade_years = years[res['trade_entry']]
                    pos_years = sum(trade_net[trade_years == y].sum() > 0 for y in [2020, 2021, 2022, 2023])
                    if pos_years < 4:
                        continue
                    
                    qualifiers.append({
                        'sym': sym,
                        'tf': '5m',
                        'family': 'orb',
                        'lb': 6, # 30 min opening range
                        'th': th,
                        'stop_atr': stop_atr,
                        'target_ratio': tgt,
                        'hold_bars': hold,
                        'trailing_atr': 0.0,
                        'session': 'orb_morning',
                        'net': float(net),
                        'trades': int(n_trades),
                        'expectancy': float(exp),
                        'pf': float(pf),
                        'max_dd': float(worst_dd),
                        'pos_years': int(pos_years),
                        'calmar': float(net / worst_dd) if worst_dd > 0 else 999.0
                    })

    # -------------------------------------------------------------
    # Family 4: 5m Volatility Squeeze Expansion
    # -------------------------------------------------------------
    for lb in [18, 24, 36]:
        feat_lb = feats['features_by_lb'][lb]
        bh = feat_lb['breakout_high']
        bl = feat_lb['breakout_low']
        vol_comp = feat_lb['vol_comp']
        
        for th in [0.25, 0.5, 1.0]:
            sig_raw = np.zeros(len(close), dtype=np.int8)
            squeeze = vol_comp < 0.8
            long_cond = squeeze & (close > bh + th * atr) & (trend60 > 0)
            short_cond = squeeze & (close < bl - th * atr) & (trend60 < 0)
            sig_raw[long_cond] = 1
            sig_raw[short_cond] = -1
            
            for sess_name, sess_mask in [('morning', d['mask_morning']), ('all_day', d['mask_all_day'])]:
                sig = np.where(sess_mask, sig_raw, 0).astype(np.int8)
                if not np.any(sig != 0):
                    continue
                
                for stop_atr in [1.5, 2.0]:
                    for tgt in [3.0, 3.5, 4.0, 5.0]:
                        for hold in [18, 24, 36]:
                            total_tested += 1
                            
                            cfg = dict(
                                tick=d['tick'], multiplier=d['mult'], commission_per_side=d['fee'],
                                slippage_ticks=1.0, spread_ticks=1.0, stop_atr=stop_atr,
                                target_ratio=tgt, hold_bars=hold, trailing_atr=0.0,
                                maxqty=1, initial_balance=50000.0, risk_per_trade=150.0,
                                max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                                funded_drawdown=2000.0, funded_cap=50100.0, flat_minute=955
                            )
                            
                            res = me.execute(data, sig, atr, cfg)
                            n_trades = len(res['trade_entry'])
                            if n_trades < MIN_TRADES or res['lock'] != 0 or res['funded_failed']:
                                continue
                            
                            trade_net = res['trade_net']
                            net = trade_net.sum()
                            if net < MIN_NET:
                                continue
                            
                            exp = net / n_trades
                            if exp < MIN_EXPECTANCY:
                                continue
                            
                            wins = trade_net[trade_net > 0].sum()
                            losses = -trade_net[trade_net < 0].sum()
                            pf = wins / losses if losses > 0 else 999.0
                            if pf < MIN_PF:
                                continue
                            
                            peak = 50000.0
                            worst_dd = 0.0
                            for c in res['worst']:
                                peak = max(peak, c)
                                worst_dd = max(worst_dd, peak - c)
                                
                            if worst_dd > MAX_DD:
                                continue
                            
                            trade_years = years[res['trade_entry']]
                            pos_years = sum(trade_net[trade_years == y].sum() > 0 for y in [2020, 2021, 2022, 2023])
                            if pos_years < 4:
                                continue
                            
                            qualifiers.append({
                                'sym': sym,
                                'tf': '5m',
                                'family': 'vol_squeeze',
                                'lb': lb,
                                'th': th,
                                'stop_atr': stop_atr,
                                'target_ratio': tgt,
                                'hold_bars': hold,
                                'trailing_atr': 0.0,
                                'session': sess_name,
                                'net': float(net),
                                'trades': int(n_trades),
                                'expectancy': float(exp),
                                'pf': float(pf),
                                'max_dd': float(worst_dd),
                                'pos_years': int(pos_years),
                                'calmar': float(net / worst_dd) if worst_dd > 0 else 999.0
                            })

    # -------------------------------------------------------------
    # Family 5: 5m Volume-Surge Momentum
    # -------------------------------------------------------------
    for lb in [18, 24, 36]:
        feat_lb = feats['features_by_lb'][lb]
        mom = feat_lb['momentum']
        
        for th in [0.75, 1.0, 1.25]:
            sig_raw = np.zeros(len(close), dtype=np.int8)
            vol_surge = vol_ratio > 1.25
            long_cond = vol_surge & (mom > th) & (trend60 > 0)
            short_cond = vol_surge & (mom < -th) & (trend60 < 0)
            sig_raw[long_cond] = 1
            sig_raw[short_cond] = -1
            
            for sess_name, sess_mask in [('morning', d['mask_morning']), ('all_day', d['mask_all_day'])]:
                sig = np.where(sess_mask, sig_raw, 0).astype(np.int8)
                if not np.any(sig != 0):
                    continue
                
                for stop_atr in [1.5, 2.0]:
                    for tgt in [3.0, 3.5, 4.0, 5.0]:
                        for hold in [18, 24, 36]:
                            total_tested += 1
                            
                            cfg = dict(
                                tick=d['tick'], multiplier=d['mult'], commission_per_side=d['fee'],
                                slippage_ticks=1.0, spread_ticks=1.0, stop_atr=stop_atr,
                                target_ratio=tgt, hold_bars=hold, trailing_atr=0.0,
                                maxqty=1, initial_balance=50000.0, risk_per_trade=150.0,
                                max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                                funded_drawdown=2000.0, funded_cap=50100.0, flat_minute=955
                            )
                            
                            res = me.execute(data, sig, atr, cfg)
                            n_trades = len(res['trade_entry'])
                            if n_trades < MIN_TRADES or res['lock'] != 0 or res['funded_failed']:
                                continue
                            
                            trade_net = res['trade_net']
                            net = trade_net.sum()
                            if net < MIN_NET:
                                continue
                            
                            exp = net / n_trades
                            if exp < MIN_EXPECTANCY:
                                continue
                            
                            wins = trade_net[trade_net > 0].sum()
                            losses = -trade_net[trade_net < 0].sum()
                            pf = wins / losses if losses > 0 else 999.0
                            if pf < MIN_PF:
                                continue
                            
                            peak = 50000.0
                            worst_dd = 0.0
                            for c in res['worst']:
                                peak = max(peak, c)
                                worst_dd = max(worst_dd, peak - c)
                                
                            if worst_dd > MAX_DD:
                                continue
                            
                            trade_years = years[res['trade_entry']]
                            pos_years = sum(trade_net[trade_years == y].sum() > 0 for y in [2020, 2021, 2022, 2023])
                            if pos_years < 4:
                                continue
                            
                            qualifiers.append({
                                'sym': sym,
                                'tf': '5m',
                                'family': 'vol_momentum',
                                'lb': lb,
                                'th': th,
                                'stop_atr': stop_atr,
                                'target_ratio': tgt,
                                'hold_bars': hold,
                                'trailing_atr': 0.0,
                                'session': sess_name,
                                'net': float(net),
                                'trades': int(n_trades),
                                'expectancy': float(exp),
                                'pf': float(pf),
                                'max_dd': float(worst_dd),
                                'pos_years': int(pos_years),
                                'calmar': float(net / worst_dd) if worst_dd > 0 else 999.0
                            })

elapsed = time.time() - t_start
print(f"\nSearch complete: {total_tested:,} configurations evaluated in {elapsed:.1f}s ({total_tested/elapsed:.1f} configs/sec)!")
print(f"Total Qualifiers Meeting Strict Training Quality Gates: {len(qualifiers)}")

# Sort by Calmar and Net
qualifiers.sort(key=lambda x: x['calmar'], reverse=True)

out_file = ROOT / 'runs/5m_mtf_training_qualifiers.json'
with open(out_file, 'w') as f:
    json.dump(qualifiers, f, indent=2)
print(f"Saved qualifiers to {out_file}")

# Display top 15 qualifiers
df_q = pd.DataFrame(qualifiers)
if not df_q.empty:
    print("\nTOP 15 5-MINUTE QUALIFIERS RANKED BY CALMAR (TRAIN 2020-2023):")
    cols = ['sym', 'family', 'lb', 'th', 'stop_atr', 'target_ratio', 'hold_bars', 'session', 'net', 'trades', 'expectancy', 'pf', 'max_dd', 'calmar']
    print(df_q[cols].head(15).to_string(index=False))

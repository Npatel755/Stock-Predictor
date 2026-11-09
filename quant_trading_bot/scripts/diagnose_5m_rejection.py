import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays, compute_5m_indicators
import mass_execution as me

bars_5m = load_resampled_bars('MNQ', 'train', '5 minutes')
bars_60m = load_resampled_bars('MNQ', 'train', '60 minutes')
data = apply_early_close(generalized_arrays(bars_5m), bars_5m)
feats = compute_5m_indicators(bars_5m, bars_60m)

close = feats['close']
atr = feats['atr']
trend60 = feats['trend60']
close_min = feats['close_min']
weekdays = feats['weekdays']
mask_morning = (close_min >= 585) & (close_min < 705) & weekdays

results = []
for lb in [12, 18, 24, 36, 48]:
    feat_lb = feats['features_by_lb'][lb]
    bh = feat_lb['breakout_high']
    bl = feat_lb['breakout_low']
    trend5 = feat_lb['trend']
    
    for th in [0.25, 0.5, 0.75, 1.0]:
        sig_raw = np.zeros(len(close), dtype=np.int8)
        long_cond = (close > bh + th * atr) & (trend60 > 0)
        short_cond = (close < bl - th * atr) & (trend60 < 0)
        sig_raw[long_cond] = 1
        sig_raw[short_cond] = -1
        sig = np.where(mask_morning, sig_raw, 0).astype(np.int8)
        
        for stop_atr in [1.5, 2.0]:
            for tgt in [3.0, 3.5, 4.0, 5.0]:
                for hold in [18, 24, 36]:
                    cfg = dict(
                        tick=0.25, multiplier=2.0, commission_per_side=0.61,
                        slippage_ticks=1.0, spread_ticks=1.0, stop_atr=stop_atr,
                        target_ratio=tgt, hold_bars=hold, trailing_atr=0.0,
                        maxqty=1, initial_balance=50000.0, risk_per_trade=150.0,
                        max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                        funded_drawdown=2000.0, funded_cap=50100.0, flat_minute=955
                    )
                    res = me.execute(data, sig, atr, cfg)
                    n_trades = len(res['trade_entry'])
                    if n_trades < 80 or res['lock'] != 0 or res['funded_failed']:
                        continue
                    trade_net = res['trade_net']
                    net = trade_net.sum()
                    exp = net / n_trades
                    worst_dd = (np.maximum.accumulate(res['cash']) - res['worst']).max()
                    if worst_dd > 1000.0: # Cushion must be >= $1,000
                        continue
                    trade_years = data['year'][res['trade_entry']]
                    pos_years = sum(trade_net[trade_years == y].sum() > 0 for y in [2020, 2021, 2022, 2023])
                    if pos_years < 4:
                        continue
                    
                    wins = trade_net[trade_net > 0].sum()
                    losses = -trade_net[trade_net < 0].sum()
                    pf = wins / losses if losses > 0 else 999.0
                    
                    results.append({
                        'lb': lb, 'th': th, 'stop': stop_atr, 'tgt': tgt, 'hold': hold,
                        'trades': n_trades, 'net': net, 'exp': exp, 'dd': worst_dd, 'pf': pf,
                        'calmar': net / worst_dd
                    })

df_res = pd.DataFrame(results)
print(f"\nTotal 5m MTF Breakout qualifiers with DD <= $1,000 and 4/4 positive years: {len(df_res)}")
if not df_res.empty:
    df_res = df_res.sort_values('calmar', ascending=False)
    print(df_res.head(15).to_string(index=False))

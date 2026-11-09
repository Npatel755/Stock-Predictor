"""Deep S2 (60m Trend) Parameter Frontier strictly on 2010-2023 Training Data.
"""
import sys, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

from research_deep_frontier_train import (
    b_mnq_15, b_mnq_30, b_mnq_60, b_mes_15, b_mes_30,
    d_mnq_15, d_mnq_30, d_mnq_60, d_mes_30,
    atr_15, f_1, f_2, f_mes,
    sig_crabel, sig_1_raw, sig_mes_raw,
    cfg_c, cfg_s1_base, cfg_mes,
    dec_60, weekdays_60, prior_backw_map, evaluate_variant
)
import mass_execution as me
from quant_futures.htf_engine import compute_htf_features

dates_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York').dt.date.to_numpy()

print(f"\nEvaluating S2 (60m Macro Trend) Variations on 2010-2023 Training Data:")
print(f"{'Variation':<35} | {'Net ($)':<10} | {'Trades':<6} | {'Exp ($)':<8} | {'MaxDD ($)':<9} | {'Cushion ($)':<11} | {'Pre-2020':<10} | {'Post-2020':<10}")
print("-" * 115)

s2_variations = [
    ("S2 Baseline (lb12, th0.75, hb6, tgt4)", 12, 0.75, 6, 1.25, 4.0),
    ("S2 lb12, th0.85, hb6, tgt4", 12, 0.85, 6, 1.25, 4.0),
    ("S2 lb12, th1.0, hb6, tgt4", 12, 1.0, 6, 1.25, 4.0),
    ("S2 lb16, th0.75, hb6, tgt4", 16, 0.75, 6, 1.25, 4.0),
    ("S2 lb8, th0.75, hb6, tgt4", 8, 0.75, 6, 1.25, 4.0),
    ("S2 lb12, th0.75, hb8, tgt4", 12, 0.75, 8, 1.25, 4.0),
    ("S2 lb12, th0.75, hb6, tgt3.5", 12, 0.75, 6, 1.25, 3.5),
    ("S2 lb12, th0.75, hb6, tgt5.0", 12, 0.75, 6, 1.25, 5.0),
    ("S2 lb12, th0.75, hb6, stop1.5, tgt4", 12, 0.75, 6, 1.5, 4.0),
]

for label, lb, th, hb, satr, tgt in s2_variations:
    f_s2 = compute_htf_features(b_mnq_60, lb, 60)
    s2_sig = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_s2['trend']) >= th), np.sign(f_s2['trend']), 0).astype(np.int8)
    for i in range(len(s2_sig)):
        if s2_sig[i] != 0 and prior_backw_map.get(dates_60[i], False):
            s2_sig[i] = 0
            
    cfg_s2_test = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                       stop_atr=satr, target_ratio=tgt, hold_bars=hb, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                       risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                       flat_minute=955, max_gap_minutes=120)

    # Execute
    r_c = me.execute(d_mnq_15, sig_crabel, atr_15, cfg_c)
    act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])

    act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
    s_1_routed = np.where(~act_c_30, sig_1_raw, 0).astype(np.int8)
    r_1 = me.execute(d_mnq_30, s_1_routed, f_1['atr'], cfg_s1_base)
    act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])

    act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
                  act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    s_2_routed = np.where(~act_all_60, s2_sig, 0).astype(np.int8)
    r_2 = me.execute(d_mnq_60, s_2_routed, f_s2['atr'], cfg_s2_test)
    act_2_60 = pd.Series(r_2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])

    act_all_mnq = (act_c_15.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                   act_1_30.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                   act_2_60.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    s_mes_routed = np.where(~act_all_mnq, sig_mes_raw, 0).astype(np.int8)
    r_mes = me.execute(d_mes_30, s_mes_routed, f_mes['atr'], cfg_mes)

    p_c = pd.Series(r_c['cash'] - 50000.0, index=b_mnq_15['timestamp_utc'])
    p_1 = pd.Series(r_1['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
    p_2 = pd.Series(r_2['cash'] - 50000.0, index=b_mnq_60['timestamp_utc'])
    p_mes = pd.Series(r_mes['cash'] - 50000.0, index=b_mes_30['timestamp_utc'])

    common_idx = b_mnq_15['timestamp_utc']
    pnl = (p_c + 
           p_1.reindex(common_idx, method='ffill').fillna(0.0) + 
           p_2.reindex(common_idx, method='ffill').fillna(0.0) +
           p_mes.reindex(common_idx, method='ffill').fillna(0.0))

    peak = pnl.cummax()
    dd = peak - pnl
    max_dd = float(dd.max())
    total_net = float(pnl.iloc[-1])

    tr_list = []
    for name, r, d in [('Crabel', r_c, d_mnq_15), ('S1_30m', r_1, d_mnq_30), ('S2_60m', r_2, d_mnq_60), ('MES_30m', r_mes, d_mes_30)]:
        if len(r['trade_entry']):
            y = d['year'][r['trade_entry']]
            net = r['trade_net']
            for yr, n in zip(y, net):
                tr_list.append((yr, n, name))

    df_trades = pd.DataFrame(tr_list, columns=['year', 'net', 'sleeve'])
    tot_trades = len(df_trades)
    exp_tot = total_net / tot_trades if tot_trades else 0.0

    m_pre = (df_trades['year'] >= 2010) & (df_trades['year'] < 2020)
    m_post = (df_trades['year'] >= 2020) & (df_trades['year'] < 2024)

    net_pre = float(df_trades.loc[m_pre, 'net'].sum()) if np.any(m_pre) else 0.0
    cnt_pre = int(np.count_nonzero(m_pre))
    exp_pre = net_pre / cnt_pre if cnt_pre else 0.0

    net_post = float(df_trades.loc[m_post, 'net'].sum()) if np.any(m_post) else 0.0
    cnt_post = int(np.count_nonzero(m_post))
    exp_post = net_post / cnt_post if cnt_post else 0.0

    cushion = 2000.0 - max_dd

    print(f"{label:<35} | +${total_net:8.2f} | {tot_trades:6d} | +${exp_tot:6.2f} | ${max_dd:7.2f} | +${cushion:9.2f} | +${net_pre:8.2f} | +${net_post:8.2f}")

"""Systematic Deep Strategy Improvement Research on 2010-2023 Training Data.

Strict Mandate:
- TRAINING DATA ONLY: 2010-01-01 to 2023-12-31.
- Absolutely NO access to 2024-2025 Validation or 2026 Test data.
- $50,000 capital, strict $2,000 trailing drawdown floor.
- Marketable micro costs: MNQ 1.75 tick spread, MES 1.00 tick spread, 1 tick slip, $0.61 comm/side.
- 1-contract maximum router across all active sleeves.

Hypotheses Tested:
H1: Trailing ATR stop on MNQ 30m & 60m sleeves (1.5, 2.0, 2.5 ATR vs 0.0).
H2: Extreme Panic Volatility Gate (VIX > 35 or VIX > 40 prior close).
H3: Combined VIX Backwardation (VIX > VIX3M) + Extreme Panic Gate.
H4: MES 30m Idle-Sleeve Parameter Sensitivity (target 2.0R to 3.5R, stop 1.0 to 1.5 ATR).
H5: Crabel 15m Hold Bar Duration (6, 8, 10, 12 bars).
"""
import os
import sys, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features

print("Loading 2010-2023 Training Data...", flush=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None)
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None)
b_mes_15 = load_resampled_bars('ES', 'train', '15 minutes', start_date=None)
b_mes_30 = load_resampled_bars('ES', 'train', '30 minutes', start_date=None)

# Precompute Session Info
loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_15.dt.date

loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
weekdays_30 = loc_30.dt.weekday.to_numpy() < 5

loc_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
dec_60 = (loc_60.dt.hour * 60 + loc_60.dt.minute + 60).to_numpy()
weekdays_60 = loc_60.dt.weekday.to_numpy() < 5

loc_mes_30 = b_mes_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_mes_30 = (loc_mes_30.dt.hour * 60 + loc_mes_30.dt.minute + 30).to_numpy()
weekdays_mes_30 = loc_mes_30.dt.weekday.to_numpy() < 5

# Generalized execution arrays
d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)
d_mnq_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)
d_mes_30 = apply_early_close(generalized_arrays(b_mes_30), b_mes_30)

# 15m ATR
close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c15 = np.roll(close_15, 1); prev_c15[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c15), np.abs(low_15 - prev_c15)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

# HTF Features for S1 and S2
f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1_raw = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)

f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)

# Crabel Open-Drive with MES Confirmation
rth_15 = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
g_15 = rth_15.groupby('date')
o930 = g_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000 = g_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
h1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'high'].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'low'].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

common_days = sorted(list(o930.dropna().index))
df_days = pd.DataFrame(index=common_days)
df_days['range'] = h1000.loc[common_days] - l1000.loc[common_days]
df_days['open_pos'] = (o930.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
df_days['close_pos'] = (c1000.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)

cond_bull_base = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80) & (df_days['range'] >= 15.0)
cond_bear_base = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20) & (df_days['range'] >= 15.0)
d_map_base = dict(zip(df_days.index, np.where(cond_bull_base, 1, np.where(cond_bear_base, -1, 0))))

loc_mes_15 = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes_15.dt.hour * 60 + loc_mes_15.dt.minute
b_mes_15['date'] = loc_mes_15.dt.date
rth_mes_15 = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)
g_mes_15 = rth_mes_15.groupby('date')
mes_o930 = g_mes_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
mes_c1000 = g_mes_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
mes_dir_1000 = np.sign(mes_c1000 - mes_o930).fillna(0).astype(int).to_dict()

sig_crabel_base = np.zeros(len(close_15), dtype=np.int8)
for i in range(len(close_15)):
    if is_1000_bar[i]:
        sig_crabel_base[i] = d_map_base.get(dates_all_15[i], 0)
        if sig_crabel_base[i] != 0:
            m_dir = mes_dir_1000.get(dates_all_15[i], 0)
            if (sig_crabel_base[i] == 1 and m_dir < 0) or (sig_crabel_base[i] == -1 and m_dir > 0):
                sig_crabel_base[i] = 0

# 1. Load CBOE VIX & VIX3M
def load_cboe(ticker):
    df = pd.read_csv(ROOT / f"data/external/{ticker}_History.csv")
    df['date'] = pd.to_datetime(df['DATE'], format='%m/%d/%Y').dt.date
    return df.set_index('date')['CLOSE'].astype(float)

vix_series = load_cboe("VIX")
vix3m_series = load_cboe("VIX3M")
vix_cboe_dates = np.array(sorted(list(vix_series.index)))
vix_close = vix_series.loc[vix_cboe_dates].to_numpy()
vix3m_close = vix3m_series.reindex(vix_cboe_dates).bfill().to_numpy()

def get_prior_vix_stats(bar_dates):
    unique_dates = np.array(sorted(list(set(bar_dates))))
    pos = np.searchsorted(vix_cboe_dates, unique_dates, side='left') - 1
    
    backwardation = {}
    vix_level = {}
    for ud, p in zip(unique_dates, pos):
        if p >= 0:
            backwardation[ud] = bool(vix_close[p] > vix3m_close[p])
            vix_level[ud] = float(vix_close[p])
        else:
            backwardation[ud] = False
            vix_level[ud] = 20.0
    return backwardation, vix_level

back_map, vix_level_map = get_prior_vix_stats(dates_all_15)

# Simulator function for full portfolio
def evaluate_portfolio(crabel_hb=8, crabel_satr=2.0, crabel_tgt=3.5,
                       s1_satr=1.5, s1_tgt=3.0, s1_hb=8, s1_trail=0.0,
                       s2_satr=1.25, s2_tgt=4.0, s2_hb=6, s2_trail=0.0,
                       mes_lb=8, mes_th=1.0, mes_satr=1.25, mes_tgt=2.5, mes_hb=12, mes_trail=0.0,
                       vix_backwardation_gate=True, vix_panic_threshold=None):
    
    # Apply VIX filters to Crabel
    sig_c = sig_crabel_base.copy()
    if vix_backwardation_gate or (vix_panic_threshold is not None):
        for i in range(len(sig_c)):
            if sig_c[i] != 0:
                d = dates_all_15[i]
                if vix_backwardation_gate and back_map.get(d, False):
                    sig_c[i] = 0
                elif (vix_panic_threshold is not None) and (vix_level_map.get(d, 0.0) >= vix_panic_threshold):
                    sig_c[i] = 0
                    
    cfg_c = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                 stop_atr=crabel_satr, target_ratio=crabel_tgt, hold_bars=crabel_hb, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                 risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                 flat_minute=955, max_gap_minutes=60)
    
    r_c = me.execute(d_mnq_15, sig_c, atr_15, cfg_c)
    act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])
    
    # S1 MNQ 30m
    act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
    sig_1 = np.where(~act_c_30, sig_1_raw, 0).astype(np.int8)
    if vix_backwardation_gate or (vix_panic_threshold is not None):
        dates_30 = loc_30.dt.date
        for i in range(len(sig_1)):
            if sig_1[i] != 0:
                d = dates_30[i]
                if vix_backwardation_gate and back_map.get(d, False):
                    sig_1[i] = 0
                elif (vix_panic_threshold is not None) and (vix_level_map.get(d, 0.0) >= vix_panic_threshold):
                    sig_1[i] = 0
                    
    cfg_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                 stop_atr=s1_satr, target_ratio=s1_tgt, hold_bars=s1_hb, trailing_atr=s1_trail, maxqty=1, initial_balance=50000.0,
                 risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                 flat_minute=955, max_gap_minutes=60)
    r_1 = me.execute(d_mnq_30, sig_1, f_1['atr'], cfg_1)
    act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
    
    # S2 MNQ 60m
    act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
                  act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    sig_2 = np.where(~act_all_60, sig_2_raw, 0).astype(np.int8)
    if vix_backwardation_gate or (vix_panic_threshold is not None):
        dates_60 = loc_60.dt.date
        for i in range(len(sig_2)):
            if sig_2[i] != 0:
                d = dates_60[i]
                if vix_backwardation_gate and back_map.get(d, False):
                    sig_2[i] = 0
                elif (vix_panic_threshold is not None) and (vix_level_map.get(d, 0.0) >= vix_panic_threshold):
                    sig_2[i] = 0
                    
    cfg_2 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                 stop_atr=s2_satr, target_ratio=s2_tgt, hold_bars=s2_hb, trailing_atr=s2_trail, maxqty=1, initial_balance=50000.0,
                 risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                 flat_minute=955, max_gap_minutes=120)
    r_2 = me.execute(d_mnq_60, sig_2, f_2['atr'], cfg_2)
    act_2_60 = pd.Series(r_2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])
    
    # MES 30m idle router
    act_all_mnq = (act_c_15.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                   act_1_30.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                   act_2_60.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
                   
    f_mes = compute_htf_features(b_mes_30, mes_lb, 30)
    sig_mes = np.where((dec_mes_30 >= 585) & (dec_mes_30 <= 930) & weekdays_mes_30 & (np.abs(f_mes['trend']) >= mes_th), np.sign(f_mes['trend']), 0).astype(np.int8)
    sig_mes_routed = np.where(~act_all_mnq, sig_mes, 0).astype(np.int8)
    
    cfg_mes = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                   stop_atr=mes_satr, target_ratio=mes_tgt, hold_bars=mes_hb, trailing_atr=mes_trail, maxqty=1, initial_balance=50000.0,
                   risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                   flat_minute=955, max_gap_minutes=60)
    r_mes = me.execute(d_mes_30, sig_mes_routed, f_mes['atr'], cfg_mes)
    
    # Portfolio stats
    common_idx = b_mnq_15['timestamp_utc']
    p_c = pd.Series(r_c['cash'] - 50000.0, index=b_mnq_15['timestamp_utc'])
    p_1 = pd.Series(r_1['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
    p_2 = pd.Series(r_2['cash'] - 50000.0, index=b_mnq_60['timestamp_utc'])
    p_mes = pd.Series(r_mes['cash'] - 50000.0, index=b_mes_30['timestamp_utc'])
    
    pnl_total = (p_c + 
                 p_1.reindex(common_idx, method='ffill').fillna(0.0) + 
                 p_2.reindex(common_idx, method='ffill').fillna(0.0) +
                 p_mes.reindex(common_idx, method='ffill').fillna(0.0))
                 
    peak = pnl_total.cummax()
    dd = peak - pnl_total
    max_dd = float(dd.max())
    total_net = float(pnl_total.iloc[-1])
    cushion = 2000.0 - max_dd
    
    tr_list = []
    for r, d in [(r_c, d_mnq_15), (r_1, d_mnq_30), (r_2, d_mnq_60), (r_mes, d_mes_30)]:
        if len(r['trade_entry']):
            y = d['year'][r['trade_entry']]
            net = r['trade_net']
            for yr, n in zip(y, net):
                tr_list.append((yr, n))
    df_tr = pd.DataFrame(tr_list, columns=['year', 'net'])
    tot_tr = len(df_tr)
    exp = total_net / tot_tr if tot_tr else 0.0
    
    m_pre = (df_tr['year'] >= 2010) & (df_tr['year'] < 2020)
    m_post = (df_tr['year'] >= 2020) & (df_tr['year'] < 2024)
    pre_net = float(df_tr.loc[m_pre, 'net'].sum())
    post_net = float(df_tr.loc[m_post, 'net'].sum())
    
    # Annual consistency
    yr_grp = df_tr.groupby('year')['net'].sum()
    pos_years = int((yr_grp > 0).sum())
    
    return dict(net=total_net, trades=tot_tr, exp=exp, max_dd=max_dd, cushion=cushion,
                pre_net=pre_net, post_net=post_net, pos_years=pos_years, total_years=len(yr_grp))

print("\n" + "=" * 120)
print(f"{'Experiment':<40} | {'Net ($)':<10} | {'Trades':<6} | {'Exp ($)':<8} | {'MaxDD ($)':<9} | {'Cushion ($)':<11} | {'Pre-2020':<10} | {'Post-2020':<10} | {'+Yrs'}")
print("=" * 120)

# 1. Baseline Architecture D+ (Current Grand Champion)
res_d_plus = evaluate_portfolio(vix_backwardation_gate=True)
print(f"{'Architecture D+ (Baseline)':<40} | +${res_d_plus['net']:8.2f} | {res_d_plus['trades']:6d} | +${res_d_plus['exp']:6.2f} | ${res_d_plus['max_dd']:7.2f} | +${res_d_plus['cushion']:9.2f} | +${res_d_plus['pre_net']:8.2f} | +${res_d_plus['post_net']:8.2f} | {res_d_plus['pos_years']}/14")

# 2. H1: Trailing Stop Testing on S1 and S2
print("-" * 120)
print("HYPOTHESIS 1: Trailing ATR Stops on MNQ Trend Sleeves")
for trail_val in [1.5, 2.0, 2.5, 3.0]:
    res = evaluate_portfolio(s1_trail=trail_val, s2_trail=trail_val)
    print(f"{f'Trail {trail_val} ATR on S1 & S2':<40} | +${res['net']:8.2f} | {res['trades']:6d} | +${res['exp']:6.2f} | ${res['max_dd']:7.2f} | +${res['cushion']:9.2f} | +${res['pre_net']:8.2f} | +${res['post_net']:8.2f} | {res['pos_years']}/14")

# 3. H2: VIX Extreme Panic Level Gate (Prior Close VIX > Threshold)
print("-" * 120)
print("HYPOTHESIS 2: Extreme Panic Volatility Gate (VIX > threshold)")
for vix_lvl in [30.0, 35.0, 40.0, 45.0]:
    res = evaluate_portfolio(vix_backwardation_gate=True, vix_panic_threshold=vix_lvl)
    print(f"{f'D+ & VIX > {vix_lvl} Gate':<40} | +${res['net']:8.2f} | {res['trades']:6d} | +${res['exp']:6.2f} | ${res['max_dd']:7.2f} | +${res['cushion']:9.2f} | +${res['pre_net']:8.2f} | +${res['post_net']:8.2f} | {res['pos_years']}/14")

# 4. H4: MES 30m Idle-Sleeve Parameter Sensitivity (Target R and Stop ATR)
print("-" * 120)
print("HYPOTHESIS 4: MES 30m Parameter Sensitivity (Target R & Stop ATR)")
for mes_tgt in [2.0, 2.5, 3.0, 3.5]:
    for mes_satr in [1.0, 1.25, 1.5]:
        res = evaluate_portfolio(mes_tgt=mes_tgt, mes_satr=mes_satr)
        print(f"{f'MES tgt={mes_tgt}R, stop={mes_satr} ATR':<40} | +${res['net']:8.2f} | {res['trades']:6d} | +${res['exp']:6.2f} | ${res['max_dd']:7.2f} | +${res['cushion']:9.2f} | +${res['pre_net']:8.2f} | +${res['post_net']:8.2f} | {res['pos_years']}/14")

# 5. H5: Toby Crabel 15m Hold Bar Duration Sensitivity
print("-" * 120)
print("HYPOTHESIS 5: Crabel 15m Hold Bar Duration Sensitivity")
for crabel_hb in [4, 6, 8, 10, 12]:
    for crabel_tgt in [3.0, 3.5, 4.0]:
        res = evaluate_portfolio(crabel_hb=crabel_hb, crabel_tgt=crabel_tgt)
        print(f"{f'Crabel hold={crabel_hb} bars, tgt={crabel_tgt}R':<40} | +${res['net']:8.2f} | {res['trades']:6d} | +${res['exp']:6.2f} | ${res['max_dd']:7.2f} | +${res['cushion']:9.2f} | +${res['pre_net']:8.2f} | +${res['post_net']:8.2f} | {res['pos_years']}/14")

print("=" * 120)

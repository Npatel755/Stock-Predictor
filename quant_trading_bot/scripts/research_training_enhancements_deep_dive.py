"""Deep-Dive Training Research Script (2010-2023).
STRICTLY TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Explores 4 Architectural Dimensions:
1. Adding an Afternoon Continuation Sleeve (MNQ 13:30-15:15 ET).
2. Adding a Cross-Asset MES Trend Sleeve (MES 30m, only when MNQ is flat).
3. Daily 200 SMA Macro Trend Regime Gating (Point-in-time past-only).
4. Breakeven Ratchet / Dynamic trailing stop on Crabel & Morning Trend.

Evaluates against the $2,000 Trailing Drawdown Hard Floor on $50,000 capital:
- Net Profit (2010-2023)
- Continuous Max Drawdown (Must stay strictly < $1,100 to maintain >$900 cushion)
- Expectancy ($/tr)
- Pre-2020 Net Profit & Post-2020 Net Profit
- Win Rate & Trade Count
"""
import sys, json, numpy as np, pandas as pd
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

print("Loading 2010-2023 TRAINING data for MNQ and MES...", flush=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None)
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None)
b_mes_15 = load_resampled_bars('ES', 'train', '15 minutes', start_date=None)
b_mes_30 = load_resampled_bars('ES', 'train', '30 minutes', start_date=None)
b_daily  = load_resampled_bars('NQ', 'train', '1 day', start_date=None)

# 1. Point-in-time Daily 200 SMA
b_daily['sma_200'] = b_daily['close'].rolling(200, min_periods=200).mean()
b_daily['daily_bull'] = (b_daily['close'] > b_daily['sma_200']).astype(int)
b_daily['daily_bear'] = (b_daily['close'] < b_daily['sma_200']).astype(int)
b_daily['avail_time'] = b_daily['timestamp_utc'] + pd.Timedelta(days=1)

# Join daily to 30m and 15m
b_mnq_15['avail_time'] = b_mnq_15['timestamp_utc']
b_mnq_15 = pd.merge_asof(
    b_mnq_15.sort_values('avail_time'),
    b_daily[['avail_time', 'sma_200', 'daily_bull', 'daily_bear']].sort_values('avail_time'),
    on='avail_time',
    direction='backward'
).sort_values('timestamp_utc').reset_index(drop=True)

loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
b_mnq_15['year'] = loc_15.dt.year

loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
weekdays_30 = loc_30.dt.weekday.to_numpy() < 5
d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)

loc_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
dec_60 = (loc_60.dt.hour * 60 + loc_60.dt.minute + 60).to_numpy()
weekdays_60 = loc_60.dt.weekday.to_numpy() < 5
d_mnq_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)

loc_mes_30 = b_mes_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_mes_30 = (loc_mes_30.dt.hour * 60 + loc_mes_30.dt.minute + 30).to_numpy()
weekdays_mes_30 = loc_mes_30.dt.weekday.to_numpy() < 5
d_mes_30 = apply_early_close(generalized_arrays(b_mes_30), b_mes_30)

d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c15 = np.roll(close_15, 1); prev_c15[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c15), np.abs(low_15 - prev_c15)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

# Morning Trend Sleeves
f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1_raw = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)

f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)

# Afternoon Trend Sleeve (13:30 - 15:15 ET)
f_aft = compute_htf_features(b_mnq_30, 8, 30)
sig_aft_raw = np.where((dec_30 >= 810) & (dec_30 <= 915) & weekdays_30 & (np.abs(f_aft['trend']) >= 0.50), np.sign(f_aft['trend']), 0).astype(np.int8)

# MES 30m Trend Sleeve
f_mes = compute_htf_features(b_mes_30, 8, 30)
sig_mes_raw = np.where((dec_mes_30 >= 585) & (dec_mes_30 <= 930) & weekdays_mes_30 & (np.abs(f_mes['trend']) >= 1.0), np.sign(f_mes['trend']), 0).astype(np.int8)

# Toby Crabel Open-Drive
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

dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_15.dt.date

sig_crabel = np.zeros(len(close_15), dtype=np.int8)
for i in range(len(close_15)):
    if is_1000_bar[i]:
        sig_crabel[i] = d_map_base.get(dates_all_15[i], 0)

# MES Direction at 10:00 ET
loc_mes_15 = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes_15.dt.hour * 60 + loc_mes_15.dt.minute
b_mes_15['date'] = loc_mes_15.dt.date
rth_mes_15 = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)
g_mes_15 = rth_mes_15.groupby('date')
mes_o930 = g_mes_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
mes_c1000 = g_mes_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
mes_dir_1000 = np.sign(mes_c1000 - mes_o930).fillna(0).astype(int).to_dict()

# Cross-asset alignment on Crabel
for i in range(len(sig_crabel)):
    if sig_crabel[i] != 0:
        m_dir = mes_dir_1000.get(dates_all_15[i], 0)
        if (sig_crabel[i] == 1 and m_dir < 0) or (sig_crabel[i] == -1 and m_dir > 0):
            sig_crabel[i] = 0

cfg_c = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=2.0, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)

cfg_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.5, target_ratio=3.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)

cfg_2 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.25, target_ratio=4.0, hold_bars=6, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=120)

cfg_aft = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
               stop_atr=1.5, target_ratio=4.0, hold_bars=4, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
               risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
               flat_minute=955, max_gap_minutes=60)

cfg_mes = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
               stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
               risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
               flat_minute=955, max_gap_minutes=60)

print("\n--- BASELINE: Architecture C++ (Crabel + S1 + S2) on 2010-2023 Train ---", flush=True)

def eval_portfolio(include_afternoon=False, include_mes=False, daily_filter=False):
    # Execute Crabel
    sig_c_use = sig_crabel.copy()
    if daily_filter:
        bull = b_mnq_15['daily_bull'].to_numpy()
        bear = b_mnq_15['daily_bear'].to_numpy()
        sig_c_use = np.where((sig_c_use == 1) & (bull == 1), 1, np.where((sig_c_use == -1) & (bear == 1), -1, 0)).astype(np.int8)
    
    r_c = me.execute(d_mnq_15, sig_c_use, atr_15, cfg_c)
    act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])
    
    # Sleeve 1 (30m)
    act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
    sig_1_use = np.where(~act_c_30, sig_1_raw, 0).astype(np.int8)
    r_1 = me.execute(d_mnq_30, sig_1_use, f_1['atr'], cfg_1)
    act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
    
    # Sleeve 2 (60m)
    act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
                  act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    sig_2_use = np.where(~act_all_60, sig_2_raw, 0).astype(np.int8)
    r_2 = me.execute(d_mnq_60, sig_2_use, f_2['atr'], cfg_2)
    act_2_60 = pd.Series(r_2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])
    
    results = [(r_c, d_mnq_15, b_mnq_15), (r_1, d_mnq_30, b_mnq_30), (r_2, d_mnq_60, b_mnq_60)]
    
    # Afternoon Sleeve
    if include_afternoon:
        act_all_30 = (act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False) |
                      act_1_30 |
                      act_2_60.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
        sig_aft_use = np.where(~act_all_30, sig_aft_raw, 0).astype(np.int8)
        r_aft = me.execute(d_mnq_30, sig_aft_use, f_aft['atr'], cfg_aft)
        act_aft_30 = pd.Series(r_aft['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
        results.append((r_aft, d_mnq_30, b_mnq_30))
    else:
        act_aft_30 = pd.Series(False, index=b_mnq_30['timestamp_utc'])
        
    # MES Sleeve
    if include_mes:
        act_all_mnq = (act_c_15.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                       act_1_30.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                       act_2_60.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                       act_aft_30.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
        sig_mes_use = np.where(~act_all_mnq, sig_mes_raw, 0).astype(np.int8)
        r_mes = me.execute(d_mes_30, sig_mes_use, f_mes['atr'], cfg_mes)
        results.append((r_mes, d_mes_30, b_mes_30))
        
    # Combine PnL
    common_idx = b_mnq_15['timestamp_utc']
    pnl = pd.Series(0.0, index=common_idx)
    tr_list = []
    
    for r, d, b in results:
        p = pd.Series(r['cash'] - 50000.0, index=b['timestamp_utc'])
        pnl = pnl + p.reindex(common_idx, method='ffill').fillna(0.0)
        if len(r['trade_entry']):
            y = d['year'][r['trade_entry']]
            net = r['trade_net']
            for yr, n in zip(y, net):
                tr_list.append((yr, n))
                
    peak = pnl.cummax()
    dd = peak - pnl
    max_dd = float(dd.max())
    total_net = float(pnl.iloc[-1])
    
    df_trades = pd.DataFrame(tr_list, columns=['year', 'net'])
    trade_years = df_trades['year'].to_numpy()
    trade_nets = df_trades['net'].to_numpy()
    
    m_pre = (trade_years >= 2010) & (trade_years < 2020)
    m_post = (trade_years >= 2020) & (trade_years < 2024)
    
    net_pre = float(trade_nets[m_pre].sum()) if np.any(m_pre) else 0.0
    cnt_pre = int(np.count_nonzero(m_pre))
    
    net_post = float(trade_nets[m_post].sum()) if np.any(m_post) else 0.0
    cnt_post = int(np.count_nonzero(m_post))
    
    tot_trades = len(trade_nets)
    exp = total_net / tot_trades if tot_trades else 0.0
    win_cnt = int(np.count_nonzero(trade_nets > 0))
    wr = win_cnt / tot_trades * 100.0 if tot_trades else 0.0
    
    yearly = df_trades.groupby('year')['net'].sum().to_dict()
    pos_years = sum(1 for y, v in yearly.items() if v > 0)
    tot_years = len(yearly)
    cushion = 2000.0 - max_dd
    
    return {
        "total_net": total_net, "tot_trades": tot_trades, "exp": exp,
        "max_dd": max_dd, "cushion": cushion, "wr": wr,
        "net_pre": net_pre, "cnt_pre": cnt_pre,
        "net_post": net_post, "cnt_post": cnt_post,
        "pos_years": pos_years, "tot_years": tot_years,
        "yearly": yearly
    }

base = eval_portfolio(include_afternoon=False, include_mes=False, daily_filter=False)
print(f"C++ BASELINE: Net: +${base['total_net']:,.2f} | Trades: {base['tot_trades']} | Exp: +${base['exp']:.2f}/tr | MaxDD: ${base['max_dd']:.2f} (Cushion: +${base['cushion']:.2f}) | Pre: +${base['net_pre']:.2f} ({base['cnt_pre']}) | Post: +${base['net_post']:.2f} ({base['cnt_post']}) | PosYears: {base['pos_years']}/{base['tot_years']}")

print("\n--- EXPERIMENT 1: Architecture C++ + Afternoon Trend Sleeve ---", flush=True)
exp1 = eval_portfolio(include_afternoon=True, include_mes=False, daily_filter=False)
print(f"C++ + AFTERNOON: Net: +${exp1['total_net']:,.2f} | Trades: {exp1['tot_trades']} | Exp: +${exp1['exp']:.2f}/tr | MaxDD: ${exp1['max_dd']:.2f} (Cushion: +${exp1['cushion']:.2f}) | Pre: +${exp1['net_pre']:.2f} ({exp1['cnt_pre']}) | Post: +${exp1['net_post']:.2f} ({exp1['cnt_post']}) | PosYears: {exp1['pos_years']}/{exp1['tot_years']}")

print("\n--- EXPERIMENT 2: Architecture C++ + MES 30m Trend Sleeve ---", flush=True)
exp2 = eval_portfolio(include_afternoon=False, include_mes=True, daily_filter=False)
print(f"C++ + MES: Net: +${exp2['total_net']:,.2f} | Trades: {exp2['tot_trades']} | Exp: +${exp2['exp']:.2f}/tr | MaxDD: ${exp2['max_dd']:.2f} (Cushion: +${exp2['cushion']:.2f}) | Pre: +${exp2['net_pre']:.2f} ({exp2['cnt_pre']}) | Post: +${exp2['net_post']:.2f} ({exp2['cnt_post']}) | PosYears: {exp2['pos_years']}/{exp2['tot_years']}")

print("\n--- EXPERIMENT 3: Architecture C++ + Afternoon + MES (Complete 5-Sleeve Ensemble) ---", flush=True)
exp3 = eval_portfolio(include_afternoon=True, include_mes=True, daily_filter=False)
print(f"C++ COMPLETE 5-SLEEVE: Net: +${exp3['total_net']:,.2f} | Trades: {exp3['tot_trades']} | Exp: +${exp3['exp']:.2f}/tr | MaxDD: ${exp3['max_dd']:.2f} (Cushion: +${exp3['cushion']:.2f}) | Pre: +${exp3['net_pre']:.2f} ({exp3['cnt_pre']}) | Post: +${exp3['net_post']:.2f} ({exp3['cnt_post']}) | PosYears: {exp3['pos_years']}/{exp3['tot_years']}")

print("\n--- EXPERIMENT 4: Architecture C++ + Daily 200 SMA Macro Filter ---", flush=True)
exp4 = eval_portfolio(include_afternoon=False, include_mes=False, daily_filter=True)
print(f"C++ + DAILY 200 SMA: Net: +${exp4['total_net']:,.2f} | Trades: {exp4['tot_trades']} | Exp: +${exp4['exp']:.2f}/tr | MaxDD: ${exp4['max_dd']:.2f} (Cushion: +${exp4['cushion']:.2f}) | Pre: +${exp4['net_pre']:.2f} ({exp4['cnt_pre']}) | Post: +${exp4['net_post']:.2f} ({exp4['cnt_post']}) | PosYears: {exp4['pos_years']}/{exp4['tot_years']}")

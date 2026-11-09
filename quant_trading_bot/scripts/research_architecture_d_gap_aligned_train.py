"""Research Script: Architecture D+ with Gap-Aligned Crabel on 14-Year Training Data (2010-2023).
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Investigates:
When Crabel Open-Drive is restricted to Gap-Continuation (drive == gap, which produced $25.29/tr & 14/14 positive years),
how does the full 4-sleeve router (Crabel > MNQ 30m > MNQ 60m > MES 30m) perform across 2010-2023?
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features

print("=" * 80)
print("RESEARCH: ARCHITECTURE D+ WITH GAP-ALIGNED CRABEL (2010-2023 TRAINING)")
print("=" * 80, flush=True)

# 1. Load 14-Year Training Bars
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mes_15 = load_resampled_bars('ES', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mes_30 = load_resampled_bars('ES', 'train', '30 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
b_mnq_15['year'] = loc_15.dt.year

loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_30['sod'] = loc_30.dt.hour * 60 + loc_30.dt.minute
b_mnq_30['date'] = loc_30.dt.date
b_mnq_30['year'] = loc_30.dt.year
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
weekdays_30 = loc_30.dt.weekday.to_numpy() < 5
d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)

loc_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_60['sod'] = loc_60.dt.hour * 60 + loc_60.dt.minute
b_mnq_60['date'] = loc_60.dt.date
b_mnq_60['year'] = loc_60.dt.year
dec_60 = (loc_60.dt.hour * 60 + loc_60.dt.minute + 60).to_numpy()
weekdays_60 = loc_60.dt.weekday.to_numpy() < 5
d_mnq_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)

loc_mes_30 = b_mes_30.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_30['sod'] = loc_mes_30.dt.hour * 60 + loc_mes_30.dt.minute
b_mes_30['date'] = loc_mes_30.dt.date
b_mes_30['year'] = loc_mes_30.dt.year
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

# 2. CBOE Backwardation Map
vix_path = ROOT / "data/external/VIX_History.csv"
vix3m_path = ROOT / "data/external/VIX3M_History.csv"
vix_df = pd.read_csv(vix_path); vix_df['date'] = pd.to_datetime(vix_df['DATE'], format='%m/%d/%Y').dt.date
vix_map = vix_df.set_index('date')['CLOSE'].astype(float).to_dict()
vix3m_df = pd.read_csv(vix3m_path); vix3m_df['date'] = pd.to_datetime(vix3m_df['DATE'], format='%m/%d/%Y').dt.date
vix3m_map = vix3m_df.set_index('date')['CLOSE'].astype(float).to_dict()
cboe_dates = np.array(sorted(list(vix_map.keys())))

def is_prior_backwardation(d):
    p = cboe_dates.searchsorted(d, side='left') - 1
    if p >= 0:
        cd = cboe_dates[p]
        return bool(vix_map.get(cd, 20.0) > vix3m_map.get(cd, 20.0))
    return False

# 3. Features
f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1_raw = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)

f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)

f_mes = compute_htf_features(b_mes_30, 8, 30)
sig_mes_raw = np.where((dec_mes_30 >= 585) & (dec_mes_30 <= 930) & weekdays_mes_30 & (np.abs(f_mes['trend']) >= 1.0), np.sign(f_mes['trend']), 0).astype(np.int8)

# 4. Opening stats for Crabel & Gap
rth_15 = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
g_15 = rth_15.groupby('date')
o930 = g_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000 = g_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
h1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'high'].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'low'].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
c1600 = g_15.apply(lambda d: d.loc[d.sod == 945, 'close'].iloc[0] if (d.sod == 945).any() else (d.iloc[-1]['close'] if len(d) else np.nan))

# MES opening
loc_mes_15 = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes_15.dt.hour * 60 + loc_mes_15.dt.minute
b_mes_15['date'] = loc_mes_15.dt.date
rth_mes_15 = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)
g_mes_15 = rth_mes_15.groupby('date')
mes_o930 = g_mes_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
mes_c1000 = g_mes_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
mes_dir_1000 = np.sign(mes_c1000 - mes_o930).fillna(0).astype(int).to_dict()

common_days = sorted(list(o930.dropna().index))
df_days = pd.DataFrame(index=common_days)
df_days['range'] = h1000.loc[common_days] - l1000.loc[common_days]
df_days['open_pos'] = (o930.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
df_days['close_pos'] = (c1000.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
df_days['prev_close'] = c1600.shift(1).loc[common_days]
df_days['gap'] = (o930.loc[common_days] - df_days['prev_close']) / df_days['prev_close']
df_days['is_backw'] = [is_prior_backwardation(d) for d in df_days.index]

dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_15.dt.date

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

cfg_mes = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
               stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
               risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
               flat_minute=955, max_gap_minutes=60)

def simulate_router(gap_align_crabel=False, label=""):
    cond_bull = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80) & (df_days['range'] >= 15.0)
    cond_bear = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20) & (df_days['range'] >= 15.0)
    
    if gap_align_crabel:
        cond_bull = cond_bull & (df_days['gap'] >= 0.0)
        cond_bear = cond_bear & (df_days['gap'] <= 0.0)
        
    d_map = dict(zip(df_days.index, np.where(cond_bull & ~df_days['is_backw'], 1, np.where(cond_bear & ~df_days['is_backw'], -1, 0))))
    
    sig_c = np.zeros(len(close_15), dtype=np.int8)
    for i in range(len(close_15)):
        if is_1000_bar[i]:
            d = dates_all_15[i]
            s = d_map.get(d, 0)
            if s != 0:
                m_dir = mes_dir_1000.get(d, 0)
                if (s == 1 and m_dir < 0) or (s == -1 and m_dir > 0):
                    s = 0
            sig_c[i] = s

    # Morning VIX term structure gate for trend sleeves
    prior_backw_dates = set(df_days.index[df_days['is_backw']])
    
    dates_30 = b_mnq_30['date'].to_numpy()
    sig_1 = sig_1_raw.copy()
    for i in range(len(sig_1)):
        if sig_1[i] != 0 and dates_30[i] in prior_backw_dates:
            sig_1[i] = 0
            
    dates_60 = b_mnq_60['date'].to_numpy()
    sig_2 = sig_2_raw.copy()
    for i in range(len(sig_2)):
        if sig_2[i] != 0 and dates_60[i] in prior_backw_dates:
            sig_2[i] = 0

    sig_mes = sig_mes_raw.copy()

    # Route sleeves with priority 1 > 2 > 3 > 4
    r_c = me.execute(d_mnq_15, sig_c, atr_15, cfg_c)
    act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])

    act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
    sig_1_routed = np.where(~act_c_30, sig_1, 0).astype(np.int8)
    r_1 = me.execute(d_mnq_30, sig_1_routed, f_1['atr'], cfg_1)
    act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])

    act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
                  act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    sig_2_routed = np.where(~act_all_60, sig_2, 0).astype(np.int8)
    r_2 = me.execute(d_mnq_60, sig_2_routed, f_2['atr'], cfg_2)
    act_2_60 = pd.Series(r_2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])

    act_all_mnq = (act_c_15.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                   act_1_30.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                   act_2_60.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    sig_mes_routed = np.where(~act_all_mnq, sig_mes, 0).astype(np.int8)
    r_mes = me.execute(d_mes_30, sig_mes_routed, f_mes['atr'], cfg_mes)

    # Compile trades
    tr_list = []
    for s_name, r, d, b_bar in [('Crabel', r_c, d_mnq_15, b_mnq_15), ('S1_30m', r_1, d_mnq_30, b_mnq_30), ('S2_60m', r_2, d_mnq_60, b_mnq_60), ('MES_30m', r_mes, d_mes_30, b_mes_30)]:
        if len(r['trade_entry']):
            y = d['year'][r['trade_entry']]
            net = r['trade_net']
            t_en = b_bar['timestamp_utc'].iloc[r['trade_entry']].values
            for yr, n, et in zip(y, net, t_en):
                tr_list.append({'sleeve': s_name, 'year': int(yr), 'net': float(n), 'entry_time': et})
                
    df_tr = pd.DataFrame(tr_list).sort_values('entry_time').reset_index(drop=True)
    
    net = float(df_tr['net'].sum())
    n_tr = len(df_tr)
    exp = net / n_tr
    wr = float((df_tr['net'] > 0).mean() * 100)
    
    cum = df_tr['net'].cumsum()
    peak = cum.cummax()
    dd = peak - cum
    max_dd = float(dd.max())
    cushion = 2000.0 - max_dd
    
    yr_g = df_tr.groupby('year')
    pos_years = sum(g['net'].sum() > 0 for _, g in yr_g)
    tot_years = len(yr_g)
    
    # Breakdown by sleeve
    sleeve_stats = {}
    for s_name, g in df_tr.groupby('sleeve'):
        sleeve_stats[s_name] = {
            'trades': len(g),
            'net': round(float(g['net'].sum()), 2),
            'exp': round(float(g['net'].mean()), 2),
            'wr': round(float((g['net'] > 0).mean() * 100), 1)
        }
        
    print(f"\n=======================================================")
    print(f"{label}")
    print(f"=======================================================")
    print(f"Net Profit:   ${net:>10,.2f}")
    print(f"Trades:        {n_tr:>10d}")
    print(f"Expectancy:   ${exp:>10.2f}/trade")
    print(f"Win Rate:      {wr:>10.1f}%")
    print(f"Realized DD:  ${max_dd:>10.2f}")
    print(f"Cushion ($2k):+${cushion:>10.2f} ({cushion/2000.0*100:.1f}%)")
    print(f"Pos Years:     {pos_years}/{tot_years}")
    print("\nSleeve Contribution:")
    for s_name, st in sleeve_stats.items():
        print(f"  {s_name:10s} | Tr: {st['trades']:>4d} | Net: ${st['net']:>8,.2f} | Exp: ${st['exp']:>6.2f}/tr | WR: {st['wr']:>5.1f}%")
        
    return {
        'net': net, 'trades': n_tr, 'exp': exp, 'wr': wr, 'max_dd': max_dd,
        'cushion': cushion, 'pos_years': f"{pos_years}/{tot_years}",
        'sleeves': sleeve_stats
    }

res_base = simulate_router(gap_align_crabel=False, label="BASELINE ARCHITECTURE D+ (Unconstrained Crabel)")
res_gap = simulate_router(gap_align_crabel=True, label="ENHANCED ARCHITECTURE D+ (Gap-Aligned Crabel)")

diff_net = res_gap['net'] - res_base['net']
diff_exp = res_gap['exp'] - res_base['exp']
diff_dd = res_gap['max_dd'] - res_base['max_dd']

print("\n" + "=" * 80)
print(f"TRAINING DELTA (ENHANCED vs BASELINE):")
print(f"  Net Profit Change:   {diff_net:>+8.2f}")
print(f"  Expectancy Change:   {diff_exp:>+8.2f}/trade")
print(f"  Max Drawdown Change: {diff_dd:>+8.2f}")
print("=" * 80)

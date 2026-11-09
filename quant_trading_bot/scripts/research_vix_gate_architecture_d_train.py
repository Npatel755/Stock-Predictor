"""Research Script: Volatility Term Structure Gate on Architecture D.
STRICTLY TRAINING DATA ONLY (2010-2023).
Zero access to Validation (2024-2025) or Blind Test (2026).

Hypothesis (from strategy-discovery and failure-learning):
When the CBOE volatility term structure closes in backwardation (VIX > VIX3M),
market openings suffer extreme gap-reversals and whipsaw chop. Gating morning MNQ
entries on days following a backwardation close eliminates loss-heavy tail sessions,
reducing continuous max drawdown and raising per-trade expectancy.

Falsification (from negative-control-testing):
Evaluate whether the P&L of trades removed by the backwardation filter is worse than
the 5th percentile of 20 random-day removals of identical count.
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

# 1. Load CBOE VIX & VIX3M
def load_cboe(ticker):
    df = pd.read_csv(ROOT / f"data/external/{ticker}_History.csv")
    df['date'] = pd.to_datetime(df['DATE'], format='%m/%d/%Y').dt.date
    return df.set_index('date')['CLOSE'].astype(float)

vix_series = load_cboe("VIX")
vix3m_series = load_cboe("VIX3M")
vix_ratio = (vix_series / vix3m_series).dropna()

loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
b_mnq_15['year'] = loc_15.dt.year

cal_dates = np.array(sorted(list(set(b_mnq_15['date']))))

def get_prior_day(d):
    idx = cal_dates.searchsorted(d)
    return cal_dates[idx - 1] if idx > 0 else None

# Prior day backwardation mapping
prior_backw_map = {}
for d in cal_dates:
    pd_date = get_prior_day(d)
    if pd_date is not None and pd_date in vix_ratio:
        prior_backw_map[d] = bool(vix_ratio.loc[pd_date] > 1.0)
    else:
        prior_backw_map[d] = False

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

f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1_raw = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)

f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)

f_mes = compute_htf_features(b_mes_30, 8, 30)
sig_mes_raw = np.where((dec_mes_30 >= 585) & (dec_mes_30 <= 930) & weekdays_mes_30 & (np.abs(f_mes['trend']) >= 1.0), np.sign(f_mes['trend']), 0).astype(np.int8)

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

loc_mes_15 = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes_15.dt.hour * 60 + loc_mes_15.dt.minute
b_mes_15['date'] = loc_mes_15.dt.date
rth_mes_15 = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)
g_mes_15 = rth_mes_15.groupby('date')
mes_o930 = g_mes_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
mes_c1000 = g_mes_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
mes_dir_1000 = np.sign(mes_c1000 - mes_o930).fillna(0).astype(int).to_dict()

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

cfg_mes = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
               stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
               risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
               flat_minute=955, max_gap_minutes=60)

def run_simulation(gate_morning_mnq=False, gate_mes=False):
    # Apply backwardation gate to signals
    s_c = sig_crabel.copy()
    s_1 = sig_1_raw.copy()
    s_2 = sig_2_raw.copy()
    s_m = sig_mes_raw.copy()
    
    if gate_morning_mnq:
        dates_15 = b_mnq_15['date'].to_numpy()
        for i in range(len(s_c)):
            if s_c[i] != 0 and prior_backw_map.get(dates_15[i], False):
                s_c[i] = 0
                
        dates_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York').dt.date.to_numpy()
        for i in range(len(s_1)):
            if s_1[i] != 0 and prior_backw_map.get(dates_30[i], False):
                s_1[i] = 0
                
        dates_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York').dt.date.to_numpy()
        for i in range(len(s_2)):
            if s_2[i] != 0 and prior_backw_map.get(dates_60[i], False):
                s_2[i] = 0
                
    if gate_mes:
        dates_mes = b_mes_30.timestamp_utc.dt.tz_convert('America/New_York').dt.date.to_numpy()
        for i in range(len(s_m)):
            if s_m[i] != 0 and prior_backw_map.get(dates_mes[i], False):
                s_m[i] = 0

    r_c = me.execute(d_mnq_15, s_c, atr_15, cfg_c)
    act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])

    act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
    s_1_routed = np.where(~act_c_30, s_1, 0).astype(np.int8)
    r_1 = me.execute(d_mnq_30, s_1_routed, f_1['atr'], cfg_1)
    act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])

    act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
                  act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    s_2_routed = np.where(~act_all_60, s_2, 0).astype(np.int8)
    r_2 = me.execute(d_mnq_60, s_2_routed, f_2['atr'], cfg_2)
    act_2_60 = pd.Series(r_2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])

    act_all_mnq = (act_c_15.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                   act_1_30.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
                   act_2_60.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    s_mes_routed = np.where(~act_all_mnq, s_m, 0).astype(np.int8)
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

    yearly = df_trades.groupby('year')['net'].sum().to_dict()
    pos_years = sum(1 for y, v in yearly.items() if v > 0)
    tot_years = len(yearly)
    cushion = 2000.0 - max_dd

    return {
        "total_net": total_net, "tot_trades": tot_trades, "exp_tot": exp_tot,
        "max_dd": max_dd, "cushion": cushion, "pos_years": pos_years, "tot_years": tot_years,
        "net_pre": net_pre, "cnt_pre": cnt_pre, "exp_pre": exp_pre,
        "net_post": net_post, "cnt_post": cnt_post, "exp_post": exp_post,
        "yearly": yearly, "df_trades": df_trades
    }

print("\n--- RUNNING TRAINING EXPERIMENTS (2010-2023) ---", flush=True)
base = run_simulation(gate_morning_mnq=False, gate_mes=False)
gated = run_simulation(gate_morning_mnq=True, gate_mes=False)
gated_all = run_simulation(gate_morning_mnq=True, gate_mes=True)

print(f"{'Configuration':<35} | {'Net ($)':<10} | {'Trades':<6} | {'Exp ($)':<8} | {'MaxDD ($)':<9} | {'Cushion ($)':<11} | {'Pre-2020':<10} | {'Post-2020':<10}")
print("-" * 115)
print(f"{'Architecture D Baseline':<35} | +${base['total_net']:8.2f} | {base['tot_trades']:6d} | +${base['exp_tot']:6.2f} | ${base['max_dd']:7.2f} | +${base['cushion']:9.2f} | +${base['net_pre']:8.2f} | +${base['net_post']:8.2f}")
print(f"{'Arch D + Morning VIX Gate':<35} | +${gated['total_net']:8.2f} | {gated['tot_trades']:6d} | +${gated['exp_tot']:6.2f} | ${gated['max_dd']:7.2f} | +${gated['cushion']:9.2f} | +${gated['net_pre']:8.2f} | +${gated['net_post']:8.2f}")
print(f"{'Arch D + All Sleeves VIX Gate':<35} | +${gated_all['total_net']:8.2f} | {gated_all['tot_trades']:6d} | +${gated_all['exp_tot']:6.2f} | ${gated_all['max_dd']:7.2f} | +${gated_all['cushion']:9.2f} | +${gated_all['net_pre']:8.2f} | +${gated_all['net_post']:8.2f}")

diff_net = gated['total_net'] - base['total_net']
diff_dd = base['max_dd'] - gated['max_dd']
print("\n" + "=" * 90)
print(f"ANALYSIS OF MORNING VIX BACKWARDATION GATE:")
print(f"Net Profit Impact:    +${diff_net:,.2f} ({'+' if diff_net > 0 else ''}{diff_net/base['total_net']*100:.2f}%)")
print(f"Max Drawdown Impact:  -${diff_dd:,.2f} ({'-' if diff_dd > 0 else ''}{diff_dd/base['max_dd']*100:.2f}% DD reduction)")
print(f"Expectancy:           Raised from +${base['exp_tot']:.2f}/tr to +${gated['exp_tot']:.2f}/tr")
print(f"Trades Filtered:      {base['tot_trades'] - gated['tot_trades']} toxic backwardation trades eliminated")
print("=" * 90)

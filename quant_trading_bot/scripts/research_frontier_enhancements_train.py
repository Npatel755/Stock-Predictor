"""Research Frontier Enhancements Strictly on 2010-2023 Training Data.
Scientific Protocol:
- STRICTLY 2010-2023 Training Bars (NQ and ES).
- ZERO access to Validation (2024-2025) or Blind Test (2026).
- CME Micro friction ($0.61/side, 1.75 tick MNQ / 1.0 tick MES spread, 1.0 tick slippage = $3.97 RT).
- $50,000 capital, strict $2,000 trailing drawdown floor.
- Strict 1-contract global limit across the account.

Frontiers Investigated:
1. Frontier 1: Cross-Asset Confirmation (Broad-Market MES Directional Alignment).
   - Thesis: A morning expansion on MNQ has significantly higher win rate and lower drawdown when MES confirms the same direction (broad institutional consensus vs tech divergence).
2. Frontier 2: Trailing ATR Stop (Chandelier Stop vs Fixed Target Ratio).
   - Thesis: Replacing or augmenting fixed targets with a trailing ATR stop allows outlier morning trends to run while locking in profits.
3. Frontier 3: Opening Range Volatility Gating.
   - Thesis: When opening 30m range is below 15 points or 0.4 ATR, chop probability is high. Filtering these sessions eliminates churn.
4. Frontier 4: Day-of-Week Seasonality Attribution.
   - Thesis: Intraday morning trend capture performance varies by day of the week (e.g. Wednesday FOMC chop vs Tuesday/Thursday continuation).
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

print("Loading STRICTLY 2010-2023 Training Bars for MNQ and MES...", flush=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mes_15 = load_resampled_bars('ES', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

# Timestamps & session arrays
loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
b_mnq_15['year'] = loc_15.dt.year
b_mnq_15['dow'] = loc_15.dt.weekday

loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
weekdays_30 = loc_30.dt.weekday.to_numpy() < 5
d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)

loc_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
dec_60 = (loc_60.dt.hour * 60 + loc_60.dt.minute + 60).to_numpy()
weekdays_60 = loc_60.dt.weekday.to_numpy() < 5
d_mnq_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)

d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c15 = np.roll(close_15, 1); prev_c15[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c15), np.abs(low_15 - prev_c15)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

# HTF features
f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1_raw = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)

f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)

# Crabel calculation
rth_15 = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
g_15 = rth_15.groupby('date')
o930 = g_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000 = g_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan) # Clean 10:00 close
h1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'high'].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'low'].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

common_days = sorted(list(o930.dropna().index))
df_days = pd.DataFrame(index=common_days)
df_days['range'] = h1000.loc[common_days] - l1000.loc[common_days]
df_days['open_pos'] = (o930.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
df_days['close_pos'] = (c1000.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)

cond_bull_base = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80)
cond_bear_base = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20)
d_map_base = dict(zip(df_days.index, np.where(cond_bull_base, 1, np.where(cond_bear_base, -1, 0))))

dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_15.dt.date

sig_crabel = np.zeros(len(close_15), dtype=np.int8)
for i in range(len(close_15)):
    if is_1000_bar[i]:
        sig_crabel[i] = d_map_base.get(dates_all_15[i], 0)

# MES Direction at 10:00 ET (Clean point-in-time calculation)
loc_mes_15 = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes_15.dt.hour * 60 + loc_mes_15.dt.minute
b_mes_15['date'] = loc_mes_15.dt.date
rth_mes_15 = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)
g_mes_15 = rth_mes_15.groupby('date')
mes_o930 = g_mes_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
mes_c1000 = g_mes_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan) # Clean 10:00 close (sod 585)
mes_dir_1000 = np.sign(mes_c1000 - mes_o930).fillna(0).astype(int).to_dict()

# Base configs (Enhanced Architecture C discovered in previous turn)
cfg_enh_c = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=2.0, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

cfg_enh_1 = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=1.5, target_ratio=3.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

cfg_enh_2 = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=1.25, target_ratio=4.0, hold_bars=6, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=120
)

def run_sim(sig_c_in, sig_1_in, sig_2_in, cfg_c_in, cfg_1_in, cfg_2_in):
    r_c = me.execute(d_mnq_15, sig_c_in, atr_15, cfg_c_in)
    act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])

    act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
    sig_1_routed = np.where(~act_c_30, sig_1_in, 0).astype(np.int8)
    r_1 = me.execute(d_mnq_30, sig_1_routed, f_1['atr'], cfg_1_in)
    act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])

    act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
                  act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    sig_2_routed = np.where(~act_all_60, sig_2_in, 0).astype(np.int8)
    r_2 = me.execute(d_mnq_60, sig_2_routed, f_2['atr'], cfg_2_in)

    p_c = pd.Series(r_c['cash'] - 50000.0, index=b_mnq_15['timestamp_utc'])
    p_1 = pd.Series(r_1['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
    p_2 = pd.Series(r_2['cash'] - 50000.0, index=b_mnq_60['timestamp_utc'])

    common_idx = b_mnq_15['timestamp_utc']
    pnl = p_c + p_1.reindex(common_idx, method='ffill').fillna(0.0) + p_2.reindex(common_idx, method='ffill').fillna(0.0)
    peak = pnl.cummax()
    dd = peak - pnl
    max_dd = float(dd.max())
    total_net = float(pnl.iloc[-1])

    tr_list = []
    for r, d in [(r_c, d_mnq_15), (r_1, d_mnq_30), (r_2, d_mnq_60)]:
        if len(r['trade_entry']):
            y = d['year'][r['trade_entry']]
            net = r['trade_net']
            for yr, n in zip(y, net):
                tr_list.append((yr, n))
    df_trades = pd.DataFrame(tr_list, columns=['year', 'net'])
    tot_tr = len(df_trades)
    exp = total_net / tot_tr if tot_tr else 0.0
    pre_net = df_trades[df_trades.year < 2020]['net'].sum() if len(df_trades) else 0.0
    post_net = df_trades[df_trades.year >= 2020]['net'].sum() if len(df_trades) else 0.0
    yearly = df_trades.groupby('year')['net'].sum().to_dict() if len(df_trades) else {}
    pos_years = sum(1 for y, v in yearly.items() if v > 0)
    cushion = 2000.0 - max_dd

    return {
        "net": total_net, "trades": tot_tr, "exp": exp,
        "max_dd": max_dd, "cushion": cushion,
        "pre_2020": pre_net, "post_2020": post_net,
        "pos_years": pos_years
    }

base_res = run_sim(sig_crabel, sig_1_raw, sig_2_raw, cfg_enh_c, cfg_enh_1, cfg_enh_2)
print("\n" + "=" * 90)
print("BENCHMARK: ENHANCED ARCHITECTURE C BASELINE (TRAIN 2010-2023)")
print("=" * 90)
print(f"Net: ${base_res['net']:+9.2f} | Tr: {base_res['trades']:4d} | Exp: ${base_res['exp']:+5.2f}/tr | Max DD: ${base_res['max_dd']:7.2f} | Cushion: ${base_res['cushion']:+7.2f} | Pre: ${base_res['pre_2020']:+8.2f} | Pos Yrs: {base_res['pos_years']}/14")

print("\n" + "=" * 90)
print("FRONTIER 1: CROSS-ASSET CONFIRMATION (MES BROAD-MARKET DIRECTIONAL ALIGNMENT)")
print("=" * 90)
# Hypothesis: Long MNQ only if MES open-drive is >= 0; Short MNQ only if MES open-drive is <= 0
for mode in ['align_crabel_only', 'align_all']:
    sig_c_f1 = sig_crabel.copy()
    sig_1_f1 = sig_1_raw.copy()
    sig_2_f1 = sig_2_raw.copy()
    
    for i in range(len(sig_c_f1)):
        if sig_c_f1[i] != 0:
            m_dir = mes_dir_1000.get(dates_all_15[i], 0)
            if (sig_c_f1[i] == 1 and m_dir < 0) or (sig_c_f1[i] == -1 and m_dir > 0):
                sig_c_f1[i] = 0
                
    if mode == 'align_all':
        dates_30 = loc_30.dt.date
        for i in range(len(sig_1_f1)):
            if sig_1_f1[i] != 0:
                m_dir = mes_dir_1000.get(dates_30[i], 0)
                if (sig_1_f1[i] == 1 and m_dir < 0) or (sig_1_f1[i] == -1 and m_dir > 0):
                    sig_1_f1[i] = 0
        dates_60 = loc_60.dt.date
        for i in range(len(sig_2_f1)):
            if sig_2_f1[i] != 0:
                m_dir = mes_dir_1000.get(dates_60[i], 0)
                if (sig_2_f1[i] == 1 and m_dir < 0) or (sig_2_f1[i] == -1 and m_dir > 0):
                    sig_2_f1[i] = 0
                    
    res = run_sim(sig_c_f1, sig_1_f1, sig_2_f1, cfg_enh_c, cfg_enh_1, cfg_enh_2)
    print(f"MES Alignment Mode '{mode:<18}': Net = ${res['net']:+9.2f} | Tr: {res['trades']:4d} | Exp: ${res['exp']:+5.2f}/tr | Max DD: ${res['max_dd']:7.2f} | Cushion: ${res['cushion']:+7.2f} | Pre: ${res['pre_2020']:+8.2f} | Pos Yrs: {res['pos_years']}/14")

print("\n" + "=" * 90)
print("FRONTIER 2: CHANDELIER TRAILING STOP EVALUATION (TRAIN 2010-2023)")
print("=" * 90)
for trail_val in [0.0, 1.5, 2.0, 2.5, 3.0]:
    cfg_c_trail = cfg_enh_c.copy()
    cfg_c_trail['trailing_atr'] = trail_val
    res = run_sim(sig_crabel, sig_1_raw, sig_2_raw, cfg_c_trail, cfg_enh_1, cfg_enh_2)
    print(f"Crabel Trailing ATR = {trail_val:4.1f}: Net = ${res['net']:+9.2f} | Tr: {res['trades']:4d} | Exp: ${res['exp']:+5.2f}/tr | Max DD: ${res['max_dd']:7.2f} | Cushion: ${res['cushion']:+7.2f} | Pre: ${res['pre_2020']:+8.2f} | Pos Yrs: {res['pos_years']}/14")

print("\n" + "=" * 90)
print("FRONTIER 3: DAY OF WEEK SEASONALITY ATTRIBUTION (TRAIN 2010-2023)")
print("=" * 90)
# Break down trades by DOW
r_c = me.execute(d_mnq_15, sig_crabel, atr_15, cfg_enh_c)
act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])
act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
sig_1_routed = np.where(~act_c_30, sig_1_raw, 0).astype(np.int8)
r_1 = me.execute(d_mnq_30, sig_1_routed, f_1['atr'], cfg_enh_1)
act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
              act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
sig_2_routed = np.where(~act_all_60, sig_2_raw, 0).astype(np.int8)
r_2 = me.execute(d_mnq_60, sig_2_routed, f_2['atr'], cfg_enh_2)

tr_dow = []
for r, d, b in [(r_c, d_mnq_15, b_mnq_15), (r_1, d_mnq_30, b_mnq_30), (r_2, d_mnq_60, b_mnq_60)]:
    if len(r['trade_entry']):
        ts = b['timestamp_utc'].iloc[r['trade_entry']]
        dow = ts.dt.tz_convert('America/New_York').dt.day_name()
        net = r['trade_net']
        for w, n in zip(dow, net):
            tr_dow.append((w, n))
df_dow = pd.DataFrame(tr_dow, columns=['dow', 'net'])
dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
for d in dow_order:
    sub = df_dow[df_dow.dow == d]
    print(f"  {d:<10}: Net = ${sub['net'].sum():+9.2f} | Trades: {len(sub):4d} | Exp: ${sub['net'].mean():+5.2f}/tr | Win Rate: {(sub['net']>0).mean()*100:.1f}%")

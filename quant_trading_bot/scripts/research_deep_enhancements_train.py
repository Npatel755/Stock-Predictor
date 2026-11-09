"""Deep Strategy Improvement & Optimization Research: 2010-2023 Training Data ONLY.
Strict Constraints:
- ZERO access to Validation (2024-2025) or Blind Test (2026).
- CME Micro friction on every trade ($0.61/side, 1.75 tick spread, 1.0 tick slippage = $3.97 RT).
- $50,000 capital, strict $2,000 trailing drawdown floor.
- Strict 1-contract global limit across the account.

Hypotheses to Test on 2010-2023 Training Data:
1. Toby Crabel Filter Enhancement (Range Expansion Filter):
   - Thesis: Open-drive setups are most reliable when the 09:30-10:00 range is >= 0.5 * 14-period ATR (avoiding compressed-range false breakouts).
2. Asymmetric Target / Hold Time for Shorts:
   - Thesis: Equity index intraday shorts are mean-reverting and spike down quickly; taking faster profit (e.g. 2.5R target / 6-8 bar hold) prevents giving back gains during morning reversals.
3. Daily Macro Trend Filter (Daily 200 SMA / 50 SMA Directional Gate):
   - Thesis: Only taking Long trend setups when price is above daily 200 SMA (or 50 SMA) and Shorts when below filters out counter-trend chop.
4. Breakeven Ratchet Mechanism:
   - Thesis: Moving stop to entry (+1 tick) after reaching +1.5 ATR favorable excursion eliminates catastrophic reversals.
5. VIX Term Structure Crush Integration:
   - Thesis: Integrating the placebo-proven VIX Term Structure Crush (+4.1k on train) as an orthogonal institutional setup on days with vol collapse.
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

print("Loading STRICTLY 2010-2023 Training Bars for MNQ (15m, 30m, 60m)...", flush=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

# Common timestamps & arrays
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

# 15m arrays
d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c15 = np.roll(close_15, 1); prev_c15[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c15), np.abs(low_15 - prev_c15)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

# Precalculate 30m and 60m trend features
f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1_raw = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)

f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)

# Crabel calculations
rth_15 = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
g_15 = rth_15.groupby('date')
o930 = g_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000 = g_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan) # Clean 10:00 close (sod 585)
h1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'high'].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'low'].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

common_days = sorted(list(o930.dropna().index))
df_days = pd.DataFrame(index=common_days)
df_days['range'] = h1000.loc[common_days] - l1000.loc[common_days]
df_days['open_pos'] = (o930.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
df_days['close_pos'] = (c1000.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)

# Map 15m ATR to dates
b_mnq_15['atr'] = atr_15
date_to_atr1000 = b_mnq_15[b_mnq_15.sod == 585].groupby('date')['atr'].first().to_dict()
df_days['atr'] = df_days.index.map(date_to_atr1000)
df_days['range_atr_ratio'] = df_days['range'] / df_days['atr'].replace(0, np.nan)

# Configurations for testing
cfg_base_c = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=2.0, target_ratio=4.0, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

cfg_base_1 = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

cfg_base_2 = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=120
)

dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_15.dt.date

def run_portfolio_sim(sig_c, sig_1_in, sig_2_in, cfg_c_in, cfg_1_in, cfg_2_in):
    r_c = me.execute(d_mnq_15, sig_c, atr_15, cfg_c_in)
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

print("\n" + "=" * 90)
print("EXPERIMENT 1: TOBY CRABEL RANGE EXPANSION FILTER (TRAIN 2010-2023)")
print("=" * 90)
# Test minimum range-to-ATR ratio: 0.0 (no filter), 0.3, 0.5, 0.7, 1.0
for min_ratio in [0.0, 0.3, 0.5, 0.7]:
    cond_bull = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80) & (df_days['range_atr_ratio'] >= min_ratio)
    cond_bear = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20) & (df_days['range_atr_ratio'] >= min_ratio)
    sig_map = np.where(cond_bull, 1, np.where(cond_bear, -1, 0))
    d_map = dict(zip(df_days.index, sig_map))
    
    sig_c_test = np.zeros(len(close_15), dtype=np.int8)
    for i in range(len(close_15)):
        if is_1000_bar[i]:
            sig_c_test[i] = d_map.get(dates_all_15[i], 0)
            
    res = run_portfolio_sim(sig_c_test, sig_1_raw, sig_2_raw, cfg_base_c, cfg_base_1, cfg_base_2)
    print(f"Min Range/ATR >= {min_ratio:3.1f}: Net = ${res['net']:+9.2f} | Tr: {res['trades']:4d} | Exp: ${res['exp']:+5.2f}/tr | Max DD: ${res['max_dd']:7.2f} | Cushion: ${res['cushion']:+7.2f} | Pre: ${res['pre_2020']:+8.2f} | Pos Yrs: {res['pos_years']}/14")

print("\n" + "=" * 90)
print("EXPERIMENT 2: CRABEL TARGET & STOP RATIO SWEEP (TRAIN 2010-2023)")
print("=" * 90)
# Base Crabel: stop_atr=2.0, target_ratio=4.0, hold_bars=12
best_sig_c = np.zeros(len(close_15), dtype=np.int8)
cond_bull_base = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80)
cond_bear_base = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20)
d_map_base = dict(zip(df_days.index, np.where(cond_bull_base, 1, np.where(cond_bear_base, -1, 0))))
for i in range(len(close_15)):
    if is_1000_bar[i]:
        best_sig_c[i] = d_map_base.get(dates_all_15[i], 0)

for s_atr in [1.5, 1.75, 2.0]:
    for t_ratio in [3.0, 3.5, 4.0, 4.5]:
        for h_bars in [8, 12]:
            cfg_c_test = cfg_base_c.copy()
            cfg_c_test['stop_atr'] = s_atr
            cfg_c_test['target_ratio'] = t_ratio
            cfg_c_test['hold_bars'] = h_bars
            
            res = run_portfolio_sim(best_sig_c, sig_1_raw, sig_2_raw, cfg_c_test, cfg_base_1, cfg_base_2)
            print(f"Stop: {s_atr:4.2f} | Tgt: {t_ratio:3.1f} | Hold: {h_bars:2d} | Net: ${res['net']:+9.2f} | Tr: {res['trades']:4d} | Exp: ${res['exp']:+5.2f}/tr | Max DD: ${res['max_dd']:7.2f} | Cushion: ${res['cushion']:+7.2f} | Pre: ${res['pre_2020']:+8.2f}")

print("\n" + "=" * 90)
print("EXPERIMENT 3: DAILY 200 SMA MACRO REGIME GATE (TRAIN 2010-2023)")
print("=" * 90)
# Build daily close series and 200 SMA
daily_close = b_mnq_15.groupby('date')['close'].last()
daily_sma200 = daily_close.rolling(200, min_periods=200).mean().shift(1) # Point-in-time previous day close SMA
date_to_sma200 = daily_sma200.to_dict()
date_to_prev_close = daily_close.shift(1).to_dict()

# Bullish macro: previous day close > 200 SMA
# Bearish macro: previous day close < 200 SMA
macro_trend = {}
for dt, pc in date_to_prev_close.items():
    sma = date_to_sma200.get(dt, np.nan)
    if np.isnan(sma):
        macro_trend[dt] = 0
    elif pc > sma:
        macro_trend[dt] = 1
    else:
        macro_trend[dt] = -1

# Test filtering:
# Mode A: Unfiltered (Baseline Architecture C)
# Mode B: Only take Longs if macro == 1, only Shorts if macro == -1 (strict alignment)
# Mode C: Only gate Crabel or only gate Trend Sleeves?

for mode in ['baseline', 'gate_all', 'gate_trend_only', 'gate_crabel_only']:
    sig_c_mode = best_sig_c.copy()
    sig_1_mode = sig_1_raw.copy()
    sig_2_mode = sig_2_raw.copy()
    
    if mode in ['gate_all', 'gate_crabel_only']:
        for i in range(len(sig_c_mode)):
            if sig_c_mode[i] != 0:
                m = macro_trend.get(dates_all_15[i], 0)
                if (sig_c_mode[i] == 1 and m == -1) or (sig_c_mode[i] == -1 and m == 1):
                    sig_c_mode[i] = 0
                    
    if mode in ['gate_all', 'gate_trend_only']:
        # Gate 30m trend
        dates_30 = loc_30.dt.date
        for i in range(len(sig_1_mode)):
            if sig_1_mode[i] != 0:
                m = macro_trend.get(dates_30[i], 0)
                if (sig_1_mode[i] == 1 and m == -1) or (sig_1_mode[i] == -1 and m == 1):
                    sig_1_mode[i] = 0
        # Gate 60m trend
        dates_60 = loc_60.dt.date
        for i in range(len(sig_2_mode)):
            if sig_2_mode[i] != 0:
                m = macro_trend.get(dates_60[i], 0)
                if (sig_2_mode[i] == 1 and m == -1) or (sig_2_mode[i] == -1 and m == 1):
                    sig_2_mode[i] = 0
                    
    res = run_portfolio_sim(sig_c_mode, sig_1_mode, sig_2_mode, cfg_base_c, cfg_base_1, cfg_base_2)
    print(f"Macro Gate Mode '{mode:<17}': Net = ${res['net']:+9.2f} | Tr: {res['trades']:4d} | Exp: ${res['exp']:+5.2f}/tr | Max DD: ${res['max_dd']:7.2f} | Cushion: ${res['cushion']:+7.2f} | Pre: ${res['pre_2020']:+8.2f} | Pos Yrs: {res['pos_years']}/14")

print("\n" + "=" * 90)
print("EXPERIMENT 4: ASYMMETRIC HOLD TIME & SHORT TARGET (TRAIN 2010-2023)")
print("=" * 90)
# Test holding longs 12 bars vs shorts 8 bars or stop/target variations on Sleeve 1 & 2
# We can evaluate standalone long vs short performance
for s_name, r, d in [('Crabel S1', me.execute(d_mnq_15, best_sig_c, atr_15, cfg_base_c), d_mnq_15),
                     ('30m S2', me.execute(d_mnq_30, sig_1_raw, f_1['atr'], cfg_base_1), d_mnq_30),
                     ('60m S3', me.execute(d_mnq_60, sig_2_raw, f_2['atr'], cfg_base_2), d_mnq_60)]:
    sides = r['trade_side']
    nets = r['trade_net']
    longs = nets[sides == 1]
    shorts = nets[sides == -1]
    print(f"{s_name:<10}: Longs: ${longs.sum():+9.2f} ({len(longs):3d} tr, ${longs.mean() if len(longs) else 0:+5.2f}/tr) | Shorts: ${shorts.sum():+9.2f} ({len(shorts):3d} tr, ${shorts.mean() if len(shorts) else 0:+5.2f}/tr)")

"""Research Script: Toby Crabel Institutional Open-Drive Enhancement Suite.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Investigates on 14 years of training data:
1. Gap Alignment Filter: Does aligning the 10:00 Open Drive with the overnight/opening gap improve expectancy?
2. Multi-Timeframe Volume Confirmation: Does above-average opening 30m volume filter out false drives?
3. Prior-Day Range Position: Does driving out of the prior day's value area / range produce higher follow-through?
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

print("=" * 80)
print("RESEARCH: CRABEL OPEN-DRIVE ENHANCEMENT SUITE (2010-2023 TRAINING)")
print("=" * 80, flush=True)

# 1. Load 14-Year Training Bars
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mes_15 = load_resampled_bars('ES', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
b_mnq_15['year'] = loc_15.dt.year

loc_mes_15 = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes_15.dt.hour * 60 + loc_mes_15.dt.minute
b_mes_15['date'] = loc_mes_15.dt.date

d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)

close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c15 = np.roll(close_15, 1); prev_c15[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c15), np.abs(low_15 - prev_c15)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

# 2. Extract daily RTH opening stats
rth_15 = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
g_15 = rth_15.groupby('date')
o930 = g_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000 = g_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
h1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'high'].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'low'].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
c1600 = g_15.apply(lambda d: d.loc[d.sod == 945, 'close'].iloc[0] if (d.sod == 945).any() else (d.iloc[-1]['close'] if len(d) else np.nan))
v1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'volume'].sum() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

# MES opening stats
rth_mes = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)
g_mes = rth_mes.groupby('date')
mes_o930 = g_mes.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
mes_c1000 = g_mes.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
mes_dir_1000 = np.sign(mes_c1000 - mes_o930).fillna(0).astype(int).to_dict()

common_days = sorted(list(o930.dropna().index))
df_days = pd.DataFrame(index=common_days)
df_days['range'] = h1000.loc[common_days] - l1000.loc[common_days]
df_days['open_pos'] = (o930.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
df_days['close_pos'] = (c1000.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
df_days['prev_close'] = c1600.shift(1).loc[common_days]
df_days['gap'] = (o930.loc[common_days] - df_days['prev_close']) / df_days['prev_close']
df_days['vol_open'] = v1000.loc[common_days]
df_days['vol_ma20'] = df_days['vol_open'].rolling(20, min_periods=10).mean().shift(1)
df_days['rvol'] = df_days['vol_open'] / df_days['vol_ma20']

# Base Crabel Signal
cond_bull_base = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80) & (df_days['range'] >= 15.0)
cond_bear_base = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20) & (df_days['range'] >= 15.0)

# CBOE Term Structure Gate
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

df_days['is_backw'] = [is_prior_backwardation(d) for d in df_days.index]

# Signal generator
dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_15.dt.date

cfg_c = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=2.0, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)

def test_signal_variant(cond_bull, cond_bear, label):
    d_map = dict(zip(df_days.index, np.where(cond_bull & ~df_days['is_backw'], 1, np.where(cond_bear & ~df_days['is_backw'], -1, 0))))
    sig = np.zeros(len(close_15), dtype=np.int8)
    for i in range(len(close_15)):
        if is_1000_bar[i]:
            d = dates_all_15[i]
            s = d_map.get(d, 0)
            if s != 0:
                m_dir = mes_dir_1000.get(d, 0)
                if (s == 1 and m_dir < 0) or (s == -1 and m_dir > 0):
                    s = 0
            sig[i] = s
            
    r = me.execute(d_mnq_15, sig, atr_15, cfg_c)
    tn = r['trade_net']
    n_tr = len(tn)
    if n_tr == 0:
        return None
    net = float(tn.sum())
    exp = net / n_tr
    wr = float(np.mean(tn > 0) * 100)
    
    cum = np.cumsum(tn)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd = float(np.max(dd))
    
    # Yearly
    t_en = r['trade_entry']
    y_arr = d_mnq_15['year'][t_en]
    years = sorted(list(set(y_arr)))
    yearly_pnl = {int(y): float(tn[y_arr == y].sum()) for y in years}
    pos_years = sum(v > 0 for v in yearly_pnl.values())
    
    print(f"{label:45s} | Net: ${net:>9,.2f} | Tr: {n_tr:>4d} | Exp: ${exp:>6.2f}/tr | WR: {wr:>5.1f}% | DD: ${max_dd:>8.2f} | Pos Yrs: {pos_years}/{len(years)}")
    return dict(name=label, net=net, trades=n_tr, exp=exp, wr=wr, max_dd=max_dd, pos_years=pos_years)

print("\n--- BASELINE CRABEL ON 14-YEAR TRAINING (2010-2023) ---")
test_signal_variant(cond_bull_base, cond_bear_base, "Baseline: Crabel + VIX Gate + MES Filter")

print("\n--- HYPOTHESIS 1: GAP ALIGNMENT FILTER ---")
# Only take bull drives if gap >= 0 (continuation)
test_signal_variant(cond_bull_base & (df_days['gap'] >= 0.0), cond_bear_base & (df_days['gap'] <= 0.0), "H1A: Gap Continuation Only (drive == gap)")
test_signal_variant(cond_bull_base & (df_days['gap'] < 0.0), cond_bear_base & (df_days['gap'] > 0.0), "H1B: Gap Fade Only (drive != gap)")

print("\n--- HYPOTHESIS 2: OPENING RELATIVE VOLUME (RVOL) ---")
test_signal_variant(cond_bull_base & (df_days['rvol'] >= 0.8), cond_bear_base & (df_days['rvol'] >= 0.8), "H2A: RVOL >= 0.8")
test_signal_variant(cond_bull_base & (df_days['rvol'] >= 1.0), cond_bear_base & (df_days['rvol'] >= 1.0), "H2B: RVOL >= 1.0 (Above Average Volume)")
test_signal_variant(cond_bull_base & (df_days['rvol'] >= 1.2), cond_bear_base & (df_days['rvol'] >= 1.2), "H2C: RVOL >= 1.2 (High Volume Surge)")

print("\n--- HYPOTHESIS 3: OPENING RANGE EXPANSION THRESHOLD ---")
for rng_th in [10.0, 15.0, 20.0, 25.0, 30.0]:
    cb = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80) & (df_days['range'] >= rng_th)
    cs = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20) & (df_days['range'] >= rng_th)
    test_signal_variant(cb, cs, f"H3: Min Range >= {rng_th} pts")

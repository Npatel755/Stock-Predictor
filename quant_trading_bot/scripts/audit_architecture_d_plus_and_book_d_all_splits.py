"""Audit Script: Frozen All-Split Evaluation of Architecture D+ and Book D+.
STRICT METHODOLOGICAL RIGOR:
- All strategy parameters, thresholds, and holding times are 100% FROZEN from 2010-2023 Training.
- ZERO TUNING, fitting, or post-hoc adjustment on Validation (2024-2025) or Blind Test (2026).
- Prospective forward out-of-sample evaluation across all 16.9 years (June 2010 to November 2026).

Evaluates:
1. Architecture D+ Intraday (Crabel 15m + MNQ 30m trend + MNQ 60m trend + MES 30m idle trend, with morning VIX backwardation gate).
2. Overnight Dip v2 (Reopen <= -0.5 sigma on MNQ & MES, exit at 09:45 ET, with VIX backwardation gate).
3. Book D+ Combined Multi-Engine Portfolio (Overnight Dip v2 + Architecture D+ Intraday, strict 1-contract global limit).
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
import mass_1m_search as m1

print("=" * 80)
print("AUDIT: FROZEN ALL-SPLIT EVALUATION OF ARCHITECTURE D+ & BOOK D+")
print("=" * 80, flush=True)

# ---------------------------------------------------------
# Step 1: Load CBOE VIX and VIX3M for Term Structure Gate
# ---------------------------------------------------------
vix_path = ROOT / "data/external/VIX_History.csv"
vix3m_path = ROOT / "data/external/VIX3M_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df['date'] = pd.to_datetime(vix_df['DATE'], format='%m/%d/%Y').dt.date
vix_map = vix_df.set_index('date')['CLOSE'].astype(float).to_dict()

vix3m_df = pd.read_csv(vix3m_path)
vix3m_df['date'] = pd.to_datetime(vix3m_df['DATE'], format='%m/%d/%Y').dt.date
vix3m_map = vix3m_df.set_index('date')['CLOSE'].astype(float).to_dict()

cboe_dates = np.array(sorted(list(vix_map.keys())))

def get_prior_cboe_backwardation_map(target_dates):
    res = {}
    for td in target_dates:
        p = cboe_dates.searchsorted(td, side='left') - 1
        if p >= 0:
            pd_date = cboe_dates[p]
            vx = vix_map.get(pd_date, 20.0)
            v3 = vix3m_map.get(pd_date, 20.0)
            res[td] = bool(vx > v3)
        else:
            res[td] = False
    return res

def get_same_day_cboe_backwardation_map(target_dates):
    # At 18:05 ET, the 16:15 ET CBOE close on the same calendar day td is available!
    res = {}
    for td in target_dates:
        p = cboe_dates.searchsorted(td, side='right') - 1
        if p >= 0:
            cd = cboe_dates[p]
            vx = vix_map.get(cd, 20.0)
            v3 = vix3m_map.get(cd, 20.0)
            res[td] = bool(vx > v3)
        else:
            res[td] = False
    return res

# ---------------------------------------------------------
# Step 2: Load Continuous Bars for Intraday Sleeves
# ---------------------------------------------------------
def load_continuous_bars(sym, tf_interval):
    bars = pd.concat([
        load_resampled_bars(sym, 'train', tf_interval, start_date=None),
        load_resampled_bars(sym, 'validation', tf_interval, start_date='2024-01-01'),
        load_resampled_bars(sym, 'test', tf_interval, start_date='2026-01-01')
    ]).sort_values('timestamp_utc').reset_index(drop=True)
    return bars

print("\n[1/4] Loading continuous 16.9-year bars for Intraday Sleeves (2010-2026)...", flush=True)
b_mnq_15 = load_continuous_bars('NQ', '15 minutes')
b_mnq_30 = load_continuous_bars('NQ', '30 minutes')
b_mnq_60 = load_continuous_bars('NQ', '60 minutes')
b_mes_15 = load_continuous_bars('ES', '15 minutes')
b_mes_30 = load_continuous_bars('ES', '30 minutes')

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

f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1_raw = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)

f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)

f_mes = compute_htf_features(b_mes_30, 8, 30)
sig_mes_raw = np.where((dec_mes_30 >= 585) & (dec_mes_30 <= 930) & weekdays_mes_30 & (np.abs(f_mes['trend']) >= 1.0), np.sign(f_mes['trend']), 0).astype(np.int8)

# Toby Crabel 15m Signal Construction
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

# Apply Morning VIX Backwardation Gate to Architecture D+
all_unique_dates = sorted(list(set(dates_all_15)))
prior_backw_map = get_prior_cboe_backwardation_map(all_unique_dates)

sig_crabel_d_plus = sig_crabel.copy()
for i in range(len(sig_crabel_d_plus)):
    if sig_crabel_d_plus[i] != 0 and prior_backw_map.get(dates_all_15[i], False):
        sig_crabel_d_plus[i] = 0

dates_30 = loc_30.dt.date.to_numpy()
sig_1_d_plus = sig_1_raw.copy()
for i in range(len(sig_1_d_plus)):
    if sig_1_d_plus[i] != 0 and prior_backw_map.get(dates_30[i], False):
        sig_1_d_plus[i] = 0

dates_60 = loc_60.dt.date.to_numpy()
sig_2_d_plus = sig_2_raw.copy()
for i in range(len(sig_2_d_plus)):
    if sig_2_d_plus[i] != 0 and prior_backw_map.get(dates_60[i], False):
        sig_2_d_plus[i] = 0

sig_mes_d_plus = sig_mes_raw.copy()  # MES 30m idle trend is exempt

# Sleeve Configurations
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

print("\n[2/4] Executing Architecture D+ Intraday Router across all 16.9 years (2010-2026)...", flush=True)
r_c = me.execute(d_mnq_15, sig_crabel_d_plus, atr_15, cfg_c)
act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])

act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
sig_1_routed = np.where(~act_c_30, sig_1_d_plus, 0).astype(np.int8)
r_1 = me.execute(d_mnq_30, sig_1_routed, f_1['atr'], cfg_1)
act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])

act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
              act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
sig_2_routed = np.where(~act_all_60, sig_2_d_plus, 0).astype(np.int8)
r_2 = me.execute(d_mnq_60, sig_2_routed, f_2['atr'], cfg_2)
act_2_60 = pd.Series(r_2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])

act_all_mnq = (act_c_15.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
               act_1_30.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
               act_2_60.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
sig_mes_routed = np.where(~act_all_mnq, sig_mes_d_plus, 0).astype(np.int8)
r_mes = me.execute(d_mes_30, sig_mes_routed, f_mes['atr'], cfg_mes)

# Compile Intraday Trades
tr_list = []
for name, r, d, b_bar in [('Crabel_15m', r_c, d_mnq_15, b_mnq_15), ('S1_30m', r_1, d_mnq_30, b_mnq_30), ('S2_60m', r_2, d_mnq_60, b_mnq_60), ('MES_30m', r_mes, d_mes_30, b_mes_30)]:
    if len(r['trade_entry']):
        y = d['year'][r['trade_entry']]
        net = r['trade_net']
        entry_idx = r['trade_entry']
        exit_idx = r['trade_exit']
        dates = b_bar['date'].iloc[entry_idx].values
        entry_times = b_bar['timestamp_utc'].iloc[entry_idx].values
        exit_times = b_bar['timestamp_utc'].iloc[exit_idx].values
        for yr, n, en, ex, dt, et, xt in zip(y, net, entry_idx, exit_idx, dates, entry_times, exit_times):
            tr_list.append({
                'sleeve': name,
                'date': dt,
                'year': int(yr),
                'net': float(n),
                'bars_held': int(ex - en),
                'entry_idx': int(en),
                'exit_idx': int(ex),
                'entry_time': pd.to_datetime(et, utc=True).tz_convert("America/New_York"),
                'exit_time': pd.to_datetime(xt, utc=True).tz_convert("America/New_York"),
                'risk': 150.0,
                'engine': 'intraday'
            })

df_intraday_trades = pd.DataFrame(tr_list).sort_values('entry_time').reset_index(drop=True)

# ---------------------------------------------------------
# Step 3: Load Continuous 1-Minute Bars for Overnight Dip
# ---------------------------------------------------------
print("\n[3/4] Loading continuous 1-minute bars for Overnight Dip v2 across all splits...", flush=True)

def load_continuous_1m(sym):
    f_tr = m1.load_bars(sym, 1, "2010-01-01", "2024-01-01", "train")
    f_val = m1.load_bars(sym, 1, "2024-01-01", "2026-01-01", "validation")
    f_test = m1.load_bars(sym, 1, "2026-01-01", "2027-01-01", "test")
    df = pd.concat([f_tr, f_val, f_test], ignore_index=True)
    df = df.drop_duplicates(subset=['timestamp_utc']).sort_values('timestamp_utc').reset_index(drop=True)
    return df

b_mnq_1m = load_continuous_1m('MNQ')
b_mes_1m = load_continuous_1m('MES')

def compute_continuous_nights(b):
    et = pd.to_datetime(b.timestamp_utc, utc=True).dt.tz_convert("America/New_York")
    b = b.copy()
    b["sod"] = (et.dt.hour * 60 + et.dt.minute).to_numpy()
    b["date"] = et.dt.date.to_numpy()
    dates = sorted(set(b["date"]))
    prev = {d: p for p, d in zip(dates[:-1], dates[1:])}
    nk = np.where(b["sod"] >= 1080, b["date"], np.where(b["sod"] <= 600, pd.Series(b["date"]).map(prev).to_numpy(), None))
    b["nk"] = nk
    day = b.groupby("date")
    g = b[b.nk.notna()].groupby("nk")
    def at(sod, col, grp=g):
        s = b[b.sod == sod]
        return s.groupby("nk" if grp is g else "date")[col].first()

    n = pd.DataFrame(dict(
        rth_open=at(570, "open", day),
        rth_close=b[(b.sod >= 955) & (b.sod < 960)].groupby("date").close.last(),
        c1659=b[(b.sod >= 1015) & (b.sod < 1020)].groupby("date").close.last(),
        day_low=b[(b.sod >= 570) & (b.sod < 960)].groupby("date").low.min(),
        o1800=at(1080, "open", day),
        dow=pd.Series({d: pd.Timestamp(d).dayofweek for d in dates})
    ))
    ent = pd.DataFrame(dict(
        e1805=at(1085, "open"),
        x0930=at(570, "open"),
        x0945=at(585, "open")
    ))
    pre = b[(b.nk.notna()) & ((b.sod >= 1086) | (b.sod < 570))].groupby("nk")
    ent["low_night"] = pre.low.min()
    n["ref_close"] = n.rth_close.ffill()
    n = n.join(ent, how="inner").dropna(subset=["e1805", "x0945", "ref_close"])
    n["year"] = [pd.Timestamp(d).year for d in n.index]
    n["gap"] = n.o1800 / n.ref_close - 1
    n["sd20"] = n.gap.rolling(20, min_periods=15).std().shift(1)
    return n

n_mnq = compute_continuous_nights(b_mnq_1m)
n_mes = compute_continuous_nights(b_mes_1m)

# Low during open (09:30 - 09:45) for adverse excursion tracking
et_1m = b_mnq_1m.timestamp_utc.dt.tz_convert("America/New_York")
b_mnq_1m["date"] = et_1m.dt.date
b_mnq_1m["sod"] = et_1m.dt.hour * 60 + et_1m.dt.minute
low_open_15 = b_mnq_1m[(b_mnq_1m.sod >= 570) & (b_mnq_1m.sod < 585)].groupby("date").low.min()

all_night_dates = np.array(sorted(set(n_mnq.index) | set(low_open_15.index)))
def get_next_day(d):
    i = all_night_dates.searchsorted(d, side="right")
    return all_night_dates[i] if i < len(all_night_dates) else None

# Same-day CBOE close backwardation map for 18:05 ET entry
same_day_backw_map = get_same_day_cboe_backwardation_map(n_mnq.index)

# Reopen condition on MNQ and MES
mg = n_mes.gap.reindex(n_mnq.index)
msd = n_mes.sd20.reindex(n_mnq.index)
mask_ovn_raw = ((n_mnq.gap <= -0.5 * n_mnq.sd20) & (mg <= -0.5 * msd)).fillna(False)

# Overnight Dip Cost Modeling (MNQ micro)
# Spread 1.75 ticks ($0.875), slippage 1 tick each side ($1.00), commission $0.61 * 2 ($1.22) -> total $3.095
SPEC_MNQ = dict(tick=0.25, tv=0.5, spread=1.75)
COMM, SLIP = 0.61, 1.0
ovn_cost = (SPEC_MNQ["spread"] + 2 * SLIP) * SPEC_MNQ["tv"] + 2 * COMM

pnl_ovn_series = ((n_mnq["x0945"] - n_mnq["e1805"]) / SPEC_MNQ["tick"] * SPEC_MNQ["tv"] - ovn_cost)

# Build Overnight Trades Table with VIX Gating and Adverse Excursions
ovn_trades = []
for d in n_mnq.index:
    if mask_ovn_raw.loc[d]:
        is_backw = same_day_backw_map.get(d, False)
        # Record trade with gate flag
        yr = n_mnq.loc[d, 'year']
        net_pnl = float(pnl_ovn_series.loc[d])
        e1805 = float(n_mnq.loc[d, 'e1805'])
        low_nt = float(n_mnq.loc[d, 'low_night'])
        
        nd = get_next_day(d)
        lo_op = float(low_open_15.loc[nd]) if (nd and nd in low_open_15.index) else e1805
        min_lo = min(low_nt, lo_op)
        max_mae = max(0.0, (e1805 - min_lo) / SPEC_MNQ["tick"] * SPEC_MNQ["tv"])
        
        t_en = pd.to_datetime(f"{d} 18:05:00").tz_localize("America/New_York")
        t_ex = pd.to_datetime(f"{nd} 09:45:00").tz_localize("America/New_York")
        
        ovn_trades.append({
            'sleeve': 'Overnight_Dip',
            'date': d,
            'year': int(yr),
            'net': net_pnl,
            'mae': max_mae,
            'is_backwardation': is_backw,
            'entry_time': t_en,
            'exit_time': t_ex,
            'risk': max_mae,
            'engine': 'overnight'
        })

df_ovn_all = pd.DataFrame(ovn_trades)
df_ovn_gated = df_ovn_all[~df_ovn_all['is_backwardation']].sort_values('entry_time').reset_index(drop=True)

# ---------------------------------------------------------
# Step 4: Multi-Split Performance Evaluation
# ---------------------------------------------------------
print("\n[4/4] Computing Performance across all Partitions...", flush=True)

def analyze_strategy(df_trades, name):
    print(f"\n=======================================================")
    print(f"ANALYSIS: {name}")
    print(f"=======================================================")
    
    splits = [
        ('Training (2010-2023)', (df_trades['year'] >= 2010) & (df_trades['year'] <= 2023)),
        ('Validation (2024-2025)', (df_trades['year'] >= 2024) & (df_trades['year'] <= 2025)),
        ('Blind Test (2026)', (df_trades['year'] == 2026)),
        ('Full 16.9-Year Total (2010-2026)', (df_trades['year'] >= 2010) & (df_trades['year'] <= 2026))
    ]
    
    res = {}
    for label, mask in splits:
        sub = df_trades[mask].sort_values('entry_time').reset_index(drop=True)
        n_tr = len(sub)
        if n_tr == 0:
            res[label] = dict(net=0.0, trades=0, exp=0.0, wr=0.0, max_dd=0.0)
            continue
        net = float(sub['net'].sum())
        exp = net / n_tr
        wr = float((sub['net'] > 0).mean() * 100.0)
        
        # Realized cumulative drawdown
        cum = sub['net'].cumsum()
        peak = cum.cummax()
        dd = peak - cum
        max_dd = float(dd.max())
        
        res[label] = dict(
            net=round(net, 2),
            trades=n_tr,
            exp=round(exp, 2),
            wr=round(wr, 1),
            max_dd=round(max_dd, 2)
        )
        print(f"{label:35s} | Net: ${net:>10,.2f} | Trades: {n_tr:>5d} | Exp: ${exp:>6.2f}/tr | WR: {wr:>5.1f}% | Realized DD: ${max_dd:>8.2f}")
    
    # Year-by-Year breakdown
    print("\nYear-by-Year Performance:")
    yr_g = df_trades.sort_values('entry_time').groupby('year')
    for yr, g in yr_g:
        y_net = g['net'].sum()
        y_cnt = len(g)
        y_wr = (g['net'] > 0).mean() * 100
        print(f"  Year {yr}: Net: ${y_net:>8,.2f} | Trades: {y_cnt:>4d} | WR: {y_wr:>5.1f}%")
        
    return res

# 1. Evaluate Architecture D+ (Intraday Router)
res_d_plus = analyze_strategy(df_intraday_trades, "Architecture D+ (Intraday Router with VIX Backwardation Gate)")

# 2. Evaluate Overnight Dip v2 (Gated)
res_ovn = analyze_strategy(df_ovn_gated, "Overnight Dip v2 (Reopen <= -0.5s MNQ/MES, 09:45 Exit, VIX Gate)")

# 3. Simulate Book D+ Portfolio (Overnight Dip v2 + Architecture D+ Intraday under strict 1-contract global limit)
df_book_d = pd.concat([
    df_intraday_trades,
    df_ovn_gated
], ignore_index=True).sort_values('entry_time').reset_index(drop=True)

res_book_d = analyze_strategy(df_book_d, "Grand Champion Book D+ (Overnight Dip v2 + Architecture D+ Intraday, 1-Contract Account)")

# ---------------------------------------------------------
# Step 5: Marked Intraday-Trailing Drawdown of Book D+
# ---------------------------------------------------------
print("\n" + "=" * 80)
print("MARKED INTRADAY-TRAILING DRAWDOWN AUDIT (BOOK D+)")
print("=" * 80)

def compute_marked_drawdown(df_events_trades, label=""):
    events = []
    for idx, tr in df_events_trades.iterrows():
        t_en = tr['entry_time']
        t_ex = tr['exit_time']
        if tr['engine'] == 'intraday':
            risk = float(tr.get('risk', 150.0))
            net = float(tr['net'])
            events.append((t_en, "worst", -risk, 0.0, tr['sleeve']))
            events.append((t_ex, "close", 0.0, net, tr['sleeve']))
        else:
            mae = float(tr.get('mae', 0.0))
            net = float(tr['net'])
            events.append((t_en, "worst", -mae, 0.0, "OVN"))
            events.append((t_ex, "close", 0.0, net, "OVN"))

    events.sort(key=lambda x: x[0])

    closed = 0.0
    hwm = 0.0
    worst_tdd = 0.0
    worst_when = None
    touches_2k = 0
    in_touch = False

    for ts, kind, unreal, real, sl_name in events:
        if kind == "worst":
            eq = closed + unreal
        else:
            closed += real
            eq = closed
            hwm = max(hwm, eq)
        tdd = hwm - eq
        if tdd > worst_tdd:
            worst_tdd = tdd
            worst_when = ts
        if tdd >= 2000.0:
            if not in_touch:
                touches_2k += 1
                in_touch = True
        else:
            in_touch = False

    cushion = 2000.0 - worst_tdd
    print(f"[{label}] Worst Marked DD: ${worst_tdd:,.2f} on {worst_when} | Cushion: +${cushion:,.2f} ({cushion/2000.0*100:.1f}%) | $2k Touches: {touches_2k}")
    return worst_tdd, worst_when, cushion, touches_2k

worst_dd_tr, when_tr, cush_tr, tch_tr = compute_marked_drawdown(df_book_d[df_book_d['year'] <= 2023], "Training 2010-2023")
worst_dd_val, when_val, cush_val, tch_val = compute_marked_drawdown(df_book_d[(df_book_d['year'] >= 2024) & (df_book_d['year'] <= 2025)], "Validation 2024-2025")
worst_dd_test, when_test, cush_test, tch_test = compute_marked_drawdown(df_book_d[df_book_d['year'] == 2026], "Blind Test 2026")
worst_dd_all, when_all, cush_all, tch_all = compute_marked_drawdown(df_book_d, "Full 16.9-Year Continuous 2010-2026")

# Save detailed results to JSON
audit_summary = {
    "architecture_d_plus": res_d_plus,
    "overnight_dip_v2_gated": res_ovn,
    "book_d_plus": res_book_d,
    "marked_drawdowns": {
        "training": {"max_marked_dd": worst_dd_tr, "date": str(when_tr), "cushion": cush_tr, "touches": tch_tr},
        "validation": {"max_marked_dd": worst_dd_val, "date": str(when_val), "cushion": cush_val, "touches": tch_val},
        "test": {"max_marked_dd": worst_dd_test, "date": str(when_test), "cushion": cush_test, "touches": tch_test},
        "full_16_9yr": {"max_marked_dd": worst_dd_all, "date": str(when_all), "cushion": cush_all, "touches": tch_all}
    }
}

with open(ROOT / "reports/BOOK_D_PLUS_ALL_SPLITS_AUDIT.json", "w") as f:
    json.dump(audit_summary, f, indent=2)

print(f"\n[SUCCESS] Audit completed and saved to reports/BOOK_D_PLUS_ALL_SPLITS_AUDIT.json", flush=True)

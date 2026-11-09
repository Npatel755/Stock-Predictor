"""Rigorous All-Split Audit of Champion 1: Dual Morning Institutional Router (Crabel + NQ Leader).
Evaluated across:
1. Pre-2020 Decade (Train: 2010-2019, 10 Years)
2. Post-2020 Era (Train: 2020-2023, 4 Years)
3. Validation Split (2024-2025, 2 Years)
4. Sealed Blind Test Split (2026, 11 Months)
5. Continuous 16.9-Year Total (2010-2026)

Parameters are 100% frozen from Training (2010-2023). ZERO TUNING on Validation or Test.
Micro friction: $0.61/side commission, 1.75 tick MNQ spread, 1.0 tick slippage/side.
Router: Strict 1-contract max limit across entire account.
"""
import sys, json, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays

def load_continuous(sym, tf_interval):
    bars = pd.concat([
        load_resampled_bars(sym, 'train', tf_interval, start_date=None),
        load_resampled_bars(sym, 'validation', tf_interval, start_date='2024-01-01'),
        load_resampled_bars(sym, 'test', tf_interval, start_date='2026-01-01')
    ]).sort_values('timestamp_utc').reset_index(drop=True)
    return bars

print("Loading continuous 16-year 15m bars for NQ and ES (2010-2026)...", flush=True)
b_mnq_15 = load_continuous('NQ', '15 minutes')
b_mes_15 = load_continuous('ES', '15 minutes')

loc_mnq = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_mnq.dt.hour * 60 + loc_mnq.dt.minute
b_mnq_15['date'] = loc_mnq.dt.date
b_mnq_15['year'] = loc_mnq.dt.year

loc_mes = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes.dt.hour * 60 + loc_mes.dt.minute
b_mes_15['date'] = loc_mes.dt.date

rth_mnq = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
rth_mes = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)

g_mnq = rth_mnq.groupby('date')
g_mes = rth_mes.groupby('date')

o930_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
h1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'high'].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
l1000_mnq = g_mnq.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'low'].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)

o930_mes = g_mes.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mes = g_mes.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)

common_days = sorted(list(set(o930_mnq.dropna().index).intersection(set(o930_mes.dropna().index))))
df_days = pd.DataFrame(index=common_days)
df_days['ret_mnq'] = (c1000_mnq.loc[common_days] / o930_mnq.loc[common_days]) - 1.0
df_days['ret_mes'] = (c1000_mes.loc[common_days] / o930_mes.loc[common_days]) - 1.0
df_days['spread'] = df_days['ret_mnq'] - df_days['ret_mes']
df_days['spread_z'] = df_days['spread'] / df_days['spread'].rolling(20, min_periods=20).std().shift(1)

# Crabel metrics
df_days['range_mnq'] = h1000_mnq.loc[common_days] - l1000_mnq.loc[common_days]
df_days['open_pos'] = (o930_mnq.loc[common_days] - l1000_mnq.loc[common_days]) / df_days['range_mnq'].replace(0, np.nan)
df_days['close_pos'] = (c1000_mnq.loc[common_days] - l1000_mnq.loc[common_days]) / df_days['range_mnq'].replace(0, np.nan)

# Frozen Training Signals:
# 1. NQ Leader (z >= 1.25 / z <= -1.25)
df_days['lead_bull'] = df_days['spread_z'] >= 1.25
df_days['lead_bear'] = df_days['spread_z'] <= -1.25

# 2. Toby Crabel Open-Drive (open in 20% extreme, close in opposite 20% extreme)
df_days['crabel_bull'] = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80)
df_days['crabel_bear'] = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20)

# Combination Router:
df_days['dir_crabel'] = 0
df_days.loc[df_days.crabel_bull, 'dir_crabel'] = 1
df_days.loc[df_days.crabel_bear, 'dir_crabel'] = -1

df_days['dir_lead'] = 0
df_days.loc[df_days.lead_bull, 'dir_lead'] = 1
df_days.loc[df_days.lead_bear, 'dir_lead'] = -1

df_days['combined_dir'] = 0
for d in df_days.index:
    c = df_days.loc[d, 'dir_crabel']
    l = df_days.loc[d, 'dir_lead']
    if c != 0 and l != 0:
        if c == l:
            df_days.loc[d, 'combined_dir'] = c
        else: # Conflict
            df_days.loc[d, 'combined_dir'] = 0
    elif c != 0:
        df_days.loc[d, 'combined_dir'] = c
    elif l != 0:
        df_days.loc[d, 'combined_dir'] = l

# Map to 15m MNQ bars
d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
loc_all = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
dec_all = (loc_all.dt.hour * 60 + loc_all.dt.minute + 15).to_numpy()
weekdays = loc_all.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_all == 600) & weekdays
dates_all = loc_all.dt.date

close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c = np.roll(close_15, 1); prev_c[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c), np.abs(low_15 - prev_c)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

# Canonical funded config
cfg_mnq = dict(
    tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
    stop_atr=2.0, target_ratio=4.0, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
    risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
    flat_minute=955, max_gap_minutes=60
)

comb_map = df_days['combined_dir'].to_dict()
sig_comb = np.zeros(len(close_15), dtype=np.int8)
for i in range(len(close_15)):
    if is_1000_bar[i]:
        sig_comb[i] = comb_map.get(dates_all[i], 0)

print("Executing canonical simulation across 2010-2026...", flush=True)
r = me.execute(d_mnq_15, sig_comb, atr_15, cfg_mnq)

pnl = pd.Series(r['cash'] - r['cash'][0], index=b_mnq_15['timestamp_utc'])
peak = pnl.cummax()
dd = peak - pnl
max_dd = float(dd.max())
total_net = float(pnl.iloc[-1])

trade_years = d_mnq_15['year'][r['trade_entry']]
trade_nets = r['trade_net']

# Splits
m_pre = (trade_years >= 2010) & (trade_years < 2020)
m_post = (trade_years >= 2020) & (trade_years < 2024)
m_val = (trade_years >= 2024) & (trade_years < 2026)
m_test = (trade_years == 2026)

net_pre = float(trade_nets[m_pre].sum()) if np.any(m_pre) else 0.0
cnt_pre = int(np.count_nonzero(m_pre))
exp_pre = net_pre / cnt_pre if cnt_pre else 0.0

net_post = float(trade_nets[m_post].sum()) if np.any(m_post) else 0.0
cnt_post = int(np.count_nonzero(m_post))
exp_post = net_post / cnt_post if cnt_post else 0.0

net_val = float(trade_nets[m_val].sum()) if np.any(m_val) else 0.0
cnt_val = int(np.count_nonzero(m_val))
exp_val = net_val / cnt_val if cnt_val else 0.0

net_test = float(trade_nets[m_test].sum()) if np.any(m_test) else 0.0
cnt_test = int(np.count_nonzero(m_test))
exp_test = net_test / cnt_test if cnt_test else 0.0

tot_trades = len(trade_nets)
exp_tot = total_net / tot_trades if tot_trades else 0.0

df_trades = pd.DataFrame({'year': trade_years, 'net': trade_nets})
yearly = df_trades.groupby('year')['net'].sum().to_dict()
pos_years = sum(1 for y, v in yearly.items() if v > 0)
tot_years = len(yearly)
cushion = 2000.0 - max_dd

print("\n" + "=" * 90)
print("CHAMPION 1: DUAL MORNING INSTITUTIONAL ROUTER (CRABEL + NQ LEADER) ALL-SPLIT AUDIT")
print("=" * 90)
print(f"16.9-Year Continuous Total Net:  +${total_net:,.2f} across {tot_trades} trades (Exp: +${exp_tot:,.2f}/tr)")
print(f"Continuous Max Drawdown:         ${max_dd:,.2f} (Safety Cushion: +${cushion:,.2f} under $2,000 floor)")
print(f"Positive Years:                  {pos_years}/{tot_years} years ({pos_years/tot_years*100:.1f}%)")
print("-" * 90)
print(f"  Pre-2020 Era (Train 2010-2019, 10Y): +${net_pre:10.2f} | {cnt_pre:4d} tr ({cnt_pre/10:.1f}/yr) | Exp: +${exp_pre:6.2f}/tr")
print(f"  Post-2020 Era (Train 2020-2023, 4Y): +${net_post:10.2f} | {cnt_post:4d} tr ({cnt_post/4:.1f}/yr) | Exp: +${exp_post:6.2f}/tr")
print(f"  Validation Split (2024-2025, 2Y):    +${net_val:10.2f} | {cnt_val:4d} tr ({cnt_val/2:.1f}/yr) | Exp: +${exp_val:6.2f}/tr")
print(f"  Sealed Blind Test (2026, 11 Months): +${net_test:10.2f} | {cnt_test:4d} tr ({cnt_test/11:.1f}/mo) | Exp: +${exp_test:6.2f}/tr")
print("-" * 90)
print("Year-by-Year Performance:")
for y in sorted(yearly.keys()):
    tag = "TRAIN" if y < 2024 else ("VAL" if y < 2026 else "TEST")
    status = "WIN" if yearly[y] > 0 else "LOSS"
    print(f"  {y} ({tag:<5}): +${yearly[y]:8.2f} | {status}")

out_data = {
    "total_net": total_net, "tot_trades": tot_trades, "exp_tot": exp_tot,
    "max_dd": max_dd, "cushion": cushion, "pos_years": pos_years, "tot_years": tot_years,
    "net_pre": net_pre, "cnt_pre": cnt_pre, "exp_pre": exp_pre,
    "net_post": net_post, "cnt_post": cnt_post, "exp_post": exp_post,
    "net_val": net_val, "cnt_val": cnt_val, "exp_val": exp_val,
    "net_test": net_test, "cnt_test": cnt_test, "exp_test": exp_test,
    "yearly": yearly
}
with open(ROOT / "reports/CHAMPION1_DUAL_MORNING_ALL_SPLITS.json", "w") as f:
    json.dump(out_data, f, indent=2, default=float)
print("\nSaved full audit to reports/CHAMPION1_DUAL_MORNING_ALL_SPLITS.json successfully!", flush=True)

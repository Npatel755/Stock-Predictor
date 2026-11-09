"""Combine Crabel Open-Drive and NQ Leader in an Exclusive 1-Contract Router on Training (2010-2023).
Rules:
- 1 contract max across the account at all times.
- If Crabel Open-Drive fires, trade Crabel.
- If NQ Leader fires and Crabel did not fire, trade NQ Leader.
- If both fire in same direction, trade 1 contract.
- If they conflict (one bull, one bear), pass (stand aside).
- STRICTLY ON 2010-2023 TRAINING DATA.
"""
import sys, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays

b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mes_15 = load_resampled_bars('ES', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

loc_mnq = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_mnq.dt.hour * 60 + loc_mnq.dt.minute
b_mnq_15['date'] = loc_mnq.dt.date

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

df_days['range_mnq'] = h1000_mnq.loc[common_days] - l1000_mnq.loc[common_days]
df_days['open_pos'] = (o930_mnq.loc[common_days] - l1000_mnq.loc[common_days]) / df_days['range_mnq'].replace(0, np.nan)
df_days['close_pos'] = (c1000_mnq.loc[common_days] - l1000_mnq.loc[common_days]) / df_days['range_mnq'].replace(0, np.nan)

df_days['lead_bull'] = df_days['spread_z'] >= 1.25
df_days['lead_bear'] = df_days['spread_z'] <= -1.25

df_days['crabel_bull'] = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80)
df_days['crabel_bear'] = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20)

# Exclusive router:
# Crabel direction: +1, -1, 0
df_days['dir_crabel'] = 0
df_days.loc[df_days.crabel_bull, 'dir_crabel'] = 1
df_days.loc[df_days.crabel_bear, 'dir_crabel'] = -1

# Leader direction: +1, -1, 0
df_days['dir_lead'] = 0
df_days.loc[df_days.lead_bull, 'dir_lead'] = 1
df_days.loc[df_days.lead_bear, 'dir_lead'] = -1

# Combined decision:
df_days['combined_dir'] = 0
for d in df_days.index:
    c = df_days.loc[d, 'dir_crabel']
    l = df_days.loc[d, 'dir_lead']
    if c != 0 and l != 0:
        if c == l: # Agreement
            df_days.loc[d, 'combined_dir'] = c
        else: # Conflict
            df_days.loc[d, 'combined_dir'] = 0
    elif c != 0:
        df_days.loc[d, 'combined_dir'] = c
    elif l != 0:
        df_days.loc[d, 'combined_dir'] = l

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

r = me.execute(d_mnq_15, sig_comb, atr_15, cfg_mnq)
pnl = r['cash'] - r['cash'][0]
total_net = float(pnl[-1])
peak = np.maximum.accumulate(pnl)
dd = peak - pnl
max_dd = float(np.max(dd))

trade_years = d_mnq_15['year'][r['trade_entry']]
trade_nets = r['trade_net']
n_trades = len(trade_nets)
exp = total_net / n_trades if n_trades else 0.0

df_tr = pd.DataFrame({'year': trade_years, 'net': trade_nets})
yearly = df_tr.groupby('year')['net'].sum().to_dict()
pos_years = sum(1 for y, v in yearly.items() if v > 0)
pre = sum(v for y, v in yearly.items() if y < 2020)
post = sum(v for y, v in yearly.items() if y >= 2020)

print("\n" + "=" * 80)
print("COMBINED CRABEL + NQ-LEADER EXCLUSIVE 1-CONTRACT ROUTER (2010-2023 TRAINING)")
print("=" * 80)
print(f"Total Net: ${total_net:+,.2f} | Trades: {n_trades} ({n_trades/14:.1f} tr/yr) | Exp: ${exp:+.2f}/tr")
print(f"Pre-2020 (2010-2019): ${pre:+,.2f} ({(df_tr[df_tr.year<2020].groupby('year')['net'].sum()>0).sum()}/10 pos years)")
print(f"Post-2020 (2020-2023): ${post:+,.2f} ({(df_tr[df_tr.year>=2020].groupby('year')['net'].sum()>0).sum()}/4 pos years)")
print(f"Positive Years: {pos_years}/14 ({pos_years/14*100:.1f}%)")
print(f"Max Continuous Drawdown: ${max_dd:,.2f} (Safety Cushion: ${2000-max_dd:+,.2f} under $2,000 floor)")
print("Yearly Breakdown:")
for y in sorted(yearly.keys()):
    print(f"  {y}: ${yearly[y]:+,.2f}")

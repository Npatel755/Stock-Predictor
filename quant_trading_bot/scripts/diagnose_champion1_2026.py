"""Diagnostic and Enhancement Protocol for Champion 1.
Questions:
1. Why did Champion 1 only take 5 trades in 2026?
2. How does adding the 3rd placebo-validated signal (VIX Velocity Crush) impact 2010-2023 Training?
3. How does adding the Afternoon Session (13:30-15:15 ET) under the 1-contract router impact 2010-2023 Training?
   - Morning trade flattens by 13:00 ET (12 bars).
   - Afternoon sleeve (lb8, th0.50) enters between 13:30 and 15:15 ET only if flat.
4. Then evaluate all splits (Train, Validation, Test) with zero parameter changes.
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
from quant_futures.htf_engine import compute_htf_features

def load_continuous(sym, tf_interval):
    bars = pd.concat([
        load_resampled_bars(sym, 'train', tf_interval, start_date=None),
        load_resampled_bars(sym, 'validation', tf_interval, start_date='2024-01-01'),
        load_resampled_bars(sym, 'test', tf_interval, start_date='2026-01-01')
    ]).sort_values('timestamp_utc').reset_index(drop=True)
    return bars

print("Loading continuous 16-year bars (2010-2026)...", flush=True)
b_mnq_15 = load_continuous('NQ', '15 minutes')
b_mnq_30 = load_continuous('NQ', '30 minutes')
b_mes_15 = load_continuous('ES', '15 minutes')

vix = pd.read_csv(ROOT / "data" / "external" / "VIX_History.csv")
vix3m = pd.read_csv(ROOT / "data" / "external" / "VIX3M_History.csv")
vix["date"] = pd.to_datetime(vix["DATE"]).dt.date
vix3m["date"] = pd.to_datetime(vix3m["DATE"]).dt.date
vix_df = pd.merge(vix[["date", "CLOSE"]].rename(columns={"CLOSE": "vix"}),
                  vix3m[["date", "CLOSE"]].rename(columns={"CLOSE": "vix3m"}),
                  on="date").sort_values("date").reset_index(drop=True)
vix_df["ratio"] = vix_df["vix"] / vix_df["vix3m"]
vix_df["ratio_d1"] = vix_df["ratio"].diff(1)
vix_df["trade_date"] = vix_df["date"].shift(-1)
date_to_vix_d1 = dict(zip(vix_df["trade_date"], vix_df["ratio_d1"]))

loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date
b_mnq_15['year'] = loc_15.dt.year

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

df_days['vix_d1'] = [date_to_vix_d1.get(d, np.nan) for d in df_days.index]

# Signal definitions:
df_days['lead_bull'] = df_days['spread_z'] >= 1.25
df_days['lead_bear'] = df_days['spread_z'] <= -1.25

df_days['crabel_bull'] = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80)
df_days['crabel_bear'] = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20)

df_days['vix_bull'] = (df_days['vix_d1'] <= -0.015) & (df_days['ret_mnq'] >= 0.001)
df_days['vix_bear'] = (df_days['vix_d1'] >= +0.02) & (df_days['ret_mnq'] <= -0.001)

# Check 2026 counts
days_2026 = [d for d in df_days.index if d.year == 2026]
print(f"\n2026 Trading Days in Census: {len(days_2026)}")
sub_26 = df_days.loc[days_2026]
print(f"2026 Crabel Triggers: Bull={sub_26.crabel_bull.sum()}, Bear={sub_26.crabel_bear.sum()} (Total={sub_26.crabel_bull.sum() + sub_26.crabel_bear.sum()})")
print(f"2026 NQ Leader Triggers: Bull={sub_26.lead_bull.sum()}, Bear={sub_26.lead_bear.sum()} (Total={sub_26.lead_bull.sum() + sub_26.lead_bear.sum()})")
print(f"2026 VIX Crush Triggers: Bull={sub_26.vix_bull.sum()}, Bear={sub_26.vix_bear.sum()} (Total={sub_26.vix_bull.sum() + sub_26.vix_bear.sum()})")

# Check why Champion 1 only had 5 trades in 2026
c1_signals = []
for d in days_2026:
    cb = sub_26.loc[d, 'crabel_bull']
    cs = sub_26.loc[d, 'crabel_bear']
    lb = sub_26.loc[d, 'lead_bull']
    ls = sub_26.loc[d, 'lead_bear']
    
    cd = 1 if cb else (-1 if cs else 0)
    ld = 1 if lb else (-1 if ls else 0)
    
    comb = 0
    if cd != 0 and ld != 0:
        if cd == ld: comb = cd
    elif cd != 0: comb = cd
    elif ld != 0: comb = ld
    if comb != 0:
        c1_signals.append((d, comb, f"crabel={cd}, lead={ld}"))
        
print(f"\nChampion 1 Trigger Days in 2026 ({len(c1_signals)} days):")
for dt, s, reason in c1_signals:
    print(f"  {dt}: Side={s:+d} ({reason})")

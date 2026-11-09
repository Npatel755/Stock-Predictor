"""Generate comprehensive 16.9-year comparison chart: Enhanced Architecture C vs AG_Quad."""
import sys, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features

def load_continuous(sym, tf_interval):
    return pd.concat([
        load_resampled_bars(sym, 'train', tf_interval, start_date=None),
        load_resampled_bars(sym, 'validation', tf_interval, start_date='2024-01-01'),
        load_resampled_bars(sym, 'test', tf_interval, start_date='2026-01-01')
    ]).sort_values('timestamp_utc').reset_index(drop=True)

print("Loading continuous 16.9-year bars...", flush=True)
b_mnq_15 = load_continuous('NQ', '15 minutes')
b_mnq_30 = load_continuous('NQ', '30 minutes')
b_mnq_60 = load_continuous('NQ', '60 minutes')
b_mes_30 = load_continuous('ES', '30 minutes')

loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
b_mnq_15['date'] = loc_15.dt.date

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

# Quad Setup
f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1 = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)
cfg_quad_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                  stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                  risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                  flat_minute=955, max_gap_minutes=60)

f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)
cfg_quad_2 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                  stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                  risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                  flat_minute=955, max_gap_minutes=120)

f_3 = compute_htf_features(b_mnq_30, 8, 30)
sig_3_raw = np.where((dec_30 >= 810) & (dec_30 < 915) & weekdays_30 & (np.abs(f_3['trend']) >= 0.50), np.sign(f_3['trend']), 0).astype(np.int8)
cfg_quad_3 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                  stop_atr=1.5, target_ratio=4.0, hold_bars=4, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                  risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                  flat_minute=955, max_gap_minutes=60)

f_4 = compute_htf_features(b_mes_30, 8, 30)
sig_4_raw = np.where((dec_mes_30 >= 600) & (dec_mes_30 < 930) & weekdays_mes_30 & (np.abs(f_4['trend']) >= 1.0), np.sign(f_4['trend']), 0).astype(np.int8)
cfg_quad_4 = dict(tick=0.25, multiplier=1.25, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                  stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                  risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                  flat_minute=955, max_gap_minutes=60)

r_1 = me.execute(d_mnq_30, sig_1, f_1['atr'], cfg_quad_1)
act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
act_1_60 = act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False).to_numpy()
sig_2 = np.where(~act_1_60, sig_2_raw, 0).astype(np.int8)
r_2 = me.execute(d_mnq_60, sig_2, f_2['atr'], cfg_quad_2)
act_2_60 = pd.Series(r_2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])
act_12_30 = (act_1_30 | act_2_60.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
sig_3 = np.where(~act_12_30, sig_3_raw, 0).astype(np.int8)
r_3 = me.execute(d_mnq_30, sig_3, f_3['atr'], cfg_quad_3)
act_3_30 = pd.Series(r_3['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
act_123_mes = ((act_1_30 | act_3_30).reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
               act_2_60.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
sig_4 = np.where(~act_123_mes, sig_4_raw, 0).astype(np.int8)
r_4 = me.execute(d_mes_30, sig_4, f_4['atr'], cfg_quad_4)

p_1 = pd.Series(r_1['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
p_2 = pd.Series(r_2['cash'] - 50000.0, index=b_mnq_60['timestamp_utc'])
p_3 = pd.Series(r_3['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
p_4 = pd.Series(r_4['cash'] - 50000.0, index=b_mes_30['timestamp_utc'])

common_idx = b_mnq_15['timestamp_utc']
pnl_quad = (p_1.reindex(common_idx, method='ffill').fillna(0.0) +
            p_2.reindex(common_idx, method='ffill').fillna(0.0) +
            p_3.reindex(common_idx, method='ffill').fillna(0.0) +
            p_4.reindex(common_idx, method='ffill').fillna(0.0))

# Crabel calculations
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
df_days['crabel_sig'] = np.where((df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80), 1,
                                 np.where((df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20), -1, 0))
date_to_crabel = df_days['crabel_sig'].to_dict()

dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_15.dt.date

d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
prev_c15 = np.roll(close_15, 1); prev_c15[0] = close_15[0]
tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c15), np.abs(low_15 - prev_c15)))
atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)

sig_crabel = np.zeros(len(close_15), dtype=np.int8)
for i in range(len(close_15)):
    if is_1000_bar[i]:
        sig_crabel[i] = date_to_crabel.get(dates_all_15[i], 0)

# Enhanced Architecture C configs
cfg_enh_c = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                 stop_atr=2.0, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                 risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                 flat_minute=955, max_gap_minutes=60)

cfg_enh_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                 stop_atr=1.5, target_ratio=3.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                 risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                 flat_minute=955, max_gap_minutes=60)

cfg_enh_2 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                 stop_atr=1.25, target_ratio=4.0, hold_bars=6, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                 risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                 flat_minute=955, max_gap_minutes=120)

r_enh_c = me.execute(d_mnq_15, sig_crabel, atr_15, cfg_enh_c)
act_enh_c_15 = pd.Series(r_enh_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])

act_enh_c_30 = act_enh_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
sig_enh_1 = np.where(~act_enh_c_30, sig_1, 0).astype(np.int8)
r_enh_1 = me.execute(d_mnq_30, sig_enh_1, f_1['atr'], cfg_enh_1)
act_enh_1_30 = pd.Series(r_enh_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])

act_enh_all_60 = (act_enh_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) |
                  act_enh_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
sig_enh_2 = np.where(~act_enh_all_60, sig_2_raw, 0).astype(np.int8)
r_enh_2 = me.execute(d_mnq_60, sig_enh_2, f_2['atr'], cfg_enh_2)

p_enh_c = pd.Series(r_enh_c['cash'] - 50000.0, index=b_mnq_15['timestamp_utc'])
p_enh_1 = pd.Series(r_enh_1['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
p_enh_2 = pd.Series(r_enh_2['cash'] - 50000.0, index=b_mnq_60['timestamp_utc'])

pnl_enh = (p_enh_c + p_enh_1.reindex(common_idx, method='ffill').fillna(0.0) +
           p_enh_2.reindex(common_idx, method='ffill').fillna(0.0))

# Plot
plt.style.use('dark_background')
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={'height_ratios': [2.5, 1]}, sharex=True)

ax1.plot(common_idx, pnl_enh, label='Enhanced Architecture C (Scaler) (+$21,890 | Max DD $1,070)', color='#00e676', lw=2.2)
ax1.plot(common_idx, pnl_quad, label='Baseline AG_Quad v1.1.0 (+$17,879 | Max DD $1,478)', color='#29b6f6', lw=1.5, alpha=0.85)

ax1.axvline(pd.Timestamp('2020-01-01', tz='UTC'), color='#9e9e9e', ls='--', alpha=0.6, label='Train Post-2020 (2020)')
ax1.axvline(pd.Timestamp('2024-01-01', tz='UTC'), color='#ffd600', ls='--', alpha=0.7, label='Validation Split (2024)')
ax1.axvline(pd.Timestamp('2026-01-01', tz='UTC'), color='#ff5252', ls='--', alpha=0.7, label='Blind Test Split (2026)')

ax1.set_ylabel('Net Profit ($)', fontsize=12)
ax1.set_title('Enhanced Architecture C (Morning Scaler) vs Baseline AG_Quad (2010–2026 Continuous)', fontsize=14, fontweight='bold', pad=12)
ax1.legend(loc='upper left', framealpha=0.3)
ax1.grid(True, alpha=0.15)

# Drawdowns
dd_enh = pnl_enh.cummax() - pnl_enh
dd_quad = pnl_quad.cummax() - pnl_quad

ax2.plot(common_idx, -dd_enh, color='#00e676', lw=1.5, label='Enhanced Architecture C Drawdown (Max: $1,070.27)')
ax2.plot(common_idx, -dd_quad, color='#29b6f6', lw=1.2, alpha=0.75, label='AG_Quad Drawdown (Max: $1,477.70)')
ax2.axhline(-2000.0, color='#ff1744', ls='-', lw=2, label='Funded Account Floor (-$2,000.00)')
ax2.set_ylabel('Drawdown ($)', fontsize=12)
ax2.set_xlabel('Date', fontsize=12)
ax2.legend(loc='lower left', framealpha=0.3)
ax2.grid(True, alpha=0.15)

plt.tight_layout()
out_png = ROOT / 'reports/enhanced_architecture_c_vs_quad_16year.png'
plt.savefig(out_png, dpi=180)
plt.close()
print(f"Saved chart to {out_png} successfully!", flush=True)

# Copy to brain artifact directory
import shutil
artifact_dir = Path(r'C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d')
if artifact_dir.exists():
    shutil.copy(out_png, artifact_dir / 'enhanced_architecture_c_vs_quad_16year.png')
    print("Copied chart to brain artifact directory!", flush=True)

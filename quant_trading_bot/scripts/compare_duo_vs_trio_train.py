"""Rigorous Evaluation of Champion Duo + MES Sleeves on TRAIN (2020-2023)."""
import sys, json, duckdb, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import generalized_arrays
from quant_futures.htf_engine import compute_htf_features

cat = json.load(open(ROOT / 'data/catalog.json'))

def load_train_bars(sym, tf_interval):
    p = cat['instruments'][sym]['splits']['train']['path']
    con = duckdb.connect()
    q = f"""
    SELECT 
        time_bucket(INTERVAL '{tf_interval}', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
        arg_min(contract, timestamp_utc) AS contract,
        arg_min(session_id, timestamp_utc) AS session_id,
        arg_min(open, timestamp_utc) AS open,
        max(high) AS high,
        min(low) AS low,
        arg_max(close, timestamp_utc) AS close,
        sum(volume)::DOUBLE AS volume
    FROM read_parquet(?)
    WHERE timestamp_utc >= '2020-01-01'
    GROUP BY 1
    ORDER BY 1
    """
    df = con.execute(q, [str(p)]).fetch_df()
    df['instrument'] = sym
    df = canonical(df)
    con.close()
    return df

b_mnq_30 = load_train_bars('MNQ', '30 minutes')
b_mnq_60 = load_train_bars('MNQ', '60 minutes')
b_mes_30 = load_train_bars('MES', '30 minutes')

# Sleeve 1: MNQ 30m Impulse Breakout (Champion)
d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)
f_mnq_30 = compute_htf_features(b_mnq_30, 16, 30)
loc_mnq_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_mnq_30 = (loc_mnq_30.dt.hour * 60 + loc_mnq_30.dt.minute + 30).to_numpy()
sig_mnq_30 = np.where((dec_mnq_30 >= 585) & (dec_mnq_30 < 720) & (loc_mnq_30.dt.weekday.to_numpy() < 5) & (np.abs(f_mnq_30['trend']) >= 0.75), np.sign(f_mnq_30['trend']), 0).astype(np.int8)
cfg_mnq_30 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                  stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                  risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                  flat_minute=955, max_gap_minutes=60)
r_mnq_30 = me.execute(d_mnq_30, sig_mnq_30, f_mnq_30['atr'], cfg_mnq_30)

# Sleeve 2: MNQ 60m Macro Trend (Champion)
d_mnq_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)
f_mnq_60 = compute_htf_features(b_mnq_60, 12, 60)
loc_mnq_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
dec_mnq_60 = (loc_mnq_60.dt.hour * 60 + loc_mnq_60.dt.minute + 60).to_numpy()
sig_mnq_60 = np.where((dec_mnq_60 >= 600) & (dec_mnq_60 < 720) & (loc_mnq_60.dt.weekday.to_numpy() < 5) & (np.abs(f_mnq_60['trend']) >= 0.75), np.sign(f_mnq_60['trend']), 0).astype(np.int8)
cfg_mnq_60 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                  stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                  risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                  flat_minute=955, max_gap_minutes=120)
r_mnq_60 = me.execute(d_mnq_60, sig_mnq_60, f_mnq_60['atr'], cfg_mnq_60)

# Sleeve 3: MES 30m Trend (Training Qualifier: lb=8, th=1.0, stop=1.25, tgt=2.5, hold=12, all_day)
d_mes_30 = apply_early_close(generalized_arrays(b_mes_30), b_mes_30)
f_mes_30 = compute_htf_features(b_mes_30, 8, 30)
loc_mes_30 = b_mes_30.timestamp_utc.dt.tz_convert('America/New_York')
dec_mes_30 = (loc_mes_30.dt.hour * 60 + loc_mes_30.dt.minute + 30).to_numpy()
sig_mes_30 = np.where((dec_mes_30 >= 585) & (dec_mes_30 < 930) & (loc_mes_30.dt.weekday.to_numpy() < 5) & (np.abs(f_mes_30['trend']) >= 1.0), np.sign(f_mes_30['trend']), 0).astype(np.int8)
cfg_mes_30 = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                  stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                  risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                  flat_minute=955, max_gap_minutes=60)
r_mes_30 = me.execute(d_mes_30, sig_mes_30, f_mes_30['atr'], cfg_mes_30)

# Reindex and combine curves
pnl_mnq_30 = pd.Series(r_mnq_30['cash'] - r_mnq_30['cash'][0], index=b_mnq_30['timestamp_utc'])
pnl_mnq_60 = pd.Series(r_mnq_60['cash'] - r_mnq_60['cash'][0], index=b_mnq_60['timestamp_utc'])
pnl_mes_30 = pd.Series(r_mes_30['cash'] - r_mes_30['cash'][0], index=b_mes_30['timestamp_utc'])

idx_all = b_mnq_30['timestamp_utc']
df_p = pd.DataFrame(index=idx_all)
df_p['MNQ_30'] = pnl_mnq_30
df_p['MNQ_60'] = pnl_mnq_60.reindex(idx_all, method='ffill').fillna(0.0)
df_p['MES_30'] = pnl_mes_30.reindex(idx_all, method='ffill').fillna(0.0)

df_p['Duo'] = df_p['MNQ_30'] + df_p['MNQ_60']
df_p['Trio'] = df_p['MNQ_30'] + df_p['MNQ_60'] + df_p['MES_30']

def calc_stats(series, trades):
    net = float(series.iloc[-1])
    peak = series.cummax()
    dd = peak - series
    mdd = float(dd.max())
    exp = net / trades if trades else 0.0
    return net, trades, exp, mdd, 2000.0 - mdd

n_mnq_30 = len(r_mnq_30['trade_net'])
n_mnq_60 = len(r_mnq_60['trade_net'])
n_mes_30 = len(r_mes_30['trade_net'])

net_duo, tr_duo, exp_duo, dd_duo, cush_duo = calc_stats(df_p['Duo'], n_mnq_30 + n_mnq_60)
net_trio, tr_trio, exp_trio, dd_trio, cush_trio = calc_stats(df_p['Trio'], n_mnq_30 + n_mnq_60 + n_mes_30)

print("=" * 80)
print("TRAINING PERFORMANCE COMPARISON (2020-2023)")
print("=" * 80)
print(f"Sleeve 1: MNQ 30m Breakout -> Net +${r_mnq_30['trade_net'].sum():,.2f} ({n_mnq_30} tr, +${r_mnq_30['trade_net'].mean():.2f}/tr)")
print(f"Sleeve 2: MNQ 60m Trend    -> Net +${r_mnq_60['trade_net'].sum():,.2f} ({n_mnq_60} tr, +${r_mnq_60['trade_net'].mean():.2f}/tr)")
print(f"Sleeve 3: MES 30m Trend    -> Net +${r_mes_30['trade_net'].sum():,.2f} ({n_mes_30} tr, +${r_mes_30['trade_net'].mean():.2f}/tr)")
print("-" * 80)
print(f"DUO (MNQ 30m + MNQ 60m):")
print(f"  Train Net:    +${net_duo:,.2f} | Trades: {tr_duo} | Exp: +${exp_duo:.2f}/tr | Max DD: ${dd_duo:,.2f} | Cushion: +${cush_duo:,.2f}")
print(f"TRIO (MNQ 30m + MNQ 60m + MES 30m Trend):")
print(f"  Train Net:    +${net_trio:,.2f} | Trades: {tr_trio} | Exp: +${exp_trio:.2f}/tr | Max DD: ${dd_trio:,.2f} | Cushion: +${cush_trio:,.2f}")
print("=" * 80)

"""Multi-Asset Portfolio Construction on TRAIN DATA ONLY (2020-2023).

Protocol:
- Evaluates candidates strictly on Train split (2020-2023).
- Zero access to Validation (2024-2025) or Test (2026) during construction.
- Strict micro transaction costs ($2.72/RT).
- Max 1 contract per sleeve.
- Tests portfolio combinations of:
  * MNQ Morning Breakout (30m)
  * MNQ Morning Macro Trend (60m)
  * MES All-Day / Swing Trend (30m)
  * MES All-Day / Swing Breakout (30m or 60m)
- Objective: Maximize combined Net PnL and Expectancy while keeping Max Drawdown <= $1,400 (leaving >= $600 safety buffer for $2,000 funded account).
"""
import sys
import json
import duckdb
import numpy as np
import pandas as pd
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

print("Loading Train (2020-2023) bars for MNQ and MES...")
b_mnq_30 = load_train_bars('MNQ', '30 minutes')
b_mnq_60 = load_train_bars('MNQ', '60 minutes')
b_mes_30 = load_train_bars('MES', '30 minutes')
b_mes_60 = load_train_bars('MES', '60 minutes')

# Helper to execute a sleeve
def run_sleeve(bars, sym, tf_min, fam, lb, th, st, tgt, hold, trail, sess, flat_min=955):
    d = apply_early_close(generalized_arrays(bars), bars)
    f = compute_htf_features(bars, lb, tf_min)
    loc = bars.timestamp_utc.dt.tz_convert('America/New_York')
    dec = (loc.dt.hour * 60 + loc.dt.minute + tf_min).to_numpy()
    weekdays = loc.dt.weekday.to_numpy() < 5
    
    if sess == 'morning':
        sess_mask = (dec >= 585) & (dec < 720) & weekdays
    else:
        sess_mask = (dec >= 585) & (dec < 930) & weekdays
        
    atr = f['atr']
    c = f['close']
    
    if fam == 'trend':
        sig = np.where(sess_mask & (np.abs(f['trend']) >= th), np.sign(f['trend']), 0).astype(np.int8)
    elif fam == 'breakout':
        bh = f['breakout_high'] + th * atr
        bl = f['breakout_low'] - th * atr
        sig = np.where(sess_mask & (c > bh), 1, np.where(sess_mask & (c < bl), -1, 0)).astype(np.int8)
        
    mult = 5.0 if sym == 'MES' else 2.0
    cfg = dict(
        tick=0.25, multiplier=mult, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
        stop_atr=st, target_ratio=tgt, hold_bars=hold, trailing_atr=trail, maxqty=1, initial_balance=50000.0,
        risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
        flat_minute=flat_min, max_gap_minutes=tf_min*2
    )
    res = me.execute(d, sig, atr, cfg)
    pnl = pd.Series(res['cash'] - res['cash'][0], index=bars['timestamp_utc'])
    return res, pnl

print("Running individual sleeves on Train (2020-2023)...")
# Candidate 1: MNQ 30m Breakout (Champion)
r_mnq_bo, s_mnq_bo = run_sleeve(b_mnq_30, 'MNQ', 30, 'breakout', 16, 0.0, 1.5, 3.5, 8, 0.0, 'morning')
# Candidate 2: MNQ 60m Trend (Champion)
r_mnq_tr, s_mnq_tr = run_sleeve(b_mnq_60, 'MNQ', 60, 'trend', 12, 0.75, 1.25, 4.0, 8, 0.0, 'morning')
# Candidate 3: MES 30m Trend (Training Top Candidate)
r_mes_tr, s_mes_tr = run_sleeve(b_mes_30, 'MES', 30, 'trend', 8, 1.0, 1.25, 2.5, 12, 0.0, 'all_day')
# Candidate 4: MES 30m Breakout (Training Top Candidate)
r_mes_bo, s_mes_bo = run_sleeve(b_mes_30, 'MES', 30, 'breakout', 16, 1.5, 1.5, 5.0, 12, 2.0, 'all_day')
# Candidate 5: MES 60m Breakout (Training Top Candidate)
r_mes_bo60, s_mes_bo60 = run_sleeve(b_mes_60, 'MES', 60, 'breakout', 8, 1.5, 1.25, 3.0, 3, 0.0, 'all_day')

def print_sleeve_metrics(name, res):
    tn = res['trade_net']
    net = tn.sum()
    cnt = len(tn)
    exp = net / cnt if cnt else 0.0
    mdd = float((np.maximum.accumulate(res['cash']) - res['worst']).max())
    print(f"{name:<25}: Net +${net:8.2f} | Trades: {cnt:3d} | Exp: +${exp:5.2f}/tr | MaxDD: ${mdd:6.2f} | Calmar: {net/mdd:5.2f}")

print("\n" + "=" * 80)
print("INDIVIDUAL SLEEVE PERFORMANCE ON TRAIN (2020-2023)")
print("=" * 80)
print_sleeve_metrics("MNQ 30m Breakout", r_mnq_bo)
print_sleeve_metrics("MNQ 60m Trend", r_mnq_tr)
print_sleeve_metrics("MES 30m Trend", r_mes_tr)
print_sleeve_metrics("MES 30m Breakout", r_mes_bo)
print_sleeve_metrics("MES 60m Breakout", r_mes_bo60)

# Build continuous time index for portfolio evaluation
all_times = sorted(list(set(b_mnq_30['timestamp_utc']).union(set(b_mes_30['timestamp_utc']))))
df_port = pd.DataFrame(index=all_times)
df_port['MNQ_BO'] = s_mnq_bo.reindex(df_port.index, method='ffill').fillna(0.0)
df_port['MNQ_TR'] = s_mnq_tr.reindex(df_port.index, method='ffill').fillna(0.0)
df_port['MES_TR'] = s_mes_tr.reindex(df_port.index, method='ffill').fillna(0.0)
df_port['MES_BO'] = s_mes_bo.reindex(df_port.index, method='ffill').fillna(0.0)
df_port['MES_BO60'] = s_mes_bo60.reindex(df_port.index, method='ffill').fillna(0.0)

print("\n" + "=" * 80)
print("PORTFOLIO COMBINATIONS ON TRAIN (2020-2023)")
print("=" * 80)

combos = [
    ("Duo: MNQ_BO + MNQ_TR (Existing Champion)", ['MNQ_BO', 'MNQ_TR']),
    ("Trio A: MNQ_BO + MNQ_TR + MES_TR", ['MNQ_BO', 'MNQ_TR', 'MES_TR']),
    ("Trio B: MNQ_BO + MNQ_TR + MES_BO", ['MNQ_BO', 'MNQ_TR', 'MES_BO']),
    ("Trio C: MNQ_BO + MNQ_TR + MES_BO60", ['MNQ_BO', 'MNQ_TR', 'MES_BO60']),
    ("Quad: MNQ_BO + MNQ_TR + MES_TR + MES_BO60", ['MNQ_BO', 'MNQ_TR', 'MES_TR', 'MES_BO60']),
]

for name, cols in combos:
    port_curve = df_port[cols].sum(axis=1)
    tot_net = port_curve.iloc[-1]
    peak = port_curve.cummax()
    dd = peak - port_curve
    max_dd = float(dd.max())
    
    # Total trades
    trade_count = 0
    if 'MNQ_BO' in cols: trade_count += len(r_mnq_bo['trade_net'])
    if 'MNQ_TR' in cols: trade_count += len(r_mnq_tr['trade_net'])
    if 'MES_TR' in cols: trade_count += len(r_mes_tr['trade_net'])
    if 'MES_BO' in cols: trade_count += len(r_mes_bo['trade_net'])
    if 'MES_BO60' in cols: trade_count += len(r_mes_bo60['trade_net'])
    
    exp = tot_net / trade_count if trade_count else 0.0
    cushion = 2000.0 - max_dd
    status = "SAFE (Cushion > $700)" if cushion >= 700 else "CAUTION (Cushion < $700)"
    print(f"\n{name}:")
    print(f"  Train Net:    +${tot_net:10.2f}")
    print(f"  Trades:       {trade_count:5d} (~{trade_count//4} trades/year)")
    print(f"  Expectancy:   +${exp:6.2f} / trade")
    print(f"  Max Drawdown: ${max_dd:8.2f} (Safety Cushion: +${cushion:6.2f} before $2k breach)")
    print(f"  Calmar Ratio: {tot_net / max_dd:6.2f}")
    print(f"  Status:       {status}")

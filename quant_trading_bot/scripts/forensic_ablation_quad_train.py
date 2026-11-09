"""Forensic Signal Ablation & Trade-Edge Attribution of AG_Quad on Training Data (2010-2023).
Strict Mandate:
- EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
- ZERO ACCESS TO VALIDATION (2024-2025) OR TEST (2026).
- Account: $50,000 capital, $2,000 trailing drawdown floor.
- Micro friction: $0.61/side, 1.75 tick MNQ / 1.0 tick MES spread, 1.0 tick slippage/side.

Questions to Answer:
1. Individual Sleeve Performance (Stand-alone):
   - Sleeve 1: MNQ 30m Morning Trend (lb16)
   - Sleeve 2: MNQ 60m Macro Trend (lb12)
   - Sleeve 3: MNQ 30m Afternoon Trend (lb8)
   - Sleeve 4: MES 30m Broad Trend (lb8)
2. Marginal Contribution & Router Interaction:
   - What happens when each sleeve is removed (Leave-One-Out Ablation)?
3. Drawdown Anatomy:
   - When did the $1,556 max drawdown occur? Which sleeve caused it?
4. Edge Attribution:
   - Long vs Short contribution.
   - Day of week attribution.
   - Hold time and exit reason (Target hit vs Stop hit vs End-of-day timeout).
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

print("Loading continuous 14-year Training bars for MNQ (30m, 60m) and MES (30m) (2010-2023)...", flush=True)
b_mnq_30 = load_resampled_bars('NQ', 'train', '30 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_60 = load_resampled_bars('NQ', 'train', '60 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mes_30 = load_resampled_bars('ES', 'train', '30 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

# Common arrays
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

# Configurations from live ensemble_paper.py
# Sleeve 1: MNQ 30m Morning Trend (lb16)
f_1 = compute_htf_features(b_mnq_30, 16, 30)
sig_1 = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)
cfg_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)

# Sleeve 2: MNQ 60m Macro Trend (lb12)
f_2 = compute_htf_features(b_mnq_60, 12, 60)
sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)
cfg_2 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=120)

# Sleeve 3: MNQ 30m Afternoon Trend (lb8)
f_3 = compute_htf_features(b_mnq_30, 8, 30)
sig_3_raw = np.where((dec_30 >= 810) & (dec_30 < 915) & weekdays_30 & (np.abs(f_3['trend']) >= 0.50), np.sign(f_3['trend']), 0).astype(np.int8)
cfg_3 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
             stop_atr=1.5, target_ratio=4.0, hold_bars=4, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)

# Sleeve 4: MES 30m Broad Trend (lb8)
f_4 = compute_htf_features(b_mes_30, 8, 30)
sig_4_raw = np.where((dec_mes_30 >= 600) & (dec_mes_30 < 930) & weekdays_mes_30 & (np.abs(f_4['trend']) >= 1.0), np.sign(f_4['trend']), 0).astype(np.int8)
cfg_4 = dict(tick=0.25, multiplier=1.25, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
             stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
             risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
             flat_minute=955, max_gap_minutes=60)

print("\n--- 1. Standalone Sleeve Evaluations (2010-2023 Training) ---", flush=True)
def eval_standalone(name, d, sig, atr, cfg, b):
    r = me.execute(d, sig, atr, cfg)
    pnl = pd.Series(r['cash'] - r['cash'][0], index=b['timestamp_utc'])
    peak = pnl.cummax()
    mdd = float((peak - pnl).max())
    tot = float(pnl.iloc[-1])
    
    trade_years = d['year'][r['trade_entry']]
    trade_nets = r['trade_net']
    n = len(trade_nets)
    exp = tot / n if n else 0.0
    
    pre = float(trade_nets[trade_years < 2020].sum()) if (trade_years < 2020).any() else 0.0
    post = float(trade_nets[trade_years >= 2020].sum()) if (trade_years >= 2020).any() else 0.0
    
    df_tr = pd.DataFrame({'year': trade_years, 'net': trade_nets})
    pos_y = sum(1 for y, v in df_tr.groupby('year')['net'].sum().items() if v > 0)
    
    print(f"\n{name}:")
    print(f"  Total Net: ${tot:+,.2f} | Trades: {n} ({n/14:.1f}/yr) | Exp: ${exp:+.2f}/tr | Max DD: ${mdd:,.2f}")
    print(f"  Pre-2020: ${pre:+,.2f} | Post-2020: ${post:+,.2f} | Positive Years: {pos_y}/14")
    return r, pnl

r1_alone, pnl1 = eval_standalone("S1 Alone: MNQ 30m Morning Trend (lb16)", d_mnq_30, sig_1, f_1['atr'], cfg_1, b_mnq_30)
r2_alone, pnl2 = eval_standalone("S2 Alone: MNQ 60m Macro Trend (lb12)", d_mnq_60, sig_2_raw, f_2['atr'], cfg_2, b_mnq_60)
r3_alone, pnl3 = eval_standalone("S3 Alone: MNQ 30m Afternoon Trend (lb8)", d_mnq_30, sig_3_raw, f_3['atr'], cfg_3, b_mnq_30)
r4_alone, pnl4 = eval_standalone("S4 Alone: MES 30m Broad Trend (lb8)", d_mes_30, sig_4_raw, f_4['atr'], cfg_4, b_mes_30)

print("\n--- 2. Full Live AG_Quad (Strict 1-Contract Router) ---", flush=True)
def run_quad(enable_s1=True, enable_s2=True, enable_s3=True, enable_s4=True):
    # S1
    if enable_s1:
        r1 = me.execute(d_mnq_30, sig_1, f_1['atr'], cfg_1)
        act_1 = pd.Series(r1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
    else:
        act_1 = pd.Series(False, index=b_mnq_30['timestamp_utc'])
        r1 = {'cash': np.full(len(b_mnq_30), 50000.0), 'trade_entry': np.array([], dtype=int), 'trade_net': np.array([])}

    # S2
    act_1_60 = act_1.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False).to_numpy()
    if enable_s2:
        sig_2 = np.where(~act_1_60, sig_2_raw, 0).astype(np.int8)
        r2 = me.execute(d_mnq_60, sig_2, f_2['atr'], cfg_2)
        act_2 = pd.Series(r2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])
    else:
        act_2 = pd.Series(False, index=b_mnq_60['timestamp_utc'])
        r2 = {'cash': np.full(len(b_mnq_60), 50000.0), 'trade_entry': np.array([], dtype=int), 'trade_net': np.array([])}

    # Combined active morning on 30m
    act_2_30 = act_2.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False)
    act_morning_30 = (act_1 | act_2_30).to_numpy()

    # S3
    if enable_s3:
        sig_3 = np.where(~act_morning_30, sig_3_raw, 0).astype(np.int8)
        r3 = me.execute(d_mnq_30, sig_3, f_3['atr'], cfg_3)
        act_3 = pd.Series(r3['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
    else:
        act_3 = pd.Series(False, index=b_mnq_30['timestamp_utc'])
        r3 = {'cash': np.full(len(b_mnq_30), 50000.0), 'trade_entry': np.array([], dtype=int), 'trade_net': np.array([])}

    # Combined MNQ active on MES 30m
    act_mnq_all = (act_1 | act_2_30 | act_3).reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()

    # S4
    if enable_s4:
        sig_4 = np.where(~act_mnq_all, sig_4_raw, 0).astype(np.int8)
        r4 = me.execute(d_mes_30, sig_4, f_4['atr'], cfg_4)
    else:
        r4 = {'cash': np.full(len(b_mes_30), 50000.0), 'trade_entry': np.array([], dtype=int), 'trade_net': np.array([])}

    # Build portfolio cash series
    p1 = pd.Series(r1['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
    p2 = pd.Series(r2['cash'] - 50000.0, index=b_mnq_60['timestamp_utc'])
    p3 = pd.Series(r3['cash'] - 50000.0, index=b_mnq_30['timestamp_utc'])
    p4 = pd.Series(r4['cash'] - 50000.0, index=b_mes_30['timestamp_utc'])

    common_idx = b_mnq_30['timestamp_utc']
    pnl = p1 + p2.reindex(common_idx, method='ffill').fillna(0.0) + p3 + p4.reindex(common_idx, method='ffill').fillna(0.0)
    peak = pnl.cummax()
    mdd = float((peak - pnl).max())
    tot = float(pnl.iloc[-1])

    # Trade counts
    tr_all = []
    for r, d in [(r1, d_mnq_30), (r2, d_mnq_60), (r3, d_mnq_30), (r4, d_mes_30)]:
        if len(r['trade_entry']):
            y = d['year'][r['trade_entry']]
            net = r['trade_net']
            for yr, n in zip(y, net):
                tr_all.append((yr, n))
    df_tr = pd.DataFrame(tr_all, columns=['year', 'net'])
    n_tr = len(df_tr)
    pre = df_tr[df_tr.year < 2020]['net'].sum() if (df_tr.year < 2020).any() else 0.0
    post = df_tr[df_tr.year >= 2020]['net'].sum() if (df_tr.year >= 2020).any() else 0.0
    exp = tot / n_tr if n_tr else 0.0

    return tot, mdd, n_tr, exp, pre, post, pnl

tot, mdd, n_tr, exp, pre, post, pnl_quad = run_quad(True, True, True, True)
print(f"Full AG_Quad (All 4 Sleeves):")
print(f"  Total Net: ${tot:+,.2f} | Trades: {n_tr} ({n_tr/14:.1f}/yr) | Exp: ${exp:+.2f}/tr | Max DD: ${mdd:,.2f} (Cushion: ${2000-mdd:+,.2f})")
print(f"  Pre-2020: ${pre:+,.2f} | Post-2020: ${post:+,.2f}")

print("\n--- 3. Leave-One-Out Signal Ablation (Which Sleeve Hurts or Helps?) ---", flush=True)
def test_ablation(name, s1, s2, s3, s4):
    t, m, n, e, pr, po, _ = run_quad(s1, s2, s3, s4)
    print(f"{name:<25}: Net=${t:+9,.2f} | Max DD=${m:7,.2f} (Cushion=${2000-m:+7.2f}) | Trades={n:4d} | Exp=${e:+5.2f} | Pre-2020=${pr:+8,.2f}")

test_ablation("Baseline Quad (All 4)", True, True, True, True)
test_ablation("Without S1 (Morning 30m)", False, True, True, True)
test_ablation("Without S2 (Macro 60m)", True, False, True, True)
test_ablation("Without S3 (Afternoon 30m)", True, True, False, True)
test_ablation("Without S4 (MES 30m)", True, True, True, False)

print("\n--- 4. Drawdown Anatomy: Where did the $1,556 Drawdown Occur? ---", flush=True)
peak_s = pnl_quad.cummax()
dd_s = peak_s - pnl_quad
max_dd_time = dd_s.idxmax()
max_dd_val = dd_s.max()
peak_time = pnl_quad.loc[:max_dd_time].idxmax()
print(f"Peak Equity Timestamp: {peak_time} (Equity: ${pnl_quad.loc[peak_time]:+,.2f})")
print(f"Trough Timestamp:      {max_dd_time} (Equity: ${pnl_quad.loc[max_dd_time]:+,.2f})")
print(f"Max Continuous DD:     ${max_dd_val:,.2f}")
print(f"Drawdown Window:       {peak_time.date()} to {max_dd_time.date()}")

print("\n--- 5. Pure S1 + S2 Duo (Morning 30m + Macro 60m MNQ) ---", flush=True)
t, m, n, e, pr, po, pnl_duo = run_quad(True, True, False, False)
print(f"S1 + S2 Duo Net: ${t:+,.2f} | Trades: {n} ({n/14:.1f}/yr) | Exp: ${e:+.2f}/tr | Max DD: ${m:,.2f} (Cushion: ${2000-m:+,.2f})")
print(f"  Pre-2020: ${pr:+,.2f} | Post-2020: ${po:+,.2f}")

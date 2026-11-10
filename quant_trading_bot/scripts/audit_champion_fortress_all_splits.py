"""Frozen Out-of-Sample All-Splits Audit: Champion Fortress Evaluation Passer.
STRICT METHODOLOGICAL DISCIPLINE:
- ZERO TUNING, fitting, or post-hoc adjustment on Validation (2024-2025) or Blind Test (2026).
- All parameters, thresholds, and sizing rules are 100% FROZEN from 2010-2023 Training.

Evaluates across:
1. Training Split: 2010-2023 (14.0 Years Benchmark)
2. Validation Split: 2024-2025 (2.0 Years Out-of-Sample)
3. Blind Test Split: 2026 (11 Months Out-of-Sample)

Rules Enforced:
- Target: +$4,000 ($54,000)
- Static Drawdown Floor: -$2,000 (Topstep Static Floor option, fixed at $48,000)
- Daily Loss Limit: -$1,000
- 50% Consistency Rule: Max single day <= $2,000 (Daily lock enforced at +$1,500)
- Full CME Micro Friction: $0.61 commission/side, 1.75 tick spread, 1.0 tick slippage = 1.30 pts roundtrip

Frozen Strategy Architecture:
- Alpha Duo: Toby Crabel 15m Continuation + Stopped Overnight Reopen Dip
- Sizing Ladder:
  * Defensive Shield: 1 MNQ when P&L < -$250
  * Base State: 4 MNQ ($0 to +$1,000)
  * Stage 2 Cushion: 8 MNQ (+$1,000 to +$2,200)
  * Stage 3 Sprint: 12 MNQ (+$2,200 to +$4,000)
- Scale-Out: 50% banked at +20 pts, 50% runner (+85 pts) with stop to breakeven +1 pt.
- Daily Circuit Breakers: Hard stop at -$250; Daily profit lock at +$1,500.
"""
import sys, json, gc, os
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

print("=" * 85)
print("FROZEN OUT-OF-SAMPLE AUDIT: CHAMPION FORTRESS PASSER")
print("Evaluating: Training (2010-23) | Validation (2024-25) | Blind Test (2026)")
print("=" * 85, flush=True)

# 1. Load VIX & VIX3M
vix_path = ROOT / "data/external/VIX_History.csv"
vix3m_path = ROOT / "data/external/VIX3M_History.csv"

vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))
cboe_dates = sorted(list(vix_dict.keys()))

vix3m_df = pd.read_csv(vix3m_path)
vix3m_df["date"] = pd.to_datetime(vix3m_df["DATE"]).dt.date
vix3m_dict = dict(zip(vix3m_df["date"], vix3m_df["CLOSE"]))

def get_vix_for_date(d):
    dt = pd.to_datetime(d).date()
    if dt in vix_dict:
        return vix_dict[dt]
    return vix_dict[cboe_dates[-1]]

def is_vix_backwardated(d):
    dt = pd.to_datetime(d).date()
    vx = vix_dict.get(dt, 20.0)
    v3 = vix3m_dict.get(dt, 20.0)
    return vx > v3

FRICTION_PTS = 1.30
PT_VAL = 2.00

def load_split_bars(parquet_path):
    """Loads minute bars efficiently via DuckDB."""
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='1GB'")
    q = f"""
    SELECT 
        (timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))::DATE AS date,
        (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
         date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ)))::INT AS sod,
        open::DOUBLE AS open,
        high::DOUBLE AS high,
        low::DOUBLE AS low,
        close::DOUBLE AS close
    FROM read_parquet('{parquet_path}')
    ORDER BY date, sod
    """
    df = con.execute(q).fetch_df()
    con.close()
    
    dates = sorted(df["date"].unique())
    
    # Extract RTH (09:30 to 16:00, sod 570 to 960)
    rth = df[(df.sod >= 570) & (df.sod <= 960)].copy()
    daily_eod = rth[rth.sod == 960].groupby("date")["close"].last()
    daily_sod = rth[rth.sod == 570].groupby("date")["open"].first()
    gap_dict = (daily_sod - daily_eod.shift(1)).dropna().to_dict()
    
    # Extract Overnight Reopen (18:05 ET to 09:45 ET next day)
    # Reopen dip: price at 18:05 vs close at 16:00
    on_grouped = {}
    for d, g in df.groupby("date"):
        on_grouped[d] = {
            "sod": g["sod"].to_numpy(),
            "open": g["open"].to_numpy(),
            "high": g["high"].to_numpy(),
            "low": g["low"].to_numpy(),
            "close": g["close"].to_numpy()
        }
        
    rth_grouped = {}
    for d, g in rth.groupby("date"):
        rth_grouped[d] = {
            "sod": g["sod"].to_numpy(),
            "high": g["high"].to_numpy(),
            "low": g["low"].to_numpy(),
            "close": g["close"].to_numpy()
        }
        
    del df, rth
    gc.collect()
    
    return dates, gap_dict, rth_grouped, on_grouped

def simulate_champion_split(dates, gap_dict, rth_grouped, on_grouped):
    """Simulates the 100% frozen Champion Fortress strategy on the given split."""
    daily_events = {}
    
    for idx_d in range(len(dates)):
        d = dates[idx_d]
        vix = get_vix_for_date(d)
        trades_for_day = []
        
        # 1. Overnight Reopen Dip (Entered at 18:05 previous day, exited at 09:45 today)
        if idx_d > 0:
            prev_d = dates[idx_d - 1]
            if prev_d in on_grouped and d in on_grouped:
                # Check VIX backwardation
                if not is_vix_backwardated(prev_d):
                    prev_bars = on_grouped[prev_d]
                    sod_p = prev_bars["sod"]
                    idx_1805 = np.where(sod_p >= 1085)[0] # 18:05 ET
                    if len(idx_1805) > 0:
                        idx_1600 = np.where(sod_p <= 960)[0]
                        c1600 = prev_bars["close"][idx_1600[-1]] if len(idx_1600) > 0 else prev_bars["close"][0]
                        e1805 = prev_bars["open"][idx_1805[0]]
                        dip_pts = e1805 - c1600
                        # Overnight Dip Trigger: Reopen <= -8 points from close
                        if dip_pts <= -8.0:
                            # Evaluate exit at 09:45 today
                            today_bars = on_grouped[d]
                            sod_t = today_bars["sod"]
                            idx_0945 = np.where(sod_t >= 585)[0]
                            if len(idx_0945) > 0:
                                ex0945 = today_bars["open"][idx_0945[0]]
                                # Overnight low between 18:05 and 09:45
                                night_low = min(prev_bars["low"][idx_1805[0]:].min(), today_bars["low"][:idx_0945[0]].min())
                                raw_pnl = (ex0945 - e1805) - FRICTION_PTS
                                mae_pts = night_low - e1805
                                
                                # Enforce 25-pt Hard Stop!
                                if mae_pts <= -25.0:
                                    raw_pnl = -25.0 - FRICTION_PTS
                                    mae_pts = -25.0
                                    
                                trades_for_day.append({
                                    "order": 0,
                                    "type": "overnight",
                                    "net_1c": raw_pnl * PT_VAL,
                                    "mae_1c": mae_pts * PT_VAL,
                                    "pts": raw_pnl
                                })
                                
        # 2. Intraday Toby Crabel 15m Continuation
        gap = gap_dict.get(d, 0.0)
        if vix >= 15.0 and d in rth_grouped:
            bars = rth_grouped[d]
            sod = bars["sod"]
            high = bars["high"]
            low = bars["low"]
            close = bars["close"]
            
            mask_15 = sod < 585
            if mask_15.any():
                hi_15 = high[mask_15].max()
                lo_15 = low[mask_15].min()
                rng_15 = hi_15 - lo_15
                
                if rng_15 >= 15.0:
                    idx_trade = np.where((sod >= 585) & (sod <= 955))[0]
                    if len(idx_trade) > 0:
                        in_pos = False
                        pos_dir = 0
                        entry_px = 0.0
                        sl_1 = 0.0
                        sl_2 = 0.0
                        tp_1 = 0.0
                        tp_2 = 0.0
                        leg1_closed = False
                        initial_stop = 18.0 # Frozen 18 pt stop
                        t1_pts = 20.0       # Frozen 20 pt banker
                        runner_pts = 85.0   # Frozen 85 pt runner
                        
                        trade_net_pts = 0.0
                        trade_mae_pts = 0.0
                        
                        for idx in idx_trade:
                            px_h, px_l = high[idx], low[idx]
                            
                            if not in_pos:
                                if gap >= 0.0 and px_h > hi_15:
                                    in_pos = True
                                    pos_dir = 1
                                    entry_px = hi_15
                                    sl_1 = entry_px - initial_stop
                                    sl_2 = sl_1
                                    tp_1 = entry_px + t1_pts
                                    tp_2 = entry_px + runner_pts
                                elif gap <= 0.0 and px_l < lo_15:
                                    in_pos = True
                                    pos_dir = -1
                                    entry_px = lo_15
                                    sl_1 = entry_px + initial_stop
                                    sl_2 = sl_1
                                    tp_1 = entry_px - t1_pts
                                    tp_2 = entry_px - runner_pts
                            else:
                                if pos_dir == 1:
                                    adv = px_l - entry_px
                                    if adv < trade_mae_pts: trade_mae_pts = adv
                                    if not leg1_closed:
                                        if px_h >= tp_1:
                                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                                            leg1_closed = True
                                            sl_2 = entry_px + 1.0 # Breakeven
                                        elif px_l <= sl_1:
                                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                                            in_pos = False; break
                                    else:
                                        if px_h >= tp_2:
                                            trade_net_pts += (runner_pts - FRICTION_PTS) * 0.5
                                            in_pos = False; break
                                        elif px_l <= sl_2:
                                            trade_net_pts += (sl_2 - entry_px - FRICTION_PTS) * 0.5
                                            in_pos = False; break
                                else: # pos_dir == -1
                                    adv = entry_px - px_h
                                    if adv < trade_mae_pts: trade_mae_pts = adv
                                    if not leg1_closed:
                                        if px_l <= tp_1:
                                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                                            leg1_closed = True
                                            sl_2 = entry_px - 1.0
                                        elif px_h >= sl_1:
                                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                                            in_pos = False; break
                                    else:
                                        if px_l <= tp_2:
                                            trade_net_pts += (runner_pts - FRICTION_PTS) * 0.5
                                            in_pos = False; break
                                        elif px_h >= sl_2:
                                            trade_net_pts += (entry_px - sl_2 - FRICTION_PTS) * 0.5
                                            in_pos = False; break
                                            
                        if in_pos: # EOD exit
                            last_c = close[idx_trade[-1]]
                            eod_pts = (last_c - entry_px if pos_dir == 1 else entry_px - last_c) - FRICTION_PTS
                            qty_rem = 0.5 if leg1_closed else 1.0
                            trade_net_pts += eod_pts * qty_rem
                            
                        if trade_net_pts != 0.0 or trade_mae_pts != 0.0:
                            trades_for_day.append({
                                "order": 1,
                                "type": "crabel",
                                "net_1c": trade_net_pts * PT_VAL,
                                "mae_1c": trade_mae_pts * PT_VAL,
                                "pts": trade_net_pts
                            })
                            
        daily_events[d] = trades_for_day
        
    return daily_events

def run_evaluation_trials(daily_events, dates, max_eval_days=90):
    """Evaluates Topstep prop firm lifecycle across the split."""
    total_starts = max(1, len(dates) - 20)
    passed = 0
    ruined = 0
    pass_days = []
    max_dds = []
    daily_pnls_all = []
    
    cum_total = 0.0
    hwm_total = 0.0
    peak_dd_total = 0.0
    
    # Continuous Ledger
    for d in dates:
        tr_list = daily_events.get(d, [])
        day_pnl = sum(tr["net_1c"] * 4.0 for tr in tr_list) # nominal 4c base
        daily_pnls_all.append(day_pnl)
        cum_total += day_pnl
        if cum_total > hwm_total: hwm_total = cum_total
        if (hwm_total - cum_total) > peak_dd_total: peak_dd_total = hwm_total - cum_total
        
    # Prop Firm Evaluation Trials (Sliding Window)
    horizon = min(len(dates) - 1, max_eval_days)
    for i in range(len(dates) - horizon):
        cum = 0.0
        hwm = 0.0
        floor = -2000.0 # Topstep static floor
        busted = False
        pass_run = False
        peak_dd = 0.0
        max_d_pnl = -9999.0
        
        for step in range(horizon):
            d = dates[i + step]
            tr_list = daily_events.get(d, [])
            if not tr_list: continue
            
            # Frozen Fortress Sizing Ladder
            if cum <= -250.0:
                sz = 1; o_sz = 1
            elif cum >= 2200.0:
                sz = 12; o_sz = 2
            elif cum >= 1000.0:
                sz = 8; o_sz = 2
            else:
                sz = 4; o_sz = 1
                
            day_pnl = 0.0
            day_mae = 0.0
            
            for tr in tr_list:
                s = o_sz if tr["type"] == "overnight" else sz
                mae = tr["mae_1c"] * s
                pnl = tr["net_1c"] * s
                
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                
                # Daily circuit breakers
                if day_pnl >= 1500.0 or day_pnl <= -250.0:
                    break
                    
            if day_pnl <= -1000.0 or day_mae <= -1000.0 or (cum + day_mae) <= floor:
                busted = True; break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            if cum <= floor: busted = True; break
            
            if day_pnl > max_d_pnl: max_d_pnl = day_pnl
            
            # Pass Target + 50% consistency rule
            if cum >= 4000.0 and max_d_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_days.append(step + 1)
                max_dds.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
            
    p_arr = np.array(pass_days) if pass_days else np.array([0])
    dd_arr = np.array(max_dds) if max_dds else np.array([0])
    
    total_evals = passed + ruined
    pass_pct = (passed / total_evals * 100) if total_evals > 0 else 0.0
    ruin_pct = (ruined / total_evals * 100) if total_evals > 0 else 0.0
    med_days = float(np.median(p_arr)) if passed > 0 else 0.0
    p25_days = float(np.percentile(p_arr, 25)) if passed > 0 else 0.0
    min_days = int(p_arr.min()) if passed > 0 else 0
    avg_dd = float(dd_arr.mean()) if passed > 0 else 0.0
    
    # Active days metrics
    act_pnls = [p for p in daily_pnls_all if p != 0.0]
    win_days = sum(1 for p in act_pnls if p > 0)
    loss_days = sum(1 for p in act_pnls if p < 0)
    wr = (win_days / len(act_pnls) * 100) if act_pnls else 0.0
    pf = (sum(p for p in act_pnls if p > 0) / abs(sum(p for p in act_pnls if p < 0))) if loss_days > 0 else 999.0
    
    return {
        "net_profit_nominal_4c": round(cum_total, 2),
        "peak_drawdown_nominal_4c": round(peak_dd_total, 2),
        "active_trading_days": len(act_pnls),
        "win_days": win_days,
        "loss_days": loss_days,
        "daily_win_rate_pct": round(wr, 1),
        "daily_profit_factor": round(pf, 2),
        "eval_trials_evaluated": total_evals,
        "eval_passed": passed,
        "eval_ruined": ruined,
        "eval_pass_rate_pct": round(pass_pct, 1),
        "eval_ruin_rate_pct": round(ruin_pct, 1),
        "med_days_to_pass": round(med_days, 1),
        "med_weeks_to_pass": round(med_days / 5.0, 1),
        "p25_days_to_pass": round(p25_days, 1),
        "min_days_to_pass": min_days,
        "avg_dd_on_pass": round(avg_dd, 2)
    }

# File paths
p_train = str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet")
p_val = str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/validation.parquet")
p_test = str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/test.parquet")

splits = [
    ("Training (2010-2023)", p_train, 250),
    ("Validation (2024-2025)", p_val, 180),
    ("Blind Test (2026)", p_test, 90),
]

all_split_report = {}

for split_name, path, max_h in splits:
    print(f"\n>>> Loading {split_name} from {path}...", flush=True)
    dates, gap_dict, rth_grouped, on_grouped = load_split_bars(path)
    print(f"Loaded {len(dates)} calendar trading days.", flush=True)
    
    print(f"Simulating frozen Champion Fortress Passer...", flush=True)
    events = simulate_champion_split(dates, gap_dict, rth_grouped, on_grouped)
    metrics = run_evaluation_trials(events, dates, max_eval_days=max_h)
    
    all_split_report[split_name] = metrics
    print(f"[{split_name.upper()}] Net PnL (4c Base): +${metrics['net_profit_nominal_4c']:,.2f} | Win Rate: {metrics['daily_win_rate_pct']}% | PF: {metrics['daily_profit_factor']}")
    print(f"  Pass Rate: {metrics['eval_pass_rate_pct']}% | Ruin Rate: {metrics['eval_ruin_rate_pct']}% | Median Days: {metrics['med_days_to_pass']}d ({metrics['med_weeks_to_pass']}w) | Avg DD: ${metrics['avg_dd_on_pass']}")
    
    del rth_grouped, on_grouped, gap_dict, dates, events
    gc.collect()

out_path = ROOT / "reports/CHAMPION_FORTRESS_ALL_SPLITS_RESULTS.json"
with open(out_path, "w") as f:
    json.dump(all_split_report, f, indent=2)

print("\n" + "=" * 85)
print(f"[SUCCESS] All-Splits audit completed! Results saved to: {out_path.name}")
print("=" * 85, flush=True)

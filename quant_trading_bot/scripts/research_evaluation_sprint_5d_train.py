"""Evaluation Sprint Strategy (5-Day / $4,000 Target) Architecture Research.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Design Criteria for Passing $4,000 in 5 Days:
1. Daily Target Lock: Once daily PnL reaches +$800, halt trading for the day (safeguards 50% consistency rule, ensuring max day <= $2,000).
2. Daily Circuit Breaker: Once daily PnL drops to -$400, halt trading for the day (safeguards $1,000 Daily Loss Limit & $2,000 Trailing DD).
3. Asymmetric Intraday Brackets: 15 pt stop / 45 pt target (1:3 RR) with Breakeven ratchet at +20 pts.
4. High-Probability Regimes: Crabel Open Drive & Opening Range Momentum during active morning hours (9:30 - 11:30 ET).
5. Micro contract sizing sweep: 2, 4, 6, 8, 10 MNQ contracts.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1

print("=" * 80)
print("EVALUATION SPRINT STRATEGY (5-DAY / $4,000) TRAINING SIMULATION")
print("=" * 80, flush=True)

# Load 1-minute MNQ training data (2010-2023)
print("Loading 14-year 1m MNQ training bars...", flush=True)
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close", "volume"]]
et = b.timestamp_utc.dt.tz_convert("America/New_York")
b["date"] = et.dt.date
b["sod"] = et.dt.hour * 60 + et.dt.minute # minutes from midnight

# Focus on RTH (9:30 to 16:00 ET -> sod 570 to 960)
rth = b[(b.sod >= 570) & (b.sod <= 960)].copy()
dates = sorted(rth["date"].unique())
print(f"Total trading days loaded: {len(dates):,}")

# Precompute daily gap
# Prior close at 16:00, today open at 9:30
daily_eod = rth[rth.sod == 960].groupby("date")["close"].last()
daily_sod = rth[rth.sod == 570].groupby("date")["open"].first()
gap_series = (daily_sod - daily_eod.shift(1)).dropna()
gap_dict = gap_series.to_dict()

# Cost model: CME Micro MNQ ($0.61 commission + 1.75 tick spread + 1 tick slippage)
# In points: ($0.61 * 2 / $2.00) + 0.4375 + 0.25 = 0.61 + 0.4375 + 0.25 = 1.30 points roundtrip friction per contract.
FRICTION_PTS = 1.30
PT_VAL = 2.00 # $2 per point for MNQ

def run_sprint_simulation(n_contracts, daily_target=800.0, daily_stop=400.0, stop_pts=18.0, target_pts=45.0):
    """
    Simulates the high-frequency Evaluation Sprint strategy across all 3,397 days.
    Generates daily P&L and intraday drawdown for each day.
    """
    daily_results = {}
    
    # Pre-filter RTH by morning session 9:30 - 11:30 (sod 570 to 690)
    morning = rth[(rth.sod >= 570) & (rth.sod <= 690)].copy()
    grouped = morning.groupby("date")
    
    for d, df in grouped:
        if len(df) < 30:
            daily_results[d] = {"net": 0.0, "mae": 0.0, "trades": 0}
            continue
            
        gap = gap_dict.get(d, 0.0)
        day_pnl = 0.0
        day_mae = 0.0
        trade_count = 0
        
        # Opening Drive Signal at 9:45 (sod 585, after first 15 mins)
        bars_15 = df[df.sod < 585]
        if len(bars_15) == 0:
            continue
        hi_15 = bars_15["high"].max()
        lo_15 = bars_15["low"].min()
        rng_15 = hi_15 - lo_15
        
        # Signals only if 15m range is sufficiently active (> 15 pts)
        if rng_15 < 15.0:
            daily_results[d] = {"net": 0.0, "mae": 0.0, "trades": 0}
            continue
            
        # Track active position
        pos = 0 # +1 long, -1 short, 0 flat
        entry_px = 0.0
        sl_px = 0.0
        tp_px = 0.0
        be_triggered = False
        
        # Iterate minute bars from 9:45 to 11:30
        trade_bars = df[df.sod >= 585]
        for _, bar in trade_bars.iterrows():
            px_o, px_h, px_l, px_c = bar["open"], bar["high"], bar["low"], bar["close"]
            
            # If in position, check SL / TP / Trailing BE
            if pos != 0:
                if pos == 1:
                    # Long position
                    # Check if reached Breakeven ratchet (+20 pts)
                    if not be_triggered and (px_h - entry_px) >= 20.0:
                        sl_px = entry_px + 1.0 # Breakeven + 1 pt
                        be_triggered = True
                        
                    # Check Target Fill
                    if px_h >= tp_px:
                        trade_net_pts = target_pts - FRICTION_PTS
                        trade_pnl = trade_net_pts * PT_VAL * n_contracts
                        day_pnl += trade_pnl
                        pos = 0
                        trade_count += 1
                    # Check Stop Fill
                    elif px_l <= sl_px:
                        trade_net_pts = (sl_px - entry_px) - FRICTION_PTS
                        trade_pnl = trade_net_pts * PT_VAL * n_contracts
                        day_pnl += trade_pnl
                        pos = 0
                        trade_count += 1
                    else:
                        # Intraday unrealized dip
                        dip_pts = px_l - entry_px
                        dip_dollars = dip_pts * PT_VAL * n_contracts
                        if (day_pnl + dip_dollars) < day_mae:
                            day_mae = day_pnl + dip_dollars
                elif pos == -1:
                    # Short position
                    if not be_triggered and (entry_px - px_l) >= 20.0:
                        sl_px = entry_px - 1.0
                        be_triggered = True
                        
                    if px_l <= tp_px:
                        trade_net_pts = target_pts - FRICTION_PTS
                        trade_pnl = trade_net_pts * PT_VAL * n_contracts
                        day_pnl += trade_pnl
                        pos = 0
                        trade_count += 1
                    elif px_h >= sl_px:
                        trade_net_pts = (entry_px - sl_px) - FRICTION_PTS
                        trade_pnl = trade_net_pts * PT_VAL * n_contracts
                        day_pnl += trade_pnl
                        pos = 0
                        trade_count += 1
                    else:
                        dip_pts = entry_px - px_h
                        dip_dollars = dip_pts * PT_VAL * n_contracts
                        if (day_pnl + dip_dollars) < day_mae:
                            day_mae = day_pnl + dip_dollars
                            
                # Check Circuit Breakers: Target Lock or Stop Out for the day
                if day_pnl >= daily_target:
                    # Target achieved today! Lock profits and stop trading
                    break
                if day_pnl <= -daily_stop:
                    # Daily loss stop hit! Protect account and stop trading
                    break
            else:
                # Flat: Check for Breakout Entries aligned with Opening Gap
                # Long Breakout: bar breaks above 15m high and gap >= 0
                if px_h > hi_15 and gap >= -10.0 and trade_count < 2:
                    pos = 1
                    entry_px = hi_15
                    sl_px = entry_px - stop_pts
                    tp_px = entry_px + target_pts
                    be_triggered = False
                # Short Breakout: bar breaks below 15m low and gap <= 10.0
                elif px_l < lo_15 and gap <= 10.0 and trade_count < 2:
                    pos = -1
                    entry_px = lo_15
                    sl_px = entry_px + stop_pts
                    tp_px = entry_px - target_pts
                    be_triggered = False
                    
        # Close any open trade at end of window (11:30 ET)
        if pos != 0:
            exit_px = trade_bars.iloc[-1]["close"]
            trade_pts = (exit_px - entry_px if pos == 1 else entry_px - exit_px) - FRICTION_PTS
            day_pnl += trade_pts * PT_VAL * n_contracts
            trade_count += 1
            
        daily_results[d] = {
            "net": day_pnl,
            "mae": min(day_mae, day_pnl),
            "trades": trade_count
        }
        
    return daily_results

print("\nRunning Evaluation Sprint Sizing Sweep (2, 4, 6, 8, 10 contracts)...", flush=True)

for nc in [2, 4, 6, 8, 10]:
    # Daily stop at $400, Daily target lock at $900 (so 5 days reaches $4k without violating consistency rule)
    res_daily = run_sprint_simulation(n_contracts=nc, daily_target=900.0, daily_stop=400.0, stop_pts=18.0, target_pts=45.0)
    
    # Now simulate rolling 5-day evaluation windows
    all_days = sorted(res_daily.keys())
    total_evals = len(all_days) - 4
    
    target = 4000.0
    floor = 2000.0 # Trailing DD
    dll = 1000.0  # Topstep Daily Loss Limit
    max_day_limit = 2000.0 # 50% Consistency Rule
    
    clean_pass = 0
    inconsistent_pass = 0
    ruined = 0
    neither = 0
    
    for i in range(total_evals):
        w_days = all_days[i : i + 5]
        cum_pnl = 0.0
        hwm = 0.0
        busted = False
        max_day = -9999.0
        
        for d in w_days:
            dp = res_daily[d]["net"]
            dm = res_daily[d]["mae"]
            
            # Check Daily Loss Limit
            if dp <= -dll or dm <= -dll:
                busted = True
                break
                
            # Check Trailing Drawdown
            if (hwm - (cum_pnl + dm)) >= floor or (cum_pnl + dm) <= -floor:
                busted = True
                break
                
            cum_pnl += dp
            if cum_pnl > hwm:
                hwm = cum_pnl
                
            if (hwm - cum_pnl) >= floor or cum_pnl <= -floor:
                busted = True
                break
                
            if dp > max_day:
                max_day = dp
                
            if cum_pnl >= target:
                break
                
        if busted:
            ruined += 1
        elif cum_pnl >= target:
            if max_day <= max_day_limit:
                clean_pass += 1
            else:
                inconsistent_pass += 1
        else:
            neither += 1
            
    pct_clean = (clean_pass / total_evals) * 100
    pct_any = ((clean_pass + inconsistent_pass) / total_evals) * 100
    pct_ruin = (ruined / total_evals) * 100
    pct_neither = (neither / total_evals) * 100
    
    print(f"\nContracts: {nc} MNQ | Daily Cap: +$900 / Stop: -$400")
    print(f"  Clean 5-Day Pass Rate (50% Consistency compliant): {pct_clean:.2f}% ({clean_pass} weeks)")
    print(f"  Any 5-Day Pass Rate:                               {pct_any:.2f}% ({clean_pass + inconsistent_pass} weeks)")
    print(f"  5-Day Account Ruin Rate (DD/DLL breach):           {pct_ruin:.2f}% ({ruined} weeks)")
    print(f"  Alive but Target Not Reached in 5 Days:            {pct_neither:.2f}% ({neither} weeks)")

print("\nSprint simulation finished.")

"""Research Lab: Trailing Profit Ratchets & Dynamic Giveback Prevention on Leg 2.
TRAINING SPLIT (2010-2023) ONLY.
Strict Methodological Protocol:
- Zero touch of Validation (2024-2025) or Blind Test (2026).
- 100% Causal Prior-Session VIX close.
- Full CME micro friction ($1.30 pts = $2.60/contract).
- Topstep 50k Prop Rules ($4k target, -$2k static floor, -$1k DLL, daily lock $1,500).
- Floor trigger -$400.
"""
import sys, json, gc, bisect
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
p_train = ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet"

# Load VIX History
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))
cboe_dates = sorted(list(vix_dict.keys()))

def get_prior_vix(d):
    dt = pd.to_datetime(d).date()
    i = bisect.bisect_left(cboe_dates, dt) - 1
    return vix_dict[cboe_dates[max(i, 0)]]

FRICTION_PTS = 1.30
PT_VAL = 2.00
STATIC_FLOOR = -2000.0
DLL_LIMIT = -1000.0
DAILY_LOCK = 1500.0

con = duckdb.connect()
con.execute("PRAGMA memory_limit='4GB'")
q = f"""
SELECT 
    (timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))::DATE AS date,
    (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
     date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ)))::INT AS sod,
    open::DOUBLE AS open, high::DOUBLE AS high, low::DOUBLE AS low, close::DOUBLE AS close
FROM read_parquet('{p_train}')
WHERE (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
       date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))) BETWEEN 570 AND 960
ORDER BY date, sod
"""
rth = con.execute(q).fetch_df()
con.close()

dates = sorted(rth["date"].unique())
daily_eod = rth[rth.sod == 960].groupby("date")["close"].last()
daily_sod = rth[rth.sod == 570].groupby("date")["open"].first()
gap_dict = (daily_sod - daily_eod.shift(1)).dropna().to_dict()

grouped = {}
for d, g in rth.groupby("date"):
    grouped[d] = {
        "sod": g["sod"].to_numpy(),
        "high": g["high"].to_numpy(),
        "low": g["low"].to_numpy(),
        "close": g["close"].to_numpy(),
    }
del rth
gc.collect()

def simulate_with_ratchet(
    ratchet_mode="none", # "none", "step_60_30", "step_50_25", "dual_50_80", "trail_25_after_40"
    initial_stop=16.0,
    t1_pts=28.0,
    runner_tp=120.0
):
    daily_res = {}
    for d in dates:
        vix = get_prior_vix(d)
        gap = gap_dict.get(d, 0.0)
        if vix < 15.0 or d not in grouped:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        bars = grouped[d]
        sod, high, low, close = bars["sod"], bars["high"], bars["low"], bars["close"]
        mask_15 = sod < 585
        if not mask_15.any():
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
        if rng_15 < 15.0:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        idx_trade = np.where((sod >= 585) & (sod <= 955))[0]
        if len(idx_trade) == 0:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        in_pos = False
        pos_dir = 0
        entry_px = 0.0
        sl_1 = 0.0
        sl_2 = 0.0
        tp_1 = 0.0
        leg1_closed = False
        trade_net_pts = 0.0
        trade_mae_pts = 0.0
        max_fav = 0.0
        
        for idx in idx_trade:
            px_h, px_l = high[idx], low[idx]
            if not in_pos:
                if gap >= 0.0 and px_h > hi_15:
                    in_pos = True; pos_dir = 1; entry_px = hi_15
                    sl_1 = entry_px - initial_stop; sl_2 = sl_1; tp_1 = entry_px + t1_pts
                elif gap <= 0.0 and px_l < lo_15:
                    in_pos = True; pos_dir = -1; entry_px = lo_15
                    sl_1 = entry_px + initial_stop; sl_2 = sl_1; tp_1 = entry_px - t1_pts
            else:
                if pos_dir == 1:
                    adv = max(px_l - entry_px, -initial_stop)
                    fav = px_h - entry_px
                    if not leg1_closed and adv < trade_mae_pts: trade_mae_pts = adv
                    if fav > max_fav: max_fav = fav
                    
                    if not leg1_closed:
                        if px_h >= tp_1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True; sl_2 = entry_px + 1.0 # Breakeven
                        elif px_l <= sl_1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        # Dynamic ratchet logic on Leg 2
                        if ratchet_mode == "step_60_30":
                            if max_fav >= 60.0: sl_2 = max(sl_2, entry_px + 30.0)
                        elif ratchet_mode == "step_50_25":
                            if max_fav >= 50.0: sl_2 = max(sl_2, entry_px + 25.0)
                        elif ratchet_mode == "dual_50_80":
                            if max_fav >= 80.0: sl_2 = max(sl_2, entry_px + 50.0)
                            elif max_fav >= 50.0: sl_2 = max(sl_2, entry_px + 25.0)
                        elif ratchet_mode == "trail_25_after_40":
                            if max_fav >= 40.0: sl_2 = max(sl_2, entry_px + (max_fav - 25.0))
                            
                        if max_fav >= runner_tp:
                            trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        if px_l <= sl_2:
                            pts_exit = sl_2 - entry_px
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                else: # Short
                    adv = max(entry_px - px_h, -initial_stop)
                    fav = entry_px - px_l
                    if not leg1_closed and adv < trade_mae_pts: trade_mae_pts = adv
                    if fav > max_fav: max_fav = fav
                    
                    if not leg1_closed:
                        if px_l <= tp_1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True; sl_2 = entry_px - 1.0 # Breakeven
                        elif px_h >= sl_1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        if ratchet_mode == "step_60_30":
                            if max_fav >= 60.0: sl_2 = min(sl_2, entry_px - 30.0)
                        elif ratchet_mode == "step_50_25":
                            if max_fav >= 50.0: sl_2 = min(sl_2, entry_px - 25.0)
                        elif ratchet_mode == "dual_50_80":
                            if max_fav >= 80.0: sl_2 = min(sl_2, entry_px - 50.0)
                            elif max_fav >= 50.0: sl_2 = min(sl_2, entry_px - 25.0)
                        elif ratchet_mode == "trail_25_after_40":
                            if max_fav >= 40.0: sl_2 = min(sl_2, entry_px - (max_fav - 25.0))
                            
                        if max_fav >= runner_tp:
                            trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        if px_h >= sl_2:
                            pts_exit = entry_px - sl_2
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                            
        if in_pos:
            last_c = close[idx_trade[-1]]
            eod_pts = (last_c - entry_px if pos_dir == 1 else entry_px - last_c) - FRICTION_PTS
            qty_rem = 0.5 if leg1_closed else 1.0
            trade_net_pts += eod_pts * qty_rem
            
        daily_res[str(d)] = {
            "net_1c": float(trade_net_pts * PT_VAL),
            "mae_1c": float(trade_mae_pts * PT_VAL),
            "traded": bool(in_pos or trade_net_pts != 0.0)
        }
    return daily_res

def eval_ladder(daily_res, base_sz=10, accel_sz=12, sprint_sz=14, def_thr=-400.0):
    ds = [str(d) for d in dates]
    passed, ruined, timeouts, dll_b = 0, 0, 0, 0
    pass_days, pass_sess, dds = [], [], []
    
    for i in range(len(ds) - 100):
        cum, hwm, busted, pass_run, peak_dd, tr_days = 0.0, 0.0, False, False, 0.0, 0
        for step in range(100):
            d_str = ds[i + step]
            tr = daily_res.get(d_str, None)
            if not tr or not tr["traded"]: continue
            tr_days += 1
            
            vix = get_prior_vix(d_str)
            is_hv = (vix >= 16.0)
            bonus = 2 if is_hv else 0
            
            if cum <= def_thr:
                sz = 1
            elif cum >= 2400.0:
                sz = sprint_sz + bonus
            elif cum >= 1200.0:
                sz = accel_sz + bonus
            else:
                sz = base_sz + bonus
                
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            if pnl <= DLL_LIMIT or mae <= DLL_LIMIT:
                busted = True; dll_b += 1; break
            if (cum + mae) <= STATIC_FLOOR:
                busted = True; break
            if pnl > DAILY_LOCK: pnl = DAILY_LOCK
            
            cum += pnl
            c_dd = hwm - cum
            if c_dd > peak_dd: peak_dd = c_dd
            if cum > hwm: hwm = cum
            if cum <= STATIC_FLOOR: busted = True; break
            if cum >= 4000.0:
                passed += 1; pass_run = True; pass_days.append(tr_days); pass_sess.append(step+1); dds.append(peak_dd); break
                
        if busted and not pass_run: ruined += 1
        elif not pass_run and not busted: timeouts += 1
        
    p_pct = (passed / max(1, passed + ruined)) * 100
    r_pct = (ruined / max(1, passed + ruined)) * 100
    mean_tr = np.mean(pass_days) if passed else 999.0
    med_tr = np.median(pass_days) if passed else 999.0
    p25_tr = np.percentile(pass_days, 25) if passed else 999.0
    p10_tr = np.percentile(pass_days, 10) if passed else 999.0
    min_tr = np.min(pass_days) if passed else 999
    avg_dd = np.mean(dds) if passed else 999.0
    
    return {
        "passed": passed, "ruined": ruined, "timeouts": timeouts,
        "pass_pct": round(p_pct, 1), "ruin_pct": round(r_pct, 1),
        "mean_days": round(mean_tr, 1), "med_days": round(med_tr, 1),
        "p25_days": round(p25_tr, 1), "p10_days": round(p10_tr, 1),
        "min_days": int(min_tr), "avg_dd": round(avg_dd, 1), "dll": dll_b
    }

print("="*95)
print("LEG 2 PROFIT RATCHET & GIVEBACK PREVENTION LAB (TRAINING 2010-2023 ONLY)")
print("="*95)

modes = [
    ("Baseline (Breakeven +1pt)", "none"),
    ("Step Ratchet (60pt fav -> lock +30pt)", "step_60_30"),
    ("Step Ratchet (50pt fav -> lock +25pt)", "step_50_25"),
    ("Dual Step (50->+25, 80->+50)", "dual_50_80"),
    ("Trailing 25pt after +40pt", "trail_25_after_40"),
]

results = []
for name, m in modes:
    dres = simulate_with_ratchet(ratchet_mode=m)
    pnl_1c = [v["net_1c"] for v in dres.values() if v["traded"]]
    wins = sum(1 for p in pnl_1c if p > 0)
    wr = wins / len(pnl_1c) * 100
    net_1c = sum(pnl_1c)
    ev = eval_ladder(dres)
    print(f"{name:38s} || WR: {wr:4.1f}% | Net 1c: ${net_1c:7.1f} || Pass: {ev['passed']:3d} ({ev['pass_pct']:5.1f}%) | Mean: {ev['mean_days']:4.1f}d | Med: {ev['med_days']:4.1f}d | P25: {ev['p25_days']:4.1f}d | P10: {ev['p10_days']:4.1f}d | DD: ${ev['avg_dd']:6.1f} | Ruin: {ev['ruin_pct']:3.1f}%")
    results.append({"mode": m, "wr": wr, "net_1c": net_1c, "eval": ev})

with open(ROOT / "reports/RESEARCH_LEG2_RATCHET_TRAINING_RESULTS.json", "w") as f:
    json.dump(results, f, indent=2)
print("Complete.")

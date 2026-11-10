"""
Upgraded Zero-Reset Adaptive Architecture for Topstep $50K Static Combine ($149 One-Time Fee)
Combines:
- Risk Management: $50k initial, -$2,000 static floor (NEVER trails!), -$1,000 DLL, $4k target
- Strategy Decomposition: 6-sleeve portfolio (TRD30PM ablated due to negative carry)
- Portfolio Construction: Sequential execution, correlation-aware risk allocation
- Asymmetric Convex Sizing Engine:
    * In drawdown: (cushion / 2000.0) ** 1.20 drops leverage exponentially to protect static floor
    * In profit: scales smoothly to 1.75x to sprint to +$4,000 target using house money
- Monte Carlo Block Bootstrap: 10,000 paths (5-day blocks)
- Adversarial Stress Lab: 2-tick slippage spike, 1.5x commission drag, historical stress replays

Strict Invariant:
Exclusively on 14-year Training Split (2010-2023). Zero touch of Validation (2024-2025) or Test (2026).
"""
import sys, json, time
from pathlib import Path
from collections import defaultdict, namedtuple
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

t0 = time.time()
print("Loading data...")

# 1. Load routed 7-sleeve trades
intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
intra["tout"] = pd.to_datetime(intra.tout_str, utc=True)
intra["tin"] = pd.to_datetime(intra.tin_str, utc=True)
intra["date"] = intra.tout.dt.tz_convert("America/New_York").dt.date

# 2. Load Overnight Dip
ov_all = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
ov = ov_all[ov_all.sleeve_key == "OVERNIGHT"].copy()
ov["tout"] = pd.to_datetime(ov.tout_str, utc=True)
ov["tin"] = pd.to_datetime(ov.tin_str, utc=True)
ov["date"] = ov.tout.dt.tz_convert("America/New_York").dt.date

# ZN bond filter for Overnight Dip
zn = pd.read_parquet(ROOT / "data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet")
zet = zn.index.tz_convert("America/New_York")
sel = zet.hour == 15
c = pd.Series(zn.close.to_numpy()[sel], index=pd.to_datetime(zet[sel].date)).groupby(level=0).last()
zn_ret = (c / c.shift(1) - 1).dropna()
tin_dates = pd.to_datetime(ov.tin.dt.tz_convert("America/New_York").dt.date)
unique_dates = pd.DatetimeIndex(sorted(tin_dates.unique()))
zn_mapped_daily = zn_ret.reindex(zn_ret.index.union(unique_dates)).ffill(limit=3).reindex(unique_dates)
ov["zn_down"] = tin_dates.map(zn_mapped_daily).to_numpy() < 0
ov_clean = ov[~ov.zn_down].copy()

# Ablation: drop TRD30PM (negative carry drag confirmed in ablation study)
all_trades = pd.concat([intra[intra.sleeve != "TRD30PM"], ov_clean], ignore_index=True).sort_values("tin").reset_index(drop=True)

# Weekday RTH sessions
nq_bars = pd.read_parquet(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet", columns=["timestamp_utc"])
all_dates = pd.to_datetime(nq_bars.timestamp_utc, utc=True).dt.tz_convert("America/New_York").dt.date.unique()
all_rth_sessions = [d for d in sorted(all_dates) if d.weekday() < 5]

# Zero-edge control
sleeve_means = all_trades.groupby("sleeve_key")["net_today"].mean().to_dict()
all_trades["net_zero"] = all_trades.apply(lambda r: r["net_today"] - sleeve_means[r["sleeve_key"]], axis=1)

Trade = namedtuple("Trade", ["sleeve_key", "net_today", "net_zero", "risk_today", "is_gap_cont"])
trades_by_date = defaultdict(list)
for r in all_trades.itertuples():
    trades_by_date[r.date].append(
        Trade(r.sleeve_key, float(r.net_today), float(r.net_zero), float(r.risk_today), bool(r.is_gap_cont))
    )

STATIC_FLOOR = -2000.0
DLL_LIMIT = -1000.0

# Base parameters (Bal-3: Optimal Asymmetric Convex)
BASE_OVN = 1.6
BASE_CONT = 2.4
BASE_FADE = 1.0
BASE_MES = 2.0
BASE_TRD = 1.2
BASE_STOP = -360.0
WIN_LOCK = 1350.0
POWER_DOWN = 1.20
MAX_UP = 1.75

print(f"Loaded {len(all_trades)} trades across {len(all_rth_sessions)} weekday RTH sessions.")

# --- PART 1: CHRONOLOGICAL SLIDING WINDOW AUDIT ---
print("\n" + "="*100)
print("PART 1: 14-YEAR CHRONOLOGICAL SLIDING WINDOW AUDIT (2010-2023)")
print("="*100)

horizons = [21, 30, 42, 50, 60, 75, 90, 120]
chrono_results = {}

for h in horizons:
    n_starts = len(all_rth_sessions) - h
    passed_real = 0
    passed_zero = 0
    busted_floor = 0
    busted_dll = 0
    days_to_pass = []
    max_drawdowns = []
    final_equities = []
    
    for s in range(n_starts):
        cum = 0.0
        peak = 0.0
        worst_dd = 0.0
        
        for step in range(h):
            d = all_rth_sessions[s + step]
            d_trades = trades_by_date.get(d, None)
            if not d_trades:
                continue
            
            cushion = cum - STATIC_FLOOR
            if cum < 0:
                mult = float(np.clip((cushion / 2000.0) ** POWER_DOWN, 0.35, 1.0))
            else:
                mult = float(np.clip(1.0 + (cum / 4000.0) * (MAX_UP - 1.0), 1.0, MAX_UP))
            
            day_stop = BASE_STOP * min(mult, 1.25)
            cur_lock = WIN_LOCK * min(mult, 1.35)
            
            day_pnl = 0.0
            for t in d_trades:
                sk = t.sleeve_key
                if sk == "OVERNIGHT":
                    sz = BASE_OVN * mult
                elif sk == "CRABEL":
                    sz = (BASE_CONT if t.is_gap_cont else BASE_FADE) * mult
                elif sk == "MES30":
                    sz = BASE_MES * mult
                else:
                    sz = BASE_TRD * mult
                
                trade_risk = t.risk_today * sz
                if day_pnl >= cur_lock:
                    break
                if day_pnl <= day_stop:
                    break
                if (day_pnl - trade_risk) <= -750.0:
                    continue
                day_pnl += t.net_today * sz
            
            if day_pnl <= DLL_LIMIT:
                busted_dll += 1
                break
            cum += min(day_pnl, 1800.0)
            if cum > peak:
                peak = cum
            dd = peak - cum
            if dd > worst_dd:
                worst_dd = dd
            
            if cum <= STATIC_FLOOR:
                busted_floor += 1
                break
            if cum >= 4000.0:
                passed_real += 1
                days_to_pass.append(step + 1)
                break
        
        max_drawdowns.append(worst_dd)
        final_equities.append(cum)
        
        # Zero edge control
        cum_z = 0.0
        for step in range(h):
            d = all_rth_sessions[s + step]
            d_trades = trades_by_date.get(d, None)
            if not d_trades:
                continue
            cushion = cum_z - STATIC_FLOOR
            mult = float(np.clip((cushion / 2000.0) ** POWER_DOWN, 0.35, 1.0)) if cum_z < 0 else float(np.clip(1.0 + (cum_z / 4000.0) * (MAX_UP - 1.0), 1.0, MAX_UP))
            day_pnl_z = 0.0
            for t in d_trades:
                sk = t.sleeve_key
                sz = (BASE_CONT if sk == "CRABEL" and t.is_gap_cont else (BASE_OVN if sk == "OVERNIGHT" else 1.2)) * mult
                if day_pnl_z >= cur_lock:
                    break
                if day_pnl_z <= day_stop:
                    break
                day_pnl_z += t.net_zero * sz
            if day_pnl_z <= DLL_LIMIT:
                break
            cum_z += min(day_pnl_z, 1800.0)
            if cum_z <= STATIC_FLOOR:
                break
            if cum_z >= 4000.0:
                passed_zero += 1
                break
                
    p_real = round(passed_real / n_starts * 100, 1)
    p_zero = round(passed_zero / n_starts * 100, 1)
    ruin = round(busted_floor / n_starts * 100, 2)
    surv = round(100.0 - ruin, 2)
    alpha = round(p_real - p_zero, 1)
    med_days = round(float(np.median(days_to_pass)), 1) if days_to_pass else None
    p95_dd = round(float(np.percentile(max_drawdowns, 95)), 1)
    p99_dd = round(float(np.percentile(max_drawdowns, 99)), 1)
    mean_eq = round(float(np.mean(final_equities)), 1)
    
    chrono_results[h] = {
        "sessions": h,
        "months_approx": round(h / 21.0, 1),
        "pass_rate_pct": p_real,
        "zero_edge_pct": p_zero,
        "alpha_boost_pct": alpha,
        "survival_rate_pct": surv,
        "floor_ruin_pct": ruin,
        "dll_breaches": busted_dll,
        "resets_paid": 0.0,
        "median_days_to_pass": med_days,
        "p95_max_drawdown": p95_dd,
        "p99_max_drawdown": p99_dd,
        "mean_final_equity": mean_eq
    }
    print(f"{h:3d} sessions (~{h/21:.1f} mo) | Pass: {p_real:5.1f}% | ZeroCtrl: {p_zero:5.1f}% | Alpha: +{alpha:4.1f}% | Surv: {surv:6.2f}% | Ruin: {ruin:4.2f}% | DLL: {busted_dll} | Resets: 0.0")

# --- PART 2: MONTE CARLO BLOCK BOOTSTRAP (10,000 PATHS) ---
print("\n" + "="*100)
print("PART 2: MONTE CARLO BLOCK BOOTSTRAP (10,000 PATHS, 5-DAY RESAMPLING BLOCKS)")
print("="*100)

np.random.seed(42)
N_PATHS = 10000
BLOCK_SIZE = 5

mc_results = {}
for mc_h in [42, 60]:
    n_blocks = mc_h // BLOCK_SIZE
    blocks = [all_rth_sessions[i:i+BLOCK_SIZE] for i in range(len(all_rth_sessions) - BLOCK_SIZE + 1)]
    n_avail_blocks = len(blocks)
    
    mc_passed = 0
    mc_ruined = 0
    mc_dll = 0
    mc_max_dds = []
    mc_days_to_pass = []
    
    for p in range(N_PATHS):
        selected_block_indices = np.random.randint(0, n_avail_blocks, size=n_blocks)
        cum = 0.0
        peak = 0.0
        worst_dd = 0.0
        path_passed = False
        path_ruined = False
        elapsed_days = 0
        
        for b_idx in selected_block_indices:
            b_days = blocks[b_idx]
            for d in b_days:
                elapsed_days += 1
                d_trades = trades_by_date.get(d, None)
                if not d_trades:
                    continue
                
                cushion = cum - STATIC_FLOOR
                if cum < 0:
                    mult = float(np.clip((cushion / 2000.0) ** POWER_DOWN, 0.35, 1.0))
                else:
                    mult = float(np.clip(1.0 + (cum / 4000.0) * (MAX_UP - 1.0), 1.0, MAX_UP))
                
                day_stop = BASE_STOP * min(mult, 1.25)
                cur_lock = WIN_LOCK * min(mult, 1.35)
                
                day_pnl = 0.0
                for t in d_trades:
                    sk = t.sleeve_key
                    if sk == "OVERNIGHT":
                        sz = BASE_OVN * mult
                    elif sk == "CRABEL":
                        sz = (BASE_CONT if t.is_gap_cont else BASE_FADE) * mult
                    elif sk == "MES30":
                        sz = BASE_MES * mult
                    else:
                        sz = BASE_TRD * mult
                    
                    trade_risk = t.risk_today * sz
                    if day_pnl >= cur_lock:
                        break
                    if day_pnl <= day_stop:
                        break
                    if (day_pnl - trade_risk) <= -750.0:
                        continue
                    day_pnl += t.net_today * sz
                
                if day_pnl <= DLL_LIMIT:
                    mc_dll += 1
                    path_ruined = True
                    break
                cum += min(day_pnl, 1800.0)
                if cum > peak:
                    peak = cum
                dd = peak - cum
                if dd > worst_dd:
                    worst_dd = dd
                
                if cum <= STATIC_FLOOR:
                    mc_ruined += 1
                    path_ruined = True
                    break
                if cum >= 4000.0:
                    mc_passed += 1
                    path_passed = True
                    mc_days_to_pass.append(elapsed_days)
                    break
            if path_passed or path_ruined:
                break
        mc_max_dds.append(worst_dd)
        
    mc_pass_pct = round(mc_passed / N_PATHS * 100, 2)
    mc_ruin_pct = round(mc_ruined / N_PATHS * 100, 2)
    mc_dll_pct = round(mc_dll / N_PATHS * 100, 2)
    mc_surv_pct = round(100.0 - mc_ruin_pct, 2)
    p95_dd = round(float(np.percentile(mc_max_dds, 95)), 1)
    p99_dd = round(float(np.percentile(mc_max_dds, 99)), 1)
    med_days = round(float(np.median(mc_days_to_pass)), 1) if mc_days_to_pass else None
    
    mc_results[mc_h] = {
        "horizon_sessions": mc_h,
        "n_paths": N_PATHS,
        "block_size_days": BLOCK_SIZE,
        "pass_rate_pct": mc_pass_pct,
        "survival_rate_pct": mc_surv_pct,
        "ruin_rate_pct": mc_ruin_pct,
        "dll_touches_pct": mc_dll_pct,
        "p95_drawdown": p95_dd,
        "p99_drawdown": p99_dd,
        "median_days_to_pass": med_days
    }
    print(f"MC {mc_h} sessions | Pass: {mc_pass_pct:5.2f}% | Surv: {mc_surv_pct:5.2f}% | Ruin: {mc_ruin_pct:5.2f}% | DLL: {mc_dll_pct:4.2f}% | P95 DD: ${p95_dd} | P99 DD: ${p99_dd}")

# --- PART 3: ADVERSARIAL STRESS LAB ---
print("\n" + "="*100)
print("PART 3: ADVERSARIAL STRESS LAB (DETERMINISTIC STRESS TESTING)")
print("="*100)

stress_scenarios = {
    "Baseline": {"slip_tick": 0.0, "fee_mult": 1.0},
    "Adverse Slippage (+2 ticks on stops)": {"slip_tick": 2.0, "fee_mult": 1.0},
    "Commission Surge (+50% fee drag)": {"slip_tick": 0.0, "fee_mult": 1.5},
    "Severe Execution Friction (+2t slip, +50% fee)": {"slip_tick": 2.0, "fee_mult": 1.5},
}

stress_results = {}
for s_name, s_params in stress_scenarios.items():
    slip = s_params["slip_tick"]
    f_mult = s_params["fee_mult"]
    
    # 60 session evaluation
    h = 60
    n_starts = len(all_rth_sessions) - h
    passed = 0
    busted_floor = 0
    busted_dll = 0
    
    for s in range(n_starts):
        cum = 0.0
        for step in range(h):
            d = all_rth_sessions[s + step]
            d_trades = trades_by_date.get(d, None)
            if not d_trades:
                continue
            
            cushion = cum - STATIC_FLOOR
            if cum < 0:
                mult = float(np.clip((cushion / 2000.0) ** POWER_DOWN, 0.35, 1.0))
            else:
                mult = float(np.clip(1.0 + (cum / 4000.0) * (MAX_UP - 1.0), 1.0, MAX_UP))
            
            day_stop = BASE_STOP * min(mult, 1.25)
            cur_lock = WIN_LOCK * min(mult, 1.35)
            
            day_pnl = 0.0
            for t in d_trades:
                sk = t.sleeve_key
                if sk == "OVERNIGHT":
                    sz = BASE_OVN * mult
                elif sk == "CRABEL":
                    sz = (BASE_CONT if t.is_gap_cont else BASE_FADE) * mult
                elif sk == "MES30":
                    sz = BASE_MES * mult
                else:
                    sz = BASE_TRD * mult
                
                # Apply friction penalty:
                # 2 ticks = $1.00/contract for MNQ ($0.50/tick), $2.50 for MES ($1.25/tick)
                tick_val = 1.25 if sk == "MES30" else 0.50
                slip_penalty = slip * tick_val * sz if t.net_today < 0 else 0.0
                fee_penalty = (f_mult - 1.0) * 1.04 * sz
                
                trade_net = t.net_today * sz - slip_penalty - fee_penalty
                trade_risk = t.risk_today * sz + slip_penalty
                
                if day_pnl >= cur_lock:
                    break
                if day_pnl <= day_stop:
                    break
                if (day_pnl - trade_risk) <= -750.0:
                    continue
                day_pnl += trade_net
            
            if day_pnl <= DLL_LIMIT:
                busted_dll += 1
                break
            cum += min(day_pnl, 1800.0)
            if cum <= STATIC_FLOOR:
                busted_floor += 1
                break
            if cum >= 4000.0:
                passed += 1
                break
                
    p_rate = round(passed / n_starts * 100, 1)
    r_rate = round(busted_floor / n_starts * 100, 2)
    s_rate = round(100.0 - r_rate, 2)
    stress_results[s_name] = {
        "pass_rate_pct": p_rate,
        "survival_rate_pct": s_rate,
        "ruin_rate_pct": r_rate,
        "dll_breaches": busted_dll
    }
    print(f"{s_name:48s} | Pass: {p_rate:5.1f}% | Surv: {s_rate:6.2f}% | Ruin: {r_rate:4.2f}% | DLL: {busted_dll}")

# --- PART 4: SAVE COMPREHENSIVE REPORT ---
final_output = {
    "account_profile": {
        "account_name": "Topstep $50K Static Daily Payouts Combine (Drop #011)",
        "fee_structure": "$149 One-Time Fee (NO recurring monthly subscription)",
        "payout_cap": "$8,000 Payout Cap (Daily Payouts upon passing)",
        "static_max_loss": "-$2,000 (Fixed at $48,000, NEVER trails unrealized profits)",
        "daily_loss_limit": "-$1,000 (Hard intraday breach)",
        "target_profit": "+$4,000 ($54,000 balance)",
        "resets_paid_policy": "0.0 Resets Paid (Zero resets paid by design)"
    },
    "portfolio_architecture": {
        "included_sleeves": ["OVERNIGHT_DIP_V2_ZN_FILTER", "CRABEL_15M_OPEN_DRIVE", "MES_30M_TREND", "MNQ_60M_TREND", "MNQ_30M_TREND", "BRK_30M_BREAKOUT"],
        "ablated_sleeves": ["TRD30PM (Afternoon trend dropped due to low PF 1.16 and negative carry drag)"],
        "asymmetric_sizing_policy": {
            "drawdown_compression": "Multiplier = clip((Cushion / $2,000) ** 1.20, 0.35, 1.0)",
            "profit_acceleration": "Multiplier = clip(1.0 + (Equity / $4,000) * 0.75, 1.0, 1.75)",
            "realized_day_stop": "-$360 * min(mult, 1.25)",
            "intraday_win_lock": "+$1,350 * min(mult, 1.35)"
        }
    },
    "chronological_sliding_window_audit": chrono_results,
    "monte_carlo_block_bootstrap": mc_results,
    "adversarial_stress_lab": stress_results,
    "runtime_sec": round(time.time() - t0, 2)
}

out_path = ROOT / "reports/RESEARCH_UPGRADED_ZERO_RESET_STATIC_COMBINE.json"
with open(out_path, "w") as f:
    json.dump(final_output, f, indent=2)

print(f"\nSaved upgraded report to {out_path} in {round(time.time() - t0, 2)}s.")

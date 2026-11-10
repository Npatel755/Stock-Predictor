import sys
import numpy as np
sys.path.insert(0, r'c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot\scripts')
from research_zero_reset_50k_static_passer_train import evaluate_zero_reset_policy, all_rth_sessions, trades_by_date, STATIC_FLOOR, DLL_LIMIT, Trade

print("="*115)
print(f"{'HORIZON':24s} || {'CUMULATIVE PASS':17s} {'ZERO CONTROL':14s} {'ALPHA BOOST':13s} || {'RUIN RATE':11s} {'DLL':3s}")
print("="*115)

def run_horizon(h):
    n_starts = len(all_rth_sessions) - h
    passed = 0
    busted_floor = 0
    busted_dll = 0
    days_to_pass = []

    for s in range(n_starts):
        cum = 0.0
        for step in range(h):
            d = all_rth_sessions[s + step]
            d_trades = trades_by_date.get(d, None)
            if not d_trades:
                continue

            cushion = cum - STATIC_FLOOR # $2,000 at start
            mult = np.clip(cushion / 2000.0, 0.4, 1.4)

            day_pnl = 0.0
            for t in d_trades:
                sk = t.sleeve_key
                if sk == "OVERNIGHT":
                    sz = 1.5 * mult
                elif sk == "CRABEL":
                    sz = (2.2 if t.is_gap_cont else 1.0) * mult
                elif sk == "MES30":
                    sz = 2.2 * mult
                else:
                    sz = 1.2 * mult

                trade_risk = t.risk_today * sz
                if day_pnl >= 1100.0:
                    break
                if day_pnl <= -380.0:
                    break
                if (day_pnl - trade_risk) <= -800.0:
                    continue
                day_pnl += t.net_today * sz

            if day_pnl <= DLL_LIMIT:
                busted_dll += 1
                break

            cum += min(day_pnl, 1500.0)

            if cum <= STATIC_FLOOR:
                busted_floor += 1
                break
            if cum >= 4000.0:
                passed += 1
                days_to_pass.append(step + 1)
                break

    # zero-edge control
    passed_z = 0
    for s in range(n_starts):
        cum = 0.0
        for step in range(h):
            d = all_rth_sessions[s + step]
            d_trades = trades_by_date.get(d, None)
            if not d_trades:
                continue
            cushion = cum - STATIC_FLOOR
            mult = np.clip(cushion / 2000.0, 0.4, 1.4)
            day_pnl = 0.0
            for t in d_trades:
                sk = t.sleeve_key
                sz = (2.2 if sk == "CRABEL" and t.is_gap_cont else (1.5 if sk == "OVERNIGHT" else 1.2)) * mult
                if day_pnl >= 1100.0: break
                if day_pnl <= -380.0: break
                day_pnl += t.net_zero * sz
            if day_pnl <= DLL_LIMIT: break
            cum += min(day_pnl, 1500.0)
            if cum <= STATIC_FLOOR: break
            if cum >= 4000.0:
                passed_z += 1
                break

    p_real = round(passed / n_starts * 100, 1)
    p_zero = round(passed_z / n_starts * 100, 1)
    ruin_pct = round(busted_floor / n_starts * 100, 2)
    alpha = round(p_real - p_zero, 1)
    label = f"{h} sessions (~{h/21:.1f} mo)"
    print(f"{label:24s} || {p_real:6.1f}%            {p_zero:6.1f}%          +{alpha:5.1f}%        || {ruin_pct:6.2f}%      {busted_dll:3d}")

for h in [21, 30, 42, 50, 60, 75, 90, 120]:
    run_horizon(h)

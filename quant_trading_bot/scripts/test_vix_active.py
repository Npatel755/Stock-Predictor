import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
src = (ROOT / "scripts/research_champion_passer_optimizer.py").read_text()
split_marker = "print(\"\\n\" + \"=\"*95)"
ns = {}
exec(src.split(split_marker)[0], ns)
all_days = ns["all_days"]
vix_dict = ns["vix_dict"]
trades_book = ns["trades_book"]

def test_vix_active(min_vix=18.0):
    total = len(all_days) - 200
    passed, ruined = 0, 0
    pass_days, max_dds = [], []
    for i in range(total):
        if vix_dict.get(all_days[i], 18.0) < min_vix: continue
        cum, hwm, floor, peak_dd = 0.0, 0.0, -2000.0, 0.0
        busted, pass_run = False, False
        for step in range(200):
            d = all_days[i + step]
            tr_list = trades_book.get(d, [])
            if not tr_list: continue
            if cum <= -300.0: sz, o_sz = 1, 1
            elif cum >= 2200.0: sz, o_sz = 12, 2
            elif cum >= 1000.0: sz, o_sz = 8, 2
            else: sz, o_sz = 4, 1
            day_pnl, day_mae = 0.0, 0.0
            for tr in tr_list:
                s = o_sz if tr["type"] == "overnight" else sz
                mae = max(tr["mae_1c"], -25.0 * 2.0) * s if tr["type"] == "overnight" else tr["mae_1c"] * s
                pts = tr["pts"]
                if tr["type"] != "overnight" and pts > 20.0:
                    pnl = (0.5 * 20.0 + 0.5 * min(pts, 85.0)) * 2.0 * s - 2.60 * s
                else: pnl = tr["net_1c"] * s
                if (day_pnl + mae) < day_mae: day_mae = day_pnl + mae
                day_pnl += pnl
                if day_pnl >= 1500.0 or day_pnl <= -250.0: break
            if day_pnl <= -1000.0 or day_mae <= -1000.0 or (cum + day_mae) <= floor:
                busted = True; break
            cum += day_pnl
            if (hwm - cum) > peak_dd: peak_dd = hwm - cum
            if cum > hwm: hwm = cum
            if cum <= floor: busted = True; break
            if cum >= 4000.0:
                pass_run = True; passed += 1; pass_days.append(step + 1); max_dds.append(peak_dd); break
        if busted and not pass_run: ruined += 1
    p_arr = np.array(pass_days) if pass_days else np.array([0])
    dd_arr = np.array(max_dds) if max_dds else np.array([0])
    p_pct = passed / max(1, passed + ruined) * 100
    r_pct = ruined / max(1, passed + ruined) * 100
    print(f"Active VIX >= {min_vix:4.1f} | Passed: {passed:4d} | Ruined: {ruined:4d} | Pass Rate: {p_pct:5.1f}% | Ruin Rate: {r_pct:5.1f}% | Median Days: {np.median(p_arr):4.1f}d | Avg DD: ${np.mean(dd_arr):6.2f}")

print("="*95)
print("TESTING ACTIVE VIX SPRINT PERFORMANCE")
print("="*95)
for v in [0.0, 16.0, 18.0, 20.0, 22.0]:
    test_vix_active(v)

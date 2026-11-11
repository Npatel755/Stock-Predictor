import sys
from pathlib import Path
ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))

from audit_vol_adaptive_fortress_train import sim, evaluate, load_train, prior_day_vix
dates, gap_dict, G = load_train()
daily, amb, n_tr = sim(dates, gap_dict, G, prior_day_vix, pess=False)

print("="*80)
print("COMPARING DEFENSIVE FLOOR TRIGGERS (PRIOR-DAY VIX, TRAINING 2010-2023)")
print("="*80)
for trig in [-200.0, -250.0, -300.0, -350.0, -400.0, -500.0]:
    res = evaluate(dates, daily, prior_day_vix, horizon=100, def_thr=trig)
    print(f"Trigger: ${trig:5.0f} | Pass% All: {res['pass_pct_of_all']:4.1f}% | Pub Pass%: {res['published_style_pass_pct']:5.1f}% | Fail%: {res['fail_pct']:3.1f}% | Med Trade Days: {res['median_trade_days_to_pass']:4.1f} | Stuck in 1-micro: {res['open_windows_stuck_in_1_micro_pct']:4.1f}%")

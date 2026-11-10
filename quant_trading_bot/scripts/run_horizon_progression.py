import sys
import numpy as np
sys.path.insert(0, r'c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot\scripts')
from research_all_sleeves_smashed_fastest_passer_train import simulate_sprint_engine

print("="*105)
print(f"{'HORIZON':22s} || {'PASS RATE':10s} {'ZERO PASS':10s} {'ALPHA BOOST':12s} || {'AVG RESETS':11s} {'TOTAL COST':10s} {'DLL':3s}")
print("="*105)

for h in [5, 10, 15, 21, 30, 42, 60, 75, 90]:
    r = simulate_sprint_engine(
        'Policy 2 Fast-Fail',
        crabel_cont_sz=6.0, crabel_fade_sz=2.0, night_sz=2.0, mes_sz=5.0, trend_sz=2.5,
        reset_thr=-350.0, day_win_lock=1500.0, day_stop_loss=520.0, cushion_boost=2.0, trailing_lock=True,
        max_evaluation_days=h
    )
    real = r['real']
    zero = r['zero']
    p_real = real['pass_final']
    p_zero = zero['pass_final']
    alpha = p_real - p_zero
    rst = real['resets']
    months = max(1.0, np.ceil(h / 21.0))
    cost = round((rst * 49.0) + (months * 49.0), 0)
    label = f"{h} sessions (~{h/21:.1f} mo)"
    print(f"{label:22s} || {p_real:6.1f}%    {p_zero:6.1f}%    +{alpha:5.1f}%      || {rst:4.1f} resets   ${cost:5.0f}    {real['dll_breaches']:3d}")

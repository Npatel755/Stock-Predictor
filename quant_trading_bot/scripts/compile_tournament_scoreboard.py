"""Unified Scoreboard: Comparing Overnight Discoveries vs Portfolio E."""
import pandas as pd
from pathlib import Path

# Load out of sample audit
df_audit = pd.read_csv('quant_trading_bot/runs/overnight_institutional_research/overnight_discoveries_out_of_sample_audit.csv')

# Portfolio E known metrics from runs/saved_portfolio_E_undisputed_champion_mes_mom_mnq_brk/summary.json
port_e = {
    'name': 'CHAMPION: Portfolio E (MES Mom 3c + MNQ AM Breakout 2c)',
    'train_net': 19095.50, 'train_dd': 1395.25, 'train_pf': 1.67, 'train_trades': 362,
    'val_net': 3142.25, 'val_dd': 1744.25, 'val_pf': 1.25, 'val_trades': 131,
    'test_net': 6562.25, 'test_dd': 964.75, 'test_pf': 1.88, 'test_trades': 77,
    '7yr_net': 28800.00, 'worst_7yr_dd': 1744.25, 'passed_2k_rule': True
}

# Portfolio E Scaled (2c MES + 1c MNQ)
port_e_scaled = {
    'name': 'CONSERVATIVE CORE: Portfolio E Scaled (MES 2c + MNQ 1c)',
    'train_net': 10791.75, 'train_dd': 926.12, 'train_pf': 1.67, 'train_trades': 362,
    'val_net': 1667.75, 'val_dd': 1152.00, 'val_pf': 1.25, 'val_trades': 131,
    'test_net': 4059.25, 'test_dd': 685.50, 'test_pf': 1.88, 'test_trades': 77,
    '7yr_net': 16518.75, 'worst_7yr_dd': 1152.00, 'passed_2k_rule': True
}

full_df = pd.concat([pd.DataFrame([port_e, port_e_scaled]), df_audit], ignore_index=True)
full_df.to_csv('quant_trading_bot/runs/overnight_institutional_research/master_finalist_tournament_audit.csv', index=False)

print("\n" + "=" * 95)
print("FINAL SCOREBOARD: ALL CANDIDATES AUDITED OUT-OF-SAMPLE (NO TUNING)")
print("=" * 95)
cols = ['name', '7yr_net', 'worst_7yr_dd', 'passed_2k_rule', 'test_net', 'test_dd', 'val_net', 'val_dd']
print(full_df[cols].to_string(index=False))

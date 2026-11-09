import json
import pandas as pd

q = json.load(open('quant_trading_bot/runs/htf_swing_training_qualifiers.json'))
df = pd.DataFrame(q)

print("Qualifiers by Instrument & Timeframe:")
print(df.groupby(['sym', 'tf']).size())

print("\n=== TOP 5 60m MNQ QUALIFIERS (TRAIN 2020-2023) ===")
q60 = df[(df.sym=='MNQ') & (df.tf=='60m')].sort_values('expectancy', ascending=False)
for _, r in q60.head(5).iterrows():
    print(f"{r['family']} lb={r['lookback']} th={r['threshold']} stop={r['stop_atr']} tgt={r['target_ratio']}R hold={r['hold_bars']} trail={r['trailing_atr']} sess={r['session']} | Exp: ${r['expectancy']:.2f}/tr | Net: ${r['net_pnl']:,.2f} | DD: ${r['intrabar_dd']:.2f} | PF: {r['profit_factor']:.2f} | Yrs: {r['yearly_pnls']}")

print("\n=== TOP 5 30m/60m MES QUALIFIERS (TRAIN 2020-2023) ===")
qmes = df[df.sym=='MES'].sort_values('expectancy', ascending=False)
for _, r in qmes.head(5).iterrows():
    print(f"{r['tf']} {r['family']} lb={r['lookback']} th={r['threshold']} stop={r['stop_atr']} tgt={r['target_ratio']}R hold={r['hold_bars']} trail={r['trailing_atr']} sess={r['session']} | Exp: ${r['expectancy']:.2f}/tr | Net: ${r['net_pnl']:,.2f} | DD: ${r['intrabar_dd']:.2f} | PF: {r['profit_factor']:.2f} | Yrs: {r['yearly_pnls']}")

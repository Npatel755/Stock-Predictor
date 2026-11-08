import json

with open("quant_trading_bot/runs/pure_1c_training_qualifiers.json") as f:
    d = json.load(f)

print("=== TOP 10 MES QUALIFIERS (TRAIN 2020-2023 ONLY) ===")
for i, x in enumerate(d["mes"][:10]):
    c = x["cfg"]
    print(f"{i+1}. {c['family']} lb={c['lookback']} th={c['threshold']} stop={c['stop_atr']} tgt={c['target_r']} hold={c['hold_bars']} sess={c['session_start']}-{c['session_end']} | Net: ${x['net']:,.2f} | DD: ${x['dd']:.2f} | PF: {x['pf']:.2f} | Exp: ${x['exp']:.2f} | Yrs: {x['yearly']}")

print("\n=== TOP 10 MNQ QUALIFIERS (TRAIN 2020-2023 ONLY) ===")
for i, x in enumerate(d["mnq"][:10]):
    c = x["cfg"]
    print(f"{i+1}. {c['family']} lb={c['lookback']} th={c['threshold']} stop={c['stop_atr']} tgt={c['target_r']} hold={c['hold_bars']} sess={c['session_start']}-{c['session_end']} | Net: ${x['net']:,.2f} | DD: ${x['dd']:.2f} | PF: {x['pf']:.2f} | Exp: ${x['exp']:.2f} | Yrs: {x['yearly']}")

import json
from pathlib import Path

p = Path('quant_trading_bot/runs/robust_pairs_finalists.json')
finalists = json.load(open(p))
print(f"Total finalists: {len(finalists)}")
for i, f in enumerate(finalists[:10]):
    mes = f['mes_cfg']
    mnq = f['mnq_cfg']
    print(f"Rank {i+1:2d}: MES {mes['family']:<8} (lb={mes['lookback']:2d}, th={mes['threshold']:.2f}, hold={mes['hold_bars']:2d}, c={mes['max_contracts']}) + "
          f"MNQ {mnq['family']:<8} (lb={mnq['lookback']:2d}, th={mnq['threshold']:.2f}, hold={mnq['hold_bars']:2d}, c={mnq['max_contracts']}) | "
          f"Train Net: ${f['train_net']:>8.2f} | Train DD: ${f['train_dd']:>7.2f} | Score: {f['stability_score']:.2f}")

import json
from pathlib import Path

finalists = json.loads(Path('quant_trading_bot/runs/robust_pairs_finalists.json').read_text())
for idx in [0, 1, 3, 4]:
    f = finalists[idx]
    print(f"\n=== Finalist Rank {idx+1} ===")
    print(f"MES ID: {f['mes_id']} | MNQ ID: {f['mnq_id']}")
    print(f"MES CFG: {f['mes_cfg']}")
    print(f"MNQ CFG: {f['mnq_cfg']}")
    print(f"Train Net: +${f['train_net']:,.2f} | Train DD: ${f['train_dd']:,.2f}")
    print(f"Annual Nets: {[round(x, 2) for x in f['annual_nets']]}")

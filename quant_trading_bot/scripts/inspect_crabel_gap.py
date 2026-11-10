import pandas as pd
from pathlib import Path

ROOT = Path(r"quant_trading_bot")
intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
crabel_gap_long = intra[(intra.sleeve == "CRABEL15") & (intra.side == 1) & (intra.is_gap_cont == True)]
print("CRABEL15 Long + GapCont:")
print(f"N = {len(crabel_gap_long)}")
print(f"WinRate = {(crabel_gap_long.net_today > 0).mean()*100:.1f}%")
print(f"Expectancy = ${crabel_gap_long.net_today.mean():.1f}")
print(f"Avg Win = ${crabel_gap_long[crabel_gap_long.net_today > 0].net_today.mean():.1f}")
print(f"Avg Loss = ${crabel_gap_long[crabel_gap_long.net_today <= 0].net_today.mean():.1f}")

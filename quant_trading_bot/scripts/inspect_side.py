import pandas as pd
from pathlib import Path

ROOT = Path(r"quant_trading_bot")
intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
print(intra[["sleeve", "side", "net_today", "risk_today"]].head(10))
print("Unique sides:", intra.side.unique())

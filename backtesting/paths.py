from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data/ethusd/perpetual"
PARQUET = DATA / "candles.parquet"
RUNS = ROOT / "artifacts/dvs"
PINE_V1 = ROOT / "reference/DVS_ETH_v1.pine"
PINE = ROOT / "reference/DVS_ETH_v1_1_fixed.pine"

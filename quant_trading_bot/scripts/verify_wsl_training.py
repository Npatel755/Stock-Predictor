"""Verify native WSL loading of actual reference training, without test prices."""
from pathlib import Path
import platform
from quant_futures.dataset_catalog import resolve_dataset
from quant_futures.research import load_dataset, json_write

if platform.system() != "Linux":
    raise RuntimeError("Run inside WSL")
root = Path(__file__).resolve().parents[1]
path = resolve_dataset("ES:train", catalog_path=root/"data/manifests/wsl/catalog.json")
bars, metadata, quality = load_dataset(path, minutes=15)
assert metadata["split_role"] == "train" and metadata["instrument"] == "ES" and quality["fatal"] == 0
assert bars.timestamp_utc.max().year == 2023 and bars.timestamp_utc.min().year == 2010
report = dict(passed=True, rows=len(bars), start=str(bars.timestamp_utc.min()), end=str(bars.timestamp_utc.max()),
    timeframe_minutes=15, instrument="ES", role="train", actual_market_data=True, test_prices_read=False)
json_write(root/"reports/wsl_actual_training_verification.json", report)
print(report)

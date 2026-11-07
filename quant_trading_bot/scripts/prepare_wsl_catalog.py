"""Create native Linux path descriptors without touching Windows data/catalog."""
from pathlib import Path
import json
import platform
import re
from quant_futures.research import json_write
from quant_futures.config import file_hash

if platform.system() != "Linux":
    raise RuntimeError("Run inside WSL")
ROOT = Path(__file__).resolve().parents[1]


def native(value):
    if isinstance(value, dict):
        return {native(key): native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [native(item) for item in value]
    if isinstance(value, str) and re.match(r"^[A-Za-z]:[\\/]", value):
        return "/mnt/"+value[0].lower()+value[2:].replace("\\", "/")
    return value


original = ROOT/"data/catalog.json"
catalog = native(json.loads(original.read_text()))
directory = ROOT/"data/manifests/wsl"
directory.mkdir(parents=True, exist_ok=True)
for symbol, item in catalog["instruments"].items():
    descriptor = native(json.loads(Path(item["path"]).read_text()))
    for path, checksum in descriptor["file_hashes"].items():
        assert file_hash(path) == checksum
    translated = directory/f"{symbol}.dataset.json"
    json_write(translated, descriptor)
    item["path"] = str(translated)
json_write(directory/"catalog.json", catalog)
json_write(ROOT/"reports/wsl_catalog_verification.json", dict(passed=True,
    source_catalog_sha256=file_hash(original), translated_catalog=str(directory/"catalog.json"),
    transformation="Path strings only; training/validation content hashes verified; no test price columns read", raw_data_modified=False))
print(directory)

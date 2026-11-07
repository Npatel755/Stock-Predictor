"""Verify physical partition hashes, timestamps and counts without reading test prices."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from quant_futures.config import file_hash
from quant_futures.research import json_write

ROOT = Path(__file__).resolve().parents[1]
catalog = json.loads((ROOT/"data/catalog.json").read_text())
protocol = catalog["split_protocol"]
boundaries = [pd.Timestamp(protocol[key]).value for key in ("training_end_exclusive", "test_start_inclusive")]
verified = {}
for instrument, item in catalog["instruments"].items():
    prior = None
    total = 0
    parts = {}
    for role in ("train", "validation", "test"):
        manifest = item["splits"][role]
        path = Path(manifest["path"])
        assert file_hash(path) == manifest["dataset_version"], f"Hash changed: {path}"
        assert manifest["split_protocol_id"] == protocol["protocol_id"]
        count, first, last = 0, None, prior
        with pq.ParquetFile(path) as parquet:
            for batch in parquet.iter_batches(batch_size=100000, columns=["timestamp_utc"]):
                column = batch.column(0)
                assert column.null_count == 0
                times = column.cast("timestamp[ns]").cast("int64").to_numpy()
                assert np.all(np.diff(times) > 0), f"Duplicate or unordered timestamps in {path}"
                assert last is None or times[0] > last, f"Overlap in {path}"
                first = int(times[0]) if first is None else first
                last = int(times[-1])
                count += len(times)
        assert count == manifest["coverage"]["rows"] and count > 0
        assert first == pd.Timestamp(manifest["coverage"]["start"]).value
        assert last == pd.Timestamp(manifest["coverage"]["end"]).value
        if role == "train":
            assert last < boundaries[0]
        elif role == "validation":
            assert first >= boundaries[0] and last < boundaries[1]
        else:
            assert first >= boundaries[1]
        parts[role] = dict(rows=count, sha256=manifest["dataset_version"], timestamps_strictly_increasing=True)
        prior, total = last, total+count
    assert total == item["coverage"]["rows"], f"Row count changed: {instrument}"
    development = json.loads(Path(item["path"]).read_text())
    assert development["files"] == [item["splits"][r]["path"] for r in ("train", "validation")]
    verified[instrument] = dict(total_rows=total, partitions=parts, overlap=False)
result = dict(passed=True, split_protocol_id=protocol["protocol_id"], catalog_sha256=file_hash(ROOT/"data/catalog.json"),
    instruments=verified, test_price_columns_read=False, market_holdout_evaluated=False)
json_write(ROOT/"reports/split_verification.json", result)
print(json.dumps(result, indent=2))

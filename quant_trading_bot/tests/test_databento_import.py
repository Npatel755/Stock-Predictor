import hashlib
import json
import zipfile
import numpy as np
import pandas as pd
import pytest
from quant_futures.databento_import import canonical_symbol, normalize_chunk, verify_archive, PARQUET_SCHEMA


def test_decade_resolution_and_spread_exclusion():
    assert canonical_symbol("ESH0", 2019) == ("ES", "ESH20")
    assert canonical_symbol("ESM0", 2010) == ("ES", "ESM10")
    assert canonical_symbol("MNQZ6", 2026) == ("MNQ", "MNQZ26")
    assert canonical_symbol("ESM6-ESU6", 2026) is None


def test_normalize_preserves_raw_prices_and_null_quotes():
    b = pd.DataFrame(dict(instrument_id=[12, 13, 14], publisher_id=1,
        open=[6000., 22000., -5.], high=[6001., 22001., -4.], low=[5999., 21999., -6.],
        close=[6000.5, 22000.5, -5.], volume=[5, 8, 2], symbol=["MESZ6", "NQZ6", "ESM6-ESU6"]),
        index=pd.DatetimeIndex(["2026-11-02T10:00Z"]*3, name="ts_event"))
    out, excluded, issues = normalize_chunk(b)
    assert out.contract.tolist() == ["MESZ26", "NQZ26"]
    assert out.close.tolist() == [6000.5, 22000.5]
    assert out.bid.isna().all() and out.ask.isna().all()
    assert sum(excluded.values()) == 1 and not sum(issues.values())
    import pyarrow as pa
    table = pa.Table.from_pandas(out[PARQUET_SCHEMA.names], schema=PARQUET_SCHEMA, preserve_index=False)
    assert table.num_rows == 2


def test_archive_manifest_mismatch_rejected(tmp_path):
    path = tmp_path/"archive.zip"
    manifest = dict(job_id="test", files=[dict(filename="payload", size=3, hash="sha256:"+hashlib.sha256(b"abc").hexdigest())])
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("payload", b"bad")
    with zipfile.ZipFile(path) as z:
        with pytest.raises(ValueError, match="checksum"):
            verify_archive(z)

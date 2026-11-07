"""Download public evaluation samples, without converting anonymous continuous prices into tradable contracts."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import io
import zipfile
import numpy as np
import pandas as pd
import requests
from quant_futures.research import json_write

ROOT = Path(__file__).resolve().parents[1]
directory = ROOT/"data/raw/provider_samples"
directory.mkdir(parents=True, exist_ok=True)
results = []
for instrument in ("MES", "MNQ"):
    url = f"https://frd001.s3.us-east-2.amazonaws.com/frd_sample_futures_{instrument}.zip"
    path = directory/f"{instrument}_public_sample.zip"
    if path.exists():
        content = path.read_bytes()
    else:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 2*1024*1024:
                raise ValueError("Public sample exceeds 2MB download budget")
            chunks.append(chunk)
        content = b"".join(chunks)
        with open(path, "xb") as f:
            f.write(content)
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        name = f"{instrument}_1min_sample.csv"
        if z.getinfo(name).file_size > 4*1024*1024:
            raise ValueError("Expanded sample exceeds budget")
        b = pd.read_csv(io.BytesIO(z.read(name)))
        times = pd.DatetimeIndex(pd.to_datetime(b.timestamp)).tz_localize("America/New_York", ambiguous="raise", nonexistent="raise").tz_convert("UTC")
        p = b[["open", "high", "low", "close"]]
        results.append(dict(instrument=instrument, url=url, accessed_at=datetime.now(timezone.utc).isoformat(),
            sha256=hashlib.sha256(content).hexdigest(), zip_bytes=len(content), rows=len(b),
            start=str(times.min()), end=str(times.max()), columns=list(b.columns),
            duplicates=int(times.duplicated().sum()), invalid_ohlc=int(((b.high < p.max(axis=1)) | (b.low > p.min(axis=1))).sum()),
            zero_volume=int((b.volume == 0).sum()), gaps_over_one_minute=int((times[1:]-times[:-1] > pd.Timedelta(minutes=1)).sum()),
            quote_data_present=False, explicit_contract_identity_present="contract" in b.columns,
            eligible_for_tradable_backtest=False,
            blocking_reason="Continuous sample has no explicit contract or adjustment provenance; do not infer raw execution prices",
            license_url="https://firstratedata.com/about/license", cost_paid_usd=0,
            readme=z.read("_readme_documentation.txt").decode("utf-8-sig")))
json_write(ROOT/"reports/provider_sample_audit.json", results)
print([{k: r[k] for k in ("instrument", "rows", "start", "end", "eligible_for_tradable_backtest")} for r in results])

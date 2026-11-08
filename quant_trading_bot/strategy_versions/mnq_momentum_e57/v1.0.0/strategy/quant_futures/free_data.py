"""Public evaluation downloads with explicit contract/adjustment evidence.

Only the provider's advertised anonymous latest-month sample and public roll
ledger are requested. Authentication errors stop the request; no paid paths,
registration, token scraping or access-control workarounds are used.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import io
import json
import re
import numpy as np
import pandas as pd
import requests
from .data import canonical, validate
from .config import file_hash

BASE = "https://historicalfuturesdata.com"
DOCS = BASE+"/docs"


def public_bytes(url, limit=8*1024*1024):
    response = requests.get(url, timeout=30, stream=True)
    response.raise_for_status()
    chunks, total = [], 0
    for chunk in response.iter_content(65536):
        total += len(chunk)
        if total > limit:
            raise ValueError("Public sample exceeds configured download budget")
        chunks.append(chunk)
    return b"".join(chunks)


def raw_anchor_sample(sample, ledger, instrument):
    """Accept only the zero-adjustment terminal segment, never guess a contract.

    Provider docs define price=raw+adjustment. The public ledger identifies the
    anchor, adjustment, last retained trade and roll switch. This checks all four.
    It is not a claim that upstream licensing or exchange capture is independently audited.
    """
    b = sample.copy()
    b["ts"] = pd.to_datetime(b.ts, utc=True)
    if b.empty or b.ts.duplicated().any() or not b.ts.is_monotonic_increasing:
        raise ValueError("Public sample timestamps invalid")
    anchor = ledger["anchor_contract"]
    if not re.fullmatch(instrument+r"[HMUZ]\d{2}-CME", anchor):
        raise ValueError("Unsupported explicit ledger contract")
    if ledger["adjustments"].get(anchor) != 0:
        raise ValueError("Latest sample is adjusted; raw execution prices cannot be inferred")
    last_roll = ledger["rolls"][-1]
    if last_roll["to_contract"] != anchor or b.ts.min() < pd.Timestamp(last_roll["switch_utc"]):
        raise ValueError("Sample crosses a roll or does not match the anchor")
    if b.ts.max() != pd.Timestamp(ledger["last_utc"]).floor("10s"):
        raise ValueError("Sample and ledger terminal timestamps differ")
    if b.ts.max()+pd.Timedelta(seconds=10) > pd.Timestamp(ledger["as_of_utc"]):
        raise ValueError("Sample includes an unfinished or future bucket")
    if (b.ts.dt.floor("10s") != b.ts).any():
        raise ValueError("Ten-second sample alignment invalid")
    for column in ("open", "high", "low", "close"):
        if not np.isfinite(b[column]).all() or (b[column] <= 0).any():
            raise ValueError("Invalid public sample prices")
    # No missing price bucket is filled. Sparse buckets stay disclosed in metadata.
    out = b.set_index("ts").resample("1min", closed="left", label="left").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"), source_buckets=("close", "count"))
    available_until = b.ts.max()+pd.Timedelta(seconds=10)
    out = out[(out.source_buckets > 0) & (out.index+pd.Timedelta(minutes=1) <= available_until)]
    out["instrument"], out["contract"] = instrument, anchor.removesuffix("-CME")
    out = out.reset_index().rename(columns={"ts": "timestamp_utc"})
    return canonical(out)


def acquire_public_samples(output_directory, period="2026-11"):
    from .research import json_write
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=False)
    if not re.fullmatch(r"20\d{2}-\d{2}", period):
        raise ValueError("Invalid sample period")
    report = []
    for instrument in ("MES", "MNQ"):
        url = f"{BASE}/samples/{instrument}/10s/cme.{instrument.lower()}.bars.10s.{period}.parquet"
        ledger_url = f"{BASE}/{instrument}/rolls/{instrument}_rolls.json"
        sample_bytes, ledger_bytes = public_bytes(url), public_bytes(ledger_url, 1024*1024)
        (output/f"{instrument}_public_10s.parquet").write_bytes(sample_bytes)
        (output/f"{instrument}_rolls.json").write_bytes(ledger_bytes)
        ledger = json.loads(ledger_bytes)
        bars = raw_anchor_sample(pd.read_parquet(io.BytesIO(sample_bytes)), ledger, instrument)
        bars, quality = validate(bars)
        if quality["fatal"]:
            raise ValueError(f"{instrument} sample failed quality checks")
        path = output/f"{instrument}_1m.parquet"
        bars.to_parquet(path, index=False)
        manifest = dict(dataset_version=file_hash(path), synthetic=False, raw_contract_prices=True,
            provider="Historical Futures Data public latest-month evaluation sample", license_note="Provider explicitly offers anonymous sample downloads for testing; private local research only. Upstream redistribution entitlement not independently verified.",
            license_verified=False, timestamp_semantics="bar_open", path=path.name,
            source_url=url, roll_ledger_url=ledger_url, methodology_url=DOCS,
            accessed_at=datetime.now(timezone.utc).isoformat(),
            sample_sha256=hashlib.sha256(sample_bytes).hexdigest(), ledger_sha256=hashlib.sha256(ledger_bytes).hexdigest(),
            contract=ledger["anchor_contract"], adjustment=0, adjustment_as_of=ledger["as_of_utc"],
            provenance="Terminal timestamps match; documented zero-adjustment anchor segment only. No exchange-level audit or release-manifest cryptographic binding claimed.",
            price_basis="raw via zero additive adjustment", coverage=quality,
            sparse_minutes=int((bars.source_buckets < 6).sum()),
            cost_paid_usd=0, capture_clock="Provider documents feed-receive timestamps; not independently verified exchange-event timestamps",
            institutional_quality_verified=False)
        json_write(path.with_suffix(".manifest.json"), manifest)
        json_write(path.with_suffix(".quality.json"), quality)
        report.append(manifest)
    json_write(output/"acquisition_report.json", report)
    return report

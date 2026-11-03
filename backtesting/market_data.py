"""Public Binance ETH perpetual archives, UTC validation, Parquet and quality audit."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
import requests

from .eth_research.data import validate_bars
from .eth_research.perpetual_data import BASE, COLUMNS, TICKER, download
from .paths import DATA, PARQUET

LOG = logging.getLogger(__name__)
BAR = pd.Timedelta(minutes=5)


def utc(value: str | pd.Timestamp) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def clean_candles(raw: pd.DataFrame, start=None, end=None) -> tuple[pd.DataFrame, dict]:
    frame = raw.copy()
    required = {"timestamp", "exchange_close_time", "ticker", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        raise ValueError("Missing required exchange candle columns: " + ", ".join(sorted(required - set(frame.columns))))
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    frame["exchange_close_time"] = pd.to_datetime(frame.exchange_close_time, utc=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    out_of_order = not frame.timestamp.is_monotonic_increasing
    before = len(frame)
    frame = frame.drop_duplicates()
    removed = before - len(frame)
    if frame.timestamp.duplicated().any():
        raise ValueError("Conflicting candles at the same exchange open timestamp")
    frame = validate_bars(frame, expected_ticker=TICKER)
    if start is not None:
        frame = frame[frame.timestamp >= utc(start)]
    if end is not None:
        frame = frame[frame.timestamp + BAR <= utc(end)]
    if frame.empty:
        raise ValueError("No completed perpetual candles in requested range")
    frame = frame.reset_index(drop=True)
    frame["available_at"] = frame.timestamp + BAR
    if "exchange_close_time" not in frame:
        raise ValueError("Original exchange close timestamps are required")
    frame["exchange_close_time"] = pd.to_datetime(frame.exchange_close_time, utc=True)
    if not ((frame.exchange_close_time >= frame.timestamp) & (frame.exchange_close_time < frame.available_at)).all():
        raise ValueError("Exchange close timestamps fall outside their five-minute candles")
    differences = frame.timestamp.diff()
    gaps = []
    for i in np.flatnonzero(differences.gt(BAR)):
        gaps.append({"start": str(frame.timestamp.iloc[i - 1] + BAR), "end_exclusive": str(frame.timestamp.iloc[i]),
                     "missing_bars": int(differences.iloc[i] / BAR) - 1})
    if start is not None and frame.timestamp.iloc[0] > utc(start):
        gaps.insert(0, {"start": str(utc(start)), "end_exclusive": str(frame.timestamp.iloc[0]),
                        "missing_bars": int((frame.timestamp.iloc[0] - utc(start)) / BAR)})
    if end is not None and frame.available_at.iloc[-1] < utc(end):
        gaps.append({"start": str(frame.available_at.iloc[-1]), "end_exclusive": str(utc(end)),
                     "missing_bars": int((utc(end) - frame.available_at.iloc[-1]) / BAR)})
    quality = {"instrument": TICKER, "rows": len(frame), "first_open_utc": str(frame.timestamp.iloc[0]),
               "last_close_exclusive_utc": str(frame.available_at.iloc[-1]), "true_duplicates_removed": removed,
               "out_of_order_input": out_of_order, "gaps": gaps,
               "missing_bars": sum(g["missing_bars"] for g in gaps), "zero_volume_bars": int(frame.volume.eq(0).sum()),
               "timestamp_rule": "exchange open unchanged; exchange close preserved; availability=open+5min"}
    return frame, quality


def read_archive(session, period: str, frequency: str, directory: Path):
    path = directory / f"ETHUSDT-5m-{period}.zip"
    checksum_path = path.with_name(path.name + ".CHECKSUM")
    if path.exists() and checksum_path.exists():
        payload, checksum = path.read_bytes(), checksum_path.read_text(encoding="utf-8")
    else:
        url = f"{BASE}/{frequency}/klines/ETHUSDT/5m/{path.name}"
        payload = download(session, url, optional=True)
        if payload is None:
            return None
        checksum = download(session, url + ".CHECKSUM").decode("utf-8")
    if hashlib.sha256(payload).hexdigest() != checksum.split()[0]:
        raise ValueError(f"Checksum mismatch for {path.name}")
    if not path.exists():
        path.write_bytes(payload)
        checksum_path.write_text(checksum, encoding="utf-8")
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        files = [item for item in z.infolist() if item.filename.endswith(".csv")]
        if len(files) != 1 or files[0].file_size > 20_000_000:
            raise ValueError("Unexpected archive CSV contents")
        content = z.read(files[0])
    first = next(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    if len(first) != len(COLUMNS):
        raise ValueError("Binance kline CSV must have exactly 12 columns")
    try:
        int(first[0])
        header = None
    except ValueError:
        normalized = ["trades" if name.strip() == "count" else name.strip() for name in first]
        if normalized != COLUMNS:
            raise ValueError("Unexpected Binance kline CSV header names/order")
        header = 0
    raw = pd.read_csv(io.BytesIO(content), header=header, names=COLUMNS)
    for column in COLUMNS:
        raw[column] = pd.to_numeric(raw[column], errors="raise")
    if raw.isna().any().any() or raw.empty:
        raise ValueError("Archive contains missing candle fields")
    if not raw.open_time.mod(1).eq(0).all() or not raw.close_time.mod(1).eq(0).all():
        raise ValueError("Exchange timestamps must be integer epoch values")
    unit = "us" if raw.open_time.max() > 10**15 else "ms"
    opens = pd.to_datetime(raw.open_time.astype("int64"), unit=unit, utc=True)
    closes = pd.to_datetime(pd.to_numeric(raw.close_time, errors="raise").astype("int64"), unit=unit, utc=True)
    result = raw[["open", "high", "low", "close", "volume"]].copy()
    result.insert(0, "timestamp", opens)
    result.insert(1, "ticker", TICKER)
    result["exchange_close_time"] = closes
    # Preserve source ordering/duplicates until clean_candles can report them.
    return result


def download_history(start="2023-01-01", end=None, directory=DATA) -> tuple[Path, dict]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    start = utc(start)
    end = utc(end) if end is not None else pd.Timestamp.now(tz="UTC").floor("D")
    if start != start.floor("D") or end != end.floor("D") or not start < end <= pd.Timestamp.now(tz="UTC").floor("D"):
        raise ValueError("Use completed UTC days; end is exclusive")
    cursor, chunks, missing_archives, manifest = start.replace(day=1), [], [], []
    with requests.Session() as session:
        while cursor < end:
            month_end = cursor + pd.offsets.MonthBegin(1)
            period = cursor.strftime("%Y-%m")
            part = read_archive(session, period, "monthly", directory) if month_end <= end else None
            if part is not None:
                chunks.append(part)
                manifest.append({"period": period, "frequency": "monthly"})
                # Repair whole absent UTC days from daily archives when available.
                available_days = set(part.timestamp.dt.floor("D"))
                days = pd.date_range(max(cursor, start), min(month_end, end), inclusive="left", freq="D")
                missing_days = [day for day in days if day not in available_days]
            else:
                missing_days = pd.date_range(max(cursor, start), min(month_end, end), inclusive="left", freq="D")
            for day in missing_days:
                daily = read_archive(session, day.strftime("%Y-%m-%d"), "daily", directory)
                if daily is None:
                    missing_archives.append(str(day.date()))
                else:
                    chunks.append(daily)
                    manifest.append({"period": str(day.date()), "frequency": "daily"})
            LOG.info("ETH perpetual %s loaded (%s)", period, "monthly/cache" if part is not None else "daily")
            cursor = month_end
    if not chunks:
        raise ValueError("No public archives were available")
    frame, quality = clean_candles(pd.concat(chunks, ignore_index=True), start, end)
    quality.update(requested_start=str(start), requested_end_exclusive=str(end), missing_archives=missing_archives,
                   archives=manifest, downloaded_at_utc=str(pd.Timestamp.now(tz="UTC")))
    output = directory / "candles.parquet"
    temporary = directory / "candles.pending.parquet"
    frame.to_parquet(temporary, index=False)
    temporary.replace(output)
    quality["parquet_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    LOG.info("Saved %s candles; %s missing bars to %s", len(frame), quality["missing_bars"], output)
    return output, quality


def load_history(path=PARQUET):
    path = Path(path)
    raw = pd.read_parquet(path)
    frame, quality = clean_candles(raw)
    sidecar = path.with_suffix(".quality.json")
    if sidecar.exists():
        original = json.loads(sidecar.read_text(encoding="utf-8"))
        if original.get("parquet_sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError("Parquet data changed after its quality audit")
        quality = original
    return frame, quality


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", help="Exclusive UTC day; defaults to current UTC day")
    args = parser.parse_args()
    download_history(args.start, args.end)

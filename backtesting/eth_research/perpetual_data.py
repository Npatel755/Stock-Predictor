"""Checksum-verified Binance ETHUSDT perpetual five-minute public archives."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import time
import zipfile

import pandas as pd
import requests

from .data import ROOT, validate_bars, write_csv_atomic

TICKER = "BINANCE:ETHUSDT.P"
SOURCE = "Binance USD-M ETHUSDT perpetual futures official public archives; ETH-only, proxy for Breakout ETHUSD execution"
BASE = "https://data.binance.vision/data/futures/um"
COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
           "trades", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


def download(session, url, optional=False):
    for attempt in range(5):
        try:
            response = session.get(url, timeout=45)
            if optional and response.status_code == 404:
                return None
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(min(15, 2 ** attempt))
                continue
            response.raise_for_status()
            return response.content
        except requests.RequestException:
            if attempt == 4:
                raise RuntimeError(f"Binance archive download failed: {url}") from None
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Binance repeatedly rejected archive: {url}")


def archive(session, period, frequency, directory):
    name = f"ETHUSDT-5m-{period}.zip"
    url = f"{BASE}/{frequency}/klines/ETHUSDT/5m/{name}"
    cache = directory / name
    checksum_path = directory / (name + ".CHECKSUM")
    if cache.exists() and checksum_path.exists():
        payload, checksum = cache.read_bytes(), checksum_path.read_text(encoding="utf-8")
    else:
        payload = download(session, url, optional=True)
        if payload is None:
            return None
        checksum = download(session, url + ".CHECKSUM").decode("utf-8")
    if hashlib.sha256(payload).hexdigest() != checksum.split()[0]:
        raise ValueError(f"Checksum mismatch for {name}")
    cache.write_bytes(payload)
    checksum_path.write_text(checksum, encoding="utf-8")
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        files = [item for item in z.infolist() if item.filename.endswith(".csv")]
        if len(files) != 1 or files[0].file_size > 20_000_000:
            raise ValueError("Unexpected Binance archive contents")
        # Read in memory; never extract paths from the archive.
        frame = pd.read_csv(z.open(files[0]), header=None, names=COLUMNS)
    frame["open_time"] = pd.to_numeric(frame.open_time, errors="coerce")
    frame = frame.dropna(subset=["open_time"])
    unit = "us" if frame.open_time.max() > 10**15 else "ms"
    frame["timestamp"] = pd.to_datetime(frame.open_time.astype("int64"), unit=unit, utc=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame["ticker"] = TICKER
    return validate_bars(frame[["timestamp", "ticker", "open", "high", "low", "close", "volume"]], expected_ticker=TICKER)


def fetch(start, end, directory=ROOT / "data/ethusd/perpetual"):
    start, end = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    if start >= end or end > pd.Timestamp.now(tz="UTC").floor("D"):
        raise ValueError("Use completed historical UTC days with end exclusive")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    cursor = start.replace(day=1)
    chunks, manifest = [], []
    while cursor < end:
        month_end = cursor + pd.offsets.MonthBegin(1)
        period = cursor.strftime("%Y-%m")
        part = archive(session, period, "monthly", directory) if month_end <= end else None
        if part is not None:
            chunks.append(part)
            manifest.append({"frequency": "monthly", "period": period})
            print(f"Binance ETH perpetual {period}: {len(part)} bars (checksum verified)", flush=True)
        else:
            day = max(cursor, start)
            while day < min(month_end, end):
                part = archive(session, day.strftime("%Y-%m-%d"), "daily", directory)
                if part is None:
                    raise ValueError(f"Missing Binance daily archive: {day.date()}")
                chunks.append(part)
                manifest.append({"frequency": "daily", "period": day.strftime("%Y-%m-%d")})
                day += pd.Timedelta(days=1)
        cursor = month_end
    frame = validate_bars(pd.concat(chunks, ignore_index=True), str(start.date()), str(end.date()), expected_ticker=TICKER)
    path = directory / "bars.csv"
    write_csv_atomic(frame, path)
    metadata = {"ticker": TICKER, "source": SOURCE, "resolution": "5min", "start_inclusive": str(start),
                "end_exclusive": str(end), "rows": len(frame), "archives": manifest,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "missing_five_minute_intervals": int(frame.timestamp.diff().gt(pd.Timedelta(minutes=5)).sum())}
    path.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved {len(frame):,} ETH perpetual bars to {path}", flush=True)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True, help="Exclusive UTC date")
    parser.add_argument("--directory", type=Path, default=ROOT / "data/ethusd/perpetual")
    args = parser.parse_args()
    fetch(args.start, args.end, args.directory)

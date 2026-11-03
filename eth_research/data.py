"""Read-only Massive ETH/USD crypto aggregates, explicitly a Breakout proxy."""
import argparse
import hashlib
import json
import os
import time
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TICKER = "X:ETHUSD"
SOURCE = "Massive consolidated ETH/USD crypto trades; proxy for Breakout ETHUSD, not futures or Breakout fills"
BAR_MINUTES = 5


def write_csv_atomic(frame, path):
    """Readers see either the old complete CSV or the new complete CSV."""
    path = Path(path)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent,
                                         suffix=".tmp", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            frame.to_csv(temporary, index=False)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


class MassiveClient:
    def __init__(self, min_interval=12.5):
        load_dotenv(ROOT / ".env")
        key = os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")
        if not key:
            raise ValueError("Configure MASSIVE_API_KEY in .env")
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {key}"
        self.min_interval = min_interval
        self.last_request = 0.0

    def pages(self, path, params):
        url = "https://api.massive.com" + path
        seen = set()
        while url:
            # Never forward credentials to an untrusted pagination origin.
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.netloc != "api.massive.com":
                raise ValueError("Unexpected Massive pagination origin")
            if url in seen:
                raise RuntimeError("Repeated Massive pagination cursor")
            seen.add(url)
            for attempt in range(6):
                time.sleep(max(0, self.min_interval - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
                try:
                    response = self.session.get(url, params=params, timeout=45, allow_redirects=False)
                except requests.RequestException:
                    if attempt == 5:
                        raise RuntimeError("Massive connection failed; check network access") from None
                    time.sleep(2 ** attempt)
                    continue
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == 5:
                        raise RuntimeError(f"Massive repeatedly returned HTTP {response.status_code}")
                    time.sleep(min(60, max(2 ** attempt, float(response.headers.get("Retry-After", 15)))))
                    continue
                if response.status_code != 200:
                    raise RuntimeError(f"Massive HTTP {response.status_code}; check crypto entitlement and date range")
                payload = response.json()
                if payload.get("status") in {"ERROR", "NOT_AUTHORIZED"}:
                    raise RuntimeError("Massive rejected the data request")
                break
            yield payload.get("results", [])
            url = payload.get("next_url")
            params = None


def validate_bars(frame, start=None, end=None, expected_ticker=TICKER):
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    if not set(required).issubset(frame.columns):
        raise ValueError("Missing ETHUSD OHLCV columns")
    frame = frame.copy()
    if "ticker" in frame and not frame["ticker"].eq(expected_ticker).all():
        raise ValueError(f"Only {expected_ticker} data is allowed")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    if frame["timestamp"].duplicated().any():
        raise ValueError("Duplicate ETHUSD timestamps")
    if (frame.timestamp.dt.minute.mod(BAR_MINUTES).ne(0) | frame.timestamp.dt.second.ne(0)).any():
        raise ValueError("Bars must align to five-minute boundaries")
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError("Invalid OHLCV values")
    if ((frame.high < frame[["open", "close", "low"]].max(axis=1)) |
            (frame.low > frame[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("Inconsistent OHLC bar")
    if start is not None:
        frame = frame[frame.timestamp >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        frame = frame[frame.timestamp + pd.Timedelta(minutes=BAR_MINUTES) <= pd.Timestamp(end, tz="UTC")]
    if frame.empty:
        raise ValueError("No completed ETHUSD bars returned")
    return frame.reset_index(drop=True)


def fetch(start, end, directory=ROOT / "data/ethusd", min_interval=12.5):
    start, end = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    if start >= end or end > pd.Timestamp.now(tz="UTC").floor("h"):
        raise ValueError("Use an increasing historical date range with end exclusive")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    client = MassiveClient(min_interval)
    chunks = []
    cursor = start
    while cursor < end:
        stop = min(cursor + pd.Timedelta(days=28), end)
        cache = directory / f"5min_{cursor:%Y%m%d}_{stop:%Y%m%d}.csv"
        if cache.exists():
            part = pd.read_csv(cache)
        else:
            rows = []
            path = f"/v2/aggs/ticker/{TICKER}/range/5/minute/{int(cursor.timestamp()*1000)}/{int(stop.timestamp()*1000)-1}"
            for page in client.pages(path, {"sort": "asc", "limit": 50000}):
                rows.extend(page)
            part = pd.DataFrame(rows).rename(columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
            if part.empty:
                raise ValueError(f"No Massive ETHUSD data for {cursor.date()} through {stop.date()}")
            part["timestamp"] = pd.to_datetime(part.timestamp, unit="ms", utc=True)
            part["ticker"] = TICKER
            part = validate_bars(part)
            write_csv_atomic(part, cache)
        chunks.append(part)
        print(f"ETHUSD {cursor.date()} through {stop.date()}: {len(part)} five-minute bars", flush=True)
        cursor = stop
    frame = validate_bars(pd.concat(chunks, ignore_index=True), str(start.date()), str(end.date()))
    path = directory / "bars.csv"
    write_csv_atomic(frame, path)
    metadata = {"ticker": TICKER, "source": SOURCE, "resolution": "5min", "start_inclusive": str(start),
                "end_exclusive": str(end), "rows": len(frame), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "missing_five_minute_intervals": int(frame.timestamp.diff().gt(pd.Timedelta(minutes=BAR_MINUTES)).sum())}
    path.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True, help="Exclusive UTC date; only complete five-minute bars")
    parser.add_argument("--directory", type=Path, default=ROOT / "data/ethusd")
    parser.add_argument("--min-interval", type=float, default=12.5)
    args = parser.parse_args()
    print(fetch(args.start, args.end, args.directory, args.min_interval))

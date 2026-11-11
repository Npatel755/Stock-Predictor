"""Free 1-minute spot gold (XAU/USD BID candles) from Dukascopy's public datafeed, weekdays 2010-06-01 .. 2023-12-31 (TRAINING years only).
Claude, 2026-11-10 (Nick: "you can probably find free data too"). Raw .bi5 files are kept so nothing is downloaded twice; they are parsed as
data only (LZMA + fixed 24-byte big-endian records: seconds from 00:00 UTC, open, close, low, high as price x 1000, volume float).
Polite: one request at a time, ~4 per second, 3 retries. Output: data/external/dukascopy_xauusd/xauusd_1m_2010_2023.parquet (UTC index).
"""
import lzma, struct, time, urllib.request
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/external/dukascopy_xauusd"; RAW = OUT / "raw"; RAW.mkdir(parents=True, exist_ok=True)
URL = "https://datafeed.dukascopy.com/datafeed/XAUUSD/{y}/{m:02d}/{d:02d}/BID_candles_min_1.bi5"


def fetch(day):
    f = RAW / f"{day:%Y-%m-%d}.bi5"
    if f.exists(): return f.read_bytes()
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL.format(y=day.year, m=day.month - 1, d=day.day), headers={"User-Agent": "personal-research/1.0"})
            b = urllib.request.urlopen(req, timeout=30).read(); f.write_bytes(b); time.sleep(0.25); return b
        except urllib.error.HTTPError as e:
            if e.code == 404: f.write_bytes(b""); return b""
            time.sleep(3 * (attempt + 1))
        except Exception:
            time.sleep(3 * (attempt + 1))
    return None


def parse(day, b):
    if not b: return None
    data = lzma.decompress(b); n = len(data) // 24
    rec = [struct.unpack(">5if", data[i * 24:(i + 1) * 24]) for i in range(n)]
    df = pd.DataFrame(rec, columns=["sec", "open", "close", "low", "high", "volume"])
    df.index = pd.Timestamp(day, tz="UTC") + pd.to_timedelta(df.sec, unit="s")
    for c in ("open", "close", "low", "high"): df[c] = df[c] / 1000.0
    return df[["open", "high", "low", "close", "volume"]]


def main():
    days = [d for d in pd.date_range("2010-06-01", "2023-12-31") if d.dayofweek < 5]
    frames, missing = [], []
    for k, d in enumerate(days):
        b = fetch(d)
        if b is None: missing.append(str(d.date())); continue
        p = parse(d, b)
        if p is not None and len(p): frames.append(p[p.volume > 0])
        if k % 250 == 0: print(f"{d.date()} {k}/{len(days)}", flush=True)
    df = pd.concat(frames).sort_index(); df = df[~df.index.duplicated()]
    assert df.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
    df.to_parquet(OUT / "xauusd_1m_2010_2023.parquet")
    print(f"done: {len(df):,} minutes with volume, {df.index.min()} .. {df.index.max()}, failed days {len(missing)} {missing[:10]}", flush=True)


if __name__ == "__main__":
    main()

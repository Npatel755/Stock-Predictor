"""Free 1-minute spot gold (XAU/USD) from HistData.com yearly ASCII files, 2010-2023 (TRAINING years only). Claude, 2026-11-10.
Replaces the Dukascopy daily feed, which started answering HTTP 503 (throttling) after ~60 days. 14 form submissions (the site's own download
button), 3 s apart. Each zip is read in memory (member CSV only; nothing extracted or executed). HistData timestamps are New York time with
daylight saving (verified against CME GC hourly bars; the site says EST without DST, which did not match). Output: data/external/histdata_xauusd/xauusd_1m_2010_2023.parquet (UTC index, OHLC, volume).
"""
import io, re, time, urllib.parse, urllib.request, zipfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/external/histdata_xauusd"; RAW = OUT / "raw"; RAW.mkdir(parents=True, exist_ok=True)
PAGE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/xauusd/{y}"
UA = {"User-Agent": "Mozilla/5.0 (personal research)"}


def fetch_year(y):
    f = RAW / f"HISTDATA_XAUUSD_M1_{y}.zip"
    if f.exists() and f.stat().st_size > 1000: return f.read_bytes()
    page = PAGE.format(y=y)
    html = urllib.request.urlopen(urllib.request.Request(page, headers=UA), timeout=60).read().decode("utf-8", "ignore")
    form = {k: re.search(rf'id="{k}"[^>]*value="([^"]*)"', html).group(1) for k in ("tk", "date", "datemonth", "platform", "timeframe", "fxpair")}
    req = urllib.request.Request("https://www.histdata.com/get.php", data=urllib.parse.urlencode(form).encode(), headers=dict(UA, Referer=page))
    b = urllib.request.urlopen(req, timeout=120).read()
    assert b[:2] == b"PK", f"{y}: not a zip ({len(b)} bytes)"
    f.write_bytes(b); time.sleep(3); return b


def parse(b, y):
    z = zipfile.ZipFile(io.BytesIO(b)); name = next(n for n in z.namelist() if n.lower().endswith(".csv") and "/" not in n and ".." not in n)
    df = pd.read_csv(io.BytesIO(z.read(name)), sep=";", header=None, names=["dt", "open", "high", "low", "close", "volume"])
    ts = pd.to_datetime(df.dt, format="%Y%m%d %H%M%S")
    # Checked against CME GC hourly bars: the clock is New York time WITH daylight saving (not fixed EST as first assumed).
    df.index = pd.DatetimeIndex(ts).tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    return df[df.index.notna()][["open", "high", "low", "close", "volume"]]


def main():
    frames = []
    for y in range(2010, 2024):
        b = fetch_year(y); p = parse(b, y); frames.append(p)
        print(f"{y}: {len(p):,} minutes {p.index.min()} .. {p.index.max()}", flush=True)
    df = pd.concat(frames).sort_index(); df = df[~df.index.duplicated()]
    df = df[(df.index >= pd.Timestamp("2010-06-01", tz="UTC")) & (df.index < pd.Timestamp("2024-01-01", tz="UTC"))]
    df.to_parquet(OUT / "xauusd_1m_2010_2023.parquet"); print(f"done: {len(df):,} minutes {df.index.min()} .. {df.index.max()}")


if __name__ == "__main__":
    main()

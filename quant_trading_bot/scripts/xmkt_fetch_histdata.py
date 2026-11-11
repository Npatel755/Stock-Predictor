"""xmkt_fetch_histdata (Claude fork A, 2026-11-11): free 1-minute spot FX (bid) from HistData.com yearly ASCII files, 2010-2023 TRAINING years
only, for the CME micro FX futures Topstep permits (M6E = EUR/USD, M6A = AUD/USD, M6B = GBP/USD). Same form flow as fetch_histdata_xauusd.py
(the site's own download button, 3 s apart). Zips are read in memory (member CSV only; nothing extracted or executed). Raw timestamps are kept
as naive wall-clock (the clock convention is verified separately in xmkt_fx_train.py before any strategy result is used).
Output: data/external/xmkt_histdata/{pair}_1m_2010_2023.parquet (naive 'wall' timestamp column + OHLC). Run with `python -P`.
"""
import io, re, sys, time, urllib.parse, urllib.request, zipfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/external/xmkt_histdata"; RAW = OUT / "raw"; RAW.mkdir(parents=True, exist_ok=True)
PAGE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{p}/{y}"
UA = {"User-Agent": "Mozilla/5.0 (personal research)"}


def fetch_year(p, y):
    f = RAW / f"HISTDATA_{p.upper()}_M1_{y}.zip"
    if f.exists() and f.stat().st_size > 1000: return f.read_bytes()
    page = PAGE.format(p=p, y=y)
    html = urllib.request.urlopen(urllib.request.Request(page, headers=UA), timeout=60).read().decode("utf-8", "ignore")
    form = {k: re.search(rf'id="{k}"[^>]*value="([^"]*)"', html).group(1) for k in ("tk", "date", "datemonth", "platform", "timeframe", "fxpair")}
    req = urllib.request.Request("https://www.histdata.com/get.php", data=urllib.parse.urlencode(form).encode(), headers=dict(UA, Referer=page))
    b = urllib.request.urlopen(req, timeout=180).read()
    assert b[:2] == b"PK", f"{p} {y}: not a zip ({len(b)} bytes)"
    f.write_bytes(b); time.sleep(3); return b


def parse(b):
    z = zipfile.ZipFile(io.BytesIO(b)); name = next(n for n in z.namelist() if n.lower().endswith(".csv") and "/" not in n and ".." not in n)
    df = pd.read_csv(io.BytesIO(z.read(name)), sep=";", header=None, names=["dt", "open", "high", "low", "close", "volume"])
    df["wall"] = pd.to_datetime(df.dt, format="%Y%m%d %H%M%S")
    return df[["wall", "open", "high", "low", "close"]]


def main(pairs):
    for p in pairs:
        frames = []
        for y in range(2010, 2024):
            q = parse(fetch_year(p, y)); frames.append(q); print(f"{p} {y}: {len(q):,} minutes {q.wall.min()} .. {q.wall.max()}", flush=True)
        df = pd.concat(frames).drop_duplicates("wall").sort_values("wall")
        df = df[(df.wall >= pd.Timestamp("2010-01-01")) & (df.wall < pd.Timestamp("2023-12-31"))].reset_index(drop=True)
        df.to_parquet(OUT / f"{p}_1m_2010_2023.parquet"); print(f"{p} done: {len(df):,} minutes", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["eurusd", "audusd", "gbpusd"])

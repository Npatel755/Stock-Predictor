"""Decode Databento DBN (bbo-1s / bbo-1m) files to parquet with UTC timestamps and tick-scaled prices."""
import sys
from pathlib import Path
import databento as db
import pandas as pd

def decode(src: Path) -> Path:
    store = db.DBNStore.from_file(src)
    df = store.to_df(price_type="float", pretty_ts=True).reset_index()
    cols = ["ts_recv", "ts_event", "symbol", "price", "size", "side", "bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00", "sequence", "flags"]
    df = df[[c for c in cols if c in df.columns]]
    out = src.with_suffix("").with_suffix(".parquet")
    df.to_parquet(out, index=False)
    print(src.name, "->", out.name, len(df), "rows", df.ts_recv.min(), df.ts_recv.max())
    return out

if __name__ == "__main__":
    for a in sys.argv[1:]:
        decode(Path(a))

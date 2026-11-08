"""orderflow_2: chunked decode of the MNQ.c.0 trades DBN into 1-second signed-volume aggregates (UTC) + per-day size quantiles.
Columns: ts (1s floor), n, vol, buy_vol, sell_vol, none_vol, big_buy, big_sell (size>=10), last_px, vwap_num (sum px*size), hi, lo."""
import sys
from pathlib import Path
import databento as db, pandas as pd, numpy as np
src = Path(sys.argv[1]); out = src.with_suffix("").with_suffix(".sec.parquet"); qout = src.with_suffix("").with_suffix(".sizeq.parquet")
store = db.DBNStore.from_file(src); parts = []; sizes = []
for i, df in enumerate(store.to_df(price_type="float", pretty_ts=True, count=5_000_000)):
    df = df.reset_index(); df["size"] = df["size"].astype(float); df["price"] = df["price"].astype(float)
    ts = df.ts_event.dt.floor("1s"); side = df.side.astype(str)
    g = pd.DataFrame(dict(ts=ts, n=1.0, vol=df["size"], buy_vol=np.where(side == "B", df["size"], 0.0), sell_vol=np.where(side == "A", df["size"], 0.0),
                          none_vol=np.where(side == "N", df["size"], 0.0), big_buy=np.where((side == "B") & (df["size"] >= 10), df["size"], 0.0),
                          big_sell=np.where((side == "A") & (df["size"] >= 10), df["size"], 0.0), pxv=df.price * df["size"], hi=df.price, lo=df.price, last_px=df.price))
    agg = g.groupby("ts").agg(n=("n", "sum"), vol=("vol", "sum"), buy_vol=("buy_vol", "sum"), sell_vol=("sell_vol", "sum"), none_vol=("none_vol", "sum"),
                              big_buy=("big_buy", "sum"), big_sell=("big_sell", "sum"), pxv=("pxv", "sum"), hi=("hi", "max"), lo=("lo", "min"), last_px=("last_px", "last"))
    parts.append(agg); d = df.ts_event.dt.floor("D"); sizes.append(df.groupby(d)["size"].quantile([0.5, 0.9, 0.99]).unstack())
    print(i, len(df), df.ts_event.iloc[0], flush=True)
sec = pd.concat(parts)
sec = sec.groupby(level=0).agg(n=("n", "sum"), vol=("vol", "sum"), buy_vol=("buy_vol", "sum"), sell_vol=("sell_vol", "sum"), none_vol=("none_vol", "sum"),
                                big_buy=("big_buy", "sum"), big_sell=("big_sell", "sum"), pxv=("pxv", "sum"), hi=("hi", "max"), lo=("lo", "min"), last_px=("last_px", "last")).reset_index()
sec.to_parquet(out, index=False); pd.concat(sizes).groupby(level=0).mean().reset_index().to_parquet(qout, index=False)
print("rows", len(sec), sec.ts.min(), sec.ts.max(), "trades", sec.n.sum(), "side share none", sec.none_vol.sum() / sec.vol.sum(), flush=True)

import pandas as pd
from pathlib import Path

ROOT = Path(r"quant_trading_bot")
intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
ov_all = pd.read_parquet(ROOT / "data/processed/clean_multi_sleeve_trades_train.parquet")
ov = ov_all[ov_all.sleeve_key == "OVERNIGHT"].copy()

print("=== Analyzing Gap Continuation Subsets ===")
for sl in ["CRABEL15", "TRD30_D", "BRK30"]:
    sub = intra[intra.sleeve == sl]
    wr_all = (sub.net_today > 0).mean() * 100
    wr_gap = (sub[sub.is_gap_cont == True].net_today > 0).mean() * 100
    n_gap = (sub.is_gap_cont == True).sum()
    print(f"{sl:<10} | All WinRate: {wr_all:5.1f}% | GapCont WinRate: {wr_gap:5.1f}% (N={n_gap})")

print("\n=== Analyzing Directional Win Rates (Long vs Short) ===")
for sl, g in intra.groupby("sleeve"):
    for side in ["long", "short"]:
        sub = g[g.side == side]
        if len(sub) > 0:
            wr = (sub.net_today > 0).mean() * 100
            exp = sub.net_today.mean()
            print(f"{sl:<10} {side:<5} | N={len(sub):3d} | WinRate: {wr:5.1f}% | Exp: ${exp:5.1f}")

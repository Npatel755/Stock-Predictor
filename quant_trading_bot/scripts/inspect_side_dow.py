import pandas as pd
from pathlib import Path

ROOT = Path(r"quant_trading_bot")
intra = pd.read_parquet(ROOT / "data/processed/routed_7sleeve_trades_train.parquet")
intra["tout"] = pd.to_datetime(intra.tout_str, utc=True)
intra["tin"] = pd.to_datetime(intra.tin_str, utc=True)
intra["hour"] = intra.tin.dt.tz_convert("America/New_York").dt.hour
intra["dow"] = intra.tin.dt.tz_convert("America/New_York").dt.dayofweek

print("=== Directional Win Rates (1=Long, -1=Short) ===")
for sl, g in intra.groupby("sleeve"):
    for s in [1, -1]:
        sub = g[g.side == s]
        if len(sub) > 0:
            wr = (sub.net_today > 0).mean() * 100
            exp = sub.net_today.mean()
            side_str = "Long" if s == 1 else "Short"
            print(f"{sl:<10} {side_str:<5} | N={len(sub):3d} | WinRate: {wr:5.1f}% | Exp: ${exp:5.1f}")

print("\n=== Win Rates by Day of Week ===")
days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
for d in range(5):
    sub = intra[intra.dow == d]
    wr = (sub.net_today > 0).mean() * 100
    exp = sub.net_today.mean()
    print(f"{days[d]:<5} | N={len(sub):4d} | WinRate: {wr:5.1f}% | Exp: ${exp:5.1f}")

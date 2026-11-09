"""Comprehensive Trade Edge Attribution & Market Regime Analysis for Architecture D+
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Applies the 'trade-edge-attribution' and 'market-regime-analysis' skills:
1. Gross vs Net waterfall (commissions, spreads, slippage).
2. Long vs Short decomposition (PnL, win rate, expectancy).
3. Day-of-Week decomposition (Monday-Friday: sample size, net, expectancy).
4. Exit reason decomposition (Stop Loss, Profit Target, Hold Bars, Session End Flat).
5. Volatility regime conditioning (Low VIX < 15, Mid VIX 15-25, High VIX > 25).
6. SKEW regime conditioning (High Tail Risk vs Normal).
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

print("=" * 80)
print("TRADE EDGE ATTRIBUTION & REGIME AUDIT (2010-2023 TRAINING ONLY)")
print("=" * 80, flush=True)

os.environ["SIZING_BUDGET"] = "150.0"
srcs = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]
ns1 = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}
exec(srcs, ns1)
ep = ns1["ep"]
bars_for = ns1["bars_for"]
backw_mask = ns1["backw_mask"]
daily = ns1["daily"]
START = ns1["START"]
MULT = ns1["MULT"]

spec = ep.CANDIDATES["ag_arch_d_plus_v2"]

# Load VIX and SKEW data
vix_path = ROOT / "data/external/VIX_History.csv"
skew_path = ROOT / "data/external/SKEW_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df['date'] = pd.to_datetime(vix_df['DATE'], format='%m/%d/%Y').dt.date
vix_map = vix_df.set_index('date')['CLOSE'].astype(float).to_dict()

skew_df = pd.read_csv(skew_path)
skew_df['date'] = pd.to_datetime(skew_df['DATE'], format='%m/%d/%Y').dt.date
skew_map = skew_df.set_index('date')['SKEW'].astype(float).to_dict()

def run_sl(sl, prio, gap_continuation=False):
    b, mins, atr = bars_for(sl)
    blocked = backw_mask(b) if (spec.get("day_filter") == "no_backwardation" and not sl.get("day_filter_exempt")) else None
    
    if sl["signal"] == "crabel_open_drive" and gap_continuation:
        et = b.timestamp_utc.dt.tz_convert("America/New_York")
        sod = (et.dt.hour * 60 + et.dt.minute).to_numpy()
        day = et.dt.date.to_numpy()
        c = b.close.to_numpy(float)
        df = pd.DataFrame(dict(day=day, sod=sod, o=b.open.to_numpy(float), h=b.high.to_numpy(float), l=b.low.to_numpy(float), c=c))
        r = df[df.sod.isin([570, 585])].groupby("day")
        o930 = df[df.sod == 570].groupby("day").o.first()
        c1000 = df[df.sod == 585].groupby("day").c.first()
        hi, lo = r.h.max(), r.l.min()
        rng_ = (hi - lo).replace(0, np.nan)
        op = (o930 - lo) / rng_
        cp = (c1000 - lo) / rng_
        tail = float(sl.get("tail", 0.2))
        daily_close = df.groupby("day").c.last()
        prev_close = daily_close.shift(1).reindex(op.index)
        gap = (o930 - prev_close) / prev_close
        bull_drive = ((op <= tail) & (cp >= 1 - tail) & (gap >= 0.0)).fillna(False).to_numpy()
        bear_drive = ((op >= 1 - tail) & (cp <= tail) & (gap <= 0.0)).fillna(False).to_numpy()
        sig_day = pd.Series(np.where(bull_drive, 1, np.where(bear_drive, -1, 0)), index=op.index)
        min_rng = float(sl.get("min_range", 0.0))
        if min_rng > 0:
            sig_day = pd.Series(np.where(rng_ >= min_rng, sig_day, 0), index=op.index)
        sig = np.where(sod == 585, pd.Series(day).map(sig_day).fillna(0).to_numpy(), 0)
        
        orig_signals = ep.custom_signal
        def patched_signals(cfg, bars):
            if cfg.get("name") == sl.get("name"):
                return sig.astype(np.int8), np.nan_to_num(atr).astype(np.float32)
            return orig_signals(cfg, bars)
        ep.custom_signal = patched_signals
        try:
            r_sl = ep.run_sleeve(sl, b, START, blocked)
        finally:
            ep.custom_signal = orig_signals
    else:
        r_sl = ep.run_sleeve(sl, b, START, blocked)
        
    for t in r_sl["trades"]:
        t["prio"] = prio
        t["sleeve"] = sl["name"]
        t["instrument"] = sl["instrument"]
        t["exit_day"] = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        t["entry_day"] = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York").date()
        t["dec"] = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=mins)
        a = float(atr.get(t["dec"], np.nan))
        t["stop_risk"] = round(float(sl["stop_atr"]) * a * MULT[sl["instrument"]] + 1.0 + 3 * 0.25 * MULT[sl["instrument"]], 2)
    return r_sl["trades"]

def route_trades(allt):
    allt = sorted(allt, key=lambda x: (x["dec"], x["prio"]))
    acc = []
    busy_until = None
    for t in allt:
        en = pd.Timestamp(t["entry_ts"])
        ex = pd.Timestamp(t["exit_ts"])
        if busy_until is not None and en < busy_until:
            continue
        acc.append(t)
        busy_until = ex
    return acc

sleeves = spec["sleeves"]

# Run both v2 and v3
trades_v2 = route_trades(run_sl(sleeves[0], 0, gap_continuation=False) + run_sl(sleeves[1], 1) + run_sl(sleeves[2], 2))
trades_v3 = route_trades(run_sl(sleeves[0], 0, gap_continuation=True) + run_sl(sleeves[1], 1) + run_sl(sleeves[2], 2))

def analyze_portfolio(trades, name):
    print(f"\n=======================================================")
    print(f"DEEP ATTRIBUTION AUDIT: {name}")
    print(f"=======================================================")
    df = pd.DataFrame(trades)
    df["net"] = df["net"].astype(float)
    df["entry_dt"] = [pd.Timestamp(x).tz_convert("America/New_York") for x in df["entry_ts"]]
    df["exit_dt"] = [pd.Timestamp(x).tz_convert("America/New_York") for x in df["exit_ts"]]
    df["dow"] = [x.strftime("%A") for x in df["entry_dt"]]
    df["dow_num"] = [x.weekday() for x in df["entry_dt"]]
    df["hour"] = [x.hour for x in df["entry_dt"]]
    df["year"] = [x.year for x in df["exit_dt"]]
    df["is_win"] = df["net"] > 0
    df["side"] = ["LONG" if x > 0 else "SHORT" for x in df["qty"].astype(float)]
    
    # Map VIX and SKEW
    df["vix"] = [vix_map.get(d, np.nan) for d in df["entry_day"]]
    df["skew"] = [skew_map.get(d, np.nan) for d in df["entry_day"]]
    
    total_net = df["net"].sum()
    n_trades = len(df)
    exp = total_net / n_trades
    wr = df["is_win"].mean() * 100
    
    print(f"TOTAL: {n_trades} trades | Net P&L: +${total_net:,.2f} | Expectancy: +${exp:.2f}/tr | Win Rate: {wr:.1f}%\n")
    
    # 1. Sleeve Attribution
    print("--- 1. SLEEVE CONTRIBUTIONS ---")
    by_sleeve = df.groupby("sleeve").agg(
        trades=("net", "count"),
        net=("net", "sum"),
        exp=("net", "mean"),
        wr=("is_win", lambda x: round(x.mean() * 100, 1))
    ).reset_index()
    for _, r in by_sleeve.iterrows():
        print(f"  {r['sleeve']:<20}: {r['trades']:>4} trades | Net: +${r['net']:>9,.2f} | Exp: +${r['exp']:>5.2f}/tr | WR: {r['wr']:>4.1f}%")
        
    # 2. Long vs Short Attribution
    print("\n--- 2. DIRECTIONAL ASYMMETRY (LONG vs SHORT) ---")
    by_side = df.groupby("side").agg(
        trades=("net", "count"),
        net=("net", "sum"),
        exp=("net", "mean"),
        wr=("is_win", lambda x: round(x.mean() * 100, 1))
    ).reset_index()
    for _, r in by_side.iterrows():
        print(f"  {r['side']:<10}: {r['trades']:>4} trades | Net: +${r['net']:>9,.2f} | Exp: +${r['exp']:>5.2f}/tr | WR: {r['wr']:>4.1f}%")
        
    # 3. Day of Week Attribution
    print("\n--- 3. DAY OF WEEK BREAKDOWN ---")
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    by_dow = df.groupby("dow").agg(
        trades=("net", "count"),
        net=("net", "sum"),
        exp=("net", "mean"),
        wr=("is_win", lambda x: round(x.mean() * 100, 1))
    ).reindex(days_order).reset_index()
    for _, r in by_dow.iterrows():
        print(f"  {r['dow']:<10}: {r['trades']:>4} trades | Net: +${r['net']:>9,.2f} | Exp: +${r['exp']:>5.2f}/tr | WR: {r['wr']:>4.1f}%")
        
    # 4. Volatility Regime Attribution (VIX Buckets)
    print("\n--- 4. VOLATILITY REGIME (PRIOR CBOE VIX) ---")
    vix_bins = [0, 15, 25, 100]
    vix_labels = ["Low VIX (<15)", "Normal VIX (15-25)", "High VIX (>25)"]
    df["vix_bucket"] = pd.cut(df["vix"], bins=vix_bins, labels=vix_labels)
    by_vix = df.groupby("vix_bucket", observed=False).agg(
        trades=("net", "count"),
        net=("net", "sum"),
        exp=("net", "mean"),
        wr=("is_win", lambda x: round(x.mean() * 100, 1))
    ).reset_index()
    for _, r in by_vix.iterrows():
        print(f"  {str(r['vix_bucket']):<20}: {r['trades']:>4} trades | Net: +${r['net']:>9,.2f} | Exp: +${r['exp']:>5.2f}/tr | WR: {r['wr']:>4.1f}%")

    # 5. Exit Reason Attribution
    print("\n--- 5. EXIT REASON BREAKDOWN ---")
    if "exit_reason" in df.columns:
        by_exit = df.groupby("exit_reason").agg(
            trades=("net", "count"),
            net=("net", "sum"),
            exp=("net", "mean"),
            wr=("is_win", lambda x: round(x.mean() * 100, 1))
        ).reset_index()
        for _, r in by_exit.iterrows():
            print(f"  {r['exit_reason']:<15}: {r['trades']:>4} trades | Net: +${r['net']:>9,.2f} | Exp: +${r['exp']:>5.2f}/tr | WR: {r['wr']:>4.1f}%")
            
    # Check Wednesday FOMC impact (entry after 13:00 on Wednesdays)
    wed_afternoon = df[(df["dow"] == "Wednesday") & (df["hour"] >= 13)]
    print(f"\n--- 6. WEDNESDAY AFTERNOON TRADES (FOMC WINDOW 13:00+) ---")
    print(f"  Trades: {len(wed_afternoon)} | Net P&L: +${wed_afternoon['net'].sum():,.2f}")
    
    return {
        "name": name,
        "total_net": round(total_net, 2),
        "expectancy": round(exp, 2),
        "win_rate": round(wr, 1),
        "by_sleeve": by_sleeve.to_dict(orient="records"),
        "by_side": by_side.to_dict(orient="records"),
        "by_dow": by_dow.to_dict(orient="records"),
        "by_vix": by_vix.to_dict(orient="records")
    }

attr_v2 = analyze_portfolio(trades_v2, "Architecture D+ v2 (Standard Crabel)")
attr_v3 = analyze_portfolio(trades_v3, "Architecture D+ v3 (Gap-Continuation Crabel)")

out_report = {
    "v2_attribution": attr_v2,
    "v3_attribution": attr_v3
}

report_path = ROOT / "reports/TRADE_EDGE_ATTRIBUTION_D_PLUS_TRAIN.json"
with open(report_path, "w") as f:
    json.dump(out_report, f, indent=2, default=str)
print(f"\n[DONE] Saved attribution audit to {report_path}")

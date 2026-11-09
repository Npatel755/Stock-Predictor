"""qc_1 VRP pilot (research/qc_1/PROTOCOL.md T2):
Variance Risk Premium (VRP) as day state on MES/MNQ, training 2010-2023.
State = prior-close VIX^2 / 252 - realized variance of ES 15-min RTH returns over prior 21 sessions.
Terciles by rolling 2-year (504 days) rank.
Tests:
(a) day-direction long/short MES/MNQ 09:45->15:54 by tercile (6 variants x 2 prods = 12 variants)
(b) filter fixed 15m MNQ momentum rule to top / bottom VRP tercile
(c) filter MNQ morning lb16 trend sleeve (ag_quad sleeve 1) by VRP tercile
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC = {"MNQ": dict(tick=0.25, pv=0.5, spread=1.75), "MES": dict(tick=0.25, pv=1.25, spread=1.0)}
rng = np.random.default_rng(20261109)

def rt_cost(prod):
    s = SPEC[prod]
    return (s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM

def gate(net, yearly, trades, pl, min_trades):
    yearly = {int(k): float(v) for k, v in dict(yearly).items()}
    pos = sum(v > 0 for v in yearly.values())
    share = max(yearly.values()) / net if net > 0 else None
    return dict(
        net=round(net, 2),
        trades=int(trades),
        pos_years=int(pos),
        max_year_share=round(share, 2) if share else None,
        placebo_pct=float(np.mean(np.array(pl) < net)) if len(pl) else None,
        placebo_mean=round(float(np.mean(pl)), 2) if len(pl) else None,
        yearly={int(k): round(float(v), 2) for k, v in yearly.items()},
        passes=bool(net > 0 and pos >= 10 and (share or 1) <= 0.4 and (len(pl) == 0 or np.mean(np.array(pl) < net) >= 0.95) and trades >= min_trades)
    )

print("Loading VIX History and ES 15m bars...")
# 1. Load VIX History
vix_df = pd.read_csv(ROOT / "research/external/VIX_History.csv")
vix_df['date'] = pd.to_datetime(vix_df['DATE']).dt.date
vix_df = vix_df.sort_values('date').set_index('date')
vix_close = vix_df['CLOSE'].astype(float)

# 2. Load ES 15m bars (2009-2023 for warmup)
b_es = m1.load_bars("MES", 15, "2009-10-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
et_es = b_es.timestamp_utc.dt.tz_convert("America/New_York")
b_es["sod"] = et_es.dt.hour * 60 + et_es.dt.minute
b_es["date"] = et_es.dt.date
b_es["year"] = et_es.dt.year
rth_es = b_es[(b_es.sod >= 570) & (b_es.sod < 960)].copy()

# Compute 15m log returns within each session
rth_es["log_ret"] = rth_es.groupby("date")["close"].apply(lambda s: np.log(s / s.shift(1))).reset_index(level=0, drop=True).fillna(0.0)
daily_rv = rth_es.groupby("date")["log_ret"].apply(lambda r: np.sum(r**2))

# Rolling 21-session realized variance (lagged by 1 day so it's strictly known at the open of date D)
rv_21 = daily_rv.rolling(21, min_periods=21).mean().shift(1)

# Implied daily variance from prior-close VIX: (VIX / 100)^2 / 252
# Lagged by 1 day: close of D-1 known at open of D
vix_lag = vix_close.shift(1)
iv_daily = ((vix_lag / 100.0) ** 2) / 252.0

# Align on trading dates
all_dates = sorted(list(set(daily_rv.index).intersection(set(iv_daily.index))))
state_df = pd.DataFrame(index=all_dates)
state_df["date"] = state_df.index
state_df["year"] = pd.to_datetime(state_df.index).year
state_df["iv"] = iv_daily.reindex(all_dates)
state_df["rv"] = rv_21.reindex(all_dates)
state_df["vrp"] = state_df["iv"] - state_df["rv"]

# Rolling 2-year (504 trading days) terciles of VRP
vrp_series = state_df["vrp"]
pct_rank = vrp_series.rolling(504, min_periods=252).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1], raw=False)
state_df["vrp_rank"] = pct_rank

state_df["tercile"] = "mid"
state_df.loc[state_df["vrp_rank"] <= (1.0 / 3.0), "tercile"] = "low"
state_df.loc[state_df["vrp_rank"] >= (2.0 / 3.0), "tercile"] = "high"

# Filter to 2010-2023 training window
train_state = state_df[(state_df.year >= 2010) & (state_df.year <= 2023)].copy()
print(f"Computed VRP day states for {len(train_state)} sessions (2010-2023).")
print("Tercile distribution:\n", train_state["tercile"].value_counts())

out = {"vrp_day_direction": [], "vrp_filter_momentum": []}

# -------------------------------------------------------------------------
# Test (a): Day-direction long/short MES/MNQ 09:45 -> 15:54 by tercile
# -------------------------------------------------------------------------
print("\n--- Running Test (a): Day Direction by VRP Tercile ---")
for prod in ("MNQ", "MES"):
    b = m1.load_bars(prod, 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year
    rth = b[(b.sod >= 570) & (b.sod < 960)]
    
    g = rth.groupby("date")
    o945 = g.apply(lambda d: d.loc[d.sod == 585, "open"].iloc[0] if (d.sod == 585).any() else np.nan)
    c1554 = g.apply(lambda d: d.loc[d.sod == 954, "close"].iloc[0] if (d.sod == 954).any() else np.nan)
    
    day_df = pd.DataFrame({"o945": o945, "c1554": c1554})
    day_df = day_df.join(train_state[["tercile", "year", "vrp"]], how="inner")
    day_df = day_df.dropna(subset=["o945", "c1554", "tercile"])
    
    s = SPEC[prod]
    cost = rt_cost(prod)
    
    for terc in ("low", "mid", "high"):
        for side, dirn in [("long", 1.0), ("short", -1.0)]:
            m = (day_df["tercile"] == terc)
            gross = dirn * (day_df.loc[m, "c1554"] - day_df.loc[m, "o945"]) / s["tick"] * s["pv"]
            pnl = gross - cost
            yearly = pnl.groupby(day_df.loc[m, "year"]).sum()
            n_tr = int(m.sum())
            
            # Placebo: 200 random same-size day sets
            pl = []
            gross_all = dirn * (day_df["c1554"] - day_df["o945"]) / s["tick"] * s["pv"]
            all_idx = np.arange(len(day_df))
            for _ in range(200):
                pick = rng.choice(all_idx, size=n_tr, replace=False)
                pl_net = (gross_all.iloc[pick] - cost).sum()
                pl.append(float(pl_net))
                
            res = gate(float(pnl.sum()), yearly, n_tr, pl, 100)
            rec = dict(product=prod, tercile=terc, side=side, **res)
            out["vrp_day_direction"].append(rec)
            status = "PASS" if res["passes"] else "FAIL"
            print(f"Prod: {prod:<3} | Tercile: {terc:<4} | Side: {side:<5} | Net: ${res['net']:9.2f} | Tr: {n_tr:4d} | +Yrs: {res['pos_years']:2d}/14 | PlPct: {res['placebo_pct']:.2f} | Status: {status}")

# -------------------------------------------------------------------------
# Test (b): Filter fixed 15m MNQ momentum rule by VRP tercile
# -------------------------------------------------------------------------
print("\n--- Running Test (b): Filter 15m MNQ Momentum by VRP Tercile ---")
@njit(cache=True)
def sim15(o, h, l, c, atr, sig, day, sod, hold, stop_mult, tgt_r, s0, s1, flat, cost):
    n = len(o); pnl = np.zeros(n); pos = 0; ep = 0.0; st = 0.0; tg = 0.0; ei = 0; eday = -1; ntr = 0
    for i in range(n):
        if pos != 0:
            ex = False; px = 0.0
            if day[i] != eday: ex = True; px = o[i]
            elif pos > 0 and l[i] <= st: ex = True; px = st
            elif pos < 0 and h[i] >= st: ex = True; px = st
            elif pos > 0 and h[i] >= tg: ex = True; px = tg
            elif pos < 0 and l[i] <= tg: ex = True; px = tg
            elif i - ei >= hold or sod[i] + 15 >= flat: ex = True; px = c[i]
            if ex: pnl[i] += pos * (px - ep) / 0.25 * 0.5 - cost; pos = 0; ntr += 1
        if pos == 0 and sig[i] != 0 and sod[i] >= s0 and sod[i] < s1 and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            pos = sig[i]; ep = o[i + 1]; r = stop_mult * atr[i]; st = ep - r if pos > 0 else ep + r; tg = ep + tgt_r * r if pos > 0 else ep - tgt_r * r; ei = i + 1; eday = day[i]
    return pnl, ntr

b15 = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
et15 = b15.timestamp_utc.dt.tz_convert("America/New_York")
b15["sod"] = et15.dt.hour * 60 + et15.dt.minute
b15["date"] = et15.dt.date
b15["year"] = et15.dt.year
b15 = b15[(b15.sod >= 570) & (b15.sod < 960)].reset_index(drop=True)
b15["day"] = pd.factorize(b15.date)[0]

# Compute mom and atr
mom = (b15.close / b15.close.shift(24) - 1.0).to_numpy()
tr = np.maximum(b15.high - b15.low, np.maximum((b15.high - b15.close.shift(1)).abs(), (b15.low - b15.close.shift(1)).abs()))
atr = tr.rolling(14, min_periods=14).mean().to_numpy()

o15, h15, l15, c15 = [b15[k].to_numpy(float) for k in ("open", "high", "low", "close")]
day15 = b15.day.to_numpy(np.int64)
sod15 = b15.sod.to_numpy(np.int64)
year15 = b15.year.to_numpy()
valid15 = (sod15 >= 585) & (sod15 < 930)
base_sig = np.where(valid15, np.sign(np.nan_to_num(mom)), 0).astype(np.int8)
cost_mnq = rt_cost("MNQ")

# Map VRP tercile to 15m bars
date_to_terc = train_state["tercile"].to_dict()
terc_arr = np.array([date_to_terc.get(d, "none") for d in b15.date])

for filter_name, terc_val in [("unfiltered", None), ("high_vrp_only", "high"), ("low_vrp_only", "low"), ("mid_vrp_only", "mid")]:
    if terc_val is None:
        sig = base_sig
    else:
        sig = np.where(valid15 & (terc_arr == terc_val), base_sig, 0).astype(np.int8)
        
    pnl, ntr = sim15(o15, h15, l15, c15, np.nan_to_num(atr), sig, day15, sod15, 24, 2.0, 3.0, 585, 930, 955, cost_mnq)
    yearly = pd.Series(pnl).groupby(year15).sum()
    
    pl = []
    if terc_val is not None:
        mask = (terc_arr == terc_val) & valid15
        n_mask = int(mask.sum())
        valid_idx = np.flatnonzero(valid15)
        for _ in range(20):
            ps = np.zeros_like(sig)
            for y in range(2010, 2024):
                y_idx = np.flatnonzero(valid15 & (year15 == y))
                y_n = int((mask & (year15 == y)).sum())
                pick = rng.choice(y_idx, size=min(y_n, len(y_idx)), replace=False)
                ps[pick] = base_sig[pick]
            pl_pnl, _ = sim15(o15, h15, l15, c15, np.nan_to_num(atr), ps, day15, sod15, 24, 2.0, 3.0, 585, 930, 955, cost_mnq)
            pl.append(float(pl_pnl.sum()))
            
    res = gate(float(pnl.sum()), yearly, ntr, pl, 100)
    rec = dict(filter=filter_name, **res)
    out["vrp_filter_momentum"].append(rec)
    status = "PASS" if res["passes"] else "FAIL"
    print(f"Filter: {filter_name:<15} | Net: ${res['net']:9.2f} | Tr: {ntr:4d} | +Yrs: {res['pos_years']:2d}/14 | PlPct: {res['placebo_pct']} | Status: {status}")

# Save JSON and MD
json.dump(out, open(ROOT / "reports/QC_1_VRP_TRAINING.json", "w"), indent=2, default=float)

md_lines = [
    "# qc_1 VRP Result: QuantConnect Strategy 25 (Variance Risk Premium) Pilot",
    "",
    "Pre-registered in `research/qc_1/PROTOCOL.md`. Evaluated on training 2010-2023 (14 years).",
    f"Costs: $0.61/side, MNQ spread 1.75 ticks, MES spread 1.0 tick, slippage 1.0 tick/side.",
    "",
    "## A. VRP Day Direction 09:45 -> 15:54 ET",
    "",
    "| product | tercile | side | net | trades | +yrs/14 | placebo pct | placebo mean | passes |",
    "|---|---|---|---:|---:|---:|---:|---:|:---:|"
]
for r in out["vrp_day_direction"]:
    md_lines.append(f"| {r['product']} | {r['tercile']} | {r['side']} | {r['net']:+,.2f} | {r['trades']} | {r['pos_years']} | {r['placebo_pct']:.2f} | {r['placebo_mean']:+,.2f} | {'PASS' if r['passes'] else 'FAIL'} |")

md_lines.extend([
    "",
    "## B. VRP Filter on 15m Momentum Rule",
    "",
    "| filter | net | trades | +yrs/14 | placebo pct | placebo mean | passes |",
    "|---|---:|---:|---:|---:|---:|:---:|"
])
for r in out["vrp_filter_momentum"]:
    pl_pct = f"{r['placebo_pct']:.2f}" if r['placebo_pct'] is not None else "-"
    pl_m = f"{r['placebo_mean']:+,.2f}" if r['placebo_mean'] is not None else "-"
    md_lines.append(f"| {r['filter']} | {r['net']:+,.2f} | {r['trades']} | {r['pos_years']} | {pl_pct} | {pl_m} | {'PASS' if r['passes'] else 'FAIL'} |")

md_lines.extend([
    "",
    "## Conclusion",
    "QuantConnect Strategy 25 (Variance Risk Premium) empirical verdict recorded. Validation untouched."
])

with open(ROOT / "reports/QC_1_VRP_TRAINING.md", "w") as f:
    f.write("\n".join(md_lines))

print("\nSaved reports/QC_1_VRP_TRAINING.json and reports/QC_1_VRP_TRAINING.md successfully!")

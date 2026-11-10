"""payout_geometry (Claude, 2026-11-09) - can a forced daily trade that banks $150 and stops produce payouts?

PRE-DECLARED (written before any result was seen):
  Question: Nick wants a $150+ day as often as possible (payout = 5 days >= $150, not consecutive).
  Every prior round found no daily-frequency edge after micro costs. This measures the payout frontier of the
  "trade every day, take +$155 net, stop at -$S" geometry, and whether the open-drive direction beats a coin flip.
  Data: TRAINING ONLY. 1-min NQ (2010-06..2018-12) + MNQ (2019..2023), RTH 09:30-16:00 ET, priced as MNQ ($2/pt).
  Costs: 2 ticks adverse per side (1 tick slip + 1.75-tick spread/2, rounded) + $0.61/side = $3.22 per contract round trip.
  Entry 09:45 at the open of the 09:45 bar. Direction: (a) open-drive = sign(09:44 close - 09:30 open); (b) coin flip, 20 seeds.
  Stop distance = f x mean prior-10-session RTH range (known before the open), f in {0.10, 0.20}.
  Size n = floor(S / (2*stop_pts + 3.22)), cap 50 micros; n = 0 -> no trade. Daily loss budget S in {150, 300, 450}.
  Target = +$155 net for the day. One trade per day. Stop and target in the same bar -> stop. Gap through stop -> bar open.
  Time exit at the last bar <= 15:55 ET. Account: static floor -$2,000, $1,000 DLL, withdraw the cycle profit at each payout.
  Grid: 6 cells x 2 directions = 12 rows + 120 coin-flip runs. Nothing is tuned; no validation/test data is loaded.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq

D = Path(r"C:/Users/Nick/OneDrive/Attachments/Desktop/Stock Predictor Codex ETH BNB/quant_trading_bot/data/market/"
         r"GLBX-20261106-FX6FM5XWUX-v3/splits")
COST = 2 * 0.5 * 2.0 + 1.22          # $ per contract round trip
TARGET = 155.0
FLOOR, DLL = -2000.0, -1000.0


def load():
    parts = []
    for sym, lo, hi in (("NQ", "2010-01-01", "2019-01-01"), ("MNQ", "2019-01-01", "2024-01-01")):
        t = pq.read_table(D / sym / "train.parquet", columns=["timestamp_utc", "open", "high", "low", "close"]).to_pandas()
        t = t[(t.timestamp_utc >= pd.Timestamp(lo, tz="UTC")) & (t.timestamp_utc < pd.Timestamp(hi, tz="UTC"))]
        parts.append(t)
    b = pd.concat(parts).drop_duplicates("timestamp_utc").sort_values("timestamp_utc")
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["date"] = et.dt.date
    b["mod"] = et.dt.hour * 60 + et.dt.minute
    b = b[(b["mod"] >= 570) & (b["mod"] < 960)]
    assert b.timestamp_utc.min().year >= 2010 and b.timestamp_utc.max().year <= 2023
    return b


def build_days(b):
    days = []
    for d, g in b.groupby("date", sort=True):
        m = g["mod"].to_numpy()
        if m[0] != 570 or (m == 944).sum() != 1 or (m == 945).sum() != 1:
            continue                                  # need 09:30 open, 09:44 close, 09:45 open
        i44, i45 = int(np.where(m == 944)[0][0]), int(np.where(m == 945)[0][0])
        last = np.where(m <= 955)[0][-1]
        days.append(dict(date=d, rng=g.high.max() - g.low.min(), o930=g.open.iloc[0], c944=g.close.iloc[i44],
                         o=g.open.to_numpy()[i45:last + 1], h=g.high.to_numpy()[i45:last + 1],
                         l=g.low.to_numpy()[i45:last + 1], c=g.close.to_numpy()[i45:last + 1]))
    rngs = pd.Series([x["rng"] for x in days]).shift(1).rolling(10).mean().to_numpy()
    for x, v in zip(days, rngs):
        x["V"] = v
    return [x for x in days if np.isfinite(x["V"])]


def day_pnl(x, direction, f, S):
    sd = f * x["V"]
    n = min(50, int(S // (2 * sd + COST)))
    if n <= 0 or direction == 0:
        return 0.0, 0
    e = x["o"][0]
    td = (TARGET + n * COST) / (2 * n)
    if direction > 0:
        stop, tgt = e - sd, e + td
        hs, ht = x["l"] <= stop, x["h"] >= tgt
    else:
        stop, tgt = e + sd, e - td
        hs, ht = x["h"] >= stop, x["l"] <= tgt
    i_s = int(np.argmax(hs)) if hs.any() else 10**9
    i_t = int(np.argmax(ht)) if ht.any() else 10**9
    if i_s == 10**9 and i_t == 10**9:
        px = x["c"][-1]
    elif i_s <= i_t:
        op = x["o"][i_s]
        px = (min(stop, op) if direction > 0 else max(stop, op)) if i_s > 0 else stop
    else:
        px = tgt
    return n * (2 * direction * (px - e)) - n * COST, n


def account(dates, pnl):
    """Sequential funded account: static floor, DLL, payout every 5 days >= $150 (withdraw cycle profit)."""
    bal = 0.0; good = 0; cyc_start = 0; payouts = []; blowups = 0; cyc_days = []
    for i, p in enumerate(pnl):
        p = max(p, DLL)
        bal += p
        if bal <= FLOOR:
            blowups += 1; bal = 0.0; good = 0; cyc_start = i + 1
            continue
        if p >= 150:
            good += 1
        if good >= 5:
            payouts.append(max(bal, 0.0)); cyc_days.append(i + 1 - cyc_start)
            bal = min(bal, 0.0); good = 0; cyc_start = i + 1
    yrs = (pd.Timestamp(dates[-1]) - pd.Timestamp(dates[0])).days / 365.25
    return dict(payouts_per_yr=round(len(payouts) / yrs, 1), median_payout=round(float(np.median(payouts)), 0) if payouts else 0,
                zero_dollar_payout_share=round(float(np.mean([q <= 0 for q in payouts])), 2) if payouts else None,
                median_sessions_per_payout=float(np.median(cyc_days)) if cyc_days else None,
                blowups_per_yr=round(blowups / yrs, 2))


def summarize(days, pnl, ntr):
    dates = [x["date"] for x in days]
    pnl, ntr = np.array(pnl), np.array(ntr)
    yr = pd.Series(pnl, index=pd.to_datetime(dates).year).groupby(level=0).sum()
    era = pd.to_datetime(dates).year < 2020
    out = dict(sessions=len(pnl), trade_day_pct=round(100 * (ntr > 0).mean(), 1),
               qual_day_pct=round(100 * (pnl >= 150).mean(), 1),
               qual_days_per_month=round(21 * (pnl >= 150).mean(), 1),
               net_per_session=round(pnl.mean(), 2), net_2010_19=round(pnl[era].sum(), 0), net_2020_23=round(pnl[~era].sum(), 0),
               pos_years=f"{int((yr > 0).sum())}/{len(yr)}", worst_day=round(pnl.min(), 0), days_le_minus_1k=int((pnl <= -1000).sum()),
               median_contracts=float(np.median(ntr[ntr > 0])) if (ntr > 0).any() else 0)
    out.update(account(dates, pnl))
    # reporting-only addition (same rules): 2020-23 slice, where contract counts resemble today's prices
    m = ~era
    d2 = [d for d, k in zip(dates, m) if k]
    out["y2020_23"] = dict(qual_day_pct=round(100 * (pnl[m] >= 150).mean(), 1), net_per_session=round(pnl[m].mean(), 2),
                           median_contracts=float(np.median(ntr[m][ntr[m] > 0])) if (ntr[m] > 0).any() else 0,
                           cost_per_session=round(float((ntr[m] * COST).mean()), 2), **account(d2, pnl[m]))
    return out


def main():
    days = build_days(load())
    print(f"sessions {len(days)}  {days[0]['date']} .. {days[-1]['date']}", flush=True)
    res = {}
    for S in (150, 300, 450):
        for f in (0.10, 0.20):
            key = f"S={S} f={f}"
            od = [day_pnl(x, int(np.sign(x["c944"] - x["o930"])), f, S) for x in days]
            res[key] = {"open_drive": summarize(days, [p for p, _ in od], [n for _, n in od])}
            coin = []
            for seed in range(20):
                r = np.random.default_rng(seed).choice([-1, 1], len(days))
                cd = [day_pnl(x, int(r[i]), f, S) for i, x in enumerate(days)]
                coin.append(summarize(days, [p for p, _ in cd], [n for _, n in cd]))
            res[key]["coin_flip_median"] = {k: (float(np.median([c[k] for c in coin])) if isinstance(coin[0][k], (int, float)) and coin[0][k] is not None else coin[0][k])
                                            for k in coin[0]}
            res[key]["open_drive_beats_coin_net"] = f"{sum(res[key]['open_drive']['net_per_session'] > c['net_per_session'] for c in coin)}/20"
            res[key]["open_drive_beats_coin_net_2020_23"] = f"{sum(res[key]['open_drive']['y2020_23']['net_per_session'] > c['y2020_23']['net_per_session'] for c in coin)}/20"
            res[key]["coin_2020_23_net_per_session_median"] = float(np.median([c["y2020_23"]["net_per_session"] for c in coin]))
            print(key, "2020-23:", json.dumps(res[key]["open_drive"]["y2020_23"]), "| coin net/session",
                  res[key]["coin_2020_23_net_per_session_median"], "| beats", res[key]["open_drive_beats_coin_net_2020_23"], flush=True)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(res, indent=1, default=str))


main()

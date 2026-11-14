"""Paper account replay for Topstep Labs' $50K Static Daily Payouts+ account (Claude, 2026-11-10). Read-only on the paper ledgers.

Replays the forward paper trades of the v5.3 payout build (ag_arch_d_plus_v2_price_aware_v53; v5.2 until 2026-11-10) and the overnight leg (overnight_dip_v2_stop055)
through two tracks, from the paper start, and writes <root>/_account_static_daily/status.json (plus an "account_static_daily" entry in
<root>/dashboard.json). Notifies (ntfy, same channel as the runner) on a new payout, a size-stage change, or an evaluation pass / fail.
  FUNDED (Fortress 4X since 2026-11-10: 1x <$4,000, 2x from $4,000, 3x from $4,800, 4x from $6,500, payouts above $8,500 - the lines below
    describe the earlier payout_24 rule it replaced; account mechanics are unchanged): balance from $0; floor -$2,000 static until the
    first payout, then $0; DLL $1,000; 1x below a $4,000 balance at the prior close, 2x from $4,000 (account stop $700; since 2026-11-10 a trade
    is TRIMMED to floor($900 / stop risk per micro) micros instead of skipped when 2x would risk more than $900, v55 cell 4); overnight leg only while the balance >= $500; daily payout of profit above $6,000 when >= $250, max $1,500,
    net profit since the last payout > 0.
  EVALUATION (eval_1, k = 3; holdout-checked in reports/HOLDOUT_EVAL1_RESULTS.json): size min(3 x base, floor($900 / stop risk per micro)),
    overnight min(3, floor($900 / risk)); account stop $700; target $4,000 with the 55% consistency rule; floor -$2,000; DLL $1,000; 90 days.
  EVALUATION CHALLENGER (since 2026-11-10, Nick: "yup"; eval_8 "SLEEVES + DEF + ENDGAME", chosen POST HOC on 2010-23 training, 60.0% vs
    53.4%; CORRECTED 2026-11-11 for a simulator look-ahead (eval_28/29): 55.2% per attempt, 49.7 / 59.4 by half): the v5.3 trades plus two Codex sleeves already on paper in portfolio_e (MNQ_BRK_E_2c, MES_MOM_3c; 1 micro base, skipped when the
    stop risks > $300 per micro), re-routed one position at a time (research rule: by decision time, then priority, v5.3 first); size
    k = 3, k = 2 once the balance is <= -$500, k = 1 at <= -$1,000 ($400 daily stop at k = 1); from calendar day 60, while more than $1,000
    short of the target and above -$500, k = 5. Same $900 per-trade risk cap, target, floor, DLL and 90 days as the 3x card.
  ROLLING STARTS: both evaluation rules are also started on every weekday since the paper start, to collect forward evidence faster
    (overlapping starts share trades, so they are not independent).
  CHAMPION/CHALLENGER TRIGGERS (written 2026-11-10, before any forward result): (a) if the two Codex sleeves' forward net per micro is below
    $0 after >= 40 forward trades, drop them from the challenger (it becomes DEF + ENDGAME on v5.3); (b) once >= 40 rolling starts of both rules
    have resolved, the challenger replaces the 3x rule as the plan for a real Combine only if its pass share >= the 3x rule's and its fail
    share <= the 3x rule's + 5 points. Nothing is promoted automatically.
  PLAN (since 2026-11-11, Nick: "do it"): the challenger's trades and sizing with CAUSAL one-position routing (route_book_strict: never two
    positions; eval_30-36, holdout_eval36) is the rule for a real Combine. Card "evaluation_strict"; the posthoc challenger stays for comparison.
  EVALUATION FLOOR (since 2026-11-11): every evaluation card checks the static floor and the DLL INTRADAY with the research v2 day rules
    (day_pnl_intraday: realised only once closed before the next entry; open trades' worst points stack; each trade's worst point from the
    runner's 1-minute bars). The funded cards still check the floor on realised day P&L. Since 2026-11-12 the intraday day's worst point is
    capped at the -$1,000 DLL (the DLL flattens the day at its first passage; it used to report the full stacked worst point).
  FUNDED CHALLENGER (since 2026-11-12, Nick: "do 2 amd 1"; research payout_34, training only): Fortress 4X plus the noise-area intraday
    momentum sleeve (eval_12 MNQ "P", published parameters) as a separate 1-micro position ONLY while at 4x, generated from the runner's own
    1-minute MNQ bars; floor and DLL checked intraday. Shown beside Fortress 4X on the same intraday check. Retire / promote triggers are in
    the card (written before any forward noise trade).
  MONTH-END WATCH (since 2026-11-13, Nick: "go ahead"; research rebal_1, which FAILED its pre-registered gate, t 1.85 vs 2.73): a
    watch-only card, never part of any account card. Last 3 CME trading days of each month (early-close days skipped), 1 MNQ micro
    18:00 ET -> 15:55, short after an up S&P 500 month-to-date, long after a down one, stop 0.5 x prior RTH ATR(14). Triggers in the card.
  KEEP-ALIVE (since 2026-11-12): every card places a simulated 1-micro round trip (-$3) on the first weekday >= 25 calendar days after its
    last trade when nothing has traded since (Topstep closes accounts after 30 days without a trade); the dashboard shows days since the
    last trade and ntfy warns at 20 days for the funded rule and the evaluation PLAN.
Known gaps vs research: trades are routed at 1x before sizing (v55 measured the rules this way); the funded floor is checked on realised day P&L
(the runner's own intrabar drawdown is reported beside it); v5.3 trades the runner rejected while routing cannot come back when a Codex trade
blocks the one that blocked them; portfolio_e's own paper-account locks can stop its sleeves. Paper only; nothing is routed anywhere.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd

NY = "America/New_York"
MULT = {"MNQ": 2.0, "MES": 5.0}
V52, NIGHT = "ag_arch_d_plus_v2_price_aware_v53", "overnight_dip_v2_stop055"   # v5.3 since 2026-11-10 (v53 cell A: v5.2 minus TRD30PM)
NIGHT_0915 = "overnight_dip_v2_stop055_0915"   # Aegis comparison leg: same overnight dip, exit 09:15 ET
BOOK = "D+ v5.3 payout build (v5.2 without the afternoon trend) + overnight leg; 2x size trimmed to $900 risk"
EXTRA = "portfolio_e"                                     # Codex sleeves added by the challenger evaluation rule (eval_8)
EXTRA_PRIO = {"MNQ_BRK_E_2c": 10, "MES_MOM_3c": 11}      # router priority after the v5.3 sleeves, as in eval_8


def read_trades(path):
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] if Path(path).exists() else []
    return [r for r in rows if r.get("kind") == "trade"]


def atr_lookup(bars_1m, minutes):
    b = bars_1m.set_index("ts").sort_index()
    g = b.resample(f"{minutes}min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    prev = g.close.shift(1)
    tr = pd.concat([g.high - g.low, (g.high - prev).abs(), (g.low - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(14, min_periods=14).mean()


def stop_risk_per_micro(trades, specs, bars):
    """Engine stop-risk formula (payout_lib.price_normalize, at actual prices): stop_atr x ATR(decision bar) x multiplier + $1 + 0.75 x multiplier."""
    cache = {}
    for t in trades:
        sp = specs.get(t["sleeve"])
        if sp is None: t["risk"] = None; continue
        inst, mins = sp["instrument"], int(sp.get("bar_minutes", 15))
        if (inst, mins) not in cache: cache[(inst, mins)] = atr_lookup(bars[inst], mins)
        dec = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=mins)
        a = cache[(inst, mins)].get(dec, np.nan)
        t["risk"] = float(sp["stop_atr"]) * float(a) * MULT[inst] + 1.0 + 0.75 * MULT[inst] if np.isfinite(a) else None
        t["inst"] = inst
    return trades


def group_intraday(trades):
    """Crabel base + gap-addon records of the same trade become one position with n_base = 2 (research: 2 micros on continuation)."""
    out = {}
    for t in trades:
        key = (t["entry_ts"], t["exit_ts"], t["side"], "CRABEL" in t["sleeve"])
        if key[3] and key in out:
            out[key]["n_base"] += 1; out[key]["net_total"] += t["net"]; continue
        out[key if key[3] else (t["entry_ts"], t["exit_ts"], t["side"], t["sleeve"])] = dict(t, n_base=1, net_total=t["net"])
    rows = []
    for v in out.values():
        rows.append(dict(tin=pd.Timestamp(v["entry_ts"]).tz_convert(NY), tout=pd.Timestamp(v["exit_ts"]).tz_convert(NY), n_base=v["n_base"],
                         per_micro=v["net_total"] / (v["n_base"] * max(1, v.get("qty", 1))), risk=v.get("risk"), night=False, sleeve=v["sleeve"],
                         side=int(v.get("side", 0) or 0), entry=v.get("entry_price")))
    return rows


def night_rows(trades):
    rows = []
    for t in trades:
        e = float(t["entry_price"])
        rows.append(dict(tin=pd.Timestamp(t["entry_ts"]).tz_convert(NY), tout=pd.Timestamp(t["exit_ts"]).tz_convert(NY), n_base=1,
                         per_micro=t["net"] / max(1, t.get("qty", 1)), risk=0.0055 * e * MULT["MNQ"] + 1.0 + 0.75 * MULT["MNQ"], night=True, sleeve=t["sleeve"],
                         side=int(t.get("side", 1) or 1), entry=e, inst="MNQ"))
    return rows


def extra_rows(trades):
    """Codex sleeve trades for the challenger: 1 micro base (P&L per micro = net / qty), skipped when the stop risks > $300 per micro."""
    rows = []
    for t in trades:
        if t["sleeve"] not in EXTRA_PRIO or t.get("risk") is None or t["risk"] > 300.0: continue
        tin = pd.Timestamp(t["entry_ts"]).tz_convert(NY)
        rows.append(dict(tin=tin, tout=pd.Timestamp(t["exit_ts"]).tz_convert(NY), n_base=1, per_micro=t["net"] / max(1, t.get("qty", 1)),
                         risk=t["risk"], night=False, sleeve=t["sleeve"], prio=EXTRA_PRIO[t["sleeve"]], dec=tin - pd.Timedelta(minutes=t.get("bar_minutes", 15)),
                         side=int(t.get("side", 0) or 0), entry=t.get("entry_price")))
    return rows


# NOISE-AREA SLEEVE (funded challenger since 2026-11-12, Nick: "do 1"; research payout_34): Zarattini, Aziz & Barbon (2024) intraday
# momentum, eval_12's MNQ "P" rules with the published parameters, computed here from the runner's own 1-minute MNQ bars (it is not a
# runner candidate). Band = 14-session mean |close(minute) / open - 1| around max/min(open, prior close); checked at the closes of 10:00,
# 10:30, ..., 15:30 ET; trailing stop = the closer of band / VWAP, also only checked at those marks; fills at the next bar's open; flat at
# the 16:00 close. Filled like the runner's overnight leg: bar open +/- (half of 1.75 ticks + 1 tick), $0.61 per side; 1 micro per trade.
NOISE_LOOK = 14
NOISE_CHECKS = [29 + 30 * j for j in range(12)]          # minute index from 09:30 of the bars closing 10:00 .. 15:30
NOISE_HALF = (1.75 / 2 + 1.0) * 0.25                     # MNQ points per side
NOISE_FEE = 2 * 0.61
NOISE_Q = {1: 0, 2: 0, 3: 0, 4: 1}                       # micros by ladder stage: only at 4x (balance >= $6,500), payout_34 cell NC


def noise_sessions(b):
    """Full RTH sessions (eval_12's rth_panel: 09:30-16:00 ET, >= 385 one-minute bars, first bar at 09:30, gaps forward-filled).
    The runner's Yahoo series carries no contract label, so the prior close is always used (eval_12 drops it when the contract changed)."""
    b = b.sort_values("ts").drop_duplicates("ts")
    t = b.ts.dt.tz_convert(NY); mi = (t.dt.hour * 60 + t.dt.minute - 570).to_numpy(); ok = (mi >= 0) & (mi < 390)
    x = b[ok].assign(m=mi[ok], d=t[ok].dt.date.to_numpy())
    out = []
    for d, g in x.groupby("d", sort=True):
        if len(g) < 385 or int(g.m.iloc[0]) != 0: continue
        g = g.set_index("m").reindex(range(390)); c = g.close.ffill().to_numpy(float)
        f = lambda col: g[col].fillna(pd.Series(c, index=g.index)).to_numpy(float)
        v = g.volume.fillna(0).to_numpy(float) if "volume" in g else np.ones(390)
        out.append(dict(d=d, o=f("open"), h=f("high"), l=f("low"), c=c, v=v, t0=g.ts.iloc[0].tz_convert(NY)))
    return out


def noise_rows(b):
    """Noise-sleeve trades (1 micro) from MNQ 1-minute bars (columns ts, open, high, low, close, volume). Rows carry extra=True so the
    funded challenger sizes them by NOISE_Q; skipped when the stop risks > $300 per micro, like every other sleeve."""
    S = noise_sessions(b); rows = []
    if len(S) <= NOISE_LOOK: return rows
    mv = np.array([np.abs(s["c"] / s["o"][0] - 1.0) for s in S])
    for i in range(NOISE_LOOK, len(S)):
        x, prev = S[i], S[i - 1]; O = x["o"][0]
        PC = prev["c"][-1] if (x["d"] - prev["d"]).days <= 4 else O
        sig = mv[i - NOISE_LOOK:i].mean(axis=0)
        typ = (x["h"] + x["l"] + x["c"]) / 3.0; cv = np.cumsum(x["v"])
        vw = np.where(cv > 0, np.cumsum(typ * x["v"]) / np.maximum(cv, 1e-9), x["c"])
        UB, LB = max(O, PC) * (1 + sig), min(O, PC) * (1 - sig)
        st = dict(pos=0, e=None, ein=None, risk=None)

        def stop_level(m, p):
            if st["pos"] > 0: return max(UB[m], vw[m]) if vw[m] < p else UB[m]
            return min(LB[m], vw[m]) if vw[m] > p else LB[m]

        def close_at(j, px):
            pos = st["pos"]; ef = st["e"] + pos * NOISE_HALF; xf = px - pos * NOISE_HALF
            rows.append(dict(tin=x["t0"] + pd.Timedelta(minutes=st["ein"]), tout=x["t0"] + pd.Timedelta(minutes=min(j, 390)), n_base=1,
                             per_micro=pos * (xf - ef) * MULT["MNQ"] - NOISE_FEE, risk=st["risk"] * ef * MULT["MNQ"] + 1.0 + 0.75 * MULT["MNQ"],
                             night=False, sleeve="NOISE_MNQ_P", side=pos, entry=ef, inst="MNQ", extra=True, prio=12, raw_entry=st["e"], raw_exit=px))
            st["pos"] = 0

        for m in NOISE_CHECKS:
            p = x["c"][m]
            if st["pos"] != 0:
                s = stop_level(m, p)
                if (st["pos"] > 0 and p <= s) or (st["pos"] < 0 and p >= s): close_at(m + 1, x["o"][m + 1])
            if st["pos"] == 0 and m + 1 < 390:
                side = 1 if p > UB[m] else (-1 if p < LB[m] else 0)
                if side:
                    st.update(pos=side, ein=m + 1, e=x["o"][m + 1])
                    st["risk"] = max(abs(st["e"] - stop_level(m, p)) / st["e"], 0.0005)
        if st["pos"] != 0: close_at(390, x["c"][389])
    return [r for r in rows if r["risk"] <= 300.0]


# MONTH-END REBALANCING WATCH (since 2026-11-13, Nick: "go ahead"; research rebal_1, training 2010-23): WATCH ONLY - never part of any
# account card. Rule frozen from rebal_1 cell END|SES|MNQ: on each of the last 3 CME trading days of a month (skipping early-close days),
# 1 MNQ micro from the 18:00 ET reopen to the 15:55 bar open, side = -sign(S&P 500 month-to-date return through the prior close),
# protective stop 0.5 x the prior MNQ RTH daily ATR(14) checked on every 1-minute bar (a gap through it fills at the open). Fills like the
# noise sleeve (bar price +/- (half of 1.75 ticks + 1 tick), $0.61 per side). Deviation from research: the signal uses the S&P 500 cash index
# (yfinance ^GSPC daily, cached to <bars>/spx_daily.csv) instead of chained ES futures closes, because the runner's Yahoo futures series has
# no contract label (a roll jump could flip a small month-to-date sign); the two signs differ only when the month-to-date move is tiny.
ME_DAYS = 3
ME_RESEARCH = ("rebal_1 training 2010-23 (MNQ, last 3 trading days, 18:00 -> 15:55): +$48.20 per trade, t 1.85 (n 469), +$53.67 / +$43.11 "
               "by half, 98.5% of random-sign versions, the same rule mid-month -$37.59; FAILED the pre-registered t >= 2.73 gate")


def _easter(y):
    a = y % 19; b, c = divmod(y, 100); d, e = divmod(b, 4); f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30; i, k = divmod(c, 4); l_ = (32 + 2 * e + 2 * i - h - k) % 7; m = (a + 11 * h + 22 * l_) // 451
    mo = (h + l_ - 7 * m + 114) // 31; dy = (h + l_ - 7 * m + 114) % 31 + 1
    return pd.Timestamp(year=y, month=mo, day=dy).date()


def cme_closed_days(y):
    """CME equity-index full closures (no session for that trade date): New Year's Day (not observed on a Friday when Jan 1 is a
    Saturday), Good Friday, Christmas (observed). Other US holidays have an abbreviated session (counted as trading days, like research)."""
    out = set()
    ny = pd.Timestamp(year=y, month=1, day=1).date()
    if ny.weekday() == 6: out.add(ny + pd.Timedelta(days=1))
    elif ny.weekday() < 5: out.add(ny)
    out.add(_easter(y) - pd.Timedelta(days=2))
    xm = pd.Timestamp(year=y, month=12, day=25).date()
    out.add(xm - pd.Timedelta(days=1) if xm.weekday() == 5 else (xm + pd.Timedelta(days=1) if xm.weekday() == 6 else xm))
    return out


def month_trading_days(y, m):
    days = pd.date_range(pd.Timestamp(year=y, month=m, day=1), pd.Timestamp(year=y, month=m, day=1) + pd.offsets.MonthEnd(0), freq="D")
    closed = cme_closed_days(y)
    return [d.date() for d in days if d.weekday() < 5 and d.date() not in closed]


def month_end_days(y, m):
    """The last ME_DAYS trading days of the month and which of them trade (early-close days are skipped, as in research)."""
    from quant_futures.session_calendar import early_close_dates
    last = month_trading_days(y, m)[-ME_DAYS:]
    early = set(early_close_dates(y))
    return [(d, d not in early) for d in last]


def spx_daily(root):
    """S&P 500 daily closes (yfinance ^GSPC, 1y), merged into <bars>/spx_daily.csv so history builds up and a feed failure falls back."""
    path = root / "bars" / "spx_daily.csv"
    old = pd.read_csv(path, index_col=0, parse_dates=True)["close"] if path.exists() else pd.Series(dtype=float)
    try:
        import yfinance as yf
        h = yf.Ticker("^GSPC").history(period="1y", interval="1d", auto_adjust=False)["Close"].dropna()
        new = pd.Series(h.to_numpy(float), index=pd.to_datetime(h.index.strftime("%Y-%m-%d")))
        s = pd.concat([old, new]); s = s[~s.index.duplicated(keep="last")].sort_index()
        s.rename("close").to_frame().to_csv(path)
        return s
    except Exception:  # noqa: BLE001
        return old.sort_index()


def rth_atr(b, d, n=14):
    """Wilder ATR(n) over RTH (09:30-16:00 ET) sessions strictly before date d, from 1-minute bars; None with fewer than n sessions."""
    t = b.ts.dt.tz_convert(NY); mi = t.dt.hour * 60 + t.dt.minute
    x = b[(mi >= 570) & (mi < 960)].assign(d=t.dt.date)
    x = x[x.d < d]
    g = x.groupby("d").agg(h=("high", "max"), l=("low", "min"), c=("close", "last"), k=("close", "size"))
    g = g[g.k >= 60]
    if len(g) < n: return None
    pc = g.c.shift(1)
    tr = np.fmax(g.h - g.l, np.fmax((g.h - pc).abs(), (g.l - pc).abs())).fillna(g.h - g.l)
    return float(tr.ewm(alpha=1.0 / n, adjust=False).mean().iloc[-1])


def month_end_trade(b, d, side, stop_dist):
    """Simulate one session: entry at the first bar at or after 18:00 ET on the latest earlier day with evening bars, exit at the open of
    the first bar at or after 15:55 ET on d; stop checked on every bar (gap through it fills at the open). None while d is incomplete."""
    t = b.ts.dt.tz_convert(NY); dd = t.dt.date.to_numpy(); mi = (t.dt.hour * 60 + t.dt.minute).to_numpy()
    eve = np.nonzero((dd < d) & (mi >= 1080))[0]
    if not len(eve): return None
    d0 = dd[eve[-1]]; i0 = int(np.nonzero((dd == d0) & (mi >= 1080))[0][0])
    xs = np.nonzero((dd == d) & (mi >= 955) & (mi < 975))[0]
    if not len(xs): return None
    i1 = int(xs[0])
    o, h, l = b.open.to_numpy(float), b.high.to_numpy(float), b.low.to_numpy(float)
    ef = o[i0] + side * NOISE_HALF; stop = o[i0] - side * stop_dist; xf, why, xi = None, "15:55", i1
    for i in range(i0, i1):
        if side > 0:
            if i > i0 and o[i] <= stop: xf, why, xi = o[i] - NOISE_HALF, "stop (gap)", i; break
            if l[i] <= stop: xf, why, xi = stop - NOISE_HALF, "stop", i; break
        else:
            if i > i0 and o[i] >= stop: xf, why, xi = o[i] + NOISE_HALF, "stop (gap)", i; break
            if h[i] >= stop: xf, why, xi = stop + NOISE_HALF, "stop", i; break
    if xf is None: xf = o[i1] - side * NOISE_HALF
    return dict(entry_ts=t.iloc[i0], exit_ts=t.iloc[xi], entry=round(ef, 2), exit=round(xf, 2), stop=round(stop, 2), why=why,
                net=round(side * (xf - ef) * MULT["MNQ"] - NOISE_FEE, 2))


def month_end_watch(b, spx, start, today):
    """Forward month-end trades since the paper start, plus a preview of the current / next window."""
    rows, months = [], pd.period_range(pd.Timestamp(start), pd.Timestamp(today), freq="M")
    for p in months:
        prev_m = (p - 1)
        base = spx[(spx.index.year == prev_m.year) & (spx.index.month == prev_m.month)]
        for d, trades in month_end_days(p.year, p.month):
            if d < start or d > today: continue
            if not trades: rows.append(dict(date=str(d), status="skipped (early close)")); continue
            before = spx[spx.index.date < d]
            if base.empty or before.empty or before.index[-1].month != p.month:
                rows.append(dict(date=str(d), status="skipped (no S&P closes)")); continue
            mtd = float(before.iloc[-1] / base.iloc[-1] - 1.0); side = -1 if mtd > 0 else (1 if mtd < 0 else 0)
            atr = rth_atr(b, d)
            if side == 0 or atr is None:
                rows.append(dict(date=str(d), status="skipped (flat month-to-date)" if side == 0 else "skipped (fewer than 14 RTH sessions for the stop)"))
                continue
            tr = month_end_trade(b, d, side, 0.5 * atr)
            base_row = dict(date=str(d), side="long" if side > 0 else "short", mtd_pct=round(100 * mtd, 2), spx_close_date=str(before.index[-1].date()))
            rows.append(dict(base_row, status="pending (session not complete)") if tr is None else
                        dict(base_row, status="closed", **{k: (v.strftime("%m-%d %H:%M") if hasattr(v, "strftime") else v) for k, v in tr.items()}))
    closed = [r for r in rows if r["status"] == "closed"]
    nets = [r["net"] for r in closed]
    # preview: the next window (this month if any of its last trading days is still ahead, else next month)
    p = pd.Period(pd.Timestamp(today), freq="M"); nxt = [d for d, ok in month_end_days(p.year, p.month) if d >= today]
    if not nxt:
        p = p + 1; nxt = [d for d, ok in month_end_days(p.year, p.month)]
    days = month_end_days(p.year, p.month)
    base = spx[(spx.index.year == (p - 1).year) & (spx.index.month == (p - 1).month)]
    cur = spx[(spx.index.year == p.year) & (spx.index.month == p.month)]
    mtd_now = float(cur.iloc[-1] / base.iloc[-1] - 1.0) if len(cur) and len(base) else None
    preview = dict(month=str(p), days=[dict(date=str(d), trades=ok) for d, ok in days], mtd_pct=round(100 * mtd_now, 2) if mtd_now is not None else None,
                   side_if_now=("short" if mtd_now > 0 else "long") if mtd_now else None,
                   as_of=str(cur.index[-1].date()) if len(cur) else None)
    trig = ("collecting" if len(nets) < 36 else ("RETIRE (mean <= $0 after 36 trades)" if np.mean(nets) <= 0 else
            ("Nick may order a pre-registered funded test" if np.mean(nets) >= 25 and all(
                np.mean([r["net"] for r in closed if r["side"] == s] or [0.0]) >= 0 for s in ("long", "short")) else "collecting")))
    return dict(name="Month-end rebalancing flow (watch only)", trades=len(nets), net=round(float(sum(nets)), 2),
                mean_per_trade=round(float(np.mean(nets)), 2) if nets else None, wins=sum(1 for x in nets if x > 0),
                longs=sum(1 for r in closed if r["side"] == "long"), shorts=sum(1 for r in closed if r["side"] == "short"),
                rows=rows[-8:], preview=preview, trigger=trig, research=ME_RESEARCH,
                rule="last 3 CME trading days of each month (early-close days skipped): 1 MNQ micro from the 18:00 ET reopen to 15:55, "
                     "short after an up month-to-date S&P 500, long after a down one; stop 0.5 x prior RTH ATR(14); never part of an account card",
                triggers="written 2026-11-13 before any forward trade: RETIRE if the mean is <= $0 after >= 36 forward trades (about a year); if it "
                         "is >= +$25 per trade with long and short trades each >= $0 on average, Nick may order a pre-registered funded add-on test "
                         "(payout_34 method with the random-time drift control). Nothing is promoted automatically.",
                caution="failed its pre-registered training gate (t 1.85 vs 2.73) - this card only collects forward evidence. About 3 trades a "
                        "month, fewer in months with early closes. Signal from the S&P 500 cash index; the stop's ATR comes from the runner's "
                        "Yahoo bars (no roll labels: one roll day a quarter inflates it slightly for a couple of weeks).")


def route_book(rows):
    """Research 1-position routing (payout_lib.route): by decision time, then priority; skip a trade decided inside [entry, exit) of one of
    the last six accepted trades. Overnight rows are not routed (as in research)."""
    acc, keep = [], []
    for r in sorted((r for r in rows if not r["night"]), key=lambda r: (r.get("dec", r["tin"]), r.get("prio", 0))):
        dec = r.get("dec", r["tin"])
        if any(a <= dec < b for a, b in acc[-6:]): continue
        acc.append((r["tin"], r["tout"])); keep.append(r)
    return keep + [r for r in rows if r["night"]]


def route_book_strict(rows):
    """PLAN rule since 2026-11-11 (eval_36, holdout_eval36): CAUSAL one position at a time. Trades in the order their signal is known and
    filled (entry time, then priority); a trade is taken only if no accepted trade is still open at that moment, one per entry minute.
    Overnight rows are not routed (they close before the RTH sleeves trade)."""
    keep, until, last = [], None, None
    for r in sorted((r for r in rows if not r["night"]), key=lambda r: (r["tin"], r.get("prio", 0))):
        if until is not None and (r["tin"] < until or r["tin"] == last): continue
        until = r["tout"] if until is None else max(until, r["tout"]); last = r["tin"]; keep.append(r)
    return keep + [r for r in rows if r["night"]]


def attach_mae(rows, specs, bars):
    """Worst point per micro of each trade from the runner's 1-minute bars (adverse bar extreme between entry and exit), never better than
    the trade's final net. Falls back to min(0, net) when the price or the bars are missing."""
    idx = {k: (b.ts.dt.as_unit("ns").astype("int64").to_numpy(), b.high.to_numpy(float), b.low.to_numpy(float)) for k, b in bars.items()}
    for r in rows:
        if "mae" in r: continue
        inst = r.get("inst") or specs.get(r["sleeve"], {}).get("instrument"); fallback = min(0.0, r["per_micro"])
        if inst not in idx or not r.get("entry") or not r.get("side"): r["mae"] = fallback; continue
        ts, hi, lo = idx[inst]; i0, i1 = np.searchsorted(ts, r["tin"].value), np.searchsorted(ts, r["tout"].value)
        if i1 <= i0: r["mae"] = fallback; continue
        adv = lo[i0:i1].min() if r["side"] > 0 else hi[i0:i1].max()
        r["mae"] = min(r["per_micro"], min(0.0, r["side"] * (adv - float(r["entry"]))) * MULT[inst])
    return rows


def day_pnl_intraday(rows, size_of, stop, night_on):
    """Evaluation day with the research v2 semantics (eval_28): a trade is realised only once it closed before the next entry (no look-ahead);
    while trades are open their worst points add up (same-direction stacking); DLL flattens at -$1,000. Returns (P&L, worst point, trades)."""
    taken = []; worst = 0.0; dll = False
    for r in sorted(rows, key=lambda r: (r["tin"], r["tout"])):
        if r["night"] and not night_on: continue
        q = size_of(r)
        if q < 1: continue
        done = [x for x in taken if x["tout"] < r["tin"] or (x["tout"] == r["tin"] and x["tin"] < r["tin"])]
        real = sum(x["net"] for x in done)
        if real <= -stop or real <= -1000.0: continue
        opn = sum(x["mae"] for x in taken if not any(x is y for y in done))
        mae = min(r.get("mae", min(0.0, r["per_micro"])), r["per_micro"]) * q
        w = real + mae + opn; worst = min(worst, w)
        if w <= -1000.0: dll = True; break
        taken.append(dict(tin=r["tin"], tout=r["tout"], net=r["per_micro"] * q, mae=mae))
    p = -1000.0 if dll else max(sum(x["net"] for x in taken), -1000.0)
    # the DLL flattens the day at its first passage through -$1,000, so the day's worst point is never below it (fixed 2026-11-12,
    # research payout_33: it used to report the full stacked worst point, which could fail an evaluation the DLL would have saved)
    return p, max(min(worst, p), -1000.0), len(taken)


def day_pnl(rows, size_of, stop, night_on):
    """One day's realised P&L: entries in time order, no new entry once realised same-day P&L <= -stop; DLL caps the day at -$1,000."""
    real = 0.0; taken = []
    for r in sorted(rows, key=lambda r: r["tin"]):
        if r["night"] and not night_on: continue
        q = size_of(r)
        if q < 1: continue
        if sum(x["net"] for x in taken if x["tout"] <= r["tin"]) <= -stop: continue
        taken.append(dict(tout=r["tout"], net=r["per_micro"] * q))
    return max(sum(x["net"] for x in taken), -1000.0), len(taken)


# Main funded rule since 2026-11-10 (Nick: "yes"): Antigravity's Fortress 4X, checked in reports/CHECK_FORTRESS_4X_TRAINING.json.
MAIN_LADDER, MAIN_K, MAIN_NAME = ((0.0, 1), (4000.0, 2), (4800.0, 3), (6500.0, 4)), 8500.0, "Fortress 4X"
# previous main rule (payout_24 + cap-aware): ((0.0, 1), (4000.0, 2)), keep $6,000
BALANCED_3X_LADDER, BALANCED_3X_K = ((0.0, 1), (4000.0, 2), (5000.0, 3)), 6500.0  # Consensus Balanced 3x (+23.2% cash, identical risk)
FORTRESS_4X_LADDER, FORTRESS_4X_K = ((0.0, 1), (4000.0, 2), (4800.0, 3), (6500.0, 4)), 8500.0  # Fortress 4X (+35.8% cash, -43% vol risk)
FORTRESS_FAST_4X_LADDER, FORTRESS_FAST_4X_K = ((0.0, 1), (4000.0, 2), (4800.0, 3), (5800.0, 4)), 8500.0  # Improved Option 2 ($35,319 cash, 9.4% vol risk)
CONVEX_4X_LADDER, CONVEX_4X_K = ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8500.0  # Convex 4X Apex ($35,617 pure, $35,512 sprint, 9.4% vol risk)
CHAMELEON_CROWN_LADDER, CHAMELEON_CROWN_K, CHAMELEON_CROWN_GATE = ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8400.0, 8500.0  # Chameleon Crown ($37,027 cash, 221-day P1)
CHAMELEON_FORTIFIED_LADDER, CHAMELEON_FORTIFIED_K, CHAMELEON_FORTIFIED_GATE = ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8500.0, 8550.0  # Chameleon Fortified ($36,672 cash, 221-day P1)
CHAMELEON_3TIER_LADDER, CHAMELEON_3TIER_K, CHAMELEON_3TIER_GATE1, CHAMELEON_3TIER_GATE2 = (
    ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8400.0, 8500.0, 9600.0
)  # Chameleon Apex 3-Tier ($40,635 cash, $10,127 Y1, 221-day P1, 9.4% tail risk)
CHAMELEON_FORTIFIED_3TIER_LADDER, CHAMELEON_FORTIFIED_3TIER_K, CHAMELEON_FORTIFIED_3TIER_GATE1, CHAMELEON_FORTIFIED_3TIER_GATE2 = (
    ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8600.0, 8700.0, 10000.0
)  # Fortified 3-Tier ($40,310 cash, +9.3%/+18.4% vs Fort 4X, +$250 buffer from cliff)
CHAMELEON_SEPTET_APEX_LADDER, CHAMELEON_SEPTET_APEX_K, CHAMELEON_SEPTET_APEX_GATE = (
    ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8600.0, 8650.0
)  # Chameleon Septet Apex ($61,652 cash, +75.3% vs Fort 4X, 221-day P1, 9.4% tail risk)
CHAMELEON_NONET_APEX_LADDER, CHAMELEON_NONET_APEX_K, CHAMELEON_NONET_APEX_GATE, CHAMELEON_NONET_DEEP_THRESH, CHAMELEON_NONET_DEEP_CAP = (
    ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8600.0, 8650.0, 12250.0, 2500.0
)  # Chameleon Nonet Apex ($95,067 cash, +170.2% vs Fort 4X, $17,347 Y1, 221-day P1, 9.4% tail risk)
AEGIS_LADDER, AEGIS_K = ((0.0, 1), (2500.0, 2), (4500.0, 3), (6500.0, 4)), 7500.0   # Antigravity's "Aegis Apex 4X" (comparison only)


def by_day(rows, start_date):
    days = {}
    for r in rows: days.setdefault(r["tout"].date(), []).append(r)
    return days, sorted(d for d in days if d >= start_date)


# KEEP-ALIVE (since 2026-11-12, Nick: "do 2"). Topstep: "If there are no trades placed for 30 days, the account will close" (Combine);
# "XFAs with no trading activity for more than 30 days may be closed" (funded). Training: 7% of Fortress 4X windows had a > 30-day gap
# (longest 49 days); the evaluation book's longest was 29 (payout_33). Rule: on the first weekday >= 25 calendar days after the last trade,
# if nothing has traded since, place a 1-micro MNQ round trip (~$3: $1.22 commission + spread and slippage). Paper simulates it at -$3.
KEEP_ALIVE_DAYS, KEEP_ALIVE_COST = 25, 3.0


def keep_alive_due(last):
    """First weekday on or after `last` + 25 calendar days (exchange holidays are not modelled)."""
    k = pd.Timestamp(last) + pd.Timedelta(days=KEEP_ALIVE_DAYS)
    while k.dayofweek >= 5: k += pd.Timedelta(days=1)
    return k.date()


def keep_alives_before(last, d):
    """Keep-alive dates strictly before `d` when the last trading activity was on `last` (one every 25 quiet days)."""
    out = []
    while keep_alive_due(last) < d:
        last = keep_alive_due(last); out.append(last)
    return out


def alive_info(last, last_trade, kas, today):
    return dict(keep_alives=[str(k) for k in kas], last_trade=str(last_trade) if last_trade else None, last_activity=str(last),
                days_since_activity=(today - last).days if today else None, next_keep_alive=str(keep_alive_due(last)))


def funded(rows, start_date, ladder=MAIN_LADDER, K=MAIN_K, sprint=False, sprint_bal=6000.0, sprint_amt=500.0, intraday=False, extra_q=None,
           today=None):
    """Static Daily Payouts+ funded account: size from the ladder (balance at the prior close), cap-aware trimming to $900 risk per trade,
    $400 account stop at 1x / $700 above, overnight only while balance >= $500, daily payouts above K ($250-$1,500), optional sprint early P1.
    intraday=True: floor and DLL checked on the day's intraday worst point (day_pnl_intraday, research payout_30-34) instead of realised day
    P&L. Rows flagged extra=True (the noise sleeve) trade extra_q[m] micros at ladder multiplier m (0 when missing). Keep-alive round trips
    after 25 quiet days; with `today`, also up to today (and days since the last activity are reported)."""
    days, order = by_day(rows, start_date)
    bal = 0.0; paid = False; since = 0.0; pays = []; closed = None; stage_log = []; stage = 1; hist = []
    last = start_date; last_trade = None; kas = []
    for d in order + [None]:
        upto = d if d is not None else (today + pd.Timedelta(days=1).to_pytimedelta() if today else None)
        for ka in (keep_alives_before(last, upto) if upto else []):
            bal -= KEEP_ALIVE_COST; since -= KEEP_ALIVE_COST; kas.append(ka); last = ka
            hist.append(dict(date=str(ka), pnl=-KEEP_ALIVE_COST, balance=round(bal, 2), payout=0.0, size=f"{stage}x", trades=1, keep_alive=True))
            if bal <= (0.0 if paid else -2000.0): closed = str(ka); break
        if closed or d is None: break
        m = max((mm for th, mm in ladder if bal >= th), default=ladder[0][1])
        if m != stage: stage_log.append(dict(date=str(d), stage=f"{m}x")); stage = m
        def size(r, m=m):
            if r.get("extra"): return int((extra_q or {}).get(m, 0))      # add-on sleeve: fixed micros by ladder stage
            if m == 1: return r["n_base"]
            if r["risk"] is None: return r["n_base"]                      # unknown stop risk: stay at 1x
            return int(min(m * r["n_base"], np.floor(900.0 / r["risk"])))  # trim to the $900 cap instead of skipping
        if intraday: p, w, n = day_pnl_intraday(days[d], size, 400.0 if m == 1 else 700.0, bal >= 500.0)
        else: (p, n), w = day_pnl(days[d], size, 400.0 if m == 1 else 700.0, bal >= 500.0), None
        if n > 0: last = d; last_trade = d
        low = p if w is None else min(w, p)
        if bal + low <= (0.0 if paid else -2000.0):
            bal += low; closed = str(d); hist.append(dict(date=str(d), pnl=round(low, 2), balance=round(bal, 2))); break
        bal += p; since += p
        w = 0.0
        payout_made = False
        if sprint and not paid and bal >= sprint_bal:
            w = sprint_amt; bal -= w; paid = True; since = 0.0; pays.append(dict(date=str(d), amount=round(w, 2))); payout_made = True
        if not payout_made and (since > 0 or not paid) and bal - K >= 250.0:
            w = min(1500.0, bal - K); bal -= w; paid = True; since = 0.0; pays.append(dict(date=str(d), amount=round(w, 2)))
        hist.append(dict(date=str(d), pnl=round(p, 2), balance=round(bal, 2), payout=round(w, 2), size=f"{m}x", trades=n))
    return dict(balance=round(bal, 2), floor=0.0 if paid else -2000.0, size_stage=f"{stage}x", payouts=pays, payouts_count=len(pays),
                withdrawn=round(sum(x["amount"] for x in pays), 2), closed_on=closed, stage_changes=stage_log, days=hist[-30:],
                next_payout_needs=None if closed else round(max(0.0, K + 250.0 - bal), 2), keep=K,
                ladder=" / ".join(f"{mm}x from ${th:,.0f}" if th else f"{mm}x" for th, mm in ladder),
                check="intraday floor and $1,000 daily limit" if intraday else "floor on realised day P&L", **alive_info(last, last_trade, kas, today))


def k3_rule(bal, day, tgt):
    return 3


def combined_rule(bal, day, tgt):
    """eval_8 DEF + ENDGAME: k3; k2 at <= -$500; k1 at <= -$1,000; from day 60, more than $1,000 short and above -$500: k5."""
    if day >= 60 and bal < tgt - 1000.0 and bal > -500.0: return 5
    return 1 if bal <= -1000.0 else (2 if bal <= -500.0 else 3)


def evaluation(rows, start_date, rule=k3_rule, today=None):
    """$50K Static Combine from start_date: size min(k x base, floor($900 / stop risk)), k = rule(balance at prior close, calendar day, target)."""
    today = today or pd.Timestamp.now(tz=NY).date()
    days, order = by_day(rows, start_date)
    bal = 0.0; best = 0.0; status = "open"; when = None; end = start_date + pd.Timedelta(days=90).to_pytimedelta()
    last = start_date; last_trade = None; kas = []          # the 30-day inactivity clock starts at purchase
    for d in order + [None]:
        upto = min(d, end) if d is not None else min(today + pd.Timedelta(days=1).to_pytimedelta(), end)
        for ka in keep_alives_before(last, upto):            # keep-alive round trips (since 2026-11-12)
            bal -= KEEP_ALIVE_COST; kas.append(ka); last = ka
            if bal <= -2000.0: status = "failed"; when = str(ka); break
        if status != "open" or d is None: break
        if d >= end: status = "expired"; break
        k = rule(bal, (d - start_date).days, max(4000.0, best / 0.55))
        def esize(r, k=k):
            if r["risk"] is None: return 0
            return int(min(k * r["n_base"], np.floor(900.0 / r["risk"])))
        p, w, n = day_pnl_intraday(days[d], esize, 400.0 if k == 1 else 700.0, True)
        if n > 0: last = d; last_trade = d
        if bal + min(w, p) <= -2000.0: bal += min(w, p); status = "failed"; when = str(d); break   # static floor checked intraday (since 2026-11-11)
        bal += p; best = max(best, p)
        if bal >= max(4000.0, best / 0.55): status = "passed"; when = str(d); break
    if status == "open" and today >= end: status = "expired"
    tgt = max(4000.0, best / 0.55)
    return dict(status=status, on=when, balance=round(bal, 2), target=round(tgt, 2), best_day=round(best, 2),
                days_left=max(0, (end - today).days), expires=str(end),
                size_now=f"{rule(bal, (today - start_date).days, tgt)}x" if status == "open" else None,
                **alive_info(last, last_trade, kas, today if status == "open" else None))


def rolling(rows, first, rule, today=None):
    """One attempt started on every weekday from first to today (forward evidence; overlapping attempts share trades)."""
    today = today or pd.Timestamp.now(tz=NY).date()
    st = [evaluation(rows, s.date(), rule, today)["status"] for s in pd.bdate_range(first, today)]
    return dict(starts=len(st), passed=st.count("passed"), failed=st.count("failed"), expired=st.count("expired"), open=st.count("open"))


def replay(rows, start_date, today=None):
    return dict(funded=funded(rows, start_date), evaluation=evaluation(rows, start_date, k3_rule, today))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--root", required=True); a = ap.parse_args(argv)
    root = Path(a.root); here = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(here / "src"))
    from quant_futures import ensemble_paper as ep
    specs = {sl["name"]: sl for k in (V52, NIGHT, EXTRA) for sl in ep.CANDIDATES[k]["sleeves"]}
    bars = {}
    for inst in ("MNQ", "MES"):
        b = pd.read_csv(root / "bars" / f"{inst}_1m.csv")
        tcol = next(c for c in b.columns if "time" in c.lower() or c.lower() in ("ts", "timestamp"))
        cols = ["ts", "open", "high", "low", "close"] + (["volume"] if "volume" in b.columns else [])
        bars[inst] = b.rename(columns={tcol: "ts"}).assign(ts=lambda x: pd.to_datetime(x.ts, utc=True))[cols]
    v = stop_risk_per_micro(read_trades(root / V52 / "ledger.jsonl"), specs, bars)
    n = read_trades(root / NIGHT / "ledger.jsonl")
    start = pd.Timestamp((root / "start.txt").read_text().strip()).date() if (root / "start.txt").exists() else min(
        [pd.Timestamp(t["exit_ts"]).tz_convert(NY).date() for t in v + n], default=pd.Timestamp.now(tz=NY).date())
    today = pd.Timestamp.now(tz=NY).date()
    book_f = attach_mae(group_intraday(v) + night_rows(n), specs, bars)
    res = dict(funded=funded(book_f, start, today=today), evaluation=evaluation(book_f, start, k3_rule, today))
    res["funded"]["name"] = MAIN_NAME
    # FUNDED CHALLENGER (since 2026-11-12, Nick: "do 1"): Fortress 4X + the noise-area sleeve, 1 micro only at 4x, intraday floor / DLL check
    noise = attach_mae(noise_rows(bars["MNQ"]), specs, bars); sess = noise_sessions(bars["MNQ"])
    fwd = [r for r in noise if r["tout"].date() >= start]; mean = float(np.mean([r["per_micro"] for r in fwd])) if fwd else None
    ch = funded(book_f + noise, start, MAIN_LADDER, MAIN_K, intraday=True, extra_q=NOISE_Q, today=today)
    same = funded(book_f, start, MAIN_LADDER, MAIN_K, intraday=True, today=today)
    trig = "collecting" if len(fwd) < 150 else ("RETIRE the noise sleeve" if mean <= -10.0 else ("promotion can be considered" if mean > 0 else "collecting"))
    res["funded_challenger"] = dict(
        ch, name="Fortress 4X + noise-area sleeve (1 micro, only at 4x)",
        same_check=dict(balance=same["balance"], withdrawn=same["withdrawn"], payouts_count=same["payouts_count"], size_stage=same["size_stage"],
                        closed_on=same["closed_on"]),
        noise=dict(trades=len(fwd), net_per_micro=round(sum(r["per_micro"] for r in fwd), 2), mean_per_trade=round(mean, 2) if fwd else None,
                   wins=sum(1 for r in fwd if r["per_micro"] > 0), sessions=len(sess), sessions_needed=NOISE_LOOK + 1,
                   first_signal_day=str(sess[NOISE_LOOK]["d"]) if len(sess) > NOISE_LOOK else None, trigger=trig,
                   last=[dict(date=str(r["tout"].date()), side="long" if r["side"] > 0 else "short", entry=r["tin"].strftime("%H:%M"),
                              exit=r["tout"].strftime("%H:%M"), net=round(r["per_micro"], 2)) for r in fwd[-5:]]),
        rule="Fortress 4X (1x < $4,000, 2x from $4,000, 3x from $4,800, 4x from $6,500; payouts above $8,500; $900 risk cap per trade) + 1 "
             "noise-area micro as a separate position only while at 4x; floor and $1,000 daily limit checked intraday",
        triggers="written 2026-11-12 before any forward noise trade: RETIRE the noise sleeve if, after >= 150 forward trades, it averages <= -$10 "
                 "per trade (per micro, after costs). Promotion is Nick's call, and only once it has >= 150 forward trades averaging > $0 and this "
                 "card's withdrawn + balance >= Fortress 4X's on the same check. Nothing is promoted automatically.",
        caution="training 2010-23 only: $35,788 vs $32,597 per 24 months (+9.8%), same closures, beats random-side and always-long placebos; the "
                "2016-21 half leans on 2018 (+2.9% without it); the signal has never been run on 2024-26. Bars are the runner's Yahoo series "
                "(no contract-roll handling: one band per quarter may be off). Until the balance reaches $6,500 this card equals Fortress 4X.")
    # MONTH-END REBALANCING WATCH (since 2026-11-13, Nick: "go ahead"; research rebal_1): watch only, never part of an account card.
    # Isolated so that a feed or code failure here can never break the account cards.
    try:
        res["month_end_watch"] = month_end_watch(bars["MNQ"], spx_daily(root), start, today)
    except Exception as e:  # noqa: BLE001
        res["month_end_watch"] = dict(name="Month-end rebalancing flow (watch only)", error=f"{type(e).__name__}: {e}", trades=0, rows=[])
    # EVALUATION challenger (eval_8): v5.3 + the two Codex sleeves, re-routed, defensive + endgame sizing
    x = stop_risk_per_micro([dict(t, bar_minutes=int(specs[t["sleeve"]].get("bar_minutes", 15))) for t in read_trades(root / EXTRA / "ledger.jsonl")
                             if t["sleeve"] in EXTRA_PRIO], specs, bars)
    prio = {sl["name"]: i for i, sl in enumerate(ep.CANDIDATES[V52]["sleeves"])}
    vr = group_intraday(v)
    for r in vr:
        r["prio"] = prio.get(r["sleeve"], 0); r["dec"] = r["tin"] - pd.Timedelta(minutes=int(specs.get(r["sleeve"], {}).get("bar_minutes", 15)))
    pool = attach_mae(vr + extra_rows(x) + night_rows(n), specs, bars)
    book_c = route_book(pool); book_s = route_book_strict(pool); book_3 = attach_mae(group_intraday(v) + night_rows(n), specs, bars)
    res["evaluation_strict"] = dict(evaluation(book_s, start, combined_rule), name="one position at a time + 2 Codex sleeves, defensive + endgame",
                                    rolling=rolling(book_s, start, combined_rule), status_note="the plan for a real Combine (Nick 2026-11-11)",
                                    extra_taken=sum(1 for r in book_s if r["sleeve"] in EXTRA_PRIO), trades=sum(1 for r in book_s if not r["night"]),
                                    rule="causal one-position routing; 3x; 2x at <= -$500; 1x at <= -$1,000; from day 60, > $1,000 short and above -$500: 5x; $900 risk cap per trade",
                                    caution="training 51.5 / 61.1 (vs 49.8 / 60.0 overlapping), one-shot 2024-25 45.3% vs 41.4%, 2026 63.1% vs 34.4% (holdout_eval36); forward paper decides")
    res["evaluation"].update(name="v5.3 book at 3x, champion", rolling=rolling(book_3, start, k3_rule))
    res["evaluation_combined"] = dict(evaluation(book_c, start, combined_rule), name="v5.3 + 2 Codex sleeves, defensive + endgame",
                                      rolling=rolling(book_c, start, combined_rule), extra_trades=len(x),
                                      extra_taken=sum(1 for r in book_c if r["sleeve"] in EXTRA_PRIO),
                                      extra_net_per_micro=round(sum(t["net"] / max(1, t.get("qty", 1)) for t in x), 2),
                                      rule="3x; 2x at <= -$500; 1x at <= -$1,000; from day 60, > $1,000 short and above -$500: 5x; $900 risk cap per trade",
                                      caution="chosen after seeing all of 2010-23 (training 55.2% per attempt after the eval_28 look-ahead fix; was quoted 60.0%; no clean holdout left); forward paper decides")
    n915 = read_trades(root / NIGHT_0915 / "ledger.jsonl")
    res["aegis"] = dict(funded(group_intraday(v) + night_rows(n915), start, AEGIS_LADDER, AEGIS_K, today=today), overnight_exit="09:15 ET", overnight_trades=len(n915),
                        name="Aegis Apex 4X (Antigravity)", status="comparison only, not adopted",
                        caution="training: +45% dollars vs the main rule with the same end-of-day closures, but worst-case intraday closures in the cost+edge stress test 15.8% vs 5.0%; 09:15 exit not better in both halves (reports/V55_CHECK_AEGIS_TRAINING.json)")
    names = {f"AG_CRABEL15_D_1c_{v}": "Crabel 15-min opening-range breakout" for v in ("v52", "v53")}
    names.update({f"AG_CRABEL15_D_GAP_{v}": "Crabel gap-continuation add-on (+1 micro when the trade agrees with the opening gap)" for v in ("v52", "v53")})
    names.update({f"AG_TRD60_D_1c_{v}": "60-min trend" for v in ("v52", "v53")}); names.update({f"AG_MES_TRD30_D_1c_{v}": "30-min trend" for v in ("v52", "v53")})
    names.update({"AG_TRD30PM_1c_v52": "30-min afternoon trend",
             "OVN_DIP2_STOP_1c": "Overnight reopen dip, 0.55% stop (only once the balance is >= $500)",
             "MNQ_BRK_E_2c": "Codex MNQ 15-min breakout (challenger evaluation only)", "MES_MOM_3c": "Codex MES 15-min momentum (challenger evaluation only)",
             "NOISE_MNQ_P": "Noise-area intraday momentum, 30-min checks (funded challenger only, 1 micro at 4x)"})
    res["strategies"] = [dict(sleeve=sl["name"], name=names.get(sl["name"], sl["name"]), instrument=sl["instrument"], bar_minutes=int(sl.get("bar_minutes", 15)),
                              trades=sum(1 for t in v + n if t["sleeve"] == sl["name"]), net_1x=round(sum(t["net"] for t in v + n if t["sleeve"] == sl["name"]), 2))
                         for sl in ep.CANDIDATES[V52]["sleeves"] + ep.CANDIDATES[NIGHT]["sleeves"]]
    res["strategies"] += [dict(sleeve=sl["name"], name=names[sl["name"]], instrument=sl["instrument"], bar_minutes=int(sl.get("bar_minutes", 15)),
                               trades=sum(1 for t in x if t["sleeve"] == sl["name"]),
                               net_1x=round(sum(t["net"] / max(1, t.get("qty", 1)) for t in x if t["sleeve"] == sl["name"]), 2), challenger=True)
                          for sl in ep.CANDIDATES[EXTRA]["sleeves"] if sl["name"] in EXTRA_PRIO]
    res["strategies"].append(dict(sleeve="NOISE_MNQ_P", name=names["NOISE_MNQ_P"], instrument="MNQ", bar_minutes=1, trades=len(fwd),
                                  net_1x=round(sum(r["per_micro"] for r in fwd), 2), challenger=True))
    st = json.loads((root / V52 / "status.json").read_text()) if (root / V52 / "status.json").exists() else {}
    res.update(updated=pd.Timestamp.now(tz="UTC").isoformat(), paper_start=str(start), source_ledgers=[V52, NIGHT, EXTRA], book=BOOK,
               runner_intrabar_drawdown_v52=st.get("intrabar_drawdown"), trades_without_risk=sum(1 for t in v if t.get("risk") is None),
               rules="see scripts/paper_account_static_daily.py docstring; paper only, simulated fills, no orders routed")
    out = root / "_account_static_daily"; out.mkdir(exist_ok=True); prev = {}
    if (out / "status.json").exists():
        try: prev = json.loads((out / "status.json").read_text())
        except Exception: prev = {}
    (out / "status.json").write_text(json.dumps(res, indent=1, default=str))
    dash = root / "dashboard.json"
    if dash.exists():
        d = json.loads(dash.read_text())
        d["account_static_daily"] = dict(funded_balance=res["funded"]["balance"], funded_payouts=res["funded"]["payouts_count"], funded_withdrawn=res["funded"]["withdrawn"],
                                         size_stage=res["funded"]["size_stage"], evaluation=res["evaluation"]["status"], evaluation_balance=res["evaluation"]["balance"],
                                         aegis_balance=res["aegis"]["balance"], aegis_payouts=res["aegis"]["payouts_count"], aegis_stage=res["aegis"]["size_stage"],
                                         evaluation_combined=res["evaluation_combined"]["status"], evaluation_combined_balance=res["evaluation_combined"]["balance"],
                                         evaluation_strict=res["evaluation_strict"]["status"], evaluation_strict_balance=res["evaluation_strict"]["balance"],
                                         funded_challenger_balance=res["funded_challenger"]["balance"], funded_challenger_payouts=res["funded_challenger"]["payouts_count"],
                                         noise_trades=res["funded_challenger"]["noise"]["trades"], noise_net_per_micro=res["funded_challenger"]["noise"]["net_per_micro"],
                                         funded_days_since_trade=res["funded"]["days_since_activity"], plan_days_since_trade=res["evaluation_strict"].get("days_since_activity"),
                                         month_end_trades=res["month_end_watch"].get("trades", 0), month_end_net=res["month_end_watch"].get("net", 0.0))
        dash.write_text(json.dumps(d, indent=1, sort_keys=True, default=str))
    pf, pe, pa, pc = prev.get("funded", {}), prev.get("evaluation", {}), prev.get("aegis", {}), prev.get("evaluation_combined", {})
    # keep-alive warnings (since 2026-11-12) for the two cards that stand for real accounts: the funded rule and the evaluation PLAN
    for key, label in (("funded", "Funded account"), ("evaluation_strict", "Evaluation PLAN")):
        cur, old = res[key], prev.get(key, {})
        ds, ods = cur.get("days_since_activity"), old.get("days_since_activity")
        if ds is not None and ds >= 20 and (ods is None or ods < 20):
            ep.notify(f"{label}: keep-alive due", f"no trade for {ds} days; on a real account place a 1-micro round trip by {cur['next_keep_alive']} "
                                                   "(Topstep closes accounts after 30 days without a trade)")
        if len(cur.get("keep_alives", [])) > len(old.get("keep_alives", [])):
            ep.notify(f"{label}: keep-alive placed (paper)", f"1-micro round trip on {cur['keep_alives'][-1]} after 25 quiet days, -${KEEP_ALIVE_COST:.0f}")
    me, pme = res["month_end_watch"], prev.get("month_end_watch", {})
    if me.get("trades", 0) > pme.get("trades", 0):
        last = [r for r in me.get("rows", []) if r.get("status") == "closed"][-1:]
        if last:
            r = last[0]
            ep.notify("Month-end watch (paper only)", f"{r['date']}: {r['side']} MNQ (S&P month-to-date {r['mtd_pct']:+.2f}%), {r['why']}, "
                                                      f"${r['net']:+,.2f}; {me['trades']} forward trades, ${me['net']:+,.2f} total")
    if me.get("trigger", "collecting") != pme.get("trigger", "collecting"):
        ep.notify("Month-end watch trigger", f"{me['trigger']} after {me['trades']} forward trades")
    pch = prev.get("funded_challenger", {})
    if res["funded_challenger"]["payouts_count"] > pch.get("payouts_count", 0):
        last = res["funded_challenger"]["payouts"][-1]
        ep.notify("Funded challenger (noise at 4x): payout", f"${last['amount']:,.2f} on {last['date']}; balance ${res['funded_challenger']['balance']:,.2f}")
    if res["funded_challenger"]["closed_on"] and not pch.get("closed_on"):
        ep.notify("Funded challenger: CLOSED", f"floor reached on {res['funded_challenger']['closed_on']}")
    if res["funded_challenger"]["noise"]["trigger"] != pch.get("noise", {}).get("trigger", "collecting"):
        ep.notify("Noise sleeve trigger", f"{res['funded_challenger']['noise']['trigger']} after {res['funded_challenger']['noise']['trades']} forward trades")
    if res["evaluation_combined"]["status"] != pc.get("status", "open") and res["evaluation_combined"]["status"] != "open":
        ep.notify(f"Paper evaluation (challenger): {res['evaluation_combined']['status']}",
                  f"balance ${res['evaluation_combined']['balance']:,.2f} on {res['evaluation_combined']['on']}")
    ps = prev.get("evaluation_strict", {})
    if res["evaluation_strict"]["status"] != ps.get("status", "open") and res["evaluation_strict"]["status"] != "open":
        ep.notify(f"Paper evaluation (PLAN, one position): {res['evaluation_strict']['status']}",
                  f"balance ${res['evaluation_strict']['balance']:,.2f} on {res['evaluation_strict']['on']}")
    if res["aegis"]["payouts_count"] > pa.get("payouts_count", 0):
        last = res["aegis"]["payouts"][-1]; ep.notify("Aegis paper: payout", f"${last['amount']:,.2f} on {last['date']}; balance ${res['aegis']['balance']:,.2f}")
    if res["aegis"]["closed_on"] and not pa.get("closed_on"):
        ep.notify("Aegis paper: CLOSED", f"floor reached on {res['aegis']['closed_on']}")
    if res["funded"]["payouts_count"] > pf.get("payouts_count", 0):
        last = res["funded"]["payouts"][-1]; ep.notify("Paper account: payout", f"${last['amount']:,.2f} on {last['date']}; balance ${res['funded']['balance']:,.2f}, {res['funded']['payouts_count']} payouts")
    if pf and res["funded"]["size_stage"] != pf.get("size_stage"):
        ep.notify("Paper account: size stage", f"now {res['funded']['size_stage']} at balance ${res['funded']['balance']:,.2f}")
    if res["funded"]["closed_on"] and not pf.get("closed_on"):
        ep.notify("Paper account: CLOSED", f"floor reached on {res['funded']['closed_on']}")
    if res["evaluation"]["status"] != pe.get("status", "open") and res["evaluation"]["status"] != "open":
        ep.notify(f"Paper evaluation: {res['evaluation']['status']}", f"balance ${res['evaluation']['balance']:,.2f} on {res['evaluation']['on']}")
    print(json.dumps({k: res[k] for k in ("funded", "evaluation", "evaluation_combined")}, default=str)[:2500])


if __name__ == "__main__":
    main()

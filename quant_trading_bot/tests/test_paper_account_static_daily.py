"""Fixtures for scripts/paper_account_static_daily.py replay (synthetic trades, no data files)."""
import importlib.util
from pathlib import Path
import pandas as pd

spec = importlib.util.spec_from_file_location("acct", Path(__file__).resolve().parents[1] / "scripts" / "paper_account_static_daily.py")
acct = importlib.util.module_from_spec(spec); spec.loader.exec_module(acct)
NY = "America/New_York"


def day(d, net, risk=150.0, n_base=1, night=False, hh=10):
    t = pd.Timestamp(f"{d} {hh:02d}:00", tz=NY)
    return dict(tin=t, tout=t + pd.Timedelta(hours=2), n_base=n_base, per_micro=net / n_base, risk=risk, night=night, sleeve="X")


def days(n, net, start="2026-01-05", **kw):
    return [day(str(d.date()), net, **kw) for d in pd.bdate_range(start, periods=n)]


def test_no_trades():
    r = acct.replay([], pd.Timestamp("2026-01-05").date(), today=pd.Timestamp("2026-01-06").date())
    assert r["funded"]["balance"] == 0 and r["funded"]["payouts_count"] == 0 and r["evaluation"]["status"] == "open"


def test_static_floor_before_first_payout():
    r = acct.replay(days(5, -450.0), pd.Timestamp("2026-01-05").date())
    assert r["funded"]["closed_on"] == "2026-01-09"           # -450 x 5 = -2,250 <= -2,000 on day 5


def test_stage_and_payouts():
    r = acct.replay(days(40, 300.0), pd.Timestamp("2026-01-05").date())
    f = r["funded"]
    assert any(s["stage"] == "2x" for s in f["stage_changes"])      # 2x once the balance reaches $4,000
    assert f["payouts_count"] > 0 and all(250.0 <= p["amount"] <= 1500.0 for p in f["payouts"])
    assert f["balance"] >= 6000.0 and f["floor"] == 0.0


def test_2x_trims_high_risk_trades():
    rows = days(14, 300.0) + [day("2026-01-26", 300.0, risk=500.0)]       # balance >= $4,000 by then; 2 x $500 > $900 -> trimmed to 1
    r = acct.replay(rows, pd.Timestamp("2026-01-05").date())
    assert r["funded"]["days"][-1]["trades"] == 1 and r["funded"]["days"][-1]["pnl"] == 300.0   # 1 micro, not 2, not skipped
    r2 = acct.replay(days(14, 300.0) + [day("2026-01-26", 300.0, risk=400.0)], pd.Timestamp("2026-01-05").date())
    assert r2["funded"]["days"][-1]["pnl"] == 600.0                      # 2 x $400 = $800 <= $900: full 2x


def test_evaluation_pass_with_consistency():
    r = acct.replay(days(30, 100.0, risk=100.0), pd.Timestamp("2026-01-05").date())   # 3 micros x $100 = $300/day -> $4,000 on day 14
    assert r["evaluation"]["status"] == "passed" and r["evaluation"]["on"] == "2026-01-22"
    big = acct.replay([day("2026-01-05", 1000.0, risk=100.0)] + days(20, 50.0, start="2026-01-06", risk=100.0), pd.Timestamp("2026-01-05").date())
    assert big["evaluation"]["target"] > 4000.0                 # $3,000 best day / 0.55 = $5,455 target


def test_aegis_ladder_and_cushion():
    f = acct.funded(days(60, 400.0, risk=100.0), pd.Timestamp("2026-01-05").date(), acct.AEGIS_LADDER, acct.AEGIS_K)
    stages = [s["stage"] for s in f["stage_changes"]]
    assert stages[:3] == ["2x", "3x", "4x"]                              # $2,500 / $4,500 / $6,500 steps
    assert f["payouts_count"] > 0 and f["balance"] >= 7500.0 and f["keep"] == 7500.0
    main = acct.funded(days(60, 400.0, risk=100.0), pd.Timestamp("2026-01-05").date())
    assert [s["stage"] for s in main["stage_changes"]][:3] == ["2x", "3x", "4x"] and main["keep"] == 8500.0   # Fortress 4X main rule
    assert main["balance"] >= 8500.0 and all(250.0 <= p["amount"] <= 1500.0 for p in main["payouts"])


def test_combined_rule_steps():
    r = acct.combined_rule
    assert [r(0, 0, 4000), r(-600, 10, 4000), r(-1200, 10, 4000)] == [3, 2, 1]               # defensive ladder
    assert [r(100, 61, 4000), r(3500, 61, 4000), r(-600, 61, 4000), r(100, 59, 4000)] == [5, 3, 2, 3]   # endgame only late, short, above -$500


def test_combined_defensive_slows_the_fail():
    rows = days(6, -300.0, risk=100.0)                                       # -$300 per micro every day
    k3 = acct.evaluation(rows, pd.Timestamp("2026-01-05").date(), acct.k3_rule)
    cb = acct.evaluation(rows, pd.Timestamp("2026-01-05").date(), acct.combined_rule)
    assert k3["status"] == "failed" and k3["on"] == "2026-01-07"              # -900 x 3
    assert cb["status"] == "failed" and cb["on"] == "2026-01-08"              # -900, -600 (2x), -300 (1x), -300 (1x)


def test_combined_endgame_size_now():
    rows = days(50, 10.0, risk=100.0)                                         # +$30 a day at 3x: far short of $4,000 by day 60
    e = acct.evaluation(rows, pd.Timestamp("2026-01-05").date(), acct.combined_rule, today=pd.Timestamp("2026-03-10").date())
    assert e["status"] == "open" and e["size_now"] == "5x"


def test_route_book_one_position():
    a = dict(day("2026-01-05", 100.0), prio=0, dec=pd.Timestamp("2026-01-05 09:45", tz=NY))        # 10:00-12:00
    b = dict(day("2026-01-05", 100.0, hh=11), prio=10, dec=pd.Timestamp("2026-01-05 10:45", tz=NY))  # decided inside a -> skipped
    c = dict(day("2026-01-05", 100.0, hh=12), prio=11, dec=pd.Timestamp("2026-01-05 12:00", tz=NY))  # a has exited -> kept
    n = day("2026-01-05", 50.0, night=True, hh=1)
    kept = acct.route_book([b, c, a, n])
    assert [r["tin"].hour for r in kept] == [10, 12, 1]


def test_rolling_starts():
    rows = days(30, 100.0, risk=100.0)
    r = acct.rolling(rows, pd.Timestamp("2026-01-05").date(), acct.k3_rule, today=pd.Timestamp("2026-02-13").date())
    assert r["starts"] == 30 and r["passed"] + r["failed"] + r["expired"] + r["open"] == 30 and r["passed"] >= 1


def test_chameleon_and_sprint():
    assert acct.CHAMELEON_CROWN_K == 8400.0
    assert acct.CHAMELEON_CROWN_GATE == 8500.0
    assert acct.CHAMELEON_FORTIFIED_K == 8500.0
    assert acct.CHAMELEON_FORTIFIED_GATE == 8550.0
    assert acct.CHAMELEON_3TIER_K == 8400.0
    assert acct.CHAMELEON_3TIER_GATE1 == 8500.0
    assert acct.CHAMELEON_3TIER_GATE2 == 9600.0
    assert acct.CHAMELEON_FORTIFIED_3TIER_K == 8600.0
    assert acct.CHAMELEON_FORTIFIED_3TIER_GATE1 == 8700.0
    assert acct.CHAMELEON_FORTIFIED_3TIER_GATE2 == 10000.0
    assert acct.CHAMELEON_SEPTET_APEX_K == 8600.0
    assert acct.CHAMELEON_SEPTET_APEX_GATE == 8650.0
    # Test sprint mode takes $500 at $6,000
    rows = days(30, 300.0, risk=100.0)
    f = acct.funded(rows, pd.Timestamp("2026-01-05").date(), acct.CHAMELEON_CROWN_LADDER, acct.CHAMELEON_CROWN_K, sprint=True)
    assert f["payouts_count"] >= 1
    assert f["payouts"][0]["amount"] == 500.0
    assert f["floor"] == 0.0


def _t(hh, mm, hh2, mm2, net, mae, prio=0, d="2026-01-05", sleeve="X"):
    a, b = pd.Timestamp(f"{d} {hh:02d}:{mm:02d}", tz=NY), pd.Timestamp(f"{d} {hh2:02d}:{mm2:02d}", tz=NY)
    return dict(tin=a, tout=b, n_base=1, per_micro=net, mae=mae, risk=100.0, night=False, sleeve=sleeve, prio=prio)


def test_strict_router_is_causal_and_one_position():
    early = _t(10, 15, 10, 45, 50.0, -20.0, prio=5)        # known and filled at 10:15
    late = _t(11, 0, 12, 0, 80.0, -30.0, prio=0)           # a 60m signal known only at 11:00 (its bar started 10:00)
    overlap = _t(11, 30, 12, 30, 40.0, -10.0, prio=1)      # would stack on `late`
    kept = acct.route_book_strict([late, overlap, early])
    assert early in kept and late in kept and overlap not in kept     # the later-known trade cannot block the earlier one
    same = acct.route_book_strict([_t(10, 0, 10, 30, 1.0, 0.0, prio=1), _t(10, 0, 10, 0, -5.0, -5.0, prio=0)])
    assert len(same) == 1 and same[0]["prio"] == 0                     # one trade per entry minute, priority decides


def test_intraday_stacking_and_floor():
    a = _t(10, 0, 12, 0, 100.0, -300.0); b = _t(10, 30, 11, 30, 50.0, -400.0)   # b opens while a is open: worst points stack
    p, w, n = acct.day_pnl_intraday([a, b], lambda r: 1, 700.0, True)
    assert n == 2 and p == 150.0 and w == -700.0
    p2, w2, _ = acct.day_pnl_intraday([dict(a, mae=-700.0), dict(b, mae=-400.0)], lambda r: 1, 700.0, True)
    assert p2 == -1000.0                                               # stacked worst point reaches the DLL: flattened at -$1,000
    rows = days(3, -450.0, risk=100.0)                                   # 3 x 3 micros x -$450 ... floor reached intraday on a positive day:
    rows = [dict(r, per_micro=-200.0, mae=-200.0) for r in rows] + [dict(day("2026-01-08", 10.0, risk=100.0), mae=-300.0)]
    ev = acct.evaluation(rows, pd.Timestamp("2026-01-05").date(), acct.k3_rule, today=pd.Timestamp("2026-01-20").date())
    assert ev["status"] == "failed" and ev["on"] == "2026-01-08"         # -1,800 after 3 days; day 4 dips 3 x -300 = -900 before closing +30


# ---- 2026-11-12: keep-alive, DLL worst cap, noise-area sleeve, funded challenger
def D(s):
    return pd.Timestamp(s).date()


def test_keep_alive_due_and_weekend_shift():
    assert acct.keep_alive_due(D("2026-01-05")) == D("2026-01-30")          # Mon + 25 = Fri
    assert acct.keep_alive_due(D("2026-01-06")) == D("2026-02-02")          # Tue + 25 = Sat -> Mon
    assert acct.keep_alives_before(D("2026-01-05"), D("2026-01-30")) == []   # due day itself not yet passed
    assert acct.keep_alives_before(D("2026-01-05"), D("2026-03-01")) == [D("2026-01-30"), D("2026-02-24")]


def test_keep_alive_funded_between_trades_and_up_to_today():
    rows = [day("2026-01-05", 100.0), day("2026-02-20", 100.0)]
    f = acct.funded(rows, D("2026-01-05"))
    assert f["keep_alives"] == ["2026-01-30"] and f["balance"] == 197.0       # one $3 round trip after 25 quiet days
    g = acct.funded(rows, D("2026-01-05"), today=D("2026-03-20"))
    assert g["keep_alives"] == ["2026-01-30", "2026-03-17"] and g["balance"] == 194.0
    assert g["days_since_activity"] == 3 and g["next_keep_alive"] == "2026-04-13" and g["last_trade"] == "2026-02-20"


def test_keep_alive_evaluation_clock_starts_at_purchase():
    e = acct.evaluation([day("2026-02-10", 100.0, risk=100.0)], D("2026-01-05"), acct.k3_rule, today=D("2026-02-11"))
    assert e["keep_alives"] == ["2026-01-30"] and e["balance"] == 297.0       # -3, then 3 micros x $100
    quiet = acct.evaluation([], D("2026-01-05"), acct.k3_rule, today=D("2026-03-01"))
    assert quiet["keep_alives"] == ["2026-01-30", "2026-02-24"] and quiet["status"] == "open" and quiet["days_since_activity"] == 5


def test_dll_day_worst_capped_at_limit():
    a = _t(10, 0, 12, 0, 100.0, -700.0); b = _t(10, 30, 11, 30, 50.0, -600.0)   # stacked worst -1,300 -> DLL at -1,000
    p, w, n = acct.day_pnl_intraday([a, b], lambda r: 1, 2000.0, True)
    assert p == -1000.0 and w == -1000.0


def _sessions(n=15, start="2026-02-02"):
    """n RTH sessions of synthetic MNQ 1-minute bars: 14 quiet ones (|move| <= 0.05%), then a breakout above the band at 10:00."""
    rows = []
    for k, d in enumerate(pd.bdate_range(start, periods=n)):
        t0 = pd.Timestamp(f"{d.date()} 09:30", tz=NY)
        for m in range(390):
            if k < n - 1:
                c = 20000.0 * (1 + 0.0005 * np.sin(m / 7.0)); o = h = l = c
            else:
                o = 20000.0 if m <= 29 else 20100.0; c = 20000.0 if m < 29 else (20100.0 if m < 389 else 20200.0)
                h, l = max(o, c), min(o, c)
            rows.append(dict(ts=(t0 + pd.Timedelta(minutes=m)).tz_convert("UTC"), open=o, high=h, low=l, close=c, volume=1.0))
    return pd.DataFrame(rows)


import numpy as np  # noqa: E402


def test_noise_rows_breakout_long_to_close():
    b = _sessions()
    assert len(acct.noise_sessions(b)) == 15 and acct.noise_rows(b.iloc[: 390 * 14]) == []     # 14 sessions: still warming up
    r = acct.noise_rows(b)
    assert len(r) == 1
    t = r[0]; h = acct.NOISE_HALF
    assert t["side"] == 1 and t["tin"].strftime("%H:%M") == "10:00" and t["tout"].strftime("%H:%M") == "16:00" and t["extra"]
    assert abs(t["per_micro"] - (((20200.0 - h) - (20100.0 + h)) * 2.0 - 1.22)) < 1e-9 and t["risk"] <= 300.0


def test_challenger_takes_noise_only_at_4x():
    book = days(30, 400.0, risk=100.0)
    noise = [dict(day(str(d.date()), 50.0, hh=13), extra=True, mae=0.0) for d in pd.bdate_range("2026-01-05", periods=30)]
    ch = acct.funded(book + noise, D("2026-01-05"), intraday=True, extra_q=acct.NOISE_Q)
    same = acct.funded(book, D("2026-01-05"), intraday=True)
    at4 = sum(1 for x in ch["days"] if x.get("size") == "4x")
    assert at4 > 0 and abs((ch["balance"] + ch["withdrawn"]) - (same["balance"] + same["withdrawn"]) - 50.0 * at4) < 1e-6
    assert all(x["size"] == y["size"] for x, y in zip(ch["days"], same["days"]))   # same ladder path: the sleeve never trades below 4x


def test_funded_intraday_dll_vs_end_of_day():
    a = dict(_t(10, 0, 12, 0, 100.0, -700.0), risk=100.0); b = dict(_t(10, 30, 11, 30, 50.0, -600.0), risk=100.0)
    eod = acct.funded([a, b], D("2026-01-05")); intra = acct.funded([a, b], D("2026-01-05"), intraday=True)
    assert eod["balance"] == 150.0 and intra["balance"] == -1000.0


# ---------------------------------------------------------------- month-end watch (Claude 2026-11-13)
def _bars(rows):
    """rows: (NY time string, open, high, low, close) -> runner-style 1-minute frame (UTC ts)."""
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close"])
    return df.assign(ts=pd.to_datetime(df.t).dt.tz_localize(NY).dt.tz_convert("UTC"), volume=1.0)[["ts", "open", "high", "low", "close", "volume"]]


def test_month_end_calendar():
    import datetime as dt
    assert acct.month_end_days(2026, 11) == [(dt.date(2026, 11, 26), False), (dt.date(2026, 11, 27), False), (dt.date(2026, 11, 30), True)]
    assert [d for d, ok in acct.month_end_days(2026, 12)] == [dt.date(2026, 12, 29), dt.date(2026, 12, 30), dt.date(2026, 12, 31)]
    assert acct.cme_closed_days(2027) == {dt.date(2027, 1, 1), dt.date(2027, 3, 26), dt.date(2027, 12, 24)}   # Good Friday; Christmas on a Saturday
    assert dt.date(2022, 12, 31) not in acct.cme_closed_days(2022) and dt.date(2021, 12, 31) not in acct.cme_closed_days(2022)


def test_month_end_trade_exit_stop_and_gap():
    import datetime as dt
    d = dt.date(2026, 11, 30)                                   # Monday: the session starts Sunday 18:00
    base = [("2026-11-27 12:00", 100, 100, 100, 100), ("2026-11-29 18:00", 100, 101, 99.5, 100.5), ("2026-11-30 09:30", 101, 102, 100.5, 101.5),
            ("2026-11-30 15:55", 103, 103, 102, 102.5)]
    r = acct.month_end_trade(_bars(base), d, 1, 5.0)            # long, stop 95: never touched -> exits at the 15:55 open
    half = acct.NOISE_HALF
    assert r["why"] == "15:55" and r["entry"] == round(100 + half, 2) and r["exit"] == round(103 - half, 2)
    assert abs(r["net"] - ((103 - half - (100 + half)) * 2 - acct.NOISE_FEE)) < 0.006          # net from unrounded fills, rounded to cents
    stop_rows = base[:2] + [("2026-11-30 09:30", 101, 101, 94.0, 96)] + base[3:]
    r = acct.month_end_trade(_bars(stop_rows), d, 1, 5.0)       # low 94 <= stop 95 -> filled at the stop minus slippage
    assert r["why"] == "stop" and r["exit"] == round(95 - half, 2)
    gap_rows = base[:2] + [("2026-11-30 09:30", 93.0, 94, 92, 93.5)] + base[3:]
    r = acct.month_end_trade(_bars(gap_rows), d, 1, 5.0)        # opens through the stop -> filled at the open
    assert r["why"] == "stop (gap)" and r["exit"] == round(93.0 - half, 2)
    assert acct.month_end_trade(_bars(base[:3]), d, 1, 5.0) is None   # no 15:55 bar yet: session incomplete


def test_month_end_watch_signal_side_and_skips():
    import datetime as dt
    spx = pd.Series([100.0, 103.0, 104.0], index=pd.to_datetime(["2026-10-30", "2026-11-25", "2026-11-27"]))
    rows = [("2026-11-27 12:00", 100, 100, 100, 100), ("2026-11-29 18:00", 100, 100, 100, 100), ("2026-11-30 15:55", 97, 97, 97, 97)]   # short wins 3 pts
    # 14 earlier RTH sessions so the stop ATR exists (range 2 points each)
    for day_ in pd.bdate_range("2026-11-02", periods=15):     # 60 RTH bars per session (the ATR counts sessions with >= 60 bars)
        for m in range(60):
            rows.append((f"{day_.date()} {9 + (30 + m) // 60:02d}:{(30 + m) % 60:02d}", 100, 101, 99, 100))
    w = acct.month_end_watch(_bars(rows), spx, dt.date(2026, 11, 2), dt.date(2026, 11, 30))
    closed = [r for r in w["rows"] if r["status"] == "closed"]
    skipped = [r for r in w["rows"] if r["status"].startswith("skipped (early")]
    assert len(skipped) == 2 and len(closed) == 1 and closed[0]["side"] == "short" and closed[0]["mtd_pct"] == 4.0   # 104 / 100 - 1
    assert closed[0]["net"] > 0 and w["trades"] == 1 and w["trigger"] == "collecting"

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
    assert [s["stage"] for s in main["stage_changes"]] == ["2x"] and main["keep"] == 6000.0

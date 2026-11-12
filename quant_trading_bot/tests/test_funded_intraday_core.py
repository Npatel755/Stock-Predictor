"""Fixtures for funded_intraday_core.sim_day / replay (simulator-verification checklist)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import funded_intraday_core as fc  # noqa: E402


def day(rows, stop=700.0, budget=False):
    a, b, per, mae, risk, q = (np.array(c, dtype=float) for c in zip(*rows))
    return fc.sim_day(a, b, per, mae, risk, q, stop, budget)


def test_single_trade_exact():
    p, w, hit = day([(0, 10, 120.0, -50.0, 100.0, 2)])
    assert (p, w, hit) == (240.0, -100.0, False)


def test_overlapping_mae_stacks_into_dll():
    # two open trades, each -600 at their worst, both end +100: the real DLL liquidates; a final-P&L clip would keep +200
    p, w, hit = day([(0, 20, 100.0, -600.0, 300.0, 1), (5, 30, 100.0, -600.0, 300.0, 1)], stop=2000.0)
    assert hit and p == -1000.0 and w == -1000.0   # liquidated at the first passage: worst is the DLL, not the full stacked MAE


def test_sequential_trades_do_not_stack():
    # first closes -500 before the second opens; the second dips -400: worst -900, no DLL
    p, w, hit = day([(0, 10, -500.0, -500.0, 600.0, 1), (11, 20, 300.0, -400.0, 600.0, 1)], stop=2000.0)
    assert not hit and p == -200.0 and w == -900.0


def test_account_stop_blocks_new_entries():
    p, w, hit = day([(0, 10, -750.0, -750.0, 800.0, 1), (11, 20, 300.0, 0.0, 300.0, 1)], stop=700.0)
    assert p == -750.0 and not hit


def test_budget_shrinks_or_skips():
    # open trade risks 900; the new one risks 300 per micro -> room 100 -> skipped under the budget, taken without it
    rows = [(0, 20, 50.0, -100.0, 900.0, 1), (5, 30, 80.0, -50.0, 300.0, 1)]
    assert day(rows, stop=2000.0, budget=True)[0] == 50.0
    assert day(rows, stop=2000.0, budget=False)[0] == 130.0


def test_higher_costs_never_help():
    rng = np.random.default_rng(1)
    for _ in range(200):
        n = 4; a = np.sort(rng.integers(0, 50, n)).astype(float); b = a + rng.integers(1, 30, n)
        per = rng.normal(0, 300, n); mae = np.minimum(rng.normal(-200, 150, n), per).clip(max=0); risk = np.full(n, 300.0); q = np.ones(n)
        p1 = fc.sim_day(a, b, per, mae, risk, q, 700.0)[0]
        p2 = fc.sim_day(a, b, per - 5.0, np.minimum(mae - 5.0, per - 5.0), risk, q, 700.0)[0]
        assert p2 <= p1 + 1e-9


def test_day_never_below_dll_without_clip():
    rng = np.random.default_rng(2)
    for _ in range(300):
        n = 5; a = np.sort(rng.integers(0, 60, n)).astype(float); b = a + rng.integers(1, 40, n)
        per = rng.normal(-100, 400, n); mae = np.minimum(rng.normal(-300, 200, n), per).clip(max=0)
        p, w, hit = fc.sim_day(a, b, per, mae, np.full(n, 300.0), np.ones(n), 5000.0)
        assert p >= -1000.0 - 1e-9 and w <= min(0.0, p) + 1e-9


def test_path_with_flat_marks_equals_sim_day():
    # marks flat at each trade's MAE (the core's coincident-worst assumption) must reproduce sim_day exactly
    rng = np.random.default_rng(3)
    for _ in range(400):
        n = int(rng.integers(2, 6)); a = np.sort(rng.integers(0, 80, n)).astype(np.int64); b = a + rng.integers(1, 60, n)
        per = rng.normal(-50, 450, n); mae = np.minimum(np.minimum(rng.normal(-300, 250, n), per), 0.0)
        q = rng.integers(1, 4, n).astype(float); stop = float(rng.choice([400.0, 700.0, 5000.0]))
        r1 = fc.sim_day(a, b, per, mae, np.full(n, 300.0), q, stop)
        r2 = fc.sim_day_path(a, b, per, q, stop, [(np.array([a[j]]), np.array([mae[j]])) for j in range(n)])
        assert r1[2] == r2[2] and abs(r1[0] - r2[0]) < 1e-6 and abs(r1[1] - r2[1]) < 1e-6, (r1, r2)


def test_path_non_coincident_worst_points_do_not_stack():
    # A long [0,100): -600 at t=10, then +100; B [60,120): -500 at t=110. The coincident-MAE core liquidates; the exact path does not.
    mA = (np.arange(0, 100), np.where(np.arange(0, 100) == 10, -600.0, 100.0)); mB = (np.arange(60, 120), np.where(np.arange(60, 120) == 110, -500.0, 0.0))
    a = np.array([0, 60]); b = np.array([100, 120]); per = np.array([100.0, 50.0]); q = np.ones(2)
    assert fc.sim_day(a, b, per, np.array([-600.0, -500.0]), np.full(2, 300.0), q, 5000.0)[2]
    p, w, hit = fc.sim_day_path(a, b, per, q, 5000.0, [mA, mB])
    assert not hit and p == 150.0 and w == -600.0


def test_path_coincident_worst_points_do_stack():
    t = np.arange(0, 200); mA = (t, np.where(t == 110, -600.0, 0.0)); mB = (t[60:], np.where(t[60:] == 110, -500.0, 0.0))
    p, w, hit = fc.sim_day_path(np.array([0, 60]), np.array([200, 200]), np.array([100.0, 50.0]), np.ones(2), 5000.0, [mA, mB])
    assert hit and p == -1000.0 and w <= -1000.0


def test_trade_marks_stop_truncation():
    ts = np.arange(10, dtype=np.int64); L = np.array([100, 99, 98, 90, 95, 99, 101, 102, 103, 104.0]); H = L + 1
    t, v = fc.trade_marks(ts, H, L, 1, 100.0, 0, 10, 100.0, 2.0, 0.5, stop_px=91.0, stop_val=-25.0)
    assert list(t) == [0, 1, 2, 3] and v[-1] == -25.0 and abs(v[0] - (0.0 - 0.5) * 2.0) < 1e-12


def test_replay_floor_moves_to_zero_after_first_payout():
    d = [pd.Timestamp("2011-01-03").date() + pd.Timedelta(days=i) for i in range(4)]
    base = {(m, n): {d[0]: (9000.0, 0.0, False), d[1]: (-500.0, -500.0, False), d[2]: (-8800.0, -8800.0, False)} for m in (1, 2, 3, 4) for n in (False, True)}
    r = fc.replay({"base": base}, ((0, 1),), K=8500.0, a0="2011-01-01", a1="2011-01-01")
    # day 0: +9000 -> payout 500 (bal 8500, floor 0); day 1: 8000; day 2: 8000 - 8800 < 0 -> closed
    assert bool(r.closed.iloc[0]) and r.usd.iloc[0] == 500.0

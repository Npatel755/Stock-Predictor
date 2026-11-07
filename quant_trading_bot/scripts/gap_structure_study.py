"""Fixed, causal opening-gap and prior-session-structure research hypotheses."""
import os
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import session_window_study as engine


WINDOWS = {
    "regular_gap_fade": (585, 660),
    "regular_gap_continuation": (585, 660),
    "trend_gap_pullback": (585, 660),
    "small_gap_open_momentum": (600, 690),
    "inside_day_breakout": (600, 690),
    "failed_gap_breakout": (600, 690),
    "overnight_extreme_reversal": (600, 690),
    "prior_day_extreme_reversal": (600, 690),
}


def history_value(group):
    local = group.timestamp_utc.dt.tz_convert("America/New_York")
    clock = (local.dt.hour*60+local.dt.minute).to_numpy()
    indexes = np.flatnonzero((clock >= 570) & (clock < 960))
    if len(indexes) != 390 or clock[indexes[0]] != 570 or clock[indexes[-1]] != 959:
        return None
    selected = group.iloc[indexes]
    times = pd.DatetimeIndex(selected.timestamp_utc).as_unit("ns").asi8
    if not np.all(np.diff(times) == 60*10**9) or selected.contract.nunique() != 1:
        return None
    return dict(high=float(selected.high.max()), low=float(selected.low.min()),
        close=float(selected.close.iloc[-1]), contract=str(selected.contract.iloc[-1]))


def context(group, history):
    # The engine appends this session's history only after all its decisions.
    result = engine.context(group, [])
    prior = history[-1] if history else None
    result["prior"] = prior
    result["prior_two"] = history[-2] if len(history) >= 2 else None
    recent = history[-20:]
    result["trend"] = (int(np.sign(prior["close"]-np.mean([row["close"] for row in recent])))
        if len(recent) == 20 and prior is not None and
        all(row is not None and row["contract"] == prior["contract"] for row in recent) else 0)
    return result


def direction(c, name, decision):
    prior = c["prior"]
    if prior is None or prior["contract"] != str(c["contract"][decision]):
        return 0
    regular = np.flatnonzero((c["minute"] >= 570) & (c["minute"] < 960) & (np.arange(len(c["minute"])) <= decision))
    expected = WINDOWS[name][0]-570
    if len(regular) != expected or c["minute"][regular[0]] != 570:
        return 0
    if not np.all(np.diff(c["time"][regular]) == 60*10**9) or np.any(c["contract"][regular] != prior["contract"]):
        return 0
    opening, close = c["open"][regular[0]], c["close"][decision]
    span = prior["high"]-prior["low"]
    if span <= 0:
        return 0
    gap = (opening-prior["close"])/span
    move = int(np.sign(close-opening))
    if name == "regular_gap_fade":
        return -int(np.sign(gap)) if .1 <= abs(gap) <= .6 else 0
    if name == "regular_gap_continuation":
        return move if .1 <= abs(gap) <= .6 and move == np.sign(gap) else 0
    if name == "trend_gap_pullback":
        trend = c["trend"]
        return trend if .05 <= abs(gap) <= .5 and np.sign(gap) == -trend and move == trend else 0
    if name == "small_gap_open_momentum":
        return move if abs(gap) < .1 else 0
    if name == "inside_day_breakout":
        earlier = c["prior_two"]
        if earlier is None or earlier["contract"] != prior["contract"] or not (prior["high"] < earlier["high"] and prior["low"] > earlier["low"]):
            return 0
        return 1 if close > prior["high"] else -1 if close < prior["low"] else 0
    if name == "failed_gap_breakout":
        return -1 if opening > prior["high"] and close < prior["high"] else 1 if opening < prior["low"] and close > prior["low"] else 0
    if name == "overnight_extreme_reversal":
        night = np.flatnonzero((c["minute"] >= 1080) | (c["minute"] < 570))
        night = night[night < regular[0]]
        if not len(night) or c["minute"][night[0]] != 1080 or c["minute"][night[-1]] != 569:
            return 0
        if np.any(np.diff(c["time"][night]) > 5*60*10**9) or np.any(c["contract"][night] != prior["contract"]):
            return 0
        high, low = c["high"][night].max(), c["low"][night].min()
    else:
        high, low = prior["high"], prior["low"]
    upper = c["high"][regular].max() > high and close < high
    lower = c["low"][regular].min() < low and close > low
    # A candle sequence sweeping both extremes has no unique direction.
    return -1 if upper and not lower else 1 if lower and not upper else 0


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        engine.main(prefix="gap_structure_minutes", windows=WINDOWS, context_fn=context, side_fn=direction,
            history_value=history_value, driver_path=Path(__file__), sources=[],
            rationale="Original research hypotheses, not established published edges: prior regular session is exactly 09:30–15:59 ET with all 390 bars and one contract. Roll mismatches disable entries. Completed 15/30-minute opening data only. Gap fade/continuation require 0.1–0.6 prior-range gap; trend pullback requires 0.05–0.5 and a 20-prior-session trend; small-gap momentum requires <0.1. Inside-day and failed-gap rules use prior completed regular-session extremes. Overnight/prior-day sweeps require a unique reversal direction. Fixed protective stops, at most one attempt per day. The 2026 consumed test is excluded; 2024–2025 is reused exploratory selection.")

"""CME equity-index early-close handling for the frozen research engine.

The engine (mass_execution.execute) flattens at ``flat_minute`` (15:55 ET) and permanently locks a sleeve
("market_data_gap") if a position is still open across a >20-minute gap.  On CME early-close sessions
(13:00/13:15 ET: day after Thanksgiving, Christmas Eve, July 3, and the abbreviated US-holiday sessions)
the regular flat never fires, the position rides into the 18:00 reopen, and the sleeve is dead for the
rest of the run.  Found 2026-11-08: all three paper candidates' 2024-25 validation runs were locked from
2024-11-29 / 2024-12-24 / 2025-07-03 onward.

``early_close_minute_offset`` returns an additive offset for the engine's ``minute`` array so that bars
from the early session's last regular bar onward look like >= 15:55 ET: the engine exits at that bar's
open and refuses new entries, with no change to the frozen engine code.  Early sessions are detected
from a rule calendar (known in advance, usable live) and, for historical bars, additionally from the data
(a session whose last bar before 16:40 ET opens before 15:00).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

ET = "America/New_York"
EARLY_LAST_BAR_MINUTE = 765  # 12:45 ET bar is the last regular bar on a 13:00 early close
FLAT_TARGET = 960


def _nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year, month, weekday):
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d):
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def early_close_dates(year):
    """Rule calendar of CME equity-index sessions that end at 13:00-13:15 ET (regular trade date)."""
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    days = {
        _nth_weekday(year, 1, 0, 3),            # MLK
        _nth_weekday(year, 2, 0, 3),            # Presidents
        _last_weekday(year, 5, 0),              # Memorial
        _observed(date(year, 6, 19)),           # Juneteenth (observed since 2022)
        _observed(date(year, 7, 4)),            # Independence Day
        date(year, 7, 3),                       # July 3 early close
        _nth_weekday(year, 9, 0, 1),            # Labor
        thanksgiving, thanksgiving + timedelta(days=1),
        date(year, 12, 24),                     # Christmas Eve
    }
    if year < 2022:
        days.discard(_observed(date(year, 6, 19)))
    return {d for d in days if d.weekday() < 5}


def early_close_minute_offset(bars):
    """Additive offset for ``arrays(bars)['minute']`` (0 for normal bars)."""
    ts = pd.DatetimeIndex(bars.timestamp_utc).tz_convert(ET)
    minute = (ts.hour * 60 + ts.minute).to_numpy()
    session = np.asarray(bars.session_id.astype(str))
    trade_date = pd.to_datetime(pd.Series(session)).dt.date.to_numpy()
    n = len(bars)
    offset = np.zeros(n, dtype=np.int64)
    if n == 0:
        return offset
    years = {d.year for d in (trade_date[0], trade_date[-1])}
    calendar = set().union(*(early_close_dates(y) for y in range(min(years), max(years) + 1)))
    frame = pd.DataFrame(dict(d=trade_date, m=minute))
    regular = frame[(frame.m >= 570) & (frame.m < 1000)]
    last_regular = regular.groupby("d").m.max()
    for d, idx in frame.groupby("d").indices.items():
        last = int(last_regular.get(d, 0))
        if d in calendar:
            cutoff = min(EARLY_LAST_BAR_MINUTE, last) if last else EARLY_LAST_BAR_MINUTE
        elif last and last < 900:
            cutoff = last
        else:
            continue
        sel = idx[(minute[idx] >= cutoff) & (minute[idx] < 1000)]
        offset[sel] = FLAT_TARGET - cutoff
    return offset


def apply_early_close(data, bars):
    """Return a copy of the engine data dict with the early-close offset applied to ``minute``."""
    out = dict(data)
    out["minute"] = np.ascontiguousarray(data["minute"] + early_close_minute_offset(bars))
    return out

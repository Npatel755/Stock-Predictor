"""Verified UTC date windows for the dashboard's day-based range picker."""
from __future__ import annotations

import pandas as pd

from .market_data import BAR, clean_candles, utc


def complete_windows(bars: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return contiguous complete-UTC-day windows, with exclusive end bounds.

    Partial days and days containing a gap never qualify. No prices are filled,
    dropped, or changed; these are selection suggestions over the audited data.
    """
    if bars.empty:
        return []
    times = pd.to_datetime(bars.timestamp, utc=True).sort_values()
    groups = times.diff().ne(BAR).cumsum()
    windows = []
    for _, part in times.groupby(groups):
        start = part.iloc[0].ceil("D")
        end = (part.iloc[-1] + BAR).floor("D")
        if start < end:
            windows.append((start, end))
    return windows


def default_dates(bars: pd.DataFrame, mode: str):
    windows = complete_windows(bars)
    if not windows:
        raise ValueError("No complete UTC day is available. Update the historical data first.")
    if mode == "parity":
        start, end = max(windows, key=lambda value: (value[1] - value[0], value[1]))
    else:
        start, end = windows[0][0], windows[-1][1]
    return start.date(), (end - pd.Timedelta(days=1)).date()


def select_dates(bars: pd.DataFrame, period):
    if not isinstance(period, (tuple, list)) or len(period) != 2:
        raise ValueError("Select a start and end date.")
    start, end = utc(period[0]), utc(period[1]) + pd.Timedelta(days=1)
    if start >= end:
        raise ValueError("The start date must be on or before the end date.")
    subset = bars[(bars.timestamp >= start) & (bars.timestamp + BAR <= end)]
    return clean_candles(subset, start, end)

"""Completed-HTF availability and Pine-style causal indicator calculations."""
from __future__ import annotations

import numpy as np
import pandas as pd

BAR = pd.Timedelta(minutes=5)


def rma(source: pd.Series, length: int) -> pd.Series:
    """Wilder smoothing, seeded by the first length non-NA samples (ta.rma)."""
    result = np.full(len(source), np.nan)
    seed, previous = [], np.nan
    for i, value in enumerate(source.to_numpy(dtype=float)):
        if np.isnan(value):
            result[i] = previous
            continue
        if np.isnan(previous):
            seed.append(value)
            if len(seed) == length:
                previous = float(np.mean(seed))
        else:
            previous = (previous * (length - 1) + value) / length
        result[i] = previous
    return pd.Series(result, index=source.index)


def confirmed_pivots(source: pd.Series, high: bool = True, left: int = 2, right: int = 2) -> pd.Series:
    """Emit at the confirmation bar, never backdate to the pivot bar.

    Ties select the rightmost equal extreme: left comparison inclusive, right strict.
    TradingView export reconciliation is still required to certify tied-pivot parity.
    """
    values = source.to_numpy(dtype=float)
    pivot = np.full(len(values), np.nan)
    for i in range(left + right, len(values)):
        c = i - right
        before, after = values[c - left:c], values[c + 1:i + 1]
        if not np.isfinite(values[c - left:i + 1]).all():
            continue
        match = ((values[c] >= before).all() and (values[c] > after).all()) if high else (
            (values[c] <= before).all() and (values[c] < after).all())
        if match:
            pivot[i] = values[c]
    return pd.Series(pivot, index=source.index)


def latest_two_events(events: pd.Series) -> tuple[pd.Series, pd.Series]:
    """ta.valuewhen(not na(pivot), pivot, 0/1), retaining equal-valued events."""
    newest, older = [], []
    latest = previous = np.nan
    for event in events:
        if pd.notna(event):
            previous, latest = latest, event
        newest.append(latest)
        older.append(previous)
    return pd.Series(newest, index=events.index), pd.Series(older, index=events.index)


def resample_complete(bars: pd.DataFrame, rule: str) -> pd.DataFrame:
    indexed = bars.set_index("timestamp")
    options = {"origin": "epoch"} if rule != "1D" else {}
    candles = indexed.resample(rule, label="left", closed="left", **options).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"), count=("close", "count"))
    expected = int(pd.Timedelta(rule) / BAR)
    # A partial initial/final HTF bucket cannot masquerade as a completed candle.
    return candles[candles["count"] == expected].drop(columns="count")


def _align(derived: pd.DataFrame, times: pd.Series, rule: str) -> pd.DataFrame:
    # Values have already been indexed [1]/[2] in HTF context. Map by the current
    # 5m BAR OPEN bucket, not its close, to reproduce lookahead_on availability.
    output = derived.reindex(pd.DatetimeIndex(times.dt.floor(rule)))
    output.index = times.index
    return output


def _segment(bars: pd.DataFrame) -> pd.DataFrame:
    output = bars.copy()
    c, h, l = bars.close, bars.high, bars.low
    previous = c.shift(1)
    true_range = pd.concat([h - l, (h - previous).abs(), (l - previous).abs()], axis=1).max(axis=1)
    output["atr5"] = rma(true_range, 14)
    output["rv5"] = bars.volume / bars.volume.shift(1).rolling(20).mean().replace(0, np.nan)
    output["previous_high"] = h.shift(1)
    output["previous_low"] = l.shift(1)
    # Include the next bucket label even if that bucket is incomplete in a prefix;
    # its values depend solely on earlier completed candles. This ensures causal
    # prefix equivalence when the dataset ends mid-HTF candle.
    for rule in ["1D", "4h", "15min"]:
        source = resample_complete(bars, rule)
        full_index = pd.date_range(bars.timestamp.iloc[0].floor(rule), bars.timestamp.iloc[-1].floor(rule), freq=rule)
        source = source.reindex(full_index)
        if rule == "1D":
            table = pd.DataFrame({"daily_up": source.close.shift(1) > source.close.shift(2),
                                  "daily_dn": source.close.shift(1) < source.close.shift(2)})
        elif rule == "4h":
            hn, ho = latest_two_events(confirmed_pivots(source.high))
            ln, lo = latest_two_events(confirmed_pivots(source.low, high=False))
            table = pd.DataFrame({"close4h": source.close.shift(1),
                                  "ema4h": source.close.ewm(span=50, adjust=False).mean().shift(1),
                                  "h4new": hn.shift(1), "h4old": ho.shift(1), "l4new": ln.shift(1), "l4old": lo.shift(1)})
        else:
            rn, _ = latest_two_events(confirmed_pivots(source.high))
            sn, _ = latest_two_events(confirmed_pivots(source.low, high=False))
            table = pd.DataFrame({"res15": rn.shift(2), "sup15": sn.shift(2), "c15": source.close.shift(1),
                                  "p15": source.close.shift(2),
                                  "v15": source.volume.shift(1) / source.volume.rolling(20).mean().shift(2).replace(0, np.nan)})
        output = pd.concat([output, _align(table, bars.timestamp, rule)], axis=1)
    output["bull_bias"] = (output.daily_up.eq(True) & (output.close4h > output.ema4h) &
                            (output.h4new > output.h4old) & (output.l4new > output.l4old))
    output["bear_bias"] = (output.daily_dn.eq(True) & (output.close4h < output.ema4h) &
                            (output.h4new < output.h4old) & (output.l4new < output.l4old))
    output["new15"] = bars.timestamp.dt.floor("15min").ne(bars.timestamp.shift().dt.floor("15min"))
    output.iloc[0, output.columns.get_loc("new15")] = False
    return output


def prepare_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    bars = bars.sort_values("timestamp").reset_index(drop=True)
    groups = bars.timestamp.diff().ne(BAR).cumsum()
    parts = []
    for segment, part in bars.groupby(groups, sort=False):
        result = _segment(part)
        result["segment"] = int(segment)
        parts.append(result)
    return pd.concat(parts).sort_index().reset_index(drop=True)

import numpy as np
import pandas as pd


def future_returns(bars, horizon=5, cost_points=0, minutes=1):
    """Decision at close i, executable entry at open i+1, exit close i+horizon.

    End timestamp includes the exit candle, and events crossing gaps/rolls are
    excluded. Targets never mix adjusted and raw contract prices.
    """
    if horizon < 1:
        raise ValueError("Positive horizon required")
    entry = bars.open.shift(-1)
    exit_price = bars.close.shift(-horizon)
    forward = exit_price/entry-1
    segment = (bars.contract.ne(bars.contract.shift()) | (bars.timestamp_utc.diff() > pd.Timedelta(minutes=max(5, 2*minutes)))).cumsum()
    valid = segment.eq(segment.shift(-horizon))
    forward = forward.where(valid)
    band = cost_points/entry
    direction = pd.Series(np.select([forward > band, forward < -band], [1, -1], default=0), index=bars.index).where(forward.notna())
    return pd.DataFrame(dict(forward_return=forward, direction=direction,
        label_end=bars.timestamp_utc.shift(-horizon)+pd.Timedelta(minutes=minutes)))


def triple_barrier(bars, horizon=20, stop_points=4, target_points=6, side=1, minutes=1):
    if horizon < 1 or stop_points <= 0 or target_points <= 0 or side not in (-1, 1):
        raise ValueError("Invalid barrier configuration")
    result = []
    for i in range(len(bars)):
        label, end, ambiguous = np.nan, pd.NaT, False
        if i+horizon < len(bars):
            entry = bars.open.iloc[i+1]
            stop, target = entry-side*stop_points, entry+side*target_points
            for j in range(i+1, i+horizon+1):
                r = bars.iloc[j]
                if r.contract != bars.contract.iloc[i] or r.timestamp_utc-bars.timestamp_utc.iloc[j-1] > pd.Timedelta(minutes=max(5, 2*minutes)):
                    label, end = np.nan, pd.NaT
                    break
                # Opening gaps occur before the candle's remaining path.
                opening_stop = side*(r.open-stop) <= 0
                opening_target = side*(r.open-target) >= 0
                hit_stop = r.low <= stop if side > 0 else r.high >= stop
                hit_target = r.high >= target if side > 0 else r.low <= target
                end = r.timestamp_utc+pd.Timedelta(minutes=minutes)
                if opening_stop or opening_target:
                    label = -1 if opening_stop else 1
                    break
                if hit_stop or hit_target:
                    ambiguous = bool(hit_stop and hit_target)
                    label = np.nan if ambiguous else (-1 if hit_stop else 1)
                    break
                label = int(np.sign(side*(r.close-entry)))
        result.append(dict(label=label, label_end=end, ambiguous=ambiguous))
    return pd.DataFrame(result)


def meta_labels(primary_signals, labels):
    result = (primary_signals*labels.direction > 0).astype(float)
    return result.where((primary_signals != 0) & labels.forward_return.notna())


def expected_value(probability, average_win, average_loss, costs):
    return probability*average_win-(1-probability)*average_loss-costs

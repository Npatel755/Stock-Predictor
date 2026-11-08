"""Bounded-memory online features with the same definitions as batch research."""
from collections import deque
from dataclasses import dataclass, field
import math
import numpy as np
import pandas as pd
from .features import _one


@dataclass
class WilderState:
    length: int = 14
    seed: list = field(default_factory=list)
    value: float = np.nan

    def update(self, value):
        if not np.isfinite(value):
            return np.nan
        if np.isnan(self.value):
            self.seed.append(value)
            if len(self.seed) == self.length:
                self.value = float(np.mean(self.seed))
        else:
            self.value = (self.value*(self.length-1)+value)/self.length
        return self.value


class FeatureState:
    def __init__(self, minutes=1, history_limit=200):
        if history_limit < 100:
            raise ValueError("At least 100 retained bars required for rolling dependencies")
        self.minutes, self.limit = minutes, history_limit
        self._reset()

    def _reset(self):
        self.bars = deque(maxlen=self.limit)
        self.rows = deque(maxlen=self.limit)
        self.atr = WilderState()
        self.gain, self.loss = WilderState(), WilderState()
        self.plus, self.minus, self.dx = WilderState(), WilderState(), WilderState()
        self.ema_fast = self.ema_slow = np.nan
        self.observations = 0
        self.last = None
        self.swing_high = self.swing_low = np.nan
        self.previous_high = self.previous_low = np.nan
        self.session = None
        self.session_high = self.session_low = np.nan
        self.session_volume = 0
        self.vwap_terms = []
        self.opening_high = self.opening_low = np.nan

    def update(self, record):
        record = dict(record)
        record["timestamp_utc"] = pd.Timestamp(record["timestamp_utc"])
        if self.last is not None:
            delta = record["timestamp_utc"]-self.last["timestamp_utc"]
            if delta <= pd.Timedelta(0):
                raise ValueError("Online feature timestamps must increase")
            boundary = record["contract"] != self.last["contract"] or (
                record["session_id"] == self.last["session_id"] and delta > pd.Timedelta(minutes=max(5, 2*self.minutes)))
            if boundary:
                self._reset()
        c, h, l = float(record["close"]), float(record["high"]), float(record["low"])
        if self.session != record["session_id"]:
            if self.session is not None:
                self.previous_high, self.previous_low = self.session_high, self.session_low
            self.session = record["session_id"]
            self.session_high, self.session_low = h, l
            self.session_volume, self.vwap_terms = 0, []
            self.opening_high = self.opening_low = np.nan
        self.session_high, self.session_low = max(self.session_high, h), min(self.session_low, l)
        volume = int(record["volume"])
        self.session_volume += volume
        self.vwap_terms.append((h+l+c)/3*volume)
        # One session contains at most 1,440 one-minute observations. This state
        # is bounded independently of the complete historical market stream.
        if len(self.vwap_terms) > max(1440, 1440//self.minutes):
            raise ValueError("Session has too many bars; invalid session IDs")
        prior = self.last
        change = c-prior["close"] if prior else np.nan
        tr = max(h-l, abs(h-prior["close"]), abs(l-prior["close"])) if prior else h-l
        atr = self.atr.update(tr)
        gain, loss = self.gain.update(max(change, 0) if np.isfinite(change) else np.nan), self.loss.update(max(-change, 0) if np.isfinite(change) else np.nan)
        up, down = (h-prior["high"], prior["low"]-l) if prior else (np.nan, np.nan)
        plus = self.plus.update(up if up > down and up > 0 else 0)
        minus = self.minus.update(down if down > up and down > 0 else 0)
        dx = abs(plus-minus)/(plus+minus) if np.isfinite(plus+minus) and plus+minus else np.nan
        adx = 100*self.dx.update(dx)
        self.ema_fast = c if not np.isfinite(self.ema_fast) else self.ema_fast+(c-self.ema_fast)*2/11
        self.ema_slow = c if not np.isfinite(self.ema_slow) else self.ema_slow+(c-self.ema_slow)*2/41
        self.observations += 1
        self.bars.append(record)
        tail = pd.DataFrame(self.bars).reset_index(drop=True)
        row = _one(tail, self.minutes).iloc[-1].copy()
        row["atr"], row["atr_relative"], row["adx"] = atr, atr/c, adx
        row["rsi"] = 50 if loss == 0 and gain == 0 else 100 if loss == 0 and gain > 0 else 100-100/(1+gain/loss) if np.isfinite(loss) and loss > 0 else np.nan
        row["ema_fast"] = self.ema_fast if self.observations >= 10 else np.nan
        row["ema_slow"] = self.ema_slow if self.observations >= 40 else np.nan
        row["session_volume"] = self.session_volume
        vwap = math.fsum(self.vwap_terms)/self.session_volume if self.session_volume else np.nan
        row["vwap"], row["vwap_deviation"] = vwap, c/vwap-1
        row["session_high_distance"], row["session_low_distance"] = c/self.session_high-1, c/self.session_low-1
        row["range_expansion"] = (self.session_high-self.session_low)/atr if np.isfinite(atr) and atr else np.nan
        row["previous_session_high"], row["previous_session_low"] = self.previous_high, self.previous_low
        local = record["timestamp_utc"].tz_convert("America/New_York")
        minute = local.hour*60+local.minute
        if 570 <= minute < 600:
            self.opening_high = h if np.isnan(self.opening_high) else max(self.opening_high, h)
            self.opening_low = l if np.isnan(self.opening_low) else min(self.opening_low, l)
        row["opening_high"] = self.opening_high if minute >= 600 else np.nan
        row["opening_low"] = self.opening_low if minute >= 600 else np.nan
        width = row["opening_high"]-row["opening_low"]
        row["opening_location"] = (c-row["opening_low"])/width if np.isfinite(width) and width else np.nan
        old_high, old_low = self.swing_high, self.swing_low
        if len(tail) >= 5:
            highs, lows = tail.high.iloc[-5:].to_numpy(), tail.low.iloc[-5:].to_numpy()
            if highs[2] >= max(highs[:2]) and highs[2] > max(highs[3:]):
                self.swing_high = highs[2]
            if lows[2] <= min(lows[:2]) and lows[2] < min(lows[3:]):
                self.swing_low = lows[2]
        row["swing_high"], row["swing_low"] = self.swing_high, self.swing_low
        row["higher_high"] = max(0, self.swing_high-old_high)/c if np.isfinite(old_high) else np.nan
        row["lower_low"] = max(0, old_low-self.swing_low)/c if np.isfinite(old_low) else np.nan
        row["support_distance"], row["resistance_distance"] = c/self.swing_low-1, c/self.swing_high-1
        self.rows.append(row)
        self.last = record
        return row

    def frames(self):
        return pd.DataFrame(self.bars).reset_index(drop=True), pd.DataFrame(self.rows).reset_index(drop=True)

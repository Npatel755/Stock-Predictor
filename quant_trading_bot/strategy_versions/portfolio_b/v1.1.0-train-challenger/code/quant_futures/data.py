from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd
from .config import file_hash
from .contracts import SPECS, expiration

REQUIRED = ["timestamp_utc", "instrument", "contract", "open", "high", "low", "close", "volume"]
OPTIONAL = ["bid", "ask", "bid_size", "ask_size", "quote_timestamp_utc"]


def utc_times(values):
    # Never interpret naive provider timestamps as UTC without an explicit import conversion.
    if isinstance(getattr(values, "dtype", None), pd.DatetimeTZDtype):
        if values.isna().any():
            raise ValueError("Missing timestamp")
        return pd.DatetimeIndex(values).tz_convert("UTC")
    parsed = [pd.Timestamp(x) for x in values]
    if any(pd.isna(x) or x.tzinfo is None for x in parsed):
        raise ValueError("Timezone-aware timestamps required")
    return pd.DatetimeIndex(pd.to_datetime(parsed, utc=True))


def session_ids(times):
    local = pd.DatetimeIndex(times).tz_convert("America/New_York")
    # Wall-clock arithmetic intentionally precedes DST-independent date assignment.
    wall = local.tz_localize(None)
    return (wall + pd.Timedelta(hours=6)).strftime("%Y-%m-%d")


def canonical(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED) - set(frame)
    if missing:
        raise ValueError(f"Missing canonical columns: {sorted(missing)}")
    result = frame.copy().reset_index(drop=True)
    result["timestamp_utc"] = utc_times(result.timestamp_utc)
    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="raise")
    for column in OPTIONAL:
        if column not in result:
            result[column] = pd.NaT if column.endswith("timestamp_utc") else np.nan
        elif not column.endswith("timestamp_utc"):
            result[column] = pd.to_numeric(result[column], errors="raise")
    result["quote_timestamp_utc"] = pd.to_datetime(result.quote_timestamp_utc, utc=True)
    result["session_id"] = session_ids(result.timestamp_utc)
    if "is_roll_period" not in result:
        result["is_roll_period"] = False
    if "data_quality_flag" not in result:
        result["data_quality_flag"] = ""
    return result


class SessionCalendar:
    """Explicit vendor/exchange schedule; never infer holidays from US bank holidays.

    Schedule rows contain session_id, open_utc, close_utc. Early closes and breaks
    are represented as separate intervals with the same session id. Fail closed
    beyond supplied coverage. Default weekday clock is a research approximation.
    """
    def __init__(self, schedule: pd.DataFrame):
        self.schedule = schedule.copy()
        for c in ("open_utc", "close_utc"):
            self.schedule[c] = utc_times(self.schedule[c])
        if (self.schedule.close_utc <= self.schedule.open_utc).any():
            raise ValueError("Invalid schedule interval")
        ordered = self.schedule.sort_values("open_utc")
        if len(ordered) > 1 and (ordered.open_utc.iloc[1:].reset_index(drop=True) < ordered.close_utc.iloc[:-1].reset_index(drop=True)).any():
            raise ValueError("Overlapping schedule intervals")

    def expected(self, minutes=1):
        times = pd.DatetimeIndex([], tz="UTC")
        for row in self.schedule.itertuples():
            times = times.union(pd.date_range(row.open_utc, row.close_utc, freq=f"{minutes}min", inclusive="left"))
        return times


def validate(bars: pd.DataFrame, minutes=1, calendar: SessionCalendar | None = None):
    bars = canonical(bars)
    flags = [[] for _ in range(len(bars))]
    counts = {}

    def flag(name, mask):
        positions = np.flatnonzero(np.asarray(mask))
        counts[name] = int(len(positions))
        for i in positions:
            flags[i].append(name)

    prices = bars[["open", "high", "low", "close"]]
    flag("invalid_price", ~np.isfinite(prices).all(axis=1) | (prices <= 0).any(axis=1))
    flag("invalid_ohlc", (bars.high < prices.max(axis=1)) | (bars.low > prices.min(axis=1)))
    flag("invalid_volume", ~np.isfinite(bars.volume) | (bars.volume < 0) | (bars.volume % 1 != 0))
    flag("zero_volume", bars.volume == 0)
    flag("duplicate", bars.duplicated(["timestamp_utc", "contract"], keep=False))
    flag("invalid_instrument", ~bars.instrument.isin(SPECS))
    alignment_minutes = minutes if minutes < 1440 else 1
    flag("timestamp_alignment", bars.timestamp_utc.dt.floor(f"{alignment_minutes}min") != bars.timestamp_utc)
    flag("invalid_quote_size", (bars.bid_size < 0) | (bars.ask_size < 0))
    invalid_contract = []
    for row in bars.itertuples():
        try:
            expiration(row.contract)
            invalid_contract.append(not row.contract.startswith(row.instrument))
        except (ValueError, TypeError):
            invalid_contract.append(True)
    flag("invalid_contract", invalid_contract)
    delta = bars.groupby("contract", sort=False).timestamp_utc.diff()
    flag("out_of_order", delta < pd.Timedelta(0))
    flag("gap", delta > pd.Timedelta(minutes=minutes))
    flag("abnormal_jump", bars.groupby("contract", sort=False).close.pct_change(fill_method=None).abs() > 0.05)
    quote = bars.bid.notna() | bars.ask.notna()
    age = bars.timestamp_utc - bars.quote_timestamp_utc
    flag("invalid_quote", quote & ((bars.ask < bars.bid) | (bars.bid <= 0) | (bars.ask <= 0) | bars.ask.isna() | bars.bid.isna()))
    flag("stale_quote", quote & (age.isna() | (age > pd.Timedelta(seconds=60)) | (age < pd.Timedelta(0))))
    off_tick = np.zeros(len(bars), dtype=bool)
    for instrument, spec in SPECS.items():
        mask = bars.instrument.eq(instrument)
        off_tick[mask] = ~np.isclose(prices.loc[mask] / spec.tick, np.round(prices.loc[mask] / spec.tick), atol=1e-6, rtol=0).all(axis=1)
    flag("off_tick", off_tick)
    missing_expected = None
    if calendar is not None:
        expected = calendar.expected(minutes)
        flag("outside_calendar", ~bars.timestamp_utc.isin(expected))
        missing_expected = {c: len(expected.difference(pd.DatetimeIndex(g.timestamp_utc))) for c, g in bars.groupby("instrument")}
    bars["data_quality_flag"] = ["|".join(x) for x in flags]
    fatal = ["invalid_price", "invalid_ohlc", "invalid_volume", "duplicate", "invalid_instrument", "invalid_contract", "out_of_order", "off_tick", "invalid_quote", "stale_quote", "timestamp_alignment", "invalid_quote_size"]
    report = dict(rows=len(bars), counts=counts, fatal=sum(counts[k] for k in fatal),
                  start=str(bars.timestamp_utc.min()), end=str(bars.timestamp_utc.max()),
                  calendar_verified=calendar is not None, missing_expected=missing_expected,
                  gap_interpretation="gaps include scheduled closures unless calendar supplied; no filling")
    return bars, report


def resample_complete(bars, minutes, base_minutes=1, calendar=None):
    if minutes < base_minutes or minutes % base_minutes:
        raise ValueError("Timeframe must be an integer multiple of base")
    bars, report = validate(bars, base_minutes)
    if report["fatal"]:
        raise ValueError("Invalid input bars")
    result = []
    # Anchor every bucket to 18:00 Eastern session open, respecting DST and session IDs.
    for (contract, session), group in bars.groupby(["contract", "session_id"], sort=False):
        start = pd.Timestamp(session).tz_localize("America/New_York") - pd.DateOffset(days=1)
        start = start.replace(hour=18).tz_convert("UTC")
        g = group.set_index("timestamp_utc")
        ag = g.resample(f"{minutes}min", origin=start, closed="left", label="left").agg(
            open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
            volume=("volume", "sum"), count=("close", "count"), instrument=("instrument", "first"))
        if minutes == 1440:
            if calendar is None:
                raise ValueError("Daily bars require explicit exchange schedule")
            expected = calendar.expected(base_minutes)
            expected = expected[session_ids(expected) == session]
            if not len(expected) or not expected.isin(g.index).all():
                continue
            g = g.reindex(expected)
            row = dict(timestamp_utc=expected[0], available_at=expected[-1]+pd.Timedelta(minutes=base_minutes),
                       open=g.open.iloc[0], high=g.high.max(), low=g.low.min(), close=g.close.iloc[-1],
                       volume=g.volume.sum(), instrument=g.instrument.iloc[0], contract=contract)
            result.append(pd.DataFrame([row]))
        else:
            ag = ag[ag["count"] == minutes // base_minutes].drop(columns="count")
            ag["contract"] = contract
            ag["available_at"] = ag.index + pd.Timedelta(minutes=minutes)
            result.append(ag.reset_index())
    return pd.concat(result, ignore_index=True) if result else pd.DataFrame()


def import_file(source, output, *, provider, license_note, timestamp_semantics, price_basis, synthetic=False, source_timezone=None):
    if not provider.strip() or not license_note.strip():
        raise ValueError("Provider and license provenance required")
    if price_basis not in ("raw", "adjusted", "unknown"):
        raise ValueError("Declare price_basis as raw, adjusted or unknown")
    source, output = Path(source), Path(output)
    if output.exists() or output.with_suffix(".manifest.json").exists():
        raise FileExistsError("Dataset versions are immutable; choose a new output")
    frame = pd.read_parquet(source) if source.suffix == ".parquet" else pd.read_csv(source)
    if source_timezone:
        frame["timestamp_utc"] = pd.DatetimeIndex(pd.to_datetime(frame.timestamp_utc)).tz_localize(source_timezone, ambiguous="raise", nonexistent="raise").tz_convert("UTC")
    if timestamp_semantics != "bar_open":
        raise ValueError("Convert provider timestamps explicitly to bar_open before import")
    bars, report = validate(frame)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".quality.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report["fatal"]:
        raise ValueError("Data quality failed; inspect quality report")
    bars.to_parquet(output, index=False)
    manifest = dict(dataset_version=file_hash(output), source_hash=file_hash(source), provider=provider,
                    license_note=license_note, synthetic=synthetic, timestamp_semantics=timestamp_semantics,
                    raw_contract_prices=price_basis == "raw", price_basis=price_basis,
                    coverage=report, path=output.name)
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

"""Contract metadata and causal roll construction; raw prices always retained."""
from dataclasses import dataclass
from datetime import date, timedelta
import re
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ContractSpec:
    instrument: str
    multiplier: float
    tick: float

    @property
    def tick_value(self):
        return self.multiplier * self.tick

    def round_price(self, price, side=0):
        units = price / self.tick
        return float((np.ceil(units) if side > 0 else np.floor(units) if side < 0 else np.round(units)) * self.tick)


SPECS = {"MES": ContractSpec("MES", 5.0, 0.25), "MNQ": ContractSpec("MNQ", 2.0, 0.25),
         "ES": ContractSpec("ES", 50.0, 0.25), "NQ": ContractSpec("NQ", 20.0, 0.25)}
SPEC_SOURCES = {
    "MES": "https://www.cmegroup.com/markets/equities/sp/micro-e-mini-sandp-500.contractSpecs.html",
    "MNQ": "https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.html",
}
VERIFIED_EXPIRATIONS = {(2026, 3): date(2026, 3, 20), (2026, 6): date(2026, 6, 18),
                        (2026, 9): date(2026, 9, 18), (2026, 12): date(2026, 12, 18)}
VERIFIED_ROLLS = {(2026, 3): date(2026, 3, 16), (2026, 6): date(2026, 6, 15),
                  (2026, 9): date(2026, 9, 14), (2026, 12): date(2026, 12, 14)}
ROLL_SOURCE = "https://www.cmegroup.com/trading/equity-index/rolldates.html"


def expiration(contract: str) -> date:
    """Official 2026 dates; nominal third Friday fallback for other years.

    Outside verified coverage, import official expiration overrides before operation.
    June 2026 expires Thursday June 18 because of the exchange holiday.
    """
    match = re.fullmatch(r"(MES|MNQ|ES|NQ)([HMUZ])(\d{2}|\d{4})", contract)
    if not match:
        raise ValueError(f"Explicit quarterly contract required, got {contract!r}")
    year = int(match[3]) + (2000 if len(match[3]) == 2 else 0)
    first = date(year, {"H": 3, "M": 6, "U": 9, "Z": 12}[match[2]], 1)
    return VERIFIED_EXPIRATIONS.get((year, first.month), first + timedelta(days=(4-first.weekday()) % 7 + 14))


def continuous(bars: pd.DataFrame, mode="volume", roll_days=None, expiration_overrides=None) -> pd.DataFrame:
    """Forward additive feature adjustment, avoiding historical feature revision.

    Select using *previous completed session* volume or an explicit calendar rule.
    Switch only forward in expiry. New-contract offset uses previous simultaneous
    closes. Missing overlap raises; execution must liquidate raw old contract.
    """
    if mode not in ("volume", "calendar"):
        raise ValueError(mode)
    if bars.instrument.nunique() != 1:
        raise ValueError("Construct each instrument independently")
    expiration_overrides = expiration_overrides or {}
    contracts = sorted(bars.contract.unique(), key=expiration)
    expiries = {c: pd.Timestamp(expiration_overrides.get(c, expiration(c))) for c in contracts}
    volumes = bars.groupby(["session_id", "contract"], sort=True).volume.sum().unstack().fillna(0)
    previous_volumes = volumes.shift(1)
    current = contracts[0]
    latest = {}
    offset = 0.0
    output = []
    for timestamp, group in bars.groupby("timestamp_utc", sort=True):
        rows = {r.contract: r for _, r in group.iterrows()}
        session = group.session_id.iloc[0]
        next_contracts = [c for c in contracts if expiries[c] > expiries[current] and c in rows]
        new = current
        if next_contracts:
            candidate = next_contracts[0]
            if mode == "calendar":
                expiry = expiries[current]
                first = date(expiry.year, expiry.month, 1)
                nominal_friday = first+timedelta(days=(4-first.weekday()) % 7 + 14)
                default_roll = VERIFIED_ROLLS.get((expiry.year, expiry.month), nominal_friday-timedelta(days=4))
                roll_date = pd.Timestamp(default_roll) if roll_days is None else expiry-pd.Timedelta(days=roll_days)
                if pd.Timestamp(session) >= roll_date:
                    new = candidate
            elif session in previous_volumes.index and previous_volumes.loc[session, candidate] > previous_volumes.loc[session, current]:
                new = candidate
        changed = new != current
        if changed:
            if current not in latest or new not in latest or latest[current][0] != latest[new][0]:
                raise ValueError("Roll requires simultaneous previous raw closes")
            offset += latest[current][1] - latest[new][1]
            current = new
        if current not in rows:
            raise ValueError("Selected contract is missing; do not fill across rolls")
        row = rows[current].copy()
        row["is_roll_period"] = changed
        row["adjustment"] = offset
        for name in ("open", "high", "low", "close"):
            row["feature_"+name] = row[name] + offset
        output.append(row)
        latest.update({c: (timestamp, r.close) for c, r in rows.items()})
    return pd.DataFrame(output).reset_index(drop=True)


def back_adjusted(bars, as_of, mode="volume", **kwargs):
    """Frozen as-of additive back-adjustment; raw tradable columns are unchanged.

    Never substitute a later as-of version into an earlier decision. Forward
    adjustment remains the streaming feature representation.
    """
    as_of = pd.Timestamp(as_of)
    if as_of.tzinfo is None:
        raise ValueError("Timezone-aware as_of required")
    selected = continuous(bars.loc[bars.timestamp_utc <= as_of].copy(), mode=mode, **kwargs)
    if selected.empty:
        return selected
    latest_offset = selected.adjustment.iloc[-1]
    for name in ("open", "high", "low", "close"):
        selected["back_adjusted_"+name] = selected["feature_"+name]-latest_offset
    selected["adjustment_as_of"] = as_of
    return selected


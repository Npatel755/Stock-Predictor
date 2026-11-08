"""Deterministic, market-balanced 10,000-case parameter universe.

This module uses the standard library only and never reads data.  Each family
uses every field below in the mass research signal/execution contract.  The
``opening_range`` lookback is exact elapsed 15-minute windows from 09:30 ET; other lookbacks are
completed bars.  Thresholds are family-specific signal thresholds.  No field
exists merely to manufacture uniqueness.
"""
from collections import Counter
import hashlib
import json
import random


SEED = 20261106
TARGET = 10000
INSTRUMENTS = ("ES", "NQ", "MES", "MNQ")
FAMILIES = (
    "trend", "momentum", "mean_reversion", "breakout", "vwap",
    "opening_range", "regime", "volatility", "volume", "hybrid",
)
PER_MARKET_FAMILY = 250
LOOKBACKS = (8, 12, 16, 24, 32, 48, 64, 96)
OPENING_LOOKBACKS = (15, 30, 45, 60, 75, 90, 105, 120)
STOP_ATR = (1.0, 1.5, 2.0, 3.0)
TARGET_R = (1.0, 1.5, 2.0, 3.0, 4.0)
HOLD_BARS = (2, 4, 8, 12, 16)
SESSIONS = ((585, 690), (600, 720), (720, 870), (840, 945), (585, 945))
MAX_CONTRACTS = (1, 2, 3)
TRAILING_ATR = (0.0, 1.0, 2.0)
THRESHOLDS = {
    "trend": (0.1, 0.25, 0.5, 0.75, 1.0),
    "momentum": (0.25, 0.5, 0.75, 1.0, 1.5),
    "mean_reversion": (0.5, 1.0, 1.5, 2.0, 2.5),
    "breakout": (0.0, 0.1, 0.25, 0.5, 0.75),
    "vwap": (0.5, 1.0, 1.5, 2.0, 2.5),
    "opening_range": (0.1, 0.25, 0.5, 0.75, 1.0),
    "regime": (0.25, 0.5, 0.75, 1.0, 1.5),
    "volatility": (0.5, 1.0, 1.5, 2.0, 2.5),
    "volume": (1.0, 1.25, 1.5, 1.75, 2.0),
    "hybrid": (0.25, 0.5, 0.75, 1.0, 1.5),
}
ACTIVE_FIELDS = (
    "family", "lookback", "threshold", "stop_atr", "target_r", "hold_bars",
    "session_start", "session_end", "max_contracts", "trailing_atr",
)
SCHEMA_VERSION = 1


def semantic_key(configuration):
    """Canonical active behavior, deliberately ignoring market/id/seed tags.

    Equal rule/execution parameters cannot count again solely because of a
    different instrument, seed, run name, or arbitrary inactive annotation.
    """
    active = {field: configuration[field] for field in ACTIVE_FIELDS}
    # Normalize equivalent JSON numeric representations, e.g. 1 and 1.0.
    for field in ("threshold", "stop_atr", "target_r", "trailing_atr"):
        active[field] = float(active[field])
    for field in ("lookback", "hold_bars", "session_start", "session_end", "max_contracts"):
        value = active[field]
        if isinstance(value, bool) or int(value) != value:
            raise ValueError(f"{field} must be an integer")
        active[field] = int(value)
    return json.dumps(active, sort_keys=True, separators=(",", ":"), allow_nan=False)


def config_id(configuration):
    """Stable identifier for the actual market and canonical configuration."""
    market = configuration["instrument"]
    if market not in INSTRUMENTS:
        raise ValueError("Unknown futures instrument")
    payload = market+"|"+semantic_key(configuration)
    return "mass_"+hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def generate(seed=SEED):
    """Generate exactly 10,000 globally distinct active configurations.

    For each family, rejection-sample 1,000 distinct active configurations with
    a local seeded PRNG.  Deal 250 to each market.  The shared seen set enforces
    disjoint parameters across markets, rather than counting a market rename as
    an additional distinct configuration.  Calls neither touch global RNG state
    nor read market observations.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Integer reproducibility seed required")
    rng = random.Random(seed)
    rows = []
    seen = set()
    for family in FAMILIES:
        for number in range(PER_MARKET_FAMILY):
            for instrument in INSTRUMENTS:
                while True:
                    start, end = rng.choice(SESSIONS)
                    row = dict(
                        instrument=instrument, family=family,
                        lookback=rng.choice(OPENING_LOOKBACKS if family == "opening_range" else LOOKBACKS), threshold=rng.choice(THRESHOLDS[family]),
                        stop_atr=rng.choice(STOP_ATR), target_r=rng.choice(TARGET_R),
                        hold_bars=rng.choice(HOLD_BARS), session_start=start, session_end=end,
                        max_contracts=rng.choice(MAX_CONTRACTS), trailing_atr=rng.choice(TRAILING_ATR),
                    )
                    key = semantic_key(row)
                    if key not in seen:
                        seen.add(key)
                        break
                row["config_id"] = config_id(row)
                rows.append(row)
    if len(rows) != TARGET or len(seen) != TARGET:
        raise AssertionError("Configuration universe is incomplete or duplicated")
    counts = Counter((row["instrument"], row["family"]) for row in rows)
    if any(counts[(market, family)] != PER_MARKET_FAMILY for market in INSTRUMENTS for family in FAMILIES):
        raise AssertionError("Configuration universe lost market/family balance")
    return rows


def metadata(configurations=None, seed=SEED):
    rows = generate(seed) if configurations is None else configurations
    keys = [semantic_key(row) for row in rows]
    counts = Counter((row["instrument"], row["family"]) for row in rows)
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return dict(
        schema_version=SCHEMA_VERSION, seed=seed, configurations=len(rows),
        distinct_active_configurations=len(set(keys)),
        market_cases=len({(row["instrument"], key) for row, key in zip(rows, keys)}),
        universe_sha256=digest, active_fields=list(ACTIVE_FIELDS),
        by_market_family={market: {family: counts[(market, family)] for family in FAMILIES} for market in INSTRUMENTS},
        uniqueness_note="Market, seed, run identifiers and inactive annotations do not establish distinct active configurations.",
        lookback_note="opening_range uses exact 15-minute multiples since 09:30 ET; all other families use completed bars.",
        total_is_parameter_configurations_not_strategy_families=True,
    )

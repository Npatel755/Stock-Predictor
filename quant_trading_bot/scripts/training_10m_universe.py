"""Universe generator for 10,000,000 Institutional Configurations.
Generates 10,000,000 globally unique configurations (5,000,000 MNQ + 5,000,000 MES)
across 8 distinct institutional strategy families, non-overlapping sessions,
and funded-account risk parameters.
"""
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]

INSTRUMENTS = ("MNQ", "MES")
FAMILIES = (
    "hybrid", "momentum", "breakout", "vwap", "trend",
    "volatility", "opening_range", "mean_reversion"
)
LOOKBACKS = (8, 10, 12, 16, 20, 24, 28, 32, 40, 48, 64, 80)
OPENING_LOOKBACKS = (15, 30, 45, 60, 75, 90, 105, 120)
STOP_ATR = (1.0, 1.25, 1.5, 1.75, 2.0, 2.25)
TARGET_R = (1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 5.0)
HOLD_BARS = (4, 6, 8, 10, 12, 16, 20, 24, 32)
SESSIONS = (
    (585, 945),  # 9:45 AM - 3:45 PM (Full regular session)
    (600, 720),  # 10:00 AM - 12:00 PM (Morning drive)
    (585, 690),  # 9:45 AM - 11:30 AM (Opening impulse)
    (720, 945),  # 12:00 PM - 3:45 PM (Afternoon continuation)
    (780, 945),  # 1:00 PM - 3:45 PM (Post-lunch trend)
    (570, 720),  # 9:30 AM - 12:00 PM (Cash open expansion)
    (585, 840),  # 9:45 AM - 2:00 PM (European close window)
    (540, 945),  # 9:00 AM - 3:45 PM (Pre-market into close)
)
MAX_CONTRACTS_BY_INSTRUMENT = {
    "MES": (1, 2, 3),
    "MNQ": (1, 2)
}
TRAILING_ATR = (0.0, 1.0, 1.5, 2.0, 2.5, 3.0)

THRESHOLDS = {
    "hybrid": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
    "momentum": (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0),
    "breakout": (0.1, 0.25, 0.5, 0.75, 1.0, 1.25),
    "vwap": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
    "trend": (0.25, 0.5, 0.75, 1.0, 1.25, 1.5),
    "opening_range": (0.25, 0.5, 0.75, 1.0, 1.25),
    "volatility": (0.5, 1.0, 1.25, 1.5, 2.0),
    "mean_reversion": (1.0, 1.25, 1.5, 1.75, 2.0, 2.5)
}

ACTIVE_FIELDS = (
    "family", "lookback", "threshold", "stop_atr", "target_r", "hold_bars",
    "session_start", "session_end", "max_contracts", "trailing_atr",
)


def semantic_key(configuration):
    active = {field: configuration[field] for field in ACTIVE_FIELDS}
    for field in ("threshold", "stop_atr", "target_r", "trailing_atr"):
        active[field] = float(active[field])
    for field in ("lookback", "hold_bars", "session_start", "session_end", "max_contracts"):
        active[field] = int(active[field])
    return json.dumps(active, sort_keys=True, separators=(",", ":"), allow_nan=False)


def config_id(configuration):
    market = configuration["instrument"]
    payload = market + "|" + semantic_key(configuration)
    return "m10_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def stream_universe_10m(folder, target=10000000, seed=20261108):
    """Generate 10,000,000 unique configurations (5M MNQ, 5M MES)."""
    cfg_file = folder / 'configurations.jsonl'
    seen_by_market = {m: set() for m in INSTRUMENTS}
    target_per_market = target // len(INSTRUMENTS)

    rng = random.Random(seed)
    order = 0

    with cfg_file.open('w', encoding='utf-8') as stream:
        for instrument in INSTRUMENTS:
            print(f"Generating {target_per_market:,} configurations for {instrument}...", flush=True)
            count = 0
            allowed_contracts = MAX_CONTRACTS_BY_INSTRUMENT[instrument]
            while count < target_per_market:
                fam = rng.choice(FAMILIES)
                start, end = rng.choice(SESSIONS)
                lb = rng.choice(OPENING_LOOKBACKS if fam == "opening_range" else LOOKBACKS)
                th = rng.choice(THRESHOLDS[fam])
                stop = rng.choice(STOP_ATR)
                tgt = rng.choice(TARGET_R)
                hold = rng.choice(HOLD_BARS)
                qty = rng.choice(allowed_contracts)
                trail = rng.choice(TRAILING_ATR)

                cand = {
                    "instrument": instrument,
                    "family": fam,
                    "lookback": lb,
                    "threshold": th,
                    "stop_atr": stop,
                    "target_r": tgt,
                    "hold_bars": hold,
                    "session_start": start,
                    "session_end": end,
                    "max_contracts": qty,
                    "trailing_atr": trail,
                }
                cid = config_id(cand)
                if cid in seen_by_market[instrument]:
                    continue

                seen_by_market[instrument].add(cid)
                cand["config_id"] = cid
                cand["experiment_order"] = order

                stream.write(json.dumps(cand) + '\n')
                count += 1
                order += 1

                if count % 1000000 == 0:
                    print(f"  ...generated {count:,} / {target_per_market:,} for {instrument}", flush=True)

    print(f"Total configurations generated: {order:,}", flush=True)

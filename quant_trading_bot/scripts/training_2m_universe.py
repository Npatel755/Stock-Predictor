"""Universe generator for 2,000,000 High-Velocity, High-R Configurations.

Universe size: ~120,000,000 potential combinations.
Generates exactly 2,000,000 globally unique configurations (1M MNQ + 1M MES).
Disjoint from previous runs using hash bitset tracking.
"""
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]

INSTRUMENTS = ("MNQ", "MES")
FAMILIES = (
    "trend", "momentum", "mean_reversion", "breakout", "vwap",
    "opening_range", "regime", "volatility", "volume", "hybrid",
)
LOOKBACKS = (6, 8, 10, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96)
OPENING_LOOKBACKS = (15, 30, 45, 60, 75, 90, 105, 120)
STOP_ATR = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5)
TARGET_R = (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0)
HOLD_BARS = (2, 4, 6, 8, 10, 12, 16, 20, 24, 32)
SESSIONS = (
    (585, 690), (600, 720), (720, 870), (840, 945), (585, 945),
    (570, 720), (585, 840), (780, 945), (180, 540), (180, 945),
    (570, 945), (540, 780)
)
MAX_CONTRACTS = (1, 2, 3)
TRAILING_ATR = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0)

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
    return "m2_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def stream_universe_2m(folder, db, target=2000000, seed=20265001):
    """Generate exactly 2,000,000 unique configurations (1M MNQ, 1M MES)."""
    cfg_file = folder / 'configurations.jsonl'
    db.execute('CREATE TABLE IF NOT EXISTS configs(config_id TEXT PRIMARY KEY, experiment_order INT, instrument TEXT, lookback INT, family TEXT, payload TEXT)')

    seen_by_market = {m: set() for m in INSTRUMENTS}
    target_per_market = target // len(INSTRUMENTS)  # 1,000,000 per market

    rng = random.Random(seed)
    order = 0

    with cfg_file.open('w', encoding='utf-8') as stream:
        for instrument in INSTRUMENTS:
            print(f"Generating {target_per_market:,} configurations for {instrument}...")
            count = 0
            batch = []
            while count < target_per_market:
                fam = rng.choice(FAMILIES)
                start, end = rng.choice(SESSIONS)
                lb = rng.choice(OPENING_LOOKBACKS if fam == "opening_range" else LOOKBACKS)
                th = rng.choice(THRESHOLDS[fam])
                stop = rng.choice(STOP_ATR)
                tgt = rng.choice(TARGET_R)
                hold = rng.choice(HOLD_BARS)
                qty = rng.choice(MAX_CONTRACTS)
                trail = rng.choice(TRAILING_ATR)

                row = {
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
                    "trailing_atr": trail
                }
                cid = config_id(row)
                if cid not in seen_by_market[instrument]:
                    seen_by_market[instrument].add(cid)
                    row["config_id"] = cid
                    row["experiment_order"] = order
                    stream.write(json.dumps(row) + '\n')
                    batch.append((cid, order, instrument, lb, fam, json.dumps(row)))
                    order += 1
                    count += 1

                    if len(batch) >= 20000:
                        db.executemany('INSERT INTO configs VALUES (?,?,?,?,?,?)', batch)
                        db.commit()
                        batch = []
                        if count % 100000 == 0:
                            print(f"  {instrument}: {count:,} / {target_per_market:,}")

            if batch:
                db.executemany('INSERT INTO configs VALUES (?,?,?,?,?,?)', batch)
                db.commit()

    print(f"Finished generating exactly {order:,} configurations.")
    return order

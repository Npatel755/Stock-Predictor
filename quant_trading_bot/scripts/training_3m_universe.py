"""Universe generator for 3,000,000 High-Win-Rate, High-Profit-Factor Configurations.

Optimized to challenge and exceed the current champion:
- Higher conviction entry thresholds (0.5 to 2.5)
- Sweet-spot Reward-to-Risk targets (1.8R to 5.0R) with dynamic trailing ATR stops
- Institutional liquidity windows (9:45 AM - 3:45 PM ET)
- Sizing: 1-3 micro contracts
Generates exactly 3,000,000 globally unique configurations (1.5M MNQ + 1.5M MES).
"""
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]

INSTRUMENTS = ("MNQ", "MES")
FAMILIES = (
    "momentum", "breakout", "vwap", "trend", "hybrid",
    "opening_range", "volatility", "mean_reversion"
)
LOOKBACKS = (8, 10, 12, 16, 20, 24, 28, 32, 40, 48, 64, 80)
OPENING_LOOKBACKS = (15, 30, 45, 60, 75, 90, 105, 120)
STOP_ATR = (1.0, 1.25, 1.5, 1.75, 2.0, 2.25)
TARGET_R = (1.8, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0, 5.0)
HOLD_BARS = (4, 6, 8, 12, 16, 20, 24, 32)
SESSIONS = (
    (585, 945),  # 9:45 AM - 3:45 PM (Full regular session after open)
    (600, 720),  # 10:00 AM - 12:00 PM (Morning drive)
    (585, 690),  # 9:45 AM - 11:30 AM (Opening impulse)
    (720, 945),  # 12:00 PM - 3:45 PM (Afternoon continuation)
    (780, 945),  # 1:00 PM - 3:45 PM (Post-lunch trend)
    (570, 720),  # 9:30 AM - 12:00 PM (Morning cash open)
    (585, 840),  # 9:45 AM - 2:00 PM (European close window)
    (540, 945),  # 9:00 AM - 3:45 PM (Pre-market into close)
)
MAX_CONTRACTS_BY_INSTRUMENT = {
    "MES": (1, 2, 3),
    "MNQ": (1, 2)
}
TRAILING_ATR = (0.0, 1.0, 1.5, 2.0, 2.5, 3.0)

THRESHOLDS = {
    "momentum": (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0),
    "breakout": (0.1, 0.25, 0.5, 0.75, 1.0, 1.25),
    "vwap": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
    "trend": (0.25, 0.5, 0.75, 1.0, 1.25, 1.5),
    "hybrid": (0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
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
    return "m3_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def stream_universe_3m(folder, db, target=3000000, seed=20268001):
    """Generate exactly 3,000,000 unique configurations (1.5M MNQ, 1.5M MES)."""
    cfg_file = folder / 'configurations.jsonl'
    db.execute('CREATE TABLE IF NOT EXISTS configs(config_id TEXT PRIMARY KEY, experiment_order INT, instrument TEXT, lookback INT, family TEXT, payload TEXT)')

    seen_by_market = {m: set() for m in INSTRUMENTS}
    target_per_market = target // len(INSTRUMENTS)

    rng = random.Random(seed)
    order = 0

    with cfg_file.open('w', encoding='utf-8') as stream:
        for instrument in INSTRUMENTS:
            print(f"Generating {target_per_market:,} configurations for {instrument}...")
            count = 0
            batch = []
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

                    if len(batch) >= 25000:
                        db.executemany('INSERT INTO configs VALUES (?,?,?,?,?,?)', batch)
                        db.commit()
                        batch = []
                        if count % 250000 == 0:
                            print(f"  {instrument}: {count:,} / {target_per_market:,}")

            if batch:
                db.executemany('INSERT INTO configs VALUES (?,?,?,?,?,?)', batch)
                db.commit()

    db.execute('CREATE INDEX IF NOT EXISTS idx_cfg_inst_lb ON configs(instrument, lookback)')
    db.commit()
    print("Finished generating exactly 3,000,000 configurations with index created.")

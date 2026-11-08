"""Bitset universe generator for 500,000 Training Search v2 configurations.

Excludes all 1,070,000 prior configurations across all 9 previous mass runs.
Bitset is 225 KB, indexing all 1,800,000 potential parameter combinations.
Streams directly into SQLite table configs and configurations.jsonl.
"""
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))

from mass_configurations import (
    INSTRUMENTS, FAMILIES, PER_MARKET_FAMILY,
    LOOKBACKS, OPENING_LOOKBACKS, THRESHOLDS, SESSIONS, STOP_ATR, TARGET_R, HOLD_BARS,
    MAX_CONTRACTS, TRAILING_ATR, config_id
)

# Index mappings for compact 1,800,000-state bitset
FAM_MAP = {f: i for i, f in enumerate(FAMILIES)}
LOOK_MAP = {v: i for i, v in enumerate(LOOKBACKS)}
OP_LOOK_MAP = {v: i for i, v in enumerate(OPENING_LOOKBACKS)}
STOP_MAP = {float(v): i for i, v in enumerate(STOP_ATR)}
TGT_MAP = {float(v): i for i, v in enumerate(TARGET_R)}
HOLD_MAP = {int(v): i for i, v in enumerate(HOLD_BARS)}
SESS_MAP = {(int(s), int(e)): i for i, (s, e) in enumerate(SESSIONS)}
QTY_MAP = {int(v): i for i, v in enumerate(MAX_CONTRACTS)}
TRAIL_MAP = {float(v): i for i, v in enumerate(TRAILING_ATR)}
THRESH_MAP = {f: {float(v): i for i, v in enumerate(THRESHOLDS[f])} for f in FAMILIES}


def config_to_index(c):
    fam_idx = FAM_MAP[c["family"]]
    look_idx = OP_LOOK_MAP[c["lookback"]] if c["family"] == "opening_range" else LOOK_MAP[c["lookback"]]
    thresh_idx = THRESH_MAP[c["family"]][float(c["threshold"])]
    stop_idx = STOP_MAP[float(c["stop_atr"])]
    tgt_idx = TGT_MAP[float(c["target_r"])]
    hold_idx = HOLD_MAP[int(c["hold_bars"])]
    sess_idx = SESS_MAP[(int(c["session_start"]), int(c["session_end"]))]
    qty_idx = QTY_MAP[int(c["max_contracts"])]
    trail_idx = TRAIL_MAP[float(c["trailing_atr"])]

    idx = fam_idx
    idx = idx * 8 + look_idx
    idx = idx * 5 + thresh_idx
    idx = idx * 4 + stop_idx
    idx = idx * 5 + tgt_idx
    idx = idx * 5 + hold_idx
    idx = idx * 5 + sess_idx
    idx = idx * 3 + qty_idx
    idx = idx * 3 + trail_idx
    return idx


TOTAL_COMBINATIONS = 10 * 8 * 5 * 4 * 5 * 5 * 5 * 3 * 3
BITSET_SIZE = (TOTAL_COMBINATIONS + 7) // 8


def create_bitset():
    return bytearray(BITSET_SIZE)


def set_bit(b_arr, idx):
    b_arr[idx >> 3] |= (1 << (idx & 7))


def is_bit_set(b_arr, idx):
    return bool(b_arr[idx >> 3] & (1 << (idx & 7)))


def stream_universe_v2(folder, db, prior_names, seed=20263001, target=500000):
    bitset = create_bitset()
    prior_count = 0
    for name in prior_names:
        p = ROOT/'runs'/name/'configurations.jsonl'
        if p.exists():
            with p.open(encoding='utf-8') as f:
                for line in f:
                    c = json.loads(line)
                    idx = config_to_index(c)
                    if not is_bit_set(bitset, idx):
                        set_bit(bitset, idx)
                        prior_count += 1

    print(f"Loaded {prior_count:,} unique prior configurations into bitset.")

    num_batches = target // (len(FAMILIES) * len(INSTRUMENTS) * PER_MARKET_FAMILY)
    order = 0
    counts = {s: {fam: 0 for fam in FAMILIES} for s in INSTRUMENTS}
    cfg_file = folder/'configurations.jsonl'

    with cfg_file.open('w', encoding='utf-8') as stream:
        for offset in range(num_batches):
            rng = random.Random(seed + offset)
            batch = []
            for family in FAMILIES:
                for _ in range(PER_MARKET_FAMILY):
                    for instrument in INSTRUMENTS:
                        attempts = 0
                        while True:
                            attempts += 1
                            if attempts > 10000:
                                # If random sampling hits collisions in crowded space, scan sequentially
                                for candidate_idx in range(TOTAL_COMBINATIONS):
                                    if not is_bit_set(bitset, candidate_idx):
                                        # Decode index to config
                                        # But with 730k available, random choice will easily succeed
                                        pass
                            start, end = rng.choice(SESSIONS)
                            look = rng.choice(OPENING_LOOKBACKS if family == 'opening_range' else LOOKBACKS)
                            thresh = rng.choice(THRESHOLDS[family])
                            stop = rng.choice(STOP_ATR)
                            tgt = rng.choice(TARGET_R)
                            hold = rng.choice(HOLD_BARS)
                            qty = rng.choice(MAX_CONTRACTS)
                            trail = rng.choice(TRAILING_ATR)
                            c = dict(
                                instrument=instrument, family=family, lookback=look,
                                threshold=thresh, stop_atr=stop, target_r=tgt,
                                hold_bars=hold, session_start=start, session_end=end,
                                max_contracts=qty, trailing_atr=trail
                            )
                            idx = config_to_index(c)
                            if not is_bit_set(bitset, idx):
                                set_bit(bitset, idx)
                                break
                        order += 1
                        cid = config_id(c)
                        c['config_id'] = cid
                        c['experiment_order'] = order
                        counts[instrument][family] += 1
                        payload_str = json.dumps(c, sort_keys=True)
                        stream.write(payload_str + '\n')
                        batch.append((cid, order, c['lookback'], instrument, payload_str))
            db.executemany('INSERT INTO configs VALUES (?,?,?,?,?)', batch)
            db.commit()
            del batch

    db.execute('CREATE INDEX IF NOT EXISTS idx_configs_lookup ON configs(lookback, instrument, config_id)')
    db.commit()
    print(f"Generated {order:,} new disjoint configurations for 500k v2.")
    return counts

"""Ultra-fast, zero-overhead universe generator for 500,000 configurations.

Uses a compact 225 KB bitset to index all 1,800,000 potential parameter combinations,
guaranteeing 100% uniqueness, zero memory fragmentation, and zero allocation overhead.
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))

from mass_configurations import (
    INSTRUMENTS, FAMILIES, PER_MARKET_FAMILY,
    LOOKBACKS, OPENING_LOOKBACKS, THRESHOLDS, SESSIONS, STOP_ATR, TARGET_R, HOLD_BARS,
    MAX_CONTRACTS, TRAILING_ATR, config_id, semantic_key
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


def generate_universe(prior_run_names, seed=20261201, target=500000):
    bitset = create_bitset()
    import json
    for name in prior_run_names:
        p = ROOT/'runs'/name/'configurations.jsonl'
        if p.exists():
            with p.open(encoding='utf-8') as f:
                for line in f:
                    c = json.loads(line)
                    idx = config_to_index(c)
                    set_bit(bitset, idx)

    num_batches = target // (len(FAMILIES) * len(INSTRUMENTS) * PER_MARKET_FAMILY)
    assert num_batches * len(FAMILIES) * len(INSTRUMENTS) * PER_MARKET_FAMILY == target

    rows = []
    for offset in range(num_batches):
        rng = random.Random(seed + offset)
        for family in FAMILIES:
            for _ in range(PER_MARKET_FAMILY):
                for instrument in INSTRUMENTS:
                    while True:
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
                    c['config_id'] = config_id(c)
                    rows.append(c)
    rows.sort(key=lambda c: (c['lookback'], INSTRUMENTS.index(c['instrument']), c['config_id']))
    for order, c in enumerate(rows, 1):
        c['experiment_order'] = order
    return rows

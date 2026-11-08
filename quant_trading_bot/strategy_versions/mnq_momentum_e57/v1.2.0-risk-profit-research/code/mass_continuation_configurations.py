"""Continue the original seeded parameter domains without reading performance."""
from collections import Counter
import random
from mass_configurations import (INSTRUMENTS,FAMILIES,PER_MARKET_FAMILY,TARGET,
    LOOKBACKS,OPENING_LOOKBACKS,THRESHOLDS,SESSIONS,STOP_ATR,TARGET_R,HOLD_BARS,
    MAX_CONTRACTS,TRAILING_ATR,semantic_key,config_id,metadata)

SEED=20261107


def generate(excluded,seed=SEED):
    if isinstance(seed,bool) or not isinstance(seed,int): raise ValueError('Integer seed required')
    rng=random.Random(seed)
    seen=set(excluded)
    rows=[]
    for family in FAMILIES:
        for _ in range(PER_MARKET_FAMILY):
            for instrument in INSTRUMENTS:
                while True:
                    start,end=rng.choice(SESSIONS)
                    c=dict(instrument=instrument,family=family,
                        lookback=rng.choice(OPENING_LOOKBACKS if family=='opening_range' else LOOKBACKS),
                        threshold=rng.choice(THRESHOLDS[family]),stop_atr=rng.choice(STOP_ATR),
                        target_r=rng.choice(TARGET_R),hold_bars=rng.choice(HOLD_BARS),
                        session_start=start,session_end=end,max_contracts=rng.choice(MAX_CONTRACTS),
                        trailing_atr=rng.choice(TRAILING_ATR))
                    key=semantic_key(c)
                    if key not in seen:
                        seen.add(key);break
                c['config_id']=config_id(c);rows.append(c)
    counts=Counter((c['instrument'],c['family']) for c in rows)
    if len(rows)!=TARGET or any(counts[(s,f)]!=250 for s in INSTRUMENTS for f in FAMILIES):
        raise AssertionError('Incomplete balanced continuation')
    return rows

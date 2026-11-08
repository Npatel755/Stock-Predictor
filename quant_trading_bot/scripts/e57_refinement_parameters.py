"""Predeclared momentum neighborhoods and explicit, bounded account risk scaling."""
from contextlib import contextmanager
import hashlib
import itertools
import json
import random
from mass_configurations import semantic_key

DOMAINS=dict(lookback=(8,12,16,20,24,32,40,48,64),threshold=(.75,1.,1.25,1.5,1.75,2.),stop_atr=(.75,1.,1.25,1.5,2.),target_r=(2.,3.,4.,5.,6.),hold_bars=(4,8,12,16),session=((585,690),(600,720),(720,870),(840,945),(585,945)),max_contracts=(1,2,3,4,6),trailing_atr=(0.,.5,1.,1.5,2.,3.),risk_scale=(1.,1.5,2.,2.5,3.,4.))
SCALING_CONTROLS=((1.5,2),(2.,2),(2.,3),(3.,3),(3.,4),(4.,4),(4.,6))


def active_key(c):
    active=json.loads(semantic_key(c))
    scale=float(c.get('risk_scale',1))
    if scale!=1:
        active.update(risk_per_trade=150.*scale,max_open_risk=150.*scale,daily_loss=300.*scale)
    return json.dumps(active,sort_keys=True,separators=(',',':'),allow_nan=False)


def fingerprint(c): return hashlib.sha256(active_key(c).encode()).digest()
def identifier(c): return 'e57_'+hashlib.sha256(('MNQ|'+active_key(c)).encode()).hexdigest()[:20]


def scaled_cfg(original,c):
    cfg=dict(original);scale=float(c.get('risk_scale',1))
    if scale not in DOMAINS['risk_scale']: raise ValueError('Unregistered risk scale')
    cfg.update(risk_per_trade=150.*scale,max_open_risk=150.*scale,daily_loss=300.*scale)
    # Original1800 internal hard stop and2000 funded-floor scenario stay fixed.
    if cfg['hard_drawdown']!=1800 or cfg['funded_drawdown']!=2000 or c['max_contracts']>6:
        raise ValueError('Unapproved account or position limit')
    return cfg


@contextmanager
def execution_scope(engine):
    original=engine.execution_cfg
    def configured(c,factor=1): return scaled_cfg(original(c,factor),c)
    engine.execution_cfg=configured
    try: yield
    finally: engine.execution_cfg=original


def universe(parent,excluded,target=200000,seed=20270122):
    rng=random.Random(seed);seen=set(excluded);controls=[];rest=[]
    def add(c,is_control=False):
        key=fingerprint(c)
        if key in seen:return
        seen.add(key);c=dict(c);c['config_id']=identifier(c);c['pure_scaling_control']=is_control
        (controls if is_control else rest).append(c)
    base={k:v for k,v in parent.items() if k not in ('config_id','experiment_order')};base['risk_scale']=1.
    for scale,cap in SCALING_CONTROLS:add(dict(base,risk_scale=scale,max_contracts=cap),True)
    # Deterministic one-coordinate changes first, then a seeded broader neighborhood.
    for field,values in DOMAINS.items():
        for value in values:
            c=dict(base)
            if field=='session':c.update(session_start=value[0],session_end=value[1])
            else:c[field]=value
            add(c)
    while len(controls)+len(rest)<target:
        c=dict(base)
        for field,values in DOMAINS.items():
            value=rng.choice(values)
            if field=='session':c.update(session_start=value[0],session_end=value[1])
            else:c[field]=value
        add(c)
    rest=rest[:target-len(controls)]
    fields=tuple(k for k in base if k not in ('instrument','family'))
    def distance(c):return sum(c[k]!=base[k] for k in fields)
    rest.sort(key=lambda c:(abs(c['lookback']-parent['lookback']),c['lookback'],distance(c),c['config_id']))
    rows=controls+rest
    if len(rows)!=target or len({fingerprint(c) for c in rows})!=target:raise ValueError('Invalid new universe')
    for i,c in enumerate(rows,1):c['experiment_order']=i
    return rows

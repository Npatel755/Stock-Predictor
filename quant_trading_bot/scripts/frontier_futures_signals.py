"""Five mechanism-level hypotheses absent from both earlier entry libraries.

Auction/profile data use only completed RTH sessions. Absorption is an OHLCV
proxy, not observed order flow. The analog model fits only earlier TRAIN.
"""
import hashlib
import json
import random
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from novel_futures_signals import primitives as base_primitives

SEED=20261118
FAMILIES={
 'auction_gap_repair':'An unresolved RTH opening gap may revisit the previous RTH closing auction; scheduled overnight information can instead sustain the gap.',
 'previous_value_migration':'A shift in the previous completed RTH volume-profile mode may attract following-session acceptance; no true trade-at-price/order-book data are claimed.',
 'high_volume_absorption':'Large bar volume with small body and asymmetric rejection wicks may indicate failed directional pressure; OHLCV is only a proxy.',
 'sequential_change_detection':'A sequential standardized-return CUSUM can identify accumulated distribution changes rather than a fixed-horizon momentum threshold.',
 'historical_analog_forecast':'Nearest historical TRAIN candle/volume states forecast the next return; fails when apparent analogs have no stable conditional edge.',
}
FITTED=('historical_analog_forecast',)
LOOKBACKS=(16,24,32,48,64,96,128,192)
THRESHOLDS={
 'auction_gap_repair':(.25,.5,.75,1.,1.5,2.),
 'previous_value_migration':(.1,.25,.5,.75,1.,1.5),
 'high_volume_absorption':(.5,.75,1.,1.25,1.5,2.),
 'sequential_change_detection':(1.,1.5,2.,2.5,3.,4.),
 'historical_analog_forecast':(.025,.05,.075,.1,.15,.2,.3),
}


def key(c):
    return json.dumps({k:c[k] for k in ('family','lookback','threshold','stop_atr','target_r','hold_bars','session_start','session_end','max_contracts','trailing_atr')},sort_keys=True)


def universe():
    rng=random.Random(SEED);rows=[];seen=set()
    for family in FAMILIES:
        for number in range(400):
            while True:
                sessions=((585,690),(600,720),(585,780)) if family=='auction_gap_repair' else ((585,690),(600,720),(720,870),(840,945),(585,945))
                start,end=rng.choice(sessions)
                c=dict(instrument=('MNQ','MES')[number%2],family=family,lookback=rng.choice(LOOKBACKS),threshold=rng.choice(THRESHOLDS[family]),
                       stop_atr=rng.choice((.75,1.,1.25,1.5,2.)),target_r=rng.choice((1.5,2.,3.,4.,6.)),hold_bars=rng.choice((2,4,8,12,16)),
                       session_start=start,session_end=end,max_contracts=rng.choice((1,2)),trailing_atr=0.)
                k=key(c)
                if k not in seen:seen.add(k);break
            c['config_id']='frontier_'+hashlib.sha256((c['instrument']+'|'+k).encode()).hexdigest()[:20]
            c['experiment_order']=len(rows);rows.append(c)
    assert len(rows)==len(seen)==2000
    return rows


def primitives(bars,peer):
    b=bars.reset_index(drop=True);p=base_primitives(b,peer);n=len(b)
    o,h,l,c,v=[b[k].to_numpy(float) for k in ('open','high','low','close','volume')]
    width=h-l
    tr=np.maximum(width,np.maximum(np.abs(h-np.r_[c[0],c[:-1]]),np.abs(l-np.r_[c[0],c[:-1]])))
    reset=np.r_[True,np.diff(p['segment'])!=0];tr[reset]=width[reset]
    p.update(open=o,high=h,low=l,close=c,bar_volume=v,tr=tr,
             location=np.divide(c-l,width,out=np.full(n,.5),where=width>0),
             wick=np.divide(np.minimum(o,c)-l-(h-np.maximum(o,c)),width,out=np.zeros(n),where=width>0),
             body_fraction=np.divide(np.abs(c-o),width,out=np.ones(n),where=width>0))
    names=('previous_rth_close','rth_open','prior_poc','older_poc','prior_profile_close')
    p.update({k:np.full(n,np.nan) for k in names})
    # Session profiles are published only AFTER the closing bar completes.
    # Bar volume is assigned to typical-price bins: a disclosed approximation.
    previous_close=np.nan;previous_poc=np.nan;older_poc=np.nan;opening=np.nan
    rth=[];day=None;contract=None
    local=b.timestamp_utc.dt.tz_convert('America/New_York')
    dates=local.dt.date.to_numpy();contracts=b.contract.to_numpy();minutes=p['clock']
    for i in range(n):
        if contracts[i]!=contract:
            previous_close=previous_poc=older_poc=opening=np.nan;rth=[];contract=contracts[i]
        if dates[i]!=day:
            if rth and minutes[rth[-1]]!=945:
                previous_close=previous_poc=older_poc=np.nan
            opening=np.nan;rth=[];day=dates[i]
        if minutes[i]==570:opening=o[i]
        p['previous_rth_close'][i]=previous_close;p['rth_open'][i]=opening
        p['prior_poc'][i]=previous_poc;p['older_poc'][i]=older_poc
        p['prior_profile_close'][i]=previous_close
        if 570<=minutes[i]<=945:rth.append(i)
        if minutes[i]==945:
            # Require all26 completed quarter-hour RTH bars, a single contract,
            # and no gap; do not silently build a holiday/missing-bar profile.
            if len(rth)==26 and np.array_equal(minutes[rth],np.arange(570,946,15)) and len(set(p['segment'].iloc[rth]))==1:
                prices=(h[rth]+l[rth]+c[rth])/3
                lo,hi=float(np.min(l[rth])),float(np.max(h[rth]))
                if hi>lo and v[rth].sum()>0:
                    edges=np.linspace(lo,hi,25)
                    bucket=np.clip(np.searchsorted(edges,prices,side='right')-1,0,23)
                    weights=np.bincount(bucket,weights=v[rth],minlength=24)
                    mode=int(np.argmax(weights));older_poc=previous_poc;previous_poc=float((edges[mode]+edges[mode+1])/2)
                else:older_poc=previous_poc;previous_poc=np.nan
                previous_close=c[i]
            else:
                previous_close=previous_poc=older_poc=np.nan
    # Analog inputs are observable at the completed signal bar.
    p['analog_x']=np.column_stack((p['r'],p['lag'],width/c,p['location'],p['volume']))
    return p


def fit_model(p,family,lookback,cutoff):
    assert family in FITTED
    cutoff_ns=pd.Timestamp(cutoff).value
    eligible=np.flatnonzero((p['timestamp']+30*60*10**9<=cutoff_ns)&np.isfinite(p['analog_x']).all(axis=1)&np.isfinite(p['y']))
    ids=eligible[-lookback*92:]
    # Predeclared deterministic cap bounds search cost, with no target-based sampling.
    if len(ids)>2048:ids=ids[np.linspace(0,len(ids)-1,2048,dtype=int)]
    if len(ids)<100:return dict(ready=False,fit_cutoff=str(cutoff))
    x=p['analog_x'][ids];y=p['y'][ids];center=x.mean(axis=0);scale=x.std(axis=0)
    scale=np.where(scale>1e-12,scale,1.)
    return dict(ready=bool(y.std()>1e-12),fit_cutoff=str(cutoff),last_label_end=str(pd.to_datetime(int(p['timestamp'][ids[-1]])+30*60*10**9,utc=True)),
                center=center.tolist(),scale=scale.tolist(),x=((x-center)/scale).tolist(),y=y.tolist(),target_std=float(y.std()),observations=len(ids),neighbors=21)


def value(p,family,lookback,model=None):
    n=len(p['r'])
    if family in FITTED:
        out=np.full(n,np.nan)
        if model is None or not model['ready']:return out
        valid=np.isfinite(p['analog_x']).all(axis=1)
        x=(p['analog_x'][valid]-np.array(model['center']))/np.array(model['scale'])
        tree=cKDTree(np.array(model['x']))
        distance,ids=tree.query(x,k=model['neighbors'],workers=1)
        weights=1/(.1+distance*distance)
        out[valid]=(np.sum(np.array(model['y'])[ids]*weights,axis=1)/weights.sum(axis=1))/model['target_std']
        return out
    g=p['segment']
    def roll(a,method,lag=False):
        s=pd.Series(a)
        if lag:s=s.groupby(g).shift()
        q=s.groupby(g).rolling(lookback,min_periods=lookback)
        z=q.std(ddof=0) if method=='std' else getattr(q,method)()
        return z.droplevel(0).sort_index().to_numpy(float)
    atr=roll(p['tr'],'mean')
    if family=='auction_gap_repair':
        opening_gap=p['rth_open']-p['previous_rth_close']
        remaining=p['close']-p['previous_rth_close']
        valid=(np.sign(opening_gap)==np.sign(remaining))&(p['clock']>=570)&(p['clock']<945)
        return np.where(valid,-remaining/np.where(atr>0,atr,np.nan),np.nan)
    if family=='previous_value_migration':
        migration=p['prior_poc']-p['older_poc']
        accepted=np.sign(p['close']-p['prior_poc'])==np.sign(migration)
        return np.where(accepted,migration/np.where(atr>0,atr,np.nan),np.nan)
    if family=='high_volume_absorption':
        average=roll(p['bar_volume'],'mean',lag=True)
        return np.where(p['body_fraction']<=.3,p['wick']*p['bar_volume']/np.where(average>0,average,np.nan),np.nan)
    if family!='sequential_change_detection':raise ValueError(family)
    std=roll(p['r'],'std',lag=True)
    normalized=p['r']/np.where(std>1e-12,std,np.nan)
    out=np.full(n,np.nan);up=down=0.;previous_segment=None
    for i,z in enumerate(normalized):
        current=g.iloc[i]
        if current!=previous_segment:up=down=0.;previous_segment=current
        if not np.isfinite(z):continue
        up=max(0.,up+z-.15);down=min(0.,down+z+.15)
        out[i]=up if up>=abs(down) else down
        # Fixed reset after a6-sigma accumulated excursion, independent of entry threshold.
        if max(up,abs(down))>=6:up=down=0.
    return out

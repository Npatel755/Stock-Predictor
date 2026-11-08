"""Five additional entry algorithms; all learned parameters use TRAIN only.

These use related OHLCV inputs, not independent sources of evidence. Cross-
index equilibrium trades a single micro future and is not a hedged arbitrage.
"""
import hashlib
import json
import random
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from novel_futures_signals import primitives as base_primitives

SEED=20261119
FAMILIES={
 'direction_probability':'Frozen regularized logistic classification predicts next-return direction from candle/volume state; classification skill may be too small to cover costs.',
 'cross_index_equilibrium':'Frozen log-price relation between indices identifies deviations; the target-only trade is unhedged and the relation can drift.',
 'wavelet_reversal':'Causal Haar detail isolates a fast oscillation that dominates the slower component; fading it fails when the oscillation becomes a trend.',
 'ordinal_entropy_persistence':'Low entropy of three-return ordinal permutations identifies organized paths; the latest three-return direction supplies exposure.',
 'run_duration_expectation':'Frozen next-return expectation by signed run duration tests persistence/exhaustion beyond the earlier two-sign Markov state.',
}
FITTED=('direction_probability','cross_index_equilibrium','run_duration_expectation')
LOOKBACKS=(16,24,32,48,64,96,128,192)
THRESHOLDS={
 'direction_probability':(.025,.05,.075,.1,.15,.2,.3),
 'cross_index_equilibrium':(.5,.75,1.,1.5,2.,2.5,3.),
 'wavelet_reversal':(.25,.5,.75,1.,1.5,2.),
 'ordinal_entropy_persistence':(.02,.04,.06,.1,.15,.25),
 'run_duration_expectation':(.025,.05,.075,.1,.15,.2,.3),
}


def key(c):
    return json.dumps({k:c[k] for k in ('family','lookback','threshold','stop_atr','target_r','hold_bars','session_start','session_end','max_contracts','trailing_atr')},sort_keys=True)


def universe():
    rng=random.Random(SEED);rows=[];seen=set()
    for family in FAMILIES:
        for number in range(400):
            while True:
                start,end=rng.choice(((585,690),(600,720),(720,870),(840,945),(585,945)))
                c=dict(instrument=('MNQ','MES')[number%2],family=family,lookback=rng.choice(LOOKBACKS),threshold=rng.choice(THRESHOLDS[family]),
                       stop_atr=rng.choice((.75,1.,1.25,1.5,2.)),target_r=rng.choice((1.5,2.,3.,4.,6.)),hold_bars=rng.choice((2,4,8,12,16)),
                       session_start=start,session_end=end,max_contracts=rng.choice((1,2)),trailing_atr=0.)
                k=key(c)
                if k not in seen:seen.add(k);break
            c['config_id']='explore_'+hashlib.sha256((c['instrument']+'|'+k).encode()).hexdigest()[:20]
            c['experiment_order']=len(rows);rows.append(c)
    assert len(rows)==len(seen)==2000
    return rows


def primitives(bars,peer):
    b=bars.reset_index(drop=True);p=base_primitives(b,peer);n=len(b)
    width=(b.high-b.low).to_numpy(float);close=b.close.to_numpy(float)
    location=np.divide(close-b.low.to_numpy(float),width,out=np.full(n,.5),where=width>0)
    p['classifier_x']=np.column_stack((p['r'],p['lag'],p['volume'],width/close,location))
    p['log_price']=np.log(close)
    aligned=b[['timestamp_utc']].merge(peer[['timestamp_utc','close']],on='timestamp_utc',how='left',validate='one_to_one')
    p['peer_log_price']=np.log(aligned.close.to_numpy(float))
    durations=np.full(n,-1,dtype=int);last=0;length=0;old_segment=None
    for i,r in enumerate(p['r']):
        segment=p['segment'].iloc[i]
        if segment!=old_segment:last=length=0;old_segment=segment
        if not np.isfinite(r) or r==0:last=length=0;continue
        sign=1 if r>0 else -1
        length=length+1 if sign==last else 1;last=sign
        durations[i]=(16 if sign>0 else 0)+min(length,16)-1
    p['duration_state']=durations
    return p


def fit_model(p,family,lookback,cutoff):
    assert family in FITTED
    cutoff_ns=pd.Timestamp(cutoff).value
    ids=np.flatnonzero(p['timestamp']+30*60*10**9<=cutoff_ns)[-lookback*92:]
    if len(ids)>4096:ids=ids[np.linspace(0,len(ids)-1,4096,dtype=int)]
    base=dict(fit_cutoff=str(cutoff))
    if len(ids)<100:return dict(base,ready=False)
    base['last_label_end']=str(pd.to_datetime(int(p['timestamp'][ids[-1]])+30*60*10**9,utc=True))
    if family=='cross_index_equilibrium':
        x=p['peer_log_price'][ids];y=p['log_price'][ids]
        valid=np.isfinite(x)&np.isfinite(y);x,y=x[valid],y[valid]
        if len(x)<100 or x.std()<1e-12:return dict(base,ready=False)
        beta=float(np.dot(x-x.mean(),y-y.mean())/np.dot(x-x.mean(),x-x.mean()))
        alpha=float(y.mean()-beta*x.mean());std=float(np.std(y-alpha-beta*x))
        return dict(base,ready=std>1e-12,beta=beta,alpha=alpha,target_std=std,observations=len(x))
    if family=='run_duration_expectation':
        y=p['y'][ids];state=p['duration_state'][ids];valid=np.isfinite(y)&(state>=0)
        if valid.sum()<100:return dict(base,ready=False)
        count=np.bincount(state[valid],minlength=32);total=np.bincount(state[valid],weights=y[valid],minlength=32)
        return dict(base,ready=bool(y[valid].std()>1e-12),target_std=float(y[valid].std()),table=(total/(count+20)).tolist(),counts=count.tolist(),observations=int(valid.sum()))
    x=p['classifier_x'][ids];y=p['y'][ids]
    valid=np.isfinite(x).all(axis=1)&np.isfinite(y);x,y=x[valid],(y[valid]>0).astype(float)
    if len(y)<100 or y.min()==y.max():return dict(base,ready=False)
    center=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale>1e-12,scale,1.)
    design=np.column_stack((np.ones(len(x)),(x-center)/scale))
    def loss(w):
        z=design@w
        objective=float(np.mean(np.logaddexp(0,z)-y*z)+.005*np.dot(w[1:],w[1:]))
        gradient=design.T@(expit(z)-y)/len(y);gradient[1:]+=.01*w[1:]
        return objective,gradient
    optimum=minimize(loss,np.zeros(design.shape[1]),jac=True,method='L-BFGS-B',options=dict(maxiter=200,ftol=1e-12))
    return dict(base,ready=bool(optimum.success),center=center.tolist(),scale=scale.tolist(),coef=optimum.x.tolist(),observations=len(y),optimizer_success=bool(optimum.success),target_std=1.)


def value(p,family,lookback,model=None):
    n=len(p['r'])
    if family in FITTED:
        if model is None or not model['ready']:return np.full(n,np.nan)
        if family=='cross_index_equilibrium':return -(p['log_price']-model['alpha']-model['beta']*p['peer_log_price'])/model['target_std']
        if family=='run_duration_expectation':
            state=p['duration_state'];table=np.array(model['table']);count=np.array(model['counts'])
            return np.where((state>=0)&(count[np.maximum(state,0)]>=20),table[np.maximum(state,0)]/model['target_std'],np.nan)
        x=(p['classifier_x']-np.array(model['center']))/np.array(model['scale'])
        return 2*expit(np.column_stack((np.ones(n),x))@np.array(model['coef']))-1
    g=p['segment'];r=pd.Series(p['r'])
    def roll(s,L,method):
        q=s.groupby(g).rolling(L,min_periods=L)
        z=q.std(ddof=0) if method=='std' else getattr(q,method)()
        return z.droplevel(0).sort_index()
    if family=='wavelet_reversal':
        short=roll(r,lookback//2,'sum');whole=roll(r,lookback,'sum');slow=roll(r,2*lookback,'sum')
        detail=2*short-whole;std=roll(r,lookback,'std')*np.sqrt(lookback)
        return np.where(detail.abs()>.5*slow.abs(),-detail/std.replace(0,np.nan),np.nan)
    if family!='ordinal_entropy_persistence':raise ValueError(family)
    previous=r.groupby(g).shift();older=r.groupby(g).shift(2)
    triplet=np.column_stack((older,previous,r));valid=np.isfinite(triplet).all(axis=1)
    order=np.argsort(triplet,axis=1,kind='stable');code=order[:,0]*9+order[:,1]*3+order[:,2]
    entropy=np.zeros(n)
    for pattern in (5,7,11,15,19,21):
        frequency=roll(pd.Series(np.where(valid,(code==pattern).astype(float),np.nan)),lookback,'mean').to_numpy(float)
        entropy-=frequency*np.log(np.maximum(frequency,1e-12))/np.log(6)
    organized=1-entropy;direction=np.sign(r+previous+older).to_numpy(float)
    std=roll(r,lookback,'std').to_numpy(float)
    return np.where(std>1e-12,direction*organized,np.nan)

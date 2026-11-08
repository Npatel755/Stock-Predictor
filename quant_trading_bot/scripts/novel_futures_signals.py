"""New statistical entry mechanisms; no EMA/momentum/channel entry recipes.

Five forecasting mechanisms fit only on history preceding the evaluated year
minus eight days. Their coefficients remain fixed throughout that evaluation.
The other three use causal distribution/liquidity measurements, with no fit.
"""
import hashlib
import json
import random
import numpy as np
import pandas as pd

SEED = 20261117
FAMILIES = {
    'autoregressive_forecast': 'Fixed two-lag return regression forecasts the next completed return; fails when serial dependence changes.',
    'markov_sign_grammar': 'Smoothed next-return expectation conditional on the last two return signs; fails when transition probabilities change.',
    'clock_expectation': 'Past same-clock next-return expectations; tests recurring inventory/auction pressure, not a hand-picked session direction.',
    'volume_response_regression': 'Fixed next-return response to unexpected log volume; volume is an OHLCV proxy, not true order flow.',
    'cross_index_leadlag': 'Fixed regression predicts this index from the other index current/lagged return; missing peer observations prohibit entry.',
    'return_skew_exhaustion': 'Opposes a sufficiently asymmetric trailing return distribution, rather than a price moving-average displacement.',
    'semivariance_exhaustion': 'Opposes large imbalance between positive and negative squared returns; fails during persistent asymmetric trends.',
    'illiquidity_reversal': 'Fades a return with unusually high absolute price impact per traded notional; no order-book/liquidation claim.',
}
FITTED = tuple(list(FAMILIES)[:5])
LOOKBACKS = (16, 24, 32, 48, 64, 96, 128, 192)
THRESHOLDS = {f: (.025, .05, .075, .1, .15, .2, .3) for f in FITTED}
THRESHOLDS.update(return_skew_exhaustion=(.25,.5,.75,1.,1.5,2.),
                  semivariance_exhaustion=(.1,.2,.3,.4,.5,.65),
                  illiquidity_reversal=(1.25,1.5,2.,2.5,3.,4.))


def key(c):
    return json.dumps({k:c[k] for k in ('family','lookback','threshold','stop_atr','target_r','hold_bars','session_start','session_end','max_contracts','trailing_atr')}, sort_keys=True)


def universe():
    rng=random.Random(SEED); seen=set(); rows=[]
    for family in FAMILIES:
        for number in range(250):
            while True:
                left,right=rng.choice(((585,690),(600,720),(720,870),(840,945),(585,945)))
                c=dict(instrument=('MNQ','MES')[number%2],family=family,lookback=rng.choice(LOOKBACKS),
                       threshold=rng.choice(THRESHOLDS[family]),stop_atr=rng.choice((.75,1.,1.25,1.5,2.)),
                       target_r=rng.choice((1.5,2.,3.,4.,6.)),hold_bars=rng.choice((2,4,8,12,16)),
                       session_start=left,session_end=right,max_contracts=rng.choice((1,2)),trailing_atr=0.)
                semantic=key(c)
                if semantic not in seen: seen.add(semantic);break
            c['config_id']='novel_'+hashlib.sha256((c['instrument']+'|'+semantic).encode()).hexdigest()[:20]
            c['experiment_order']=len(rows);rows.append(c)
    assert len(rows)==len(seen)==2000
    return rows


def primitives(bars, peer):
    b=bars.reset_index(drop=True);t=pd.to_datetime(b.timestamp_utc,utc=True)
    segment=(b.contract.ne(b.contract.shift())|t.diff().ne(pd.Timedelta(minutes=15))).cumsum()
    def lag(s,n=1): return s.groupby(segment,sort=False).shift(n)
    r=np.log(b.close/lag(b.close))
    prior_volume=b.volume.groupby(segment,sort=False).shift().groupby(segment).rolling(20,min_periods=20).mean().droplevel(0).sort_index()
    volume=np.log(b.volume.replace(0,np.nan)/prior_volume.replace(0,np.nan))
    pt=pd.to_datetime(peer.timestamp_utc,utc=True)
    ps=(peer.contract.ne(peer.contract.shift())|pt.diff().ne(pd.Timedelta(minutes=15))).cumsum()
    pr=np.log(peer.close/peer.close.groupby(ps).shift())
    previous_pr=pr.groupby(ps).shift()
    context=pd.DataFrame(dict(timestamp_utc=peer.timestamp_utc,peer_r=pr,peer_lag=previous_pr))
    aligned=b[['timestamp_utc']].merge(context,on='timestamp_utc',how='left',validate='one_to_one')
    minute=(t.dt.tz_convert('America/New_York').dt.hour*60+t.dt.tz_convert('America/New_York').dt.minute).to_numpy()
    y=lag(r,-1).to_numpy(float)
    return dict(segment=segment,r=r.to_numpy(float),lag=lag(r).to_numpy(float),volume=volume.to_numpy(float),
                peer=aligned.peer_r.to_numpy(float),peer_lag=aligned.peer_lag.to_numpy(float),
                clock=minute,y=y,timestamp=pd.DatetimeIndex(t).as_unit('ns').asi8,
                notional=(b.close*b.volume).to_numpy(float),
                transition=np.where(np.isfinite(r)&np.isfinite(lag(r)),(r>0).astype(int)*2+(lag(r)>0).astype(int),-1))


def regress(x,y):
    a=np.column_stack((np.ones(len(x)),x));valid=np.isfinite(a).all(axis=1)&np.isfinite(y)
    if valid.sum()<100: return None
    a,y=a[valid],y[valid];scale=np.std(a[:,1:],axis=0);scale=np.where(scale>1e-12,scale,1.)
    standardized=np.column_stack((np.ones(len(a)),a[:,1:]/scale))
    ridge=np.eye(a.shape[1])*.01;ridge[0,0]=0
    coef=np.linalg.solve(standardized.T@standardized+ridge,standardized.T@y)
    return dict(coef=coef.tolist(),scale=scale.tolist(),target_std=float(np.std(y)),observations=int(len(y)))


def fit_model(p,family,lookback,cutoff):
    """Fit complete labels strictly before cutoff; never fits evaluated outcomes."""
    cutoff_ns=pd.Timestamp(cutoff).value
    eligible=np.flatnonzero(p['timestamp']+30*60*10**9<=cutoff_ns)
    # Lookback means prior observed sessions for fitted models, bars otherwise.
    ids=eligible[-lookback*92:]
    y=p['y'][ids]
    if family in ('markov_sign_grammar','clock_expectation'):
        states=p['transition'] if family=='markov_sign_grammar' else p['clock']
        valid=np.isfinite(y)&(states[ids]>=0)
        if valid.sum()<100: return dict(ready=False,fit_cutoff=str(cutoff))
        nstates=4 if family=='markov_sign_grammar' else 1440
        # Twenty zero-return pseudo-observations avoid tiny-state extremes.
        count=np.bincount(states[ids][valid],minlength=nstates)
        sums=np.bincount(states[ids][valid],weights=y[valid],minlength=nstates)
        m=dict(table=(sums/(count+20)).tolist(),counts=count.tolist(),target_std=float(np.std(y[valid])),observations=int(valid.sum()))
    else:
        cols={'autoregressive_forecast':('r','lag'),'volume_response_regression':('volume',),
              'cross_index_leadlag':('peer','peer_lag')}[family]
        m=regress(np.column_stack([p[k][ids] for k in cols]),y)
        if m is None: return dict(ready=False,fit_cutoff=str(cutoff))
        m['columns']=list(cols)
    m.update(ready=m['target_std']>1e-12,fit_cutoff=str(cutoff),last_label_end=str(pd.to_datetime(int(p['timestamp'][ids[-1]])+30*60*10**9,utc=True)))
    return m


def value(p,family,lookback,model=None):
    if family in FITTED:
        if model is None or not model['ready']: return np.full(len(p['r']),np.nan)
        if family in ('markov_sign_grammar','clock_expectation'):
            state=p['transition'] if family=='markov_sign_grammar' else p['clock']
            table=np.array(model['table']);counts=np.array(model['counts'])
            out=table[np.maximum(state,0)]/model['target_std']
            out=np.where((state>=0)&(counts[np.maximum(state,0)]>=20),out,np.nan)
        else:
            x=np.column_stack([p[k] for k in model['columns']])
            out=(np.column_stack((np.ones(len(x)),x/np.array(model['scale'])))@np.array(model['coef']))/model['target_std']
        return out
    r=pd.Series(p['r']);g=p['segment']
    def roll(s,op):return getattr(s.groupby(g).rolling(lookback,min_periods=lookback),op)().droplevel(0).sort_index()
    if family=='return_skew_exhaustion': return -roll(r,'skew').to_numpy(float)
    if family=='semivariance_exhaustion':
        total=roll(r*r,'sum');signed=roll(r*r*np.sign(r),'sum')
        return -(signed/total.replace(0,np.nan)).to_numpy(float)
    impact=r.abs()/pd.Series(p['notional']).replace(0,np.nan)
    # Benchmark excludes the current observation, while current completed impact is observable.
    benchmark=roll(impact.groupby(g).shift(),'mean')
    return (-np.sign(r)*impact/benchmark.replace(0,np.nan)).to_numpy(float)


def decisions(c,p,model=None):
    v=value(p,c['family'],c['lookback'],model)
    decision=p['clock']+15
    mask=np.isfinite(v)&(np.abs(v)>=c['threshold'])&(decision>=c['session_start'])&(decision<c['session_end'])
    return np.where(mask,np.sign(v),0).astype(np.int8)

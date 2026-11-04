"""Closed-bar price-action events; pending setups never backdate executions."""
from __future__ import annotations

import numpy as np
import pandas as pd

FAMILIES=('sweep_reclaim','failed_breakout','break_retest','opening_breakout','opening_fade','imbalance_retest','shock_reversal','vwap_trend_pullback')


def library():
    rows=[]
    for timeframe in ['15m','1h']:
        for family in FAMILIES:
            for reward in [1.5,3.]:
                rows.append(dict(id=f'{family}_{timeframe}_R{reward:g}',family=family,timeframe=timeframe,
                                 reward_r=reward,baseline=False,hold_bars=24))
        for family in ['flat','momentum']:
            rows.append(dict(id=f'{family}_{timeframe}',family=family,timeframe=timeframe,reward_r=2.,baseline=True,hold_bars=24))
    return rows


def detect(frame):
    """Raw entries/stops, independent of the two frozen exit target profiles."""
    h,l,o,c,v,a=[frame[k].to_numpy(float) for k in ['high','low','open','close','volume','atr']]
    upper=frame.high.shift().rolling(20,min_periods=20).max().to_numpy()
    lower=frame.low.shift().rolling(20,min_periods=20).min().to_numpy()
    average=frame.volume.shift().rolling(20,min_periods=20).mean().to_numpy()
    volume=np.divide(v,average,out=np.zeros(len(v)),where=average>0)
    fast=frame.close.ewm(span=50,adjust=False,min_periods=50).mean().to_numpy()
    slow=frame.close.ewm(span=200,adjust=False,min_periods=200).mean().to_numpy()
    vwap=frame.session_vwap.to_numpy(float)
    times=pd.DatetimeIndex(frame.timestamp)
    span=pd.Timedelta(frame.attrs['timeframe'])
    events=[];last={(f,d):-999999 for f in FAMILIES for d in [-1,1]}
    breakout=None;retest=None;gap=None;shock=None
    day=None;range_high=-np.inf;range_low=np.inf;range_bars=0;range_ready=False
    range_break_used=False;range_fade_used=False;range_excursion=None;vwap_count=0

    def emit(i,family,d,anchor,origin,session_end=None):
        if i-last[family,d]<6 or not np.isfinite(a[i]) or a[i]<=0:
            return
        if session_end is not None and times[i]+span>=session_end:
            return
        stop=min(anchor-d*.2*a[i],c[i]-a[i]) if d==1 else max(anchor-d*.2*a[i],c[i]+a[i])
        risk=d*(c[i]-stop)
        if not (stop>0 and .999999*a[i]<=risk<=4*a[i]):
            return
        events.append(dict(index=i,bar_open=str(times[i]),available_at=str(times[i]+span),family=family,direction=d,
                           planned_stop=float(stop),reference_close=float(c[i]),risk_distance=float(risk),
                           setup_id=f'{family}:{origin}:{i}',origin_index=origin,session_end=str(session_end) if session_end is not None else None))
        last[family,d]=i

    for i in range(1,len(frame)):
        current_day=times[i].floor('D')
        if day!=current_day:
            day=current_day;range_high=-np.inf;range_low=np.inf;range_bars=0;range_ready=False
            range_break_used=False;range_fade_used=False;range_excursion=None;vwap_count=0
        if times[i].hour==7:
            range_high=max(range_high,h[i]);range_low=min(range_low,l[i]);range_bars+=1
        if times[i].hour>=8 and range_bars==int(pd.Timedelta('1h')/span):
            range_ready=True
        if not np.isfinite(a[i]) or a[i]<=0 or not np.isfinite(upper[i]):
            continue
        # Sweep is confirmed by this candle's final close, never by its wick alone.
        width=h[i]-l[i]
        if width>0 and volume[i]>=1.2:
            if h[i]>upper[i]+.05*a[i] and c[i]<upper[i]-.05*a[i] and c[i]<o[i] and (h[i]-max(c[i],o[i]))/width>=.4:
                emit(i,'sweep_reclaim',-1,h[i],i)
            if l[i]<lower[i]-.05*a[i] and c[i]>lower[i]+.05*a[i] and c[i]>o[i] and (min(c[i],o[i])-l[i])/width>=.4:
                emit(i,'sweep_reclaim',1,l[i],i)
        # Process previously known breakouts before arming new ones.
        if breakout:
            b=breakout;d=b['direction']
            b['extreme']=max(b['extreme'],h[i]) if d==1 else min(b['extreme'],l[i])
            if i-b['index']>6:
                breakout=None
            elif d*(c[i]-b['level'])<-.05*a[i]:
                emit(i,'failed_breakout',-d,b['extreme'],b['index']);breakout=None
        if retest:
            b=retest;d=b['direction']
            if i-b['index']>8 or d*(c[i]-b['level'])<-.5*a[i]:
                retest=None
            else:
                near=l[i]<=b['level']+.2*a[i] and h[i]>=b['level']-.2*a[i]
                if near and d*(c[i]-b['level'])>=0:
                    b['touch']=i
                    b['anchor']=min(b.get('anchor',np.inf),l[i]) if d==1 else max(b.get('anchor',-np.inf),h[i])
                elif ('touch' in b and i>b['touch'] and d*(c[i]-o[i])>0
                      and (c[i]>h[i-1] if d==1 else c[i]<l[i-1])):
                    emit(i,'break_retest',d,b['anchor'],b['index']);retest=None
        outside=1 if c[i]>upper[i]+.1*a[i] else -1 if c[i]<lower[i]-.1*a[i] else 0
        if outside and volume[i]>=1.:
            known=dict(index=i,direction=outside,level=float(upper[i] if outside==1 else lower[i]),extreme=float(h[i] if outside==1 else l[i]))
            if breakout is None:
                breakout=known.copy()
            if retest is None:
                retest=known.copy()
        # Session boundary is fixed UTC, with the complete range gated above.
        if range_ready and 8<=times[i].hour<16 and range_high>range_low:
            d=1 if c[i]>range_high+.1*a[i] else -1 if c[i]<range_low-.1*a[i] else 0
            if not range_break_used and d and volume[i]>=1. and d*(c[i]-fast[i])>0:
                emit(i,'opening_breakout',d,range_low if d==1 else range_high,i,day+pd.Timedelta(hours=16))
                range_break_used=True
            if range_excursion and not range_fade_used:
                b=range_excursion;bd=b['direction']
                b['extreme']=max(b['extreme'],h[i]) if bd==1 else min(b['extreme'],l[i])
                if i-b['index']>4:
                    range_excursion=None
                elif bd*(c[i]-b['level'])<-.05*a[i]:
                    emit(i,'opening_fade',-bd,b['extreme'],b['index'],day+pd.Timedelta(hours=16))
                    range_fade_used=True;range_excursion=None
            if d and not range_excursion and not range_fade_used:
                range_excursion=dict(index=i,direction=d,level=range_high if d==1 else range_low,extreme=h[i] if d==1 else l[i])
        # Existing three-candle zone must be touched on a LATER completed candle.
        if gap:
            b=gap;d=b['direction']
            if i-b['index']>12 or (c[i]<b['lower']-.2*a[i] if d==1 else c[i]>b['upper']+.2*a[i]):
                gap=None
            elif (l[i]<=b['upper'] and c[i]>b['upper'] and c[i]>o[i] if d==1 else h[i]>=b['lower'] and c[i]<b['lower'] and c[i]<o[i]):
                emit(i,'imbalance_retest',d,b['lower'] if d==1 else b['upper'],b['index']);gap=None
        if i>=2 and np.isfinite(a[i-1]) and abs(c[i-1]-o[i-1])>=a[i-1]:
            if c[i-1]>o[i-1] and l[i]>h[i-2] and .2*a[i]<=l[i]-h[i-2]<=2*a[i]:
                gap=dict(index=i,direction=1,lower=h[i-2],upper=l[i])
            elif c[i-1]<o[i-1] and h[i]<l[i-2] and .2*a[i]<=l[i-2]-h[i]<=2*a[i]:
                gap=dict(index=i,direction=-1,lower=h[i],upper=l[i-2])
        if shock:
            b=shock;d=b['direction']
            b['extreme']=max(b['extreme'],h[i]) if d==1 else min(b['extreme'],l[i])
            if i-b['index']>3:
                shock=None
            elif d*(c[i]-b['midpoint'])<0 and d*(c[i]-o[i])<0:
                emit(i,'shock_reversal',-d,b['extreme'],b['index']);shock=None
        if (np.isfinite(a[i-1]) and width>=2.5*a[i-1] and width>0 and abs(c[i]-o[i])>=.5*width and volume[i]>=2.):
            d=1 if c[i]>o[i] else -1
            outer=(c[i]-l[i])/width>=.75 if d==1 else (c[i]-l[i])/width<=.25
            if outer:
                shock=dict(index=i,direction=d,midpoint=(h[i]+l[i])/2,extreme=h[i] if d==1 else l[i])
        if i>=200 and vwap_count<2 and volume[i]>=1. and np.isfinite(vwap[i]):
            d=1 if fast[i]>slow[i] and fast[i]>fast[i-8] else -1 if fast[i]<slow[i] and fast[i]<fast[i-8] else 0
            touch=l[i]<=vwap[i]+.25*a[i] and h[i]>=vwap[i]-.25*a[i]
            confirm=(c[i]>h[i-1] and c[i]>o[i] if d==1 else c[i]<l[i-1] and c[i]<o[i])
            if d and touch and confirm and d*(c[i]-vwap[i])>0:
                emit(i,'vwap_trend_pullback',d,l[i] if d==1 else h[i],i,day+pd.Timedelta(days=1))
                vwap_count+=1
    columns=['index','bar_open','available_at','family','direction','planned_stop','reference_close','risk_distance','setup_id','origin_index','session_end']
    return pd.DataFrame(events,columns=columns)


def signalize(frame,spec,events=None):
    out=frame.copy().reset_index(drop=True)
    if spec['family']=='momentum':
        out['signal']=np.sign(out.close.pct_change(48,fill_method=None)).fillna(0).astype(np.int8)
        out['setup_id']=None;out['planned_stop']=np.nan;out['planned_target']=np.nan
        return out
    if spec['family']=='flat':
        chosen=pd.DataFrame()
    else:
        events=detect(out) if events is None else events
        chosen=events[events.family.eq(spec['family'])].copy()
        chosen['planned_target']=chosen.reference_close+chosen.direction*spec['reward_r']*chosen.risk_distance
        chosen=chosen[chosen.risk_distance*spec['reward_r']>=chosen.reference_close*.003]
    by_index={int(e['index']):e for e in chosen.to_dict('records')} if len(chosen) else {}
    state=None;signals=[];ids=[];stops=[];targets=[]
    span=pd.Timedelta(spec['timeframe'])
    for i,row in enumerate(out.itertuples(index=False)):
        if state:
            ends=state.get('session_end')
            session_expired=ends is not None and pd.notna(ends) and row.timestamp+span>=pd.Timestamp(ends)
            if (i-state['index']>=spec['hold_bars'] or session_expired
                    or state['direction']*(row.close-state['planned_stop'])<=0
                    or state['direction']*(row.close-state['planned_target'])>=0):
                state=None
        if i in by_index:
            state=by_index[i]
        signals.append(state['direction'] if state else 0);ids.append(state['setup_id'] if state else None)
        stops.append(state['planned_stop'] if state else np.nan);targets.append(state['planned_target'] if state else np.nan)
    out['signal']=np.asarray(signals,dtype=np.int8);out['setup_id']=pd.Series(ids,dtype=object)
    out['planned_stop']=stops;out['planned_target']=targets
    return out

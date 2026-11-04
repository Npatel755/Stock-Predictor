"""Deterministic geometric formations; all extrema wait for right-hand bars."""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

FAMILIES = ('head_shoulders', 'double_top_bottom', 'triangle', 'flag', 'rectangle', 'pattern_mix')
TIMEFRAMES = ('15m', '30m', '1h')


def library():
    rows = []
    for timeframe in TIMEFRAMES:
        for sensitivity, width, tolerance, prominence in [('responsive', 2, 1.25, .25), ('selective', 3, .75, .5)]:
            for family in FAMILIES:
                rows.append(dict(id=f'{family}_{timeframe}_{sensitivity}', family=family, timeframe=timeframe,
                                 sensitivity=sensitivity, pivot_width=width, tolerance_atr=tolerance,
                                 head_prominence_atr=prominence, baseline=False, hold_bars=24))
        for family in ['flat', 'momentum']:
            rows.append(dict(id=f'{family}_{timeframe}', family=family, timeframe=timeframe,
                             sensitivity='baseline', baseline=True, hold_bars=24))
    return rows


def line(points):
    """Small local least-squares line through already confirmed contact points."""
    x = np.asarray([p['index'] for p in points], dtype=float)
    y = np.asarray([p['price'] for p in points], dtype=float)
    origin = float(x[0])
    slope = float(np.dot(x-x.mean(), y-y.mean())/np.dot(x-x.mean(), x-x.mean()))
    intercept = float(y.mean()-slope*(x.mean()-origin))
    residual = float(np.max(np.abs(y-(intercept+slope*(x-origin)))))
    return dict(origin=origin, intercept=intercept, slope=slope, residual=residual)


def value(boundary, index):
    return boundary['intercept']+boundary['slope']*(index-boundary['origin'])


def _neck(points):
    return line(points)


def _trend_before(point, orientation, fast, slow):
    j = point['index']
    return np.isfinite(slow[j]) and orientation*(fast[j]-slow[j]) > 0


def recognize(pivots, atr, tolerance, prominence, fast, slow, formed_at):
    """Templates depend only on the supplied confirmed pivot prefix."""
    templates = {}
    if len(pivots) >= 5:
        p = pivots[-5:]
        orientation = p[0]['kind']
        z = [orientation*x['price'] for x in p]
        span = p[-1]['index']-p[0]['index']
        left = p[2]['index']-p[0]['index']
        right = p[4]['index']-p[2]['index']
        neckline = _neck([p[1],p[3]])
        height = orientation*(p[2]['price']-value(neckline,p[2]['index']))
        valid = (orientation in [-1,1] and [x['kind'] for x in p] == [orientation,-orientation,orientation,-orientation,orientation]
                 and 8 <= span <= 96 and right > 0 and .25 <= left/right <= 4.
                 and z[2]-max(z[0],z[4]) >= prominence*atr
                 and abs(z[0]-z[4]) <= tolerance*atr
                 and min(z[0]-z[1],z[4]-z[3]) >= .5*atr
                 and abs(z[1]-z[3]) <= 2*atr and height >= atr
                 and _trend_before(p[0],orientation,fast,slow))
        if valid:
            templates['head_shoulders'] = dict(family='head_shoulders', mode='neck', direction=-orientation,
                                               neckline=neckline, height=height, stop_anchor=p[-1]['price'],
                                               invalidation=p[2]['price'], points=p, formed_at=formed_at)
    if len(pivots) >= 3:
        p = pivots[-3:]
        orientation = p[0]['kind']
        z = [orientation*x['price'] for x in p]
        height = min(z[0],z[2])-z[1]
        valid = ([x['kind'] for x in p] == [orientation,-orientation,orientation]
                 and 4 <= p[-1]['index']-p[0]['index'] <= 80
                 and abs(z[0]-z[2]) <= tolerance*atr and height >= atr
                 and _trend_before(p[0],orientation,fast,slow))
        if valid:
            templates['double_top_bottom'] = dict(family='double_top_bottom', mode='neck', direction=-orientation,
                                                  neckline=dict(origin=p[1]['index'],intercept=p[1]['price'],slope=0.),
                                                  height=height, stop_anchor=p[-1]['price'],
                                                  invalidation=max(x['price'] for x in p) if orientation==1 else min(x['price'] for x in p),
                                                  points=p, formed_at=formed_at)
    if len(pivots) >= 6:
        p = pivots[-6:]
        highs, lows = [x for x in p if x['kind']==1], [x for x in p if x['kind']==-1]
        if len(highs)==3 and len(lows)==3 and 8 <= p[-1]['index']-p[0]['index'] <= 96:
            upper, lower = line(highs), line(lows)
            first, last = p[0]['index'], p[-1]['index']
            initial = value(upper,first)-value(lower,first)
            width = value(upper,last)-value(lower,last)
            slopes = (upper['slope'] < -.01*atr and lower['slope'] > .01*atr
                      or abs(upper['slope']) <= .02*atr and lower['slope'] > .02*atr
                      or upper['slope'] < -.02*atr and abs(lower['slope']) <= .02*atr)
            if (initial >= 2*atr and .25*initial <= width <= .85*initial and slopes
                    and max(upper['residual'],lower['residual']) <= .75*atr):
                templates['triangle'] = dict(family='triangle',mode='bounds',upper=upper,lower=lower,
                                              height=initial,points=p,formed_at=formed_at)
    if len(pivots) >= 4:
        p = pivots[-4:]
        highs, lows = [x for x in p if x['kind']==1], [x for x in p if x['kind']==-1]
        if len(highs)==2 and len(lows)==2 and 6 <= p[-1]['index']-p[0]['index'] <= 96:
            up = np.mean([x['price'] for x in highs]); down = np.mean([x['price'] for x in lows])
            if (abs(highs[0]['price']-highs[1]['price']) <= tolerance*atr
                    and abs(lows[0]['price']-lows[1]['price']) <= tolerance*atr and 1.5*atr <= up-down <= 5*atr):
                templates['rectangle'] = dict(family='rectangle',mode='bounds',
                                               upper=dict(origin=0,intercept=up,slope=0.),
                                               lower=dict(origin=0,intercept=down,slope=0.),
                                               height=up-down,points=p,formed_at=formed_at)
    return templates


def _event(frame, index, template, direction, level, atr):
    close = float(frame.close.iloc[index])
    if template['mode']=='neck':
        anchor = template['stop_anchor']
    else:
        anchor = value(template['lower'] if direction==1 else template['upper'],index)
    raw_stop = anchor-direction*.25*atr
    stop = min(raw_stop,close-atr) if direction==1 else max(raw_stop,close+atr)
    target = level+direction*template['height']
    risk, reward = direction*(close-stop), direction*(target-close)
    if not (0 < stop and atr <= risk <= 6*atr and reward >= max(.5*risk,close*.003)):
        return None
    points = template['points']
    key = template['family']+':'+','.join(f'{p["kind"]}@{p["index"]}' for p in points)
    duration = pd.Timedelta(frame.attrs['timeframe'])
    return dict(index=index, bar_open=str(frame.timestamp.iloc[index]), available_at=str(frame.timestamp.iloc[index]+duration),
                family=template['family'],direction=direction,setup_id=key,
                planned_stop=stop,planned_target=target,break_level=float(level),height=float(template['height']),
                formed_at=template['formed_at'],points=json.dumps(points))


def detect(frame, sensitivity):
    """Return breakout events and raw confirmed extrema, never backdated signals."""
    width,tolerance,prominence = (2,1.25,.25) if sensitivity=='responsive' else (3,.75,.5)
    high,low,close,atr = [frame[c].to_numpy(float) for c in ['high','low','close','atr']]
    fast = frame.close.ewm(span=20,adjust=False,min_periods=20).mean().to_numpy()
    slow = frame.close.ewm(span=50,adjust=False,min_periods=50).mean().to_numpy()
    pivots,raw_pivots,templates,events,used = [],[],{},[],set()
    last_flag = {1:-999999,-1:-999999}
    for i in range(len(frame)):
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        j = i-width
        if j >= width:
            is_high = high[j] >= np.max(high[j-width:j]) and high[j] > np.max(high[j+1:i+1])
            is_low = low[j] <= np.min(low[j-width:j]) and low[j] < np.min(low[j+1:i+1])
            # An outside bar that is both extrema has no known internal ordering.
            if is_high != is_low:
                p = dict(index=j,confirmed_at=i,kind=1 if is_high else -1,price=float(high[j] if is_high else low[j]))
                raw_pivots.append(p.copy())
                changed = False
                if not pivots or pivots[-1]['kind'] != p['kind']:
                    pivots.append(p); changed=True
                elif p['kind']*(p['price']-pivots[-1]['price']) >= 0:
                    pivots[-1]=p; changed=True
                if changed:
                    templates.update(recognize(pivots[-6:],atr[i],tolerance,prominence,fast,slow,i))
        if i == 0:
            continue
        for family,template in list(templates.items()):
            if i-template['formed_at'] > 24:
                templates.pop(family); continue
            buffer = .05*atr[i]
            if template['mode']=='neck':
                d = template['direction']
                if d*(close[i]-template['invalidation']) < 0:
                    templates.pop(family); continue
                boundary = template['neckline']
                level,previous = value(boundary,i),value(boundary,i-1)
                crossed = d*(close[i]-level) > buffer and d*(close[i-1]-previous) <= buffer
            else:
                upper,lower=template['upper'],template['lower']
                if value(upper,i) <= value(lower,i):
                    templates.pop(family); continue
                up = close[i] > value(upper,i)+buffer and close[i-1] <= value(upper,i-1)+buffer
                down = close[i] < value(lower,i)-buffer and close[i-1] >= value(lower,i-1)-buffer
                crossed=up or down; d=1 if up else -1
                level=value(upper if d==1 else lower,i)
            if crossed:
                event=_event(frame,i,template,d,level,atr[i])
                if event and event['setup_id'] not in used:
                    events.append(event); used.add(event['setup_id'])
                templates.pop(family,None)
        if i >= 70:
            # Flagpole and consolidation end BEFORE the breakout candle.
            pole=close[i-9]-float(frame.open.iloc[i-20]); d=1 if pole>0 else -1
            height=abs(pole)
            h,l=np.max(high[i-8:i]),np.min(low[i-8:i])
            slope=float(np.polyfit(np.arange(8),close[i-8:i],1)[0])
            progress=d*(close[i-1]-close[i-9])
            valid=(height>=3*atr[i-8] and h-l <= .65*height
                   and -.65*height <= progress <= .1*height and d*slope <= .1*atr[i]
                   and d*(fast[i-9]-slow[i-9])>0 and i-last_flag[d]>=12)
            level=h if d==1 else l
            if valid and d*(close[i]-level)>.05*atr[i]:
                p=[dict(index=i-20,confirmed_at=i-20,kind=-d,price=float(frame.open.iloc[i-20])),
                   dict(index=i-9,confirmed_at=i-9,kind=d,price=float(close[i-9])),
                   dict(index=i-1,confirmed_at=i-1,kind=-d,price=float(l if d==1 else h))]
                template=dict(family='flag',mode='bounds',upper=dict(origin=0,intercept=h,slope=0.),
                              lower=dict(origin=0,intercept=l,slope=0.),height=height,points=p,formed_at=i-1)
                event=_event(frame,i,template,d,level,atr[i])
                if event:
                    events.append(event);last_flag[d]=i
    columns=['index','bar_open','available_at','family','direction','setup_id','planned_stop','planned_target',
             'break_level','height','formed_at','points']
    return pd.DataFrame(events,columns=columns),pd.DataFrame(raw_pivots,columns=['index','confirmed_at','kind','price'])


def signalize(frame, spec, events=None):
    out=frame.copy().reset_index(drop=True)
    if spec['family']=='flat':
        chosen=pd.DataFrame()
    elif spec['family']=='momentum':
        signal=np.sign(out.close.pct_change(48,fill_method=None)).fillna(0).astype(int)
        out['signal']=signal
        # Baseline is intentionally the same persistent-direction process as
        # the prior study, rather than a claim of distinct geometric setups.
        out['setup_id']=None;out['planned_stop']=np.nan;out['planned_target']=np.nan
        return out
    else:
        if events is None:
            events,_=detect(out,spec['sensitivity'])
        chosen=events if spec['family']=='pattern_mix' else events[events.family.eq(spec['family'])]
    by_index={}
    if len(chosen):
        for index,group in chosen.groupby('index',sort=True):
            if group.direction.nunique()==1:
                priority={f:n for n,f in enumerate(FAMILIES)}
                by_index[int(index)]=min(group.to_dict('records'),key=lambda r:priority[r['family']])
    state=None
    signals=[];ids=[];stops=[];targets=[]
    for i,close in enumerate(out.close.to_numpy(float)):
        if state and (i-state['index']>=spec['hold_bars'] or state['direction']*(close-state['planned_stop'])<=0
                      or state['direction']*(close-state['planned_target'])>=0):
            state=None
        if i in by_index:
            state=by_index[i]
        signals.append(state['direction'] if state else 0)
        ids.append(state['setup_id'] if state else None)
        stops.append(state['planned_stop'] if state else np.nan)
        targets.append(state['planned_target'] if state else np.nan)
    out['signal']=np.asarray(signals,dtype=np.int8)
    out['setup_id']=pd.Series(ids,dtype=object);out['planned_stop']=stops;out['planned_target']=targets
    return out

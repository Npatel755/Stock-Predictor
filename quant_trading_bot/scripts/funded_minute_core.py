"""Joint minute-OHLC research replay. No daily P&L clipping.

Program risk uses conservative simultaneous adverse quotes across assets.
Intrabar liquidation uses those adverse prices plus market costs, not a magic
fill at exactly the DLL/floor. Exact tick order and real broker latency unknown.
"""
import math
import numpy as np
from numba import njit


@njit(cache=True)
def market_fill(price,direction,adverse):
    value=price+direction*adverse
    return (math.ceil(value/.25-1e-10) if direction>0 else math.floor(value/.25+1e-10))*.25


@njit(cache=True)
def close_slot(slot,ref,limit,reason,i,qty,side,asset,entry,fee_entry,eindex,sig_id,hist,exit_hist,cash,since,
               fee,adverse,logs,nlog):
    q=qty[slot];s=side[slot];mult=2. if asset[slot]==0 else 5.
    price=ref if limit else market_fill(ref,-s,adverse)
    delta=s*q*(price-entry[slot])*mult-fee*q
    net=delta-fee_entry[slot]
    cash+=delta;since+=delta
    logs[nlog,0]=sig_id[slot];logs[nlog,1]=eindex[slot];logs[nlog,2]=i;logs[nlog,3]=s;logs[nlog,4]=q
    logs[nlog,5]=entry[slot];logs[nlog,6]=price;logs[nlog,7]=net;logs[nlog,8]=fee*q+fee_entry[slot]
    logs[nlog,9]=reason;logs[nlog,10]=cash
    if hist[slot]>=0:exit_hist[hist[slot]]=i
    qty[slot]=0
    return cash,since,nlog+1


@njit(cache=True)
def payout(cash,since,paid,requests,wins,keep,mode):
    cap=1500.;available=cash-max(2000.,keep)
    if mode==1 and wins>=5:cap=8000.;available=min(available,.5*cash)
    if requests>0 and since<=0:return cash,since,paid,requests,wins,0.
    amount=min(cap,available,max(0.,since))
    if amount<250:return cash,since,paid,requests,wins,0.
    return cash-amount,0.,paid+amount,requests+1,0,amount


@njit(cache=True)
def replay(ts,trade_day,ohlc,contracts,capacity,news_limit,entry_allowed,signals,start_day,end_day,
           keep,equal_risk,fraction,night_always,payout_mode,cost_factor,trace=False):
    # signals: entryindex,decision_ns,asset,side,stopdist/percent,targetR,
    # expiry_ns,baseweight,night. Quotes are [asset,open/high/low/close,time].
    slots=8;n=len(ts);ns=len(signals);logs=np.zeros((ns+8,11));nlog=0
    qty=np.zeros(slots,np.int64);side=np.zeros(slots,np.int64);asset=np.zeros(slots,np.int64)
    entry=np.zeros(slots);stop=np.zeros(slots);target=np.zeros(slots);expires=np.zeros(slots,np.int64)
    fee_entry=np.zeros(slots);eindex=np.zeros(slots,np.int64);sig_id=np.zeros(slots,np.int64);contract_at=np.zeros(slots,np.int64)
    hist=np.full(slots,-1,np.int64);hist_entry=np.zeros(ns+8,np.int64);hist_exit=np.full(ns+8,n+1,np.int64);nhist=0
    last_quote=np.full(2,-1,np.int64)
    available=np.zeros(2,np.bool_);refs=np.zeros(slots);used_capacity=np.zeros(2,np.int64)
    cash=0.;paid=0.;since=0.;requests=0;wins=0;dll_days=0;floor_closed=0;inactive_closed=0;data_fault=0
    day_start=0.;day=-1;paused=False;tier=1;peak=0.;maxdd=0.;last_trade_day=start_day;trades=0;maxqty=0;minroom=2000.
    fee=.5*cost_factor;adv=.5*cost_factor;signal_pointer=0
    lo=np.searchsorted(trade_day,start_day);hi=np.searchsorted(trade_day,end_day)
    while signal_pointer<ns and signals[signal_pointer,0]<lo:signal_pointer+=1
    for i in range(lo,hi):
        thisday=trade_day[i]
        if thisday!=day:
            if day>=0:
                if np.sum(qty)>0:data_fault=1;break
                net=cash-day_start
                if net>=150.:wins+=1
                cash,since,paid,requests,wins,_=payout(cash,since,paid,requests,wins,keep,payout_mode)
            if thisday-last_trade_day>30*86400000000000:inactive_closed=1;break
            day=thisday;day_start=cash;paused=False
            tier=4 if cash>=6500 else 3 if cash>=4800 else 2 if cash>=4000 else 1
        if np.sum(qty)==0 and (signal_pointer>=ns or signals[signal_pointer,0]!=i):continue
        used_capacity[0]=0;used_capacity[1]=0
        for a in range(2):
            available[a]=np.isfinite(ohlc[a,0,i])
            if available[a]:
                # Never value an old-contract position using new-contract bars.
                for k in range(slots):
                    if qty[k]>0 and asset[k]==a:
                        if contracts[a,i]!=contract_at[k]:data_fault=1
                        if last_quote[a]>=0 and ts[i]-ts[last_quote[a]]>5*60000000000:data_fault=1
                last_quote[a]=i
            else:
                for k in range(slots):
                    if qty[k]>0 and asset[k]==a and last_quote[a]>=0 and ts[i]-ts[last_quote[a]]>5*60000000000:data_fault=1
        if data_fault:break
        floor=0. if requests>0 else -2000.
        # 1. Mark at actual opening quotes. Gap triggers liquidate at opens.
        openeq=cash;allquotes=True
        for k in range(slots):
            if qty[k]==0:continue
            a=asset[k]
            mult=2. if a==0 else 5.
            if not available[a]:
                allquotes=False
                if last_quote[a]<0:data_fault=1;break
                ref=ohlc[a,3,last_quote[a]]
            else:ref=ohlc[a,0,i]
            openeq+=side[k]*qty[k]*(ref-entry[k])*mult-(fee+adv*mult)*qty[k]
        if data_fault:break
        if not allquotes and (openeq<=floor or openeq<=day_start-1000.):data_fault=1;break
        if allquotes and np.sum(qty)>0 and (openeq<=floor or openeq<=day_start-1000.):
            if not paused:dll_days+=int(openeq<=day_start-1000.)
            paused=True
            for k in range(slots):
                if qty[k]>0:
                    cash,since,nlog=close_slot(k,ohlc[asset[k],0,i],False,6,i,qty,side,asset,entry,fee_entry,eindex,sig_id,hist,hist_exit,cash,since,fee,adv,logs,nlog)
            minroom=min(minroom,cash-floor)
            if openeq<=floor or cash<=floor:floor_closed=1;break
        # 2. Scheduled source exits at the first available tradable open.
        for k in range(slots):
            if qty[k]>0 and ts[i]>=expires[k] and available[asset[k]]:
                cash,since,nlog=close_slot(k,ohlc[asset[k],0,i],False,2,i,qty,side,asset,entry,fee_entry,eindex,sig_id,hist,hist_exit,cash,since,fee,adv,logs,nlog)
        if cash<=floor and np.sum(qty)==0:floor_closed=1;break
        if cash-day_start<=-1000.:
            if not paused:dll_days+=1
            paused=True
        # 3. Entry decisions use current opening quotes and known risk only.
        while signal_pointer<ns and signals[signal_pointer,0]==i:
            j=signal_pointer;signal_pointer+=1
            if paused or not entry_allowed[i]:continue
            s=signals[j];a=int(s[2]);direction=int(s[3]);night=s[8]>0
            if s[6]<=ts[i]:continue
            if not available[a]:data_fault=1;continue
            if night and not night_always and cash<500.:continue
            if cash-day_start<=(-400. if tier==1 else -700.):continue
            block=False
            if not night:
                for h in range(nhist):
                    if ts[hist_entry[h]]<=s[1] and (hist_exit[h]>=n or ts[hist_exit[h]]>s[1]):block=True;break
            if block:continue
            for k in range(slots):
                if qty[k]>0 and (not available[asset[k]] or (asset[k]==a and side[k]!=direction)):block=True
            if block:continue
            total=int(np.sum(qty));limit=min(20,int(news_limit[i]));roomq=max(0,limit-total)
            if roomq==0:continue
            price=market_fill(ohlc[a,0,i],direction,adv);mult=2. if a==0 else 5.
            dist=s[4] if not night else ohlc[a,0,i]*.0055+adv
            risk=dist*mult+2*fee+(2*adv+.25)*mult
            equity=cash;reserved=0.
            for k in range(slots):
                if qty[k]>0:
                    ak=asset[k];mk=2. if ak==0 else 5.;current=ohlc[ak,0,i]
                    equity+=side[k]*qty[k]*(current-entry[k])*mk-fee*qty[k]
                    reserved+=max(0.,side[k]*(current-stop[k]))*mk*qty[k]+(fee+adv*mk)*qty[k]
            budget=900.
            if fraction>0.:budget=min(budget,fraction*max(0.,equity-floor-reserved),fraction*max(0.,1000.+equity-day_start-reserved))
            desired=300.*tier*s[7]/risk if equal_risk else tier*s[7]
            q=int(min(roomq,max(0,int(capacity[a,i])-used_capacity[a]),math.floor(desired),math.floor(budget/risk)))
            if q<1:continue
            slot=-1
            for k in range(slots):
                if qty[k]==0:slot=k;break
            if slot<0:data_fault=1;break
            qty[slot]=q;side[slot]=direction;asset[slot]=a;entry[slot]=price;stop[slot]=price-direction*dist
            target[slot]=round((price+direction*dist*s[5])/.25)*.25 if s[5]>0 else (1e30 if direction>0 else -1e30)
            expires[slot]=int(s[6]);fee_entry[slot]=fee*q;eindex[slot]=i;sig_id[slot]=j;contract_at[slot]=contracts[a,i]
            cash-=fee*q;since-=fee*q;last_trade_day=thisday;trades+=1;maxqty=max(maxqty,int(np.sum(qty)))
            used_capacity[a]+=q
            if not night:
                hist[slot]=nhist;hist_entry[nhist]=i;hist_exit[nhist]=n+1;nhist+=1
            else:hist[slot]=-1
        if data_fault:break
        # 4. Adverse minute occurs before favorable target when order unknown.
        worst=cash;canclose=True
        for k in range(slots):
            if qty[k]==0:continue
            a=asset[k];mult=2. if a==0 else 5.
            if not available[a]:
                canclose=False
                if last_quote[a]<0:data_fault=1;break
                ref=ohlc[a,3,last_quote[a]];refs[k]=ref
                exitprice=market_fill(ref,-side[k],adv)
                worst+=side[k]*qty[k]*(exitprice-entry[k])*mult-fee*qty[k]
                continue
            opening=ohlc[a,0,i];low=ohlc[a,2,i];high=ohlc[a,1,i]
            hit=(low<=stop[k]) if side[k]>0 else (high>=stop[k])
            ref=(min(opening,stop[k]) if side[k]>0 else max(opening,stop[k])) if hit else (low if side[k]>0 else high)
            refs[k]=ref
            exitprice=market_fill(ref,-side[k],adv)
            worst+=side[k]*qty[k]*(exitprice-entry[k])*mult-fee*qty[k]
        if data_fault:break
        minroom=min(minroom,worst-floor)
        wealth_low=worst+paid;maxdd=max(maxdd,peak-wealth_low)
        if worst<=floor or worst<=day_start-1000.:
            if not canclose:data_fault=1;break
            if not paused:dll_days+=int(worst<=day_start-1000.)
            paused=True
            for k in range(slots):
                if qty[k]>0:
                    cash,since,nlog=close_slot(k,refs[k],False,6,i,qty,side,asset,entry,fee_entry,eindex,sig_id,hist,hist_exit,cash,since,fee,adv,logs,nlog)
            if worst<=floor or cash<=floor:floor_closed=1;break
        else:
            for k in range(slots):
                if qty[k]==0 or not available[asset[k]]:continue
                a=asset[k];opening=ohlc[a,0,i];high=ohlc[a,1,i];low=ohlc[a,2,i]
                hit=low<=stop[k] if side[k]>0 else high>=stop[k]
                target_hit=high>=target[k]+.25 if side[k]>0 else low<=target[k]-.25
                if hit:
                    ref=min(opening,stop[k]) if side[k]>0 else max(opening,stop[k])
                    cash,since,nlog=close_slot(k,ref,False,3,i,qty,side,asset,entry,fee_entry,eindex,sig_id,hist,hist_exit,cash,since,fee,adv,logs,nlog)
                elif target_hit:
                    cash,since,nlog=close_slot(k,target[k],True,4,i,qty,side,asset,entry,fee_entry,eindex,sig_id,hist,hist_exit,cash,since,fee,adv,logs,nlog)
        # Available last trade marks only; never fill on a carried quote.
        equity=cash
        for k in range(slots):
            if qty[k]>0:
                a=asset[k];last=last_quote[a]
                if last<0:data_fault=1;break
                mult=2. if a==0 else 5.
                equity+=side[k]*qty[k]*(ohlc[a,3,last]-entry[k])*mult-fee*qty[k]
        peak=max(peak,equity+paid)
        if data_fault:break
    if not floor_closed and not inactive_closed and not data_fault:
        if np.sum(qty)>0:data_fault=1
        elif day>=0:
            if cash-day_start>=150:wins+=1
            cash,since,paid,requests,wins,_=payout(cash,since,paid,requests,wins,keep,payout_mode)
            if end_day-last_trade_day>30*86400000000000:inactive_closed=1
    value=.9*paid
    if not floor_closed and not inactive_closed and not data_fault:value+=.9*max(0.,cash-2000.)
    openfees=float(np.sum(fee_entry*(qty>0)))
    metrics=np.array([.9*paid,paid,cash,cash+paid,value,float(requests),float(trades),float(floor_closed),float(dll_days),float(inactive_closed),float(data_fault),maxdd,float(maxqty),minroom,openfees])
    return metrics,logs[:nlog].copy()

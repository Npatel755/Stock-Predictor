"""Account-floor/DLL bound screen, no global drawdown filter or loss clipping.

Bound touches are UNRESOLVED, not simulated broker liquidations or confirmed
violations. Claims require zero touches: accepted paths never need unknown
forced-fill reconstruction. Opportunities are intraday-only and one position.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def replay(days,offsets,tin,tout,per,risk,weight,adverse,favorable,start,end,keep,max_m,initial_m,cap,fraction):
    bal=0.;paid=0.;since=0.;pnl=0.;peak=0.;dd=0.;payouts=0;trades=0;floor_flag=0;dll_flag=0;maxq=0.;mindll=1000.;minfloor=2000.
    busy=-1;last=start;maxgap=0.
    for di in range(len(days)):
        if days[di]<start or days[di]>=end:continue
        daynet=0.;m=1
        if bal>=4000.:m=2
        if bal>=4800.:m=3
        if bal>=6500.:m=4
        m=min(max(m,initial_m),max_m)
        stop=400. if m==1 else 700.
        floor=0. if payouts>0 else -2000.
        for j in range(offsets[di],offsets[di+1]):
            if tout[j]>=end or tin[j]<busy:continue
            if daynet<=-stop:break
            allowed=cap
            if fraction>0.:
                allowed=min(allowed,max(0.,bal-floor)*fraction,max(0.,1000.+daynet)*fraction)
            q=min(m*weight[j],20.,np.floor(allowed/risk[j]))
            if q<1.:continue
            # Current excursions cannot select quantity. They assess whether
            # the unchanged saved fill path provably avoids program controls.
            loss=min(adverse[j],per[j])*q
            floor_room=bal+loss-floor;dll_room=1000.+daynet+loss
            minfloor=min(minfloor,floor_room);mindll=min(mindll,dll_room)
            if floor_room<=0.:floor_flag=1
            if dll_room<=0.:dll_flag=1
            if floor_flag or dll_flag:break
            high=max(peak,pnl+favorable[j]*q)
            dd=max(dd,high-(pnl+loss));peak=high
            result=per[j]*q;bal+=result;daynet+=result;since+=result;pnl+=result;peak=max(peak,pnl)
            maxq=max(maxq,q);trades+=1;maxgap=max(maxgap,(tin[j]-last)/86400000000000.);last=tin[j];busy=tout[j]
        if floor_flag or dll_flag:break
        # Conservative trader choice: never withdraw more than new profit
        # since the last request. This is stricter than an eligibility check.
        if (payouts==0 or since>0.) and bal-max(keep,2000.)>=250.:
            w=min(1500.,bal-max(keep,2000.),max(0.,since))
            if w>=250.:bal-=w;paid+=w;payouts+=1;since=0.
    valid=floor_flag==0 and dll_flag==0
    # On unresolved paths, ending assets are not valued. This is not a claim
    # that a DLL would close the account; full forced-fill replay is missing.
    value=.9*paid+(.9*max(0.,bal-2000.) if valid else 0.)
    maxgap=max(maxgap,(end-last)/86400000000000.)
    return np.array([paid,.9*paid,bal,pnl,value,float(payouts),float(trades),float(floor_flag),float(dll_flag),dd,maxq,minfloor,mindll,maxgap])


def reference(days,offsets,tin,tout,per,risk,weight,adverse,favorable,start,end,keep,max_m,initial_m,cap,fraction):
    balance=withdrawals=since=trading=peak=dd=0.;counts=n=0;busy=-1;last=start;gap=0.;floorflag=dllflag=False;maxqty=0.;floorroom=2000.;dllroom=1000.
    for d,day in enumerate(days):
        if not start<=day<end:continue
        size=min(max_m,max(initial_m,4 if balance>=6500 else 3 if balance>=4800 else 2 if balance>=4000 else 1))
        daypnl=0.;personal=400. if size==1 else 700.;floor=0. if counts else -2000.
        for j in range(offsets[d],offsets[d+1]):
            if tout[j]>=end or tin[j]<busy:continue
            if daypnl<=-personal:break
            budget=min(cap,max(0.,balance-floor)*fraction,max(0.,1000+daypnl)*fraction) if fraction else cap
            q=min(size*weight[j],20,int(budget//risk[j]))
            if q<1:continue
            low=min(per[j],adverse[j])*q
            floorroom=min(floorroom,balance+low-floor);dllroom=min(dllroom,1000+daypnl+low)
            floorflag|=balance+low<=floor;dllflag|=daypnl+low<=-1000
            if floorflag or dllflag:break
            high=max(peak,trading+favorable[j]*q);dd=max(dd,high-(trading+low))
            change=per[j]*q;balance+=change;since+=change;daypnl+=change;trading+=change;peak=max(high,trading)
            maxqty=max(maxqty,q);n+=1;gap=max(gap,float(tin[j]-last)/86400000000000.);last=tin[j];busy=tout[j]
        if floorflag or dllflag:break
        if (not counts or since>0) and balance>=max(keep,2000)+250:
            cash=min(1500.,balance-max(keep,2000),max(0,since))
            if cash>=250:balance-=cash;withdrawals+=cash;counts+=1;since=0.
    valid=not(floorflag or dllflag)
    value=.9*withdrawals+(.9*max(0,balance-2000) if valid else 0)
    gap=max(gap,float(end-last)/86400000000000.)
    return np.array([withdrawals,.9*withdrawals,balance,trading,value,counts,n,int(floorflag),int(dllflag),dd,maxqty,floorroom,dllroom,gap])

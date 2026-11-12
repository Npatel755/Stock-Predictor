"""Causal sizing overlay over a fixed nonoverlapping training trade book.

MAE is used only to assess a trade after its entry size has been set. It never
enters the sizing or entry decision. Daily DLL uses incumbent conservative
trade-MAE approximation, not an exact intrabar stop execution reconstruction.
"""
import numpy as np
from numba import njit


def configurations():
    rows=[dict(name='INCUMBENT',fraction=0.,cap=900.,lock=False,top=3,late=5,late_day=60)]
    # Floor-distance allocation is a different control rule, not a new sleeve
    # or a posthoc priority change. These settings are frozen before outcomes.
    for fraction in (.15,.25,.35,.5):
        for cap in (450.,600.,750.,900.):
            for lock in (False,True):
                rows.append(dict(name=f'ROOM_{fraction:g}_CAP_{cap:g}_LOCK_{int(lock)}',fraction=fraction,cap=cap,lock=lock,top=3,late=5,late_day=60))
    for top in (2,3,4):
        for late in (0,4,5,6):
            rows.append(dict(name=f'LADDER_{top}_LATE_{late}',fraction=.35,cap=900.,lock=True,top=top,late=late,late_day=60))
    return rows


@njit(cache=True)
def day(per,mae,n,risk,a,b,k,bal,best,fraction,cap,lock,extra_cost):
    m=len(per);accepted=np.zeros(m,np.bool_);qty=np.zeros(m)
    # Match the deployed PLAN card: daily stop known at day start,400at k1,
    # otherwise700. Do not inspect future signals/risk to decide today's stop.
    stop=400. if k==1 else 700.
    worst=0.;dll=False
    for j in range(m):
        realised=0.;open_bound=0.
        for i in range(j):
            if not accepted[i]:continue
            done=b[i]<a[j] or (b[i]==a[j] and a[i]<a[j])
            if done:realised+=(per[i]-extra_cost[i])*qty[i]
            else:open_bound+=min(0.,min(mae[i],per[i]-extra_cost[i])*qty[i])
        if realised<=-stop or realised<=-1000.:break
        if lock:
            target=max(4000.,max(best,realised)/.55)
            if bal+realised>=target:break
        allowed=cap
        if fraction>0:allowed=min(cap,max(0.,bal+realised+2000.)*fraction)
        q=min(k*n[j],np.floor(allowed/risk[j])) if risk[j]>0 else 0.
        q=min(q,50.)
        if q<1:continue
        # Position size is fixed BEFORE consulting MAE or final trade P&L.
        w=realised+open_bound+min(mae[j],per[j]-extra_cost[j])*q
        worst=min(worst,w)
        if w<=-1000.:dll=True;break
        accepted[j]=True;qty[j]=q
    pnl=-1000. if dll else 0.
    if not dll:
        for j in range(m):
            if accepted[j]:pnl+=(per[j]-extra_cost[j])*qty[j]
        pnl=max(-1000.,pnl)
    return pnl,min(worst,pnl)


@njit(cache=True)
def evaluate(offsets,per,mae,n,risk,a,b,dates,start_dates,policy,extra_cost):
    fraction,cap,lock,top,late,late_day=policy
    status=np.zeros(len(start_dates),np.int8) #0timeout,1pass,2fail
    elapsed=np.full(len(start_dates),90,np.int64);ending=np.zeros(len(start_dates));lows=np.zeros(len(start_dates))
    for z in range(len(start_dates)):
        start=start_dates[z];ix=np.searchsorted(dates,start);balance=0.;best=0.;low=0.
        for i in range(ix,len(dates)):
            age=dates[i]-start
            if age>=90:break
            target=max(4000.,best/.55)
            k=1 if balance<=-1000. else 2 if balance<=-500. else int(top)
            if late>0 and age>=late_day and balance<target-1000. and balance> -500.:k=int(late)
            left,right=offsets[i],offsets[i+1]
            p,w=day(per[left:right],mae[left:right],n[left:right],risk[left:right],a[left:right],b[left:right],k,balance,best,fraction,cap,lock>0,extra_cost[left:right])
            low=min(low,balance+min(w,p))
            if balance+min(w,p)<=-2000.:
                status[z]=2;elapsed[z]=age;balance+=min(w,p);break
            balance+=p;best=max(best,p)
            if balance>=max(4000.,best/.55):status[z]=1;elapsed[z]=age;break
        ending[z]=balance;lows[z]=low
    return status,elapsed,ending,lows

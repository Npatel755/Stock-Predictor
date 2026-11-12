"""Historical-dollar continuous cash allocation with conservative OHLC bounds.

Entry sizing sees prior completed paths and entry risk only. Excursions enter
the assessment AFTER size is set. No loss/threshold fill is clipped.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def continuous(tin,tout,per,risk,base_n,mult,adverse,favorable,valid,years,start,end,cap,risk_cap,fraction,target,marked,cost_factor):
    cash=0.;cash_peak=0.;bound_peak=0.;cash_dd=0.;bound_dd=0.;busy=-1;last=start;gap=0.;wins=0.;losses=0.;trades=0;bad=0;breach=0
    annual=np.zeros(14);counts=np.zeros(14);qty=np.zeros(len(tin));path=np.zeros((len(tin),4))
    for j in range(len(tin)):
        if tin[j]<start or tin[j]>=end or tout[j]>=end or tin[j]<busy:continue
        peak=bound_peak if marked else cash_peak
        room=max(0.,target-(peak-cash))
        allowed=min(risk_cap,fraction*room)
        # Contract weighting inherited; hard global micro cap remains6.
        q=min(cap*base_n[j],6.,np.floor(allowed/risk[j]))
        if q<1:continue
        if not valid[j]:bad+=1;breach=1;break
        gap=max(gap,(tin[j]-last)/86400000000000.)
        prior=cash
        # Per-contract adverse is full-exit-cost liquidation bound. Favorable
        # is an upper mark before exit costs. Unknown intrabar ordering is
        # handled pessimistically: favorable could precede adverse.
        high=max(bound_peak,prior+favorable[j]*q)
        low=prior+min(adverse[j],per[j])*q
        bound_dd=max(bound_dd,high-low)
        entry_fee=.5*cost_factor*q
        cash_dd=max(cash_dd,cash_peak-(cash-entry_fee))
        cash+=per[j]*q;cash_peak=max(cash_peak,cash);cash_dd=max(cash_dd,cash_peak-cash)
        bound_peak=max(high,cash);bound_dd=max(bound_dd,bound_peak-cash)
        annual[years[j]]+=per[j]*q;counts[years[j]]+=1
        if per[j]>0:wins+=per[j]*q
        else:losses-=per[j]*q
        trades+=1;bad+=not valid[j];busy=tout[j];last=tout[j];qty[j]=q
        path[j,0]=cash;path[j,1]=low;path[j,2]=bound_peak;path[j,3]=cash_dd
        # Conservative-bound rejection stops new entries only; prior trade's
        # actual closed P&L is retained, never replaced by a magic stop fill.
        if cash_dd>=2000. or bound_dd>=2000.:breach=1;break
    gap=max(gap,(end-last)/86400000000000.)
    pf=wins/losses if losses>0 else (1e6 if wins>0 else 0.)
    metrics=np.array([cash,cash_dd,bound_dd,float(trades),pf,gap,float(bad),float(breach)])
    return metrics,annual,counts,qty,path


def reference(tin,tout,per,risk,base_n,mult,adverse,favorable,valid,years,start,end,cap,risk_cap,fraction,target,marked,cost_factor):
    cash=peak=upper_peak=dd=upper_dd=profits=losses=0.;busy=-1;last=start;gap=0.;n=bad=breach=0
    annual=np.zeros(14);counts=np.zeros(14);qty=np.zeros(len(tin));path=np.zeros((len(tin),4))
    for j in range(len(tin)):
        if not start<=tin[j]<end or tout[j]>=end or tin[j]<busy:continue
        previous_peak=upper_peak if marked else peak
        budget=min(risk_cap,fraction*max(0,target-(previous_peak-cash)))
        q=min(cap*base_n[j],6,int(budget//risk[j]))
        if q==0:continue
        if not valid[j]:bad+=1;breach=1;break
        gap=max(gap,float(tin[j]-last)/86400000000000)
        high=max(upper_peak,cash+favorable[j]*q)
        low=cash+min(adverse[j],per[j])*q
        upper_dd=max(upper_dd,high-low)
        dd=max(dd,peak-(cash-.5*cost_factor*q))
        net=per[j]*q;cash+=net;peak=max(peak,cash);dd=max(dd,peak-cash)
        upper_peak=max(high,cash);upper_dd=max(upper_dd,upper_peak-cash)
        annual[years[j]]+=net;counts[years[j]]+=1
        profits+=max(0,net);losses+=max(0,-net)
        n+=1;bad+=int(not valid[j]);busy=tout[j];last=tout[j];qty[j]=q
        path[j]=[cash,low,upper_peak,dd]
        if dd>=2000 or upper_dd>=2000:breach=1;break
    gap=max(gap,float(end-last)/86400000000000)
    pf=profits/losses if losses else 1e6 if profits else 0
    return np.array([cash,dd,upper_dd,n,pf,gap,bad,breach]),annual,counts,qty,path

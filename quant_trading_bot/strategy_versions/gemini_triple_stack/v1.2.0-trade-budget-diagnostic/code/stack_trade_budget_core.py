"""Causal trade-entry allocation. No loss clipping or holdout access.

Measures transaction/closed-cash drawdown, not the unknown within-trade mark.
Input trades reserve one position through the confirmation of the exit bar.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def allocate(tin,tout,per,risk,base_n,mult,night,years,start,end,cap,risk_cap,fraction,cost_factor):
    # Policy uses entry risk, completed prior trades, and closed-equity peak.
    bal=0.;peak=0.;dd=0.;until=-1;last=start;max_gap=0.;wins=0.;losses=0.;count=0;skips=0;breach=0
    annual=np.zeros(7);annual_n=np.zeros(7);qty=np.zeros(len(tin));path=np.zeros(len(tin))
    for j in range(len(tin)):
        if tin[j]<start or tin[j]>=end:continue
        # Prevent unfinished trades/labels crossing the internal TRAIN boundary.
        if tout[j]>=end:continue
        if tin[j]<until:continue
        if night[j] and bal<500.:continue
        room=max(0.,1800.-(peak-bal))
        allowed=risk_cap if fraction==0. else min(risk_cap,fraction*room)
        # Include added stress costs in the entry budget, not future trade net.
        extra=(cost_factor-1.)*(1.+mult[j])
        q=min(cap*base_n[j],6.,np.floor(allowed/(risk[j]+extra)))
        if q<1.:skips+=1;continue
        gap=(tin[j]-last)/86400000000000.;max_gap=max(max_gap,gap)
        # Full round-trip fees are already in per. Debit half the fee at entry
        # to avoid understating cash drawdown between the two executions.
        entry_fee=.5*cost_factor*q
        bal-=entry_fee;dd=max(dd,peak-bal)
        result=(per[j]-extra)*q
        bal+=result+entry_fee;peak=max(peak,bal);dd=max(dd,peak-bal)
        annual[years[j]]+=result;annual_n[years[j]]+=1
        if result>0:wins+=result
        else:losses-=result
        count+=1;last=tout[j];until=tout[j];qty[j]=q;path[j]=bal
        # This is a stop after the observed fill, never a clipped fill at2000.
        if dd>=2000.:breach=1;break
    max_gap=max(max_gap,(end-last)/86400000000000.)
    pf=wins/losses if losses>0. else (1e6 if wins>0. else 0.)
    metrics=np.array([bal,dd,float(count),pf,float(np.sum(annual>0)),float(np.min(annual_n)),
                      max_gap,float(skips),float(breach)])
    return metrics,annual,annual_n,qty,path


def reference(tin,tout,per,risk,base_n,mult,night,years,start,end,cap,risk_cap,fraction,cost_factor):
    balance=peak=dd=wins=losses=0.;until=-1;last=start;max_gap=0.;count=skips=breach=0
    annual=np.zeros(7);numbers=np.zeros(7);quantities=np.zeros(len(tin));path=np.zeros(len(tin))
    for j in range(len(tin)):
        if not start<=tin[j]<end or tout[j]>=end or tin[j]<until:continue
        if bool(night[j]) and balance<500:continue
        extra=(cost_factor-1)*(1+mult[j]);room=max(0,1800-(peak-balance))
        budget=min(risk_cap,fraction*room) if fraction else risk_cap
        quantity=min(cap*base_n[j],6,int(budget//(risk[j]+extra)))
        if quantity<=0:skips+=1;continue
        max_gap=max(max_gap,float(tin[j]-last)/86400000000000)
        fee=cost_factor*.5*quantity
        dd=max(dd,peak-(balance-fee))
        net=(per[j]-extra)*quantity
        balance+=net;peak=max(peak,balance);dd=max(dd,peak-balance)
        annual[int(years[j])]+=net;numbers[int(years[j])]+=1
        wins+=max(0,net);losses+=max(0,-net)
        count+=1;last=tout[j];until=tout[j];quantities[j]=quantity;path[j]=balance
        if dd>=2000:breach=1;break
    max_gap=max(max_gap,float(end-last)/86400000000000)
    pf=wins/losses if losses else 1e6 if wins else 0
    return np.array([balance,dd,count,pf,np.sum(annual>0),min(numbers),max_gap,skips,breach]),annual,numbers,quantities,path

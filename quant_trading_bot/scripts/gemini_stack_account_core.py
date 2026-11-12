"""Scenario replay of cached TRAIN daily streams; no market/holdout access.

Preserves Gemini's withdrawal-account assumptions. Daily stop/DLL clipping and
largest-stop-risk flags are approximations, not exact intrabar account replay.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def replay(net,risk,dates,starts,ends,yearends,K,gate1,gate2,max_p4):
    # Bookaxis0base,1portfolioE,2specifiedstack. m=1..4,nightoff/on.
    out=np.zeros((len(starts),10))
    for si in range(len(starts)):
        bal=0.;paid=0;since=0.;withdrawn=0.;closed=0.;cons=0.;low=0.;first=730.;pays1=0.;cash1=0.;pnl=0.
        a=np.searchsorted(dates,starts[si]);b=np.searchsorted(dates,ends[si])
        for j in range(a,b):
            m=1
            if bal>=4000:m=2
            if bal>=4600:m=3
            if bal>=5400:m=4
            floor=0. if paid>0 else -2000.
            bi=2 if bal>=gate2 else 1 if bal>=gate1 else 0
            if bal-risk[bi,m-1,j]<=floor:cons=1.
            night=1 if bal>=500. else 0
            p=max(net[bi,m-1,night,j],-1000.)
            bal+=p;since+=p;pnl+=p
            if paid==0:low=min(low,bal)
            if bal<=floor:closed=1.;break
            w=0.
            if paid==0 and bal>=6000.:
                w=500.;bal-=w;withdrawn+=w;paid+=1;since=0.
            elif (since>0. or paid==0) and bal-K>=250.:
                w=min(1500. if paid<3 else max_p4,bal-K)
                bal-=w;withdrawn+=w;paid+=1;since=0.
            if w>0:
                if first==730.:first=dates[j]-starts[si]
                if dates[j]<yearends[si]:pays1+=1;cash1+=w
        out[si,0]=withdrawn;out[si,1]=closed;out[si,2]=cons;out[si,3]=low<=-1500.;out[si,4]=first
        out[si,5]=pays1;out[si,6]=cash1;out[si,7]=bal;out[si,8]=pnl;out[si,9]=paid
    return out


def summary(rows):
    return dict(mean_withdrawals=float(rows[:,0].mean()),closed_fraction=float(rows[:,1].mean()),
        conservative_stoprisk_flag_fraction=float(rows[:,2].mean()),near_miss_fraction=float(rows[:,3].mean()),
        median_first_withdrawal_calendar_days=float(np.median(rows[:,4])),mean_firstyear_payouts=float(rows[:,5].mean()),
        mean_firstyear_withdrawals=float(rows[:,6].mean()),mean_ending_balance=float(rows[:,7].mean()),
        mean_net_trading_pnl=float(rows[:,8].mean()),mean_payout_count=float(rows[:,9].mean()),windows=len(rows))


def independent_reference(net,risk,dates,start,end,yearend,K,gate1,gate2,max_p4):
    bal=0.;paid=0;since=0.;withdrawn=0.;closed=0.;cons=0.;low=0.;first=730.;pays1=0.;cash1=0.;pnl=0.
    for j in np.flatnonzero((dates>=start)&(dates<end)):
        m=4 if bal>=5400 else 3 if bal>=4600 else 2 if bal>=4000 else 1
        bi=2 if bal>=gate2 else 1 if bal>=gate1 else 0
        floor=0. if paid else -2000.
        cons=max(cons,float(bal-risk[bi,m-1,j]<=floor))
        p=max(float(net[bi,m-1,int(bal>=500),j]),-1000.);bal+=p;since+=p;pnl+=p
        if not paid:low=min(low,bal)
        if bal<=floor:closed=1.;break
        if not paid and bal>=6000.:w=500.
        elif (since>0 or not paid) and bal-K>=250.:w=min(1500. if paid<3 else max_p4,bal-K)
        else:w=0.
        if w:
            bal-=w;withdrawn+=w;paid+=1;since=0.
            if first==730.:first=int(dates[j]-start)
            if dates[j]<yearend:pays1+=1;cash1+=w
    return np.array([withdrawn,closed,cons,float(low<=-1500),first,pays1,cash1,bal,pnl,paid])

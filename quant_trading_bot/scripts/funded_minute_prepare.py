"""Prepare past-only signal slots, raw TRAIN quotes and conservative calendars."""
import sys
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
import json
from pandas.tseries.holiday import (AbstractHolidayCalendar, Holiday, USMartinLutherKingJr,
    USPresidentsDay, GoodFriday, USMemorialDay, USLaborDay, USThanksgivingDay,
    nearest_workday, sunday_to_monday)

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from quant_futures.session_calendar import early_close_dates

BASE=ROOT/'runs/gemini_stack_continuation_v1/causal/raw_base.parquet'
NIGHT=ROOT/'runs/gemini_stack_continuation_v1/causal/overnight_training.parquet'
EVENTS=ROOT/'research/news/official_calendar_2010_2026.csv'
NSDAY=86400000000000


class CashHolidayCalendar(AbstractHolidayCalendar):
    rules=[Holiday('NewYear',month=1,day=1,observance=sunday_to_monday),
        USMartinLutherKingJr,USPresidentsDay,GoodFriday,USMemorialDay,
        Holiday('Juneteenth',month=6,day=19,start_date='2022-01-01',observance=nearest_workday),
        Holiday('Independence',month=7,day=4,observance=nearest_workday),USLaborDay,
        USThanksgivingDay,Holiday('Christmas',month=12,day=25,observance=nearest_workday)]


def cash_closed_dates():
    # Conservative strategy policy, not a claim that futures never trade on holidays.
    regular=set(CashHolidayCalendar().holidays('2010-01-01','2023-12-31').date)
    return regular|{pd.Timestamp(x).date() for x in ('2012-10-29','2012-10-30','2018-12-05')}


def planned_night_expiry(tin):
    local=pd.Timestamp(tin).tz_convert('America/New_York')
    date=local.tz_localize(None).normalize()+pd.Timedelta(days=1,minutes=585)
    return date.tz_localize('America/New_York').tz_convert('UTC')


def trade_dates(stamps):
    local=pd.DatetimeIndex(stamps).tz_convert('America/New_York')
    return local.tz_localize(None).normalize().as_unit('ns').asi8+np.where(local.hour>=18,NSDAY,0)


def roll_allowed(day):
    d=pd.Timestamp(day);month=d.month
    if month not in (3,6,9,12):return True
    first=pd.Timestamp(year=d.year,month=month,day=1);third=first+pd.Timedelta(days=(4-first.weekday())%7+14)
    # Conservative research blackout, not a CME-required trading ban.
    return not third-pd.Timedelta(days=14)<=d<=third


def source_signals():
    b=pd.read_parquet(BASE).copy();n=pd.read_parquet(NIGHT).copy();rows=[]
    specs={'AG_CRABEL15_D_1c':(3.5,8),'AG_TRD60_D_1c':(4.,6),'AG_MES_TRD30_D_1c':(2.5,12)}
    years=range(2010,2024);early=set().union(*(early_close_dates(y) for y in years))
    for row in b.itertuples():
        tin=pd.Timestamp(row.tin).tz_convert('UTC');local=tin.tz_convert('America/New_York');length=int((row.tin-row.dec).total_seconds()/60)
        ratio,hold=specs[row.sleeve];flat=local.normalize()+pd.Timedelta(minutes=765 if local.date() in early else 960)
        expiry=min(tin+pd.Timedelta(minutes=hold*length),flat.tz_convert('UTC'))
        rows.append(dict(tin=tin,dec=pd.Timestamp(row.dec).tz_convert('UTC'),asset=0 if row.inst=='MNQ' else 1,side=int(row.side),
            distance=float(row.stop_pct*row.entry),target_r=ratio,expiry=expiry,weight=float(row.n_contracts),night=False,sleeve=row.sleeve,priority=int(row.prio)))
    for row in n.itertuples():
        tin=pd.Timestamp(row.tin).tz_convert('UTC');rows.append(dict(tin=tin,dec=tin-pd.Timedelta(minutes=1),asset=0,side=1,distance=.0055,
            target_r=0.,expiry=planned_night_expiry(tin),weight=1.,night=True,sleeve='NIGHT',priority=-1))
    d=pd.DataFrame(rows).sort_values(['tin','priority'],kind='stable').reset_index(drop=True)
    assert d.tin.ge(pd.Timestamp('2010-01-01T00:00Z')).all() and d.expiry.lt(pd.Timestamp('2024-01-01T00:00Z')).all()
    closed=cash_closed_dates()
    d['calendar_eligible']=np.array([roll_allowed(x) and pd.Timestamp(x).date() not in closed for x in trade_dates(d.tin)]) & d.expiry.gt(d.tin)
    return d


def prepare(run,protocol,sha,write):
    cache=run/'minute_inputs.npz';identity=run/'minute_identity.json'
    if cache.exists():
        meta=json.loads(identity.read_text());assert sha(cache)==meta['sha256'];return np.load(cache),pd.read_parquet(run/'signal_slots.parquet')
    for rel,h in protocol['data_hashes'].items():assert sha(ROOT/rel)==h
    d=source_signals();d.to_parquet(run/'signal_slots.parquet',index=False)
    intervals=sorted((int(r.tin.value),int((r.expiry+pd.Timedelta(minutes=5)).value)) for r in d[d.calendar_eligible].itertuples())
    merged=[]
    for lo,hi in intervals:
        if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
        else:merged.append([lo,hi])
    ranges=pd.DataFrame(dict(lo=pd.to_datetime([x[0] for x in merged],utc=True),hi=pd.to_datetime([x[1] for x in merged],utc=True)))
    frames={};qa={}
    for asset,(micro,mini) in enumerate((('MNQ','NQ'),('MES','ES'))):
        con=duckdb.connect();con.execute("SET memory_limit='2GB'");con.execute('SET threads=2');con.register('ranges',ranges)
        streams=[];params=[]
        for symbol,lo,hi in ((mini,'2010-01-01','2019-05-06'),(micro,'2019-05-06','2024-01-01')):
            source=protocol['training_sources'][symbol];assert source['role']=='train' and sha(source['path'])==source['sha256']
            streams.append('SELECT timestamp_utc::TIMESTAMPTZ AS ts,open,high,low,close,volume,contract FROM read_parquet(?) WHERE timestamp_utc::TIMESTAMPTZ>=?::TIMESTAMPTZ AND timestamp_utc::TIMESTAMPTZ<?::TIMESTAMPTZ')
            params.extend([source['path'],lo,hi])
        query='''WITH p AS ('''+ ' UNION ALL '.join(streams)+'''),q AS (
          SELECT *,lag(volume) OVER(ORDER BY ts) AS prior_volume,lag(ts) OVER(ORDER BY ts) AS prior_ts FROM p)
          SELECT q.* FROM q SEMI JOIN ranges r ON q.ts>=r.lo AND q.ts<=r.hi ORDER BY ts'''
        f=con.execute(query,params).fetch_df();con.close()
        f['ts']=pd.to_datetime(f.ts,utc=True)
        assert f.ts.lt(pd.Timestamp('2024-01-01T00:00Z')).all() and not f.ts.duplicated().any()
        numeric=f[['open','high','low','close','volume']]
        assert np.isfinite(numeric).all().all() and f.low.gt(0).all() and f.volume.ge(0).all()
        assert f.high.ge(f[['open','close','low']].max(axis=1)).all() and f.low.le(f[['open','close','high']].min(axis=1)).all()
        for field in ('open','high','low','close'):assert np.max(np.abs(f[field]*4-np.round(f[field]*4)))<1e-6
        dt=f.ts-pd.to_datetime(f.prior_ts,utc=True);scale=np.where(f.ts<pd.Timestamp('2019-05-06T00:00Z'),10.,1.)
        cap=np.floor(f.prior_volume.fillna(0).to_numpy(float)*.01*scale)
        f['capacity']=np.where(dt.ge(pd.Timedelta(minutes=1))&dt.le(pd.Timedelta(minutes=5)),np.minimum(cap,20),0).astype(np.int64)
        frames[asset]=f;qa[micro]=dict(rows=len(f),first=str(f.ts.min()),last=str(f.ts.max()),bad_OHLC=0,source_role='train',liquidity='1%of previous available minute volume; pre2019mini proxy converted10:1, hypothetical microcapacity')
        print('TRAIN minute quotes',micro,len(f),flush=True)
    clock=np.unique(np.r_[*(pd.DatetimeIndex(f.ts).as_unit('ns').asi8 for f in frames.values()),d.tin.dt.as_unit('ns').astype('int64').to_numpy(),d.expiry.dt.as_unit('ns').astype('int64').to_numpy()])
    clock=clock[clock<int(pd.Timestamp('2024-01-01T00:00Z').value)]
    quotes=np.full((2,4,len(clock)),np.nan);contracts=np.full((2,len(clock)),-1,np.int64);capacity=np.zeros((2,len(clock)),np.int64)
    for asset,f in frames.items():
        idx=np.searchsorted(clock,pd.DatetimeIndex(f.ts).as_unit('ns').asi8)
        for k,col in enumerate(('open','high','low','close')):quotes[asset,k,idx]=f[col].to_numpy(float)
        contracts[asset,idx]=pd.factorize(f.contract,sort=True)[0];capacity[asset,idx]=f.capacity.to_numpy(np.int64)
    dates=trade_dates(pd.to_datetime(clock,utc=True));unique,inverse=np.unique(dates,return_inverse=True)
    closed=cash_closed_dates()
    allow=np.array([roll_allowed(x) and pd.Timestamp(x).date() not in closed for x in unique],bool)[inverse]
    con=duckdb.connect();ev=con.execute("SELECT scheduled_utc,family FROM read_csv_auto(?) WHERE date_et>='2010-01-01' AND date_et<'2024-01-01' AND impact='high' ORDER BY scheduled_utc",[str(EVENTS)]).fetch_df();con.close()
    evtime=pd.to_datetime(ev.scheduled_utc,utc=True).dt.as_unit('ns').astype('int64').to_numpy();assert (evtime<int(pd.Timestamp('2024-01-01T00:00Z').value)).all()
    limits=np.full(len(clock),20,np.int64)
    for event in evtime:
        a=np.searchsorted(clock,event-5*60000000000);b=np.searchsorted(clock,event+5*60000000000,side='right');limits[a:b]=3
    ev.to_csv(run/'TRAIN_scheduled_high_impact_events.csv',index=False)
    sig=np.column_stack([np.searchsorted(clock,d.tin.dt.as_unit('ns').astype('int64').to_numpy()),d.dec.dt.as_unit('ns').astype('int64').to_numpy(),d.asset,d.side,d.distance,d.target_r,d.expiry.dt.as_unit('ns').astype('int64').to_numpy(),d.weight,d.night.astype(int)]).astype(float)
    np.savez_compressed(cache,ts=clock,trade_day=dates,ohlc=quotes,contracts=contracts,capacity=capacity,news_limit=limits,entry_allowed=allow,signals=sig)
    missing=sum(not np.isfinite(quotes[int(row[2]),0,int(row[0])]) for row in sig if allow[int(row[0])])
    assert missing==0
    meta=dict(sha256=sha(cache),signal_slots=len(d),intraday_slots=int((~d.night).sum()),overnight_slots=int(d.night.sum()),clock_rows=len(clock),
        exante_roll_or_time_skips=int((~d.calendar_eligible).sum()),source_quotes=qa,missing_eligible_entry_quotes=int(missing),
        news_events_TRAIN_only=len(ev),calendar_assumption='Scheduled dates assumed announced; no economic values or future labels used.',
        session_clock='NY18:00/CT17:00 trade date rollover; UTC execution times, DST-aware local dates.',
        expiry='Source fixed brackets and hold horizons; rule-calendar earlyflat12:45else16:00; night09:45. Source virtual entry opportunity schedule retained.',
        roll_rule='Known quarterly thirdFriday minus14calendar days through expiry inclusive: no new orders. Conservative research blackout, not a CME trading ban.',
        holiday_policy='No entries on full UScashmarket closed trade dates; overnight scheduled exit always nextNYdate09:45, never cached realized safety exit. Regular holidays plus announced Sandy2012Oct29/30 and Bushfuneral2018Dec5 closures; announcement-time precision assumed, no price-based holiday inference.',
        validation_accessed=False,test_accessed=False)
    write(identity,meta);print('TRAIN MARKET CACHE',len(clock),'minutes;',len(d),'slots',flush=True)
    return np.load(cache),d

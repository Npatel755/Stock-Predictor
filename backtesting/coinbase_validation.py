"""Fixed ETH-rule transfer tests on direct Coinbase ETH/USD and BTC/USD data."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict,replace
import hashlib
import json
from pathlib import Path
import threading
import time

import numpy as np
import pandas as pd
import requests

from .alternative_strategies import simulate
from .eth_research.data import validate_bars
from .exit_research import freeze
from .forward_collection import atomic_json,collection_lock
from .generalization_policy import digest,frozen_profile
from .independent_visuals import equity_curve
from .market_data import BAR,utc
from .optimize import pnl
from .paths import ROOT
from .regime_filters import RegimeFilter,apply_filter,prepare_features
from .reporting import safe_value

BASE='https://api.exchange.coinbase.com'
DOCS='https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles'
PRODUCTS={'ETH-USD':'COINBASE:ETH-USD.SPOT','BTC-USD':'COINBASE:BTC-USD.SPOT'}


def validate_coinbase(raw,product):
    if product not in PRODUCTS:raise ValueError('Unsupported Coinbase transfer product')
    frame=validate_bars(raw,expected_ticker=PRODUCTS[product])
    frame['available_at']=frame.timestamp+BAR
    return frame,dict(rows=len(frame),instrument=PRODUCTS[product],
        missing_bars=int(frame.timestamp.diff().div(BAR).sub(1).clip(lower=0).sum()),
        close_time_rule='API supplies candle-open seconds only; availability is open+5min. No exchange-close timestamp is asserted.')


def parse_day(payload,product,start,end):
    if product not in PRODUCTS:raise ValueError('Unsupported Coinbase transfer product')
    rows=json.loads(payload)
    if not isinstance(rows,list) or len(rows)>300 or any(not isinstance(r,list) or len(r)!=6 for r in rows):
        raise ValueError('Unexpected Coinbase candle response shape')
    frame=pd.DataFrame(rows,columns=['epoch','low','high','open','close','volume'])
    for name in frame:frame[name]=pd.to_numeric(frame[name],errors='raise')
    if not np.isfinite(frame.to_numpy(dtype=float)).all():raise ValueError('Nonfinite Coinbase candle fields')
    if not frame.epoch.mod(1).eq(0).all():raise ValueError('Coinbase candle times must be integer seconds')
    frame['timestamp']=pd.to_datetime(frame.epoch.astype('int64'),unit='s',utc=True)
    frame['ticker']=PRODUCTS[product]
    start,end=utc(start),utc(end)
    keep=(frame.timestamp>=start)&(frame.timestamp+BAR<=end)
    excluded=int((~keep).sum())
    frame=frame.loc[keep].drop(columns='epoch')
    if frame.empty:return frame,dict(raw_rows=len(rows),excluded_outside_requested_day=excluded,rows=0)
    frame,_=validate_coinbase(frame,product)
    return frame,dict(raw_rows=len(rows),excluded_outside_requested_day=excluded,rows=len(frame))


class RateLimit:
    def __init__(self,per_second=6.):
        self.interval=1/per_second;self.lock=threading.Lock();self.next=0.

    def wait(self):
        with self.lock:
            time.sleep(max(0.,self.next-time.monotonic()))
            self.next=time.monotonic()+self.interval


def fetch_day(product,day,directory,limiter):
    if product not in PRODUCTS:raise ValueError('Unsupported Coinbase transfer product')
    day=utc(day)
    if day!=day.floor('D'):raise ValueError('Coinbase requests must cover complete UTC days')
    end=day+pd.Timedelta(days=1);name=f'{product}_{day:%Y%m%d}'
    raw=directory/f'{name}.json';sidecar=directory/f'{name}.source.json'
    url=f'{BASE}/products/{product}/candles'
    params=dict(start=day.isoformat(),end=end.isoformat(),granularity=300)
    if raw.exists() or sidecar.exists():
        if not raw.exists() or not sidecar.exists():raise ValueError('Incomplete pinned Coinbase response cache')
        provenance=json.loads(sidecar.read_text(encoding='utf-8'));payload=raw.read_bytes()
        if provenance['url']!=url or provenance['params']!=params or hashlib.sha256(payload).hexdigest()!=provenance['sha256']:
            raise ValueError('Pinned Coinbase response changed')
    else:
        payload=None
        for attempt in range(5):
            limiter.wait()
            try:
                response=requests.get(url,params=params,timeout=20,allow_redirects=False)
            except requests.RequestException:
                if attempt==4:raise RuntimeError('Coinbase public candle connection failed') from None
                time.sleep(2**attempt);continue
            if response.status_code==429 or response.status_code>=500:
                if attempt==4:raise RuntimeError(f'Coinbase public candles repeatedly returned HTTP {response.status_code}')
                try:delay=float(response.headers.get('Retry-After',2**attempt))
                except ValueError:delay=2**attempt
                time.sleep(min(30,max(1,delay)));continue
            if response.status_code!=200:raise ValueError(f'Coinbase public candles returned HTTP {response.status_code}')
            if len(response.content)>512_000:raise ValueError('Coinbase day response exceeds bounded size')
            payload=response.content
            break
        if payload is None:raise RuntimeError('No successful Coinbase response')
        # Validate the raw response before pinning it. Inclusive end candles
        # are retained in the raw response and excluded explicitly on parsing.
        parse_day(payload,product,day,end)
        provenance=dict(url=url,params=params,sha256=hashlib.sha256(payload).hexdigest(),retrieved_at_utc=str(pd.Timestamp.now(tz='UTC')),
                        integrity='HTTPS response pinned by local SHA-256; no provider-published response checksum is available.')
        raw.write_bytes(payload);freeze(sidecar,provenance)
    frame,quality=parse_day(payload,product,day,end)
    return frame,dict(product=product,day=str(day.date()),response_file=raw.name,**provenance,parse_quality=quality)


def recorded(root=ROOT,verify_sources=False):
    out=root/'artifacts/generalization/coinbase';path=out/'results.json'
    if not path.exists():return None
    result=json.loads(path.read_text(encoding='utf-8'));p,_,_,_=frozen_profile(root)
    if result['plan']['protocol_sha256']!=digest(p) or result['plan']['configuration_sha256']!=p['frozen_configuration_sha256']:
        raise ValueError('Coinbase audit does not match the frozen protocol')
    for product,row in result['products'].items():
        path=root/f'data/generalization/coinbase/{product}.parquet'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['dataset_sha256']:raise ValueError('Consumed Coinbase dataset changed')
    if verify_sources:
        for row in result['sources']:
            raw=root/f"data/generalization/coinbase/responses/{row['response_file']}"
            if not raw.exists() or hashlib.sha256(raw.read_bytes()).hexdigest()!=row['sha256']:
                raise ValueError('Consumed raw Coinbase response changed')
    return result


def run(root=ROOT):
    p,rule,cfg,meta=frozen_profile(root)
    out=root/'artifacts/generalization/coinbase';out.mkdir(parents=True,exist_ok=True)
    with collection_lock(out/'audit.lock'):
        data=root/'data/generalization/coinbase';data.mkdir(parents=True,exist_ok=True)
        raw_dir=data/'responses';raw_dir.mkdir(exist_ok=True)
        start,end=utc('2023-01-01'),utc('2026-10-28')
        plan=dict(name='Coinbase direct ETH/USD and BTC/USD frozen-rule transfer',
                  frozen_version=p['frozen_version'],protocol_sha256=digest(p),configuration_sha256=p['frozen_configuration_sha256'],
                  rule=asdict(rule),filters=meta['entry_filters'],execution=asdict(cfg),products=PRODUCTS,
                  period=[str(start),str(end)],granularity_seconds=300,source=DOCS,
                  fixed_rules_before_full_data_fetch=True,access_probes_before_manifest='API accessibility/shape probes only; the ETH strategy was already frozen. No outcomes selected parameters.',
                  parameter_selection_permitted=False,cost_scenarios_extra_slippage_bps=[2.,4.,8.],
                  cost_note='Controlled hypothetical execution: unchanged ETH research fees, shorting, leverage, financing and 0.001 quantity rounding; 0.01 USD tick for both products. These are not Coinbase spot execution costs or certified Breakout fills.',
                  gap_policy='Split real gaps into independent accounts and fresh indicators; skip segments shorter than 3000 bars. Never fill, relabel or shift bars.',
                  rate_limit_requests_per_second=6.,request_count=2*len(pd.date_range(start,end,inclusive='left',freq='D')),
                  integrity='Retain each raw HTTPS response and local SHA-256. No provider-published response checksum or independent historical feed verification is claimed.',
                  future_eth_validation=False,independent_asset_claim=False,ready_for_funded_trading=False)
        freeze(out/'manifest.json',plan)
        existing=recorded(root,verify_sources=True)
        if existing is not None:
            if existing['plan']!=plan:raise ValueError('Consumed Coinbase audit has a different plan')
            print('Coinbase transfer audit already consumed; frozen data hashes verified, no rerun.',flush=True)
            return existing
        jobs=[(product,day) for product in PRODUCTS for day in pd.date_range(start,end,inclusive='left',freq='D')]
        chunks={product:[] for product in PRODUCTS};sources=[];limiter=RateLimit(plan['rate_limit_requests_per_second'])
        def fetch(job):return job[0],*fetch_day(job[0],job[1],raw_dir,limiter)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for count,(product,frame,provenance) in enumerate(pool.map(fetch,jobs),1):
                if len(frame):chunks[product].append(frame)
                sources.append(provenance)
                if count%50==0 or count==len(jobs):
                    atomic_json(out/'download_checkpoint.json',dict(completed_responses=count,expected_responses=len(jobs),last_product=product,last_day=provenance['day'],performance_evaluated=False))
                    print(f'COINBASE DATA {count}/{len(jobs)} {product} through {provenance["day"]}; no strategy outcomes evaluated.',flush=True)
        products={}
        for product in PRODUCTS:
            if not chunks[product]:raise ValueError(f'No actual Coinbase bars for {product}')
            frame,quality=validate_coinbase(pd.concat(chunks[product],ignore_index=True),product)
            quality['missing_bars_in_requested_period']=int((end-start)/BAR)-len(frame)
            frame.to_parquet(data/f'{product}.parquet',index=False)
            records=[];skipped=[]
            for index,part in frame.groupby(frame.timestamp.diff().ne(BAR).cumsum()):
                part=part.reset_index(drop=True)
                if len(part)<3000:
                    skipped.append(dict(segment=int(index),rows=len(part),start=str(part.timestamp.min()),end=str(part.available_at.max())))
                    continue
                signals=apply_filter(prepare_features(part,rule),RegimeFilter(**meta['entry_filters']))
                location=out/product/f'segment{index}';location.mkdir(parents=True,exist_ok=True)
                metrics={}
                for bps in plan['cost_scenarios_extra_slippage_bps']:
                    execution=replace(cfg,tick_size=.01,slippage_bps=bps)
                    m,trades,events=simulate(part,rule,execution,signals=signals,validator=lambda raw,prod=product:validate_coinbase(raw,prod))
                    metrics[str(bps)]=m
                    if bps==2.:
                        curve=equity_curve(part,events,execution)
                        if abs(curve.equity.iloc[-1]-m['final_equity'])>1e-6:raise ValueError('Coinbase equity does not reconcile')
                        part.to_parquet(location/'bars.parquet',index=False);curve.to_parquet(location/'equity.parquet',index=False)
                        trades.to_csv(location/'trades.csv',index=False);events.to_csv(location/'events.csv',index=False)
                records.append(dict(segment=int(index),rows=len(part),start=str(part.timestamp.min()),end=str(part.available_at.max()),cost_metrics=metrics))
                print(f'COINBASE TEST {product} segment{index}: net=${pnl(metrics["2.0"]):.2f}, entries={metrics["2.0"]["entries"]}',flush=True)
            aggregates={str(bps):dict(sum_independent_account_net=sum(pnl(r['cost_metrics'][str(bps)]) for r in records),
                entries=sum(r['cost_metrics'][str(bps)]['entries'] for r in records),segments=len(records),
                worst_segment_drawdown=max((r['cost_metrics'][str(bps)]['max_intrabar_drawdown'] for r in records),default=None)) for bps in plan['cost_scenarios_extra_slippage_bps']}
            products[product]=dict(quality=quality,segments=records,skipped_segments=skipped,aggregates=aggregates,
                retained_rows=sum(r['rows'] for r in records),post_warmup_row_upper_bound=sum(max(0,r['rows']-rule.slow*12) for r in records),
                dataset_sha256=hashlib.sha256((data/f'{product}.parquet').read_bytes()).hexdigest())
        result=dict(plan=plan,products=products,sources=sources,data_now_consumed=True,prospective_validation=False,ready_for_funded_trading=False)
        freeze(out/'results.json',safe_value(result))
        report=['# Coinbase ETH/USD and BTC/USD frozen-rule transfer','',
            f"Direct Coinbase Exchange candles. Frozen **{p['frozen_version']}**, {start} to {end} exclusive. No Binance candles were used for either test. Rule and filter settings were fixed before full data retrieval; no transfer result selected parameters.",'',
            plan['cost_note'],'',plan['gap_policy'],'',plan['integrity'],'',
            '| Product | Extra slippage bp per side | Sum of reset-account net | Entries | Segments | Worst segment drawdown |','| --- | ---: | ---: | ---: | ---: | ---: |']
        for product,row in products.items():
            for bps,a in row['aggregates'].items():
                dd=f"{a['worst_segment_drawdown']:.2%}" if a['worst_segment_drawdown'] is not None else 'N/A'
                report.append(f"| {product} | {bps} | ${a['sum_independent_account_net']:,.2f} | {a['entries']} | {a['segments']} | {dd} |")
        report+=['','Multiple reset-account sums are not continuous returns and are not added to the Binance development score. Same-asset prices across exchanges and BTC/ETH prices are related; neither test establishes statistical independence or future ETH profitability.','',
                 '| Product | Actual rows | Missing requested intervals | Retained rows | Upper-bound rows after warm-up | Skipped short segments |','| --- | ---: | ---: | ---: | ---: | ---: |']
        for product,row in products.items():report.append(f"| {product} | {row['quality']['rows']:,} | {row['quality']['missing_bars_in_requested_period']:,} | {row['retained_rows']:,} | {row['post_warmup_row_upper_bound']:,} | {len(row['skipped_segments'])} |")
        report+=['','API responses may include the candle at the requested exclusive end or preceding the start. Raw responses are retained; out-of-range records are explicitly excluded. Bucket order is time, low, high, open, close, volume. No missing candle is fabricated.','',
                 'Both datasets are now consumed diagnostic evidence. Failed outcomes stay failed; they do not authorize retuning until the test passes. The frozen ETH forward-test protocol remains unchanged.','',f'[Official candle schema and range limits]({DOCS}).','']
        (root/'reports/generalization_coinbase.md').write_text('\n'.join(report),encoding='utf-8')
        return result


def render(product,root=ROOT):
    import streamlit as st
    from .independent_visuals import performance_chart,monthly_chart,trade_chart
    if product not in PRODUCTS:raise ValueError('Unsupported Coinbase transfer product')
    key='coinbase_'+product.replace('-','_')
    st.subheader(f'Coinbase {product} · frozen ETH-rule transfer')
    st.caption('Direct Coinbase Exchange candles, with no Binance candles used for this test. No parameter tuning. Price histories across exchanges and ETH/BTC are related; this is not independent future ETH validation.')
    path=root/'artifacts/generalization/coinbase/results.json'
    if not path.exists():
        checkpoint=root/'artifacts/generalization/coinbase/download_checkpoint.json'
        if checkpoint.exists():
            c=json.loads(checkpoint.read_text(encoding='utf-8'))
            st.info(f"Last saved download checkpoint: {c['completed_responses']:,}/{c['expected_responses']:,} daily responses. No strategy outcomes have been evaluated. A checkpoint does not prove a downloader is currently running.")
        else:st.info('No completed Coinbase fixed-rule audit yet.')
        return
    try:result=recorded(root)
    except (ValueError,OSError) as exc:st.error(str(exc));return
    row=result['products'][product];plan=result['plan']
    st.write(f"Frozen **{plan['frozen_version']}** · **{PRODUCTS[product]}** · {plan['period'][0]} to {plan['period'][1]} exclusive")
    st.caption(plan['cost_note'])
    st.dataframe(pd.DataFrame([dict(extra_slippage_bps=float(bps),**value) for bps,value in row['aggregates'].items()]),hide_index=True)
    ratio=row['post_warmup_row_upper_bound']/row['quality']['rows'] if row['quality']['rows'] else 0
    st.caption(f"Actual candles: {row['quality']['rows']:,}; missing requested intervals: {row['quality']['missing_bars_in_requested_period']:,}; skipped short segments: {len(row['skipped_segments'])}. At most {ratio:.1%} of rows remain after minimum segment warm-up. Multiple segment-account sums are not a continuous return and are not added to the ETH development score.")
    if ratio<.5:
        st.warning('Less than half of the requested source history remains eligible after segment exclusions and warm-up. This fragmented test has limited coverage.')
    if row['aggregates']['2.0']['entries']<30:
        st.warning('Fewer than 30 entries: this transfer sample is too sparse for a reliable strategy estimate.')
    if any(v['sum_independent_account_net']<0 for v in row['aggregates'].values()):
        st.warning('This frozen-rule Coinbase transfer loses money in at least one cost scenario. The failure is retained; these data will not be tuned until it passes.')
    st.caption('Each original API response and its local SHA-256 are retained. No provider-published response checksum is available. These datasets are now consumed diagnostic evidence; the locked future ETH test is unchanged.')
    verification=root/'artifacts/generalization/coinbase/verification_latest.json'
    if verification.exists():
        try:
            proof=json.loads(verification.read_text(encoding='utf-8'))
            target=(root/proof['path']).resolve()
            base=(root/'artifacts/generalization/coinbase/verification').resolve()
            if (not target.is_relative_to(base) or hashlib.sha256(target.read_bytes()).hexdigest()!=proof['sha256']
                    or hashlib.sha256(path.read_bytes()).hexdigest()!=proof['results_sha256']):
                raise ValueError('Coinbase reproduction certificate differs from its pinned results.')
        except (OSError,ValueError,KeyError) as exc:st.error(str(exc));return
        st.caption('Computational reproduction verified: candles rebuilt from pinned raw responses; every main/stressed broker replay and stored equity curve reproduced. This is not prospective validation.')
    else:st.info('Fresh computational reproduction is pending; these are saved historical transfer results.')
    if not row['segments']:return
    options=sorted(row['segments'],key=lambda r:(-r['rows'],r['segment']))
    chosen=st.selectbox('Inspect Coinbase segment',[r['segment'] for r in options],key=f'{key}_segment')
    location=root/f'artifacts/generalization/coinbase/{product}/segment{chosen}'
    bars=pd.read_parquet(location/'bars.parquet');curve=pd.read_parquet(location/'equity.parquet')
    def csv(path):
        try:return pd.read_csv(path)
        except pd.errors.EmptyDataError:return pd.DataFrame()
    trades=csv(location/'trades.csv');events=csv(location/'events.csv')
    for name in ['entry_bar_open','exit_bar_open','entry_time','exit_time']:
        if name in trades:trades[name]=pd.to_datetime(trades[name],utc=True)
    for name in ['bar_open','effective_at']:
        if name in events:events[name]=pd.to_datetime(events[name],utc=True)
    fig=performance_chart(curve,plan['execution']['initial_capital'])
    fig.update_layout(title=f'Coinbase {product} · Independent segment {chosen} · Equity and drawdown')
    st.plotly_chart(fig,width='stretch',key=f'{key}_equity')
    st.plotly_chart(monthly_chart(curve,plan['execution']['initial_capital']),width='stretch',key=f'{key}_monthly')
    if len(trades):
        chosen_trade=st.selectbox('Inspect Coinbase transfer trade',list(range(len(trades))),key=f'{key}_trade')
        figure,_=trade_chart(bars,trades.iloc[chosen_trade],events,plan['rule']['reward_r'])
        for trace in figure.data:
            if trace.type=='candlestick':trace.name=PRODUCTS[product]+' candles'
        st.plotly_chart(figure,width='stretch',key=f'{key}_candles')
    else:st.info('No trades after warm-up in this segment.')


if __name__=='__main__':run()

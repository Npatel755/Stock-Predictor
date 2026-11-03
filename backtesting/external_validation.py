"""One-time frozen-rule ETH-2017 and BTC transfer checks, without optimization."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pandas as pd
import requests

from .alternative_strategies import simulate
from .eth_research.data import validate_bars
from .eth_research.perpetual_data import BASE, COLUMNS, download
from .exit_research import freeze
from .generalization_policy import digest, frozen_profile
from .independent_visuals import equity_curve
from .market_data import BAR, utc
from .optimize import pnl, write_json
from .paths import ROOT
from .regime_filters import RegimeFilter, apply_filter, prepare_features
from .spot_proxy_data import fetch as fetch_spot, validate_proxy
from .reporting import safe_value

BTC='BINANCE:BTCUSDT.P'


def recorded_result(kind,root=ROOT):
    path=root/f'artifacts/generalization/{kind}/results.json'
    if not path.exists():return None
    result=json.loads(path.read_text(encoding='utf-8'))
    data=root/f'data/generalization/{kind}'
    parquet=data/'candles.parquet'
    if not parquet.exists() or hashlib.sha256(parquet.read_bytes()).hexdigest()!=result['provenance']['dataset_sha256']:
        raise ValueError('Recorded transfer data changed; the consumed audit cannot be overwritten')
    for archive in result['provenance']['archives']:
        if archive.get('unavailable'):continue
        raw=data/archive['url'].rsplit('/',1)[-1]
        if not raw.exists() or hashlib.sha256(raw.read_bytes()).hexdigest()!=archive['sha256']:
            raise ValueError('A recorded raw transfer archive changed')
    return result


def fetch_early_eth(directory,start,end):
    directory.mkdir(parents=True,exist_ok=True)
    chunks=[];archives=[]
    for month in pd.date_range(utc(start),utc(end)-BAR,freq='MS'):
        name=f'ETHUSDT-5m-{month:%Y-%m}.zip';path=directory/name;check=directory/(name+'.CHECKSUM')
        url=f'https://data.binance.vision/data/spot/monthly/klines/ETHUSDT/5m/{name}'
        with requests.Session() as session:
            payload=path.read_bytes() if path.exists() else download(session,url,optional=True)
            if payload is None:continue
            checksum=check.read_text() if check.exists() else download(session,url+'.CHECKSUM').decode()
        sha=hashlib.sha256(payload).hexdigest()
        if sha!=checksum.split()[0]:raise ValueError('Early ETH archive checksum mismatch')
        path.write_bytes(payload);check.write_text(checksum)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members=[f for f in archive.infolist() if f.filename.endswith('.csv')]
            if len(members)!=1 or members[0].file_size>20_000_000:raise ValueError('Unexpected early ETH archive')
            raw=pd.read_csv(archive.open(members[0]),header=None,names=COLUMNS)
        for col in COLUMNS:raw[col]=pd.to_numeric(raw[col],errors='raise')
        opens=pd.to_datetime(raw.open_time.astype('int64'),unit='ms',utc=True)
        closes=pd.to_datetime(raw.close_time.astype('int64'),unit='ms',utc=True)
        valid_time=opens.eq(opens.dt.floor('5min'))&(closes>=opens)&(closes<opens+BAR)
        # Preserve the raw archive; exclude/report malformed source intervals.
        # In 2017 a legacy record closes at the next candle's boundary. Never
        # shift that timestamp or pretend its OHLC belongs to a corrected bar.
        frame=raw.loc[valid_time,['open','high','low','close','volume']].copy()
        frame['timestamp']=opens.loc[valid_time];frame['exchange_close_time']=closes.loc[valid_time];frame['ticker']='BINANCE:ETHUSDT'
        chunks.append(validate_proxy(frame)[0]);archives.append(dict(url=url,sha256=sha,excluded_invalid_time_rows=int((~valid_time).sum())))
    if not chunks:raise ValueError('No early ETH archives available')
    frame,_=validate_proxy(pd.concat(chunks,ignore_index=True))
    frame=frame[(frame.timestamp>=utc(start))&(frame.available_at<=utc(end))].reset_index(drop=True)
    path=directory/'candles.parquet';frame.to_parquet(path,index=False)
    return frame,dict(archives=archives,dataset_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def validate_btc(raw):
    frame=validate_bars(raw,expected_ticker=BTC)
    frame['exchange_close_time']=pd.to_datetime(frame.exchange_close_time,utc=True)
    frame['available_at']=frame.timestamp+BAR
    if not ((frame.exchange_close_time>=frame.timestamp)&(frame.exchange_close_time<frame.available_at)).all():
        raise ValueError('BTC exchange close timestamp outside candle')
    gaps=frame.timestamp.diff().div(BAR).sub(1).clip(lower=0).sum()
    return frame,dict(rows=len(frame),missing_bars=int(gaps),instrument=BTC)


def parse_btc(payload):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        files=[f for f in archive.infolist() if f.filename.endswith('.csv')]
        if len(files)!=1 or files[0].file_size>20_000_000: raise ValueError('Unexpected BTC archive')
        raw=pd.read_csv(archive.open(files[0]),header=None,names=COLUMNS)
    # Official archives may include the column header; reject any other bad row.
    if str(raw.iloc[0].open_time)=='open_time':raw=raw.iloc[1:].copy()
    for col in COLUMNS:raw[col]=pd.to_numeric(raw[col],errors='raise')
    if raw.empty or raw.isna().any().any():raise ValueError('BTC archive has missing fields')
    if not raw.open_time.mod(1).eq(0).all() or not raw.close_time.mod(1).eq(0).all():raise ValueError('Noninteger BTC timestamps')
    unit='us' if raw.open_time.max()>10**15 else 'ms'
    frame=raw[['open','high','low','close','volume']].copy()
    frame['timestamp']=pd.to_datetime(raw.open_time.astype('int64'),unit=unit,utc=True)
    frame['exchange_close_time']=pd.to_datetime(raw.close_time.astype('int64'),unit=unit,utc=True)
    frame['ticker']=BTC
    return validate_btc(frame)[0]


def fetch_btc(directory,start='2023-01-01',end='2026-10-28'):
    directory.mkdir(parents=True,exist_ok=True)
    start,end=utc(start),utc(end)
    months=pd.date_range(start.replace(day=1),end-pd.Timedelta(days=1),freq='MS')
    def get_month(month):
        filename=f'BTCUSDT-5m-{month:%Y-%m}.zip'
        path=directory/filename;check=directory/(filename+'.CHECKSUM')
        url=f'{BASE}/monthly/klines/BTCUSDT/5m/{filename}'
        with requests.Session() as session:
            payload=path.read_bytes() if path.exists() else download(session,url,optional=True)
            if payload is None:return None,dict(url=url,unavailable=True)
            checksum=check.read_text() if check.exists() else download(session,url+'.CHECKSUM').decode()
        sha=hashlib.sha256(payload).hexdigest()
        if sha!=checksum.split()[0]:raise ValueError('BTC archive checksum mismatch')
        path.write_bytes(payload);check.write_text(checksum)
        return parse_btc(payload),dict(url=url,sha256=sha)
    with ThreadPoolExecutor(max_workers=4) as pool: parts=list(pool.map(get_month,months))
    frames=[frame for frame,_ in parts if frame is not None]
    if not frames:raise ValueError('No BTC archives available')
    frame,_=validate_btc(pd.concat(frames,ignore_index=True))
    frame=frame[(frame.timestamp>=start)&(frame.available_at<=end)].reset_index(drop=True)
    path=directory/'candles.parquet';frame.to_parquet(path,index=False)
    return frame,dict(archives=[m for _,m in parts],dataset_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def run(kind,root=ROOT):
    p,rule,cfg,meta=frozen_profile(root)
    directory=root/f'artifacts/generalization/{kind}'
    directory.mkdir(parents=True,exist_ok=True)
    is_btc=kind=='btc'
    if kind not in {'btc','eth2017'}:raise ValueError('Unknown fixed-rule audit')
    execution=replace(cfg,tick_size=.1) if is_btc else cfg
    start,end=('2023-01-01','2026-10-28') if is_btc else ('2017-08-01','2018-01-01')
    plan=dict(name=kind,protocol_sha256=digest(p),configuration_sha256=p['frozen_configuration_sha256'],
              frozen_version=p['frozen_version'],rule=asdict(rule),filters=meta['entry_filters'],execution=asdict(execution),
              requested_period=[start,end],rules_frozen_before_data_fetch=True,parameter_selection_permitted=False,
              is_future_eth_validation=False,source='Binance public BTC USD-M perpetual archives' if is_btc else 'Binance public ETHUSDT spot archives',
              ticker=BTC if is_btc else 'BINANCE:ETHUSDT',
              execution_note='Controlled hypothetical costs: same ETH assumptions; BTC tick model 0.10. These are not certified BTC or Breakout execution costs.' if is_btc else 'Hypothetical leveraged shorting/financing on spot; not observed futures execution.',
              gap_policy='Split at real gaps into independently reset accounts and indicators. Skip segments shorter than 3000 bars. Never fill missing candles.')
    freeze(directory/'manifest.json',plan)
    existing=recorded_result(kind,root)
    if existing is not None:
        if existing['plan']!=plan:raise ValueError('Consumed transfer audit has a different frozen plan')
        print(f'FIXED {kind}: existing consumed audit verified; no rerun or artifact overwrite.',flush=True)
        return existing
    data=root/f'data/generalization/{kind}'
    frame,provenance=fetch_btc(data,start,end) if is_btc else fetch_early_eth(data,start,end)
    validator=validate_btc if is_btc else validate_proxy
    frame,quality=validator(frame)
    records=[];skipped=[]
    for index,part in frame.groupby(frame.timestamp.diff().ne(BAR).cumsum()):
        part=part.reset_index(drop=True)
        if len(part)<3000:
            skipped.append(dict(segment=int(index),rows=len(part),start=str(part.timestamp.min()),end=str(part.available_at.max())))
            continue
        signals=apply_filter(prepare_features(part,rule),RegimeFilter(**meta['entry_filters']))
        metrics,trades,events=simulate(part,rule,execution,signals=signals,validator=validator)
        curve=equity_curve(part,events,execution)
        if abs(curve.equity.iloc[-1]-metrics['final_equity'])>1e-6:raise ValueError('Transfer equity does not reconcile')
        location=directory/f'segment{index}';location.mkdir(exist_ok=True)
        part.to_parquet(location/'bars.parquet',index=False);curve.to_parquet(location/'equity.parquet',index=False)
        trades.to_csv(location/'trades.csv',index=False);events.to_csv(location/'events.csv',index=False)
        records.append(dict(segment=int(index),rows=len(part),start=str(part.timestamp.min()),end=str(part.available_at.max()),metrics=metrics))
        print(f'FIXED {kind} segment {index}: net=${pnl(metrics):.2f} entries={metrics["entries"]}',flush=True)
    result=dict(plan=plan,quality=quality,provenance=provenance,segments=records,skipped_segments=skipped,
                sum_independent_account_net=sum(pnl(r['metrics']) for r in records),
                data_is_now_inspected=True,future_validation=False,ready_for_funded_trading=False)
    freeze(directory/'results.json',safe_value(result))
    report=[f'# Frozen {kind} transfer diagnostic','',f"Frozen ETH rules: {p['frozen_version']}. No parameter tuning was performed on this dataset. This is a cross-market/earlier-regime diagnostic, not future ETH validation.",'',
            plan['execution_note'],'',plan['gap_policy'],'',
            '| Segment | Rows | Net P&L | Entries | Drawdown |','| --- | ---: | ---: | ---: | ---: |']
    for r in records:report.append(f"| {r['segment']} | {r['rows']} | ${pnl(r['metrics']):,.2f} | {r['metrics']['entries']} | {r['metrics']['max_intrabar_drawdown']:.2%} |")
    report+=['',f"Sum of {len(records)} independent account results: ${result['sum_independent_account_net']:,.2f}. With multiple segments this is not a continuous return. Skipped short segments: {len(skipped)}. Missing bars are never fabricated.",'',
             'The raw archives and hashes are retained. These outcomes are now inspected development evidence and must not be reused as an untouched holdout. A failed transfer does not authorize tuning this same test until it passes. No version promotion or account orders occurred.','']
    (root/f'reports/generalization_{kind}.md').write_text('\n'.join(report),encoding='utf-8')
    return result


def render(kind,root=ROOT):
    import streamlit as st
    from .independent_visuals import performance_chart,monthly_chart,trade_chart
    directory=root/f'artifacts/generalization/{kind}'
    title='BTC transfer test' if kind=='btc' else 'Additional ETH 2017 regime'
    st.subheader(title)
    st.caption('Frozen ETH rules only. No optimization on this test. Cross-asset/earlier-regime results do not establish future ETH profitability.')
    if st.button(f'Fetch data and run {title}',key=f'fixed_{kind}'):
        try:
            with st.spinner('Downloading checksum-verified archives and replaying fixed rules…'):run(kind,root)
        except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
    path=directory/'results.json'
    if not path.exists():st.info('No completed fixed-rule audit yet.');return
    try:result=recorded_result(kind,root)
    except (ValueError,OSError) as exc:st.error(str(exc));return
    st.write(f"Frozen {result['plan']['frozen_version']} · {result['plan']['ticker']}")
    st.caption(result['plan']['execution_note'])
    excluded=sum(r.get('excluded_invalid_time_rows',0) for r in result['provenance']['archives'])
    st.caption(f"Missing real intervals: {result['quality']['missing_bars']}; excluded invalid source timestamps: {excluded}. Raw archives are retained; nothing is filled or shifted.")
    st.metric('Sum of independent segment-account net P&L',f"${result['sum_independent_account_net']:,.2f}")
    st.caption('Multiple reset-account sums are not a continuous return. These data are now inspected; the outcomes cannot select new parameters while retaining holdout status.')
    st.dataframe(pd.DataFrame([dict(segment=r['segment'],rows=r['rows'],net_pnl=pnl(r['metrics']),entries=r['metrics']['entries'],drawdown=r['metrics']['max_intrabar_drawdown']) for r in result['segments']]),hide_index=True)
    stress_path=directory/'cost_stress.json'
    if stress_path.exists():
        st.caption('Fixed-rule cost stress. These post-inspection checks do not reselect parameters.')
        st.dataframe(pd.DataFrame(json.loads(stress_path.read_text())['rows']),hide_index=True)
        stress=json.loads(stress_path.read_text())['rows']
        if any(r['net_pnl']<0 for r in stress):st.warning('This fixed-rule transfer has negative outcomes under cost stress. It does not establish robust generalization.')
    if sum(r['metrics']['entries'] for r in result['segments'])<30:
        st.warning('Fewer than 30 entries: this sparse sample is insufficient to establish a reliable strategy estimate.')
    if not result['segments']:return
    segment=st.selectbox('Inspect independent segment',[r['segment'] for r in result['segments']],key=f'{kind}_segment')
    location=directory/f'segment{segment}';curve=pd.read_parquet(location/'equity.parquet');bars=pd.read_parquet(location/'bars.parquet')
    def csv(path):
        try:return pd.read_csv(path)
        except pd.errors.EmptyDataError:return pd.DataFrame()
    trades=csv(location/'trades.csv');events=csv(location/'events.csv')
    for column in ['entry_bar_open','exit_bar_open','entry_time','exit_time']:
        if column in trades:trades[column]=pd.to_datetime(trades[column],utc=True)
    for column in ['bar_open','effective_at']:
        if column in events:events[column]=pd.to_datetime(events[column],utc=True)
    equity_fig=performance_chart(curve,50000.)
    equity_fig.update_layout(title=f"{title} · Frozen {result['plan']['frozen_version']} · Equity and drawdown")
    month_fig=monthly_chart(curve,50000.);month_fig.update_layout(title=f'{title} · Monthly marked P&L')
    st.plotly_chart(equity_fig,width='stretch',key=f'{kind}_equity')
    st.plotly_chart(month_fig,width='stretch',key=f'{kind}_monthly')
    if len(trades):
        chosen=st.selectbox('Inspect transfer trade',list(range(len(trades))),key=f'{kind}_trade')
        fig,_=trade_chart(bars,trades.iloc[chosen],events,result['plan']['rule']['reward_r'])
        for trace in fig.data:
            if trace.type=='candlestick':trace.name=result['plan']['ticker']+' candles'
        st.plotly_chart(fig,width='stretch',key=f'{kind}_candles')


def cost_stress(kind,root=ROOT):
    p,rule,cfg,meta=frozen_profile(root)
    directory=root/f'artifacts/generalization/{kind}'
    original=recorded_result(kind,root)
    if original is None:raise ValueError('Run the fixed-rule audit before cost stress')
    if original['plan']['configuration_sha256']!=p['frozen_configuration_sha256']:raise ValueError('Audit profile differs')
    plan=dict(configuration_sha256=p['frozen_configuration_sha256'],post_inspection=True,selection_permitted=False,extra_slippage_bps=[2.,4.,8.])
    freeze(directory/'cost_stress_plan.json',plan)
    rows=[]
    for r in original['segments']:
        bars=pd.read_parquet(directory/f"segment{r['segment']}/bars.parquet")
        signals=apply_filter(prepare_features(bars,rule),RegimeFilter(**meta['entry_filters']))
        for bps in plan['extra_slippage_bps']:
            execution=replace(cfg,slippage_bps=bps,tick_size=.1 if kind=='btc' else cfg.tick_size)
            m,_,_=simulate(bars,rule,execution,signals=signals,validator=validate_btc if kind=='btc' else validate_proxy)
            rows.append(dict(segment=r['segment'],extra_slippage_bps=bps,net_pnl=pnl(m),entries=m['entries'],drawdown=m['max_intrabar_drawdown']))
    result=dict(plan=plan,rows=rows)
    freeze(directory/'cost_stress.json',safe_value(result))
    report=['# Fixed-rule '+kind+' cost stress','',
            'Post-inspection stress diagnostic, with identical frozen rules and no parameter selection. Multiple segment-account sums are not a continuous return.','',
            '| Segment | Extra slippage bp | Net P&L | Entries | Drawdown |','| --- | ---: | ---: | ---: | ---: |']
    for r in rows:report.append(f"| {r['segment']} | {r['extra_slippage_bps']} | ${r['net_pnl']:,.2f} | {r['entries']} | {r['drawdown']:.2%} |")
    (root/f'reports/generalization_{kind}_stress.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(kind,'COST STRESS',rows,flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('kind',choices=['btc','eth2017']);parser.add_argument('--stress',action='store_true')
    args=parser.parse_args()
    cost_stress(args.kind) if args.stress else run(args.kind)

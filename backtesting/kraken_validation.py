"""Frozen ETH/USD venue-transfer diagnostic on official Kraken spot history."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict,replace
import hashlib
import io
import json
import zipfile

import numpy as np
import pandas as pd
import requests

from .alternative_strategies import simulate
from .eth_research.data import validate_bars
from .exit_research import freeze
from .generalization_policy import digest,frozen_profile
from .independent_visuals import equity_curve
from .market_data import BAR,utc
from .optimize import pnl,write_json
from .paths import ROOT
from .regime_filters import RegimeFilter,apply_filter,prepare_features
from .remote_zip import RangeZip
from .reporting import safe_value

SOURCE='https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data'
BASE='https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_Full.zip.part'
TICKER='KRAKEN:ETHUSD.SPOT'


def validate_kraken(raw):
    frame=validate_bars(raw,expected_ticker=TICKER)
    frame['available_at']=frame.timestamp+BAR
    return frame,dict(rows=len(frame),instrument=TICKER,
                       missing_bars=int(frame.timestamp.diff().div(BAR).sub(1).clip(lower=0).sum()),
                       close_timestamp='Kraken CSV supplies candle-open seconds only; availability is open+5min. No exchange-close timestamp is asserted.')


def parse_csv(payload,start='2020-01-01',end='2026-10-01'):
    raw=pd.read_csv(io.BytesIO(payload),header=None,names=['epoch','open','high','low','close','volume','trades'])
    if raw.empty or raw.isna().any().any():raise ValueError('Kraken member has missing fields')
    for col in raw:raw[col]=pd.to_numeric(raw[col],errors='raise')
    if not np.isfinite(raw.to_numpy(dtype=float)).all():raise ValueError('Nonfinite Kraken source fields')
    if not raw.epoch.mod(1).eq(0).all() or not raw.trades.mod(1).eq(0).all() or (raw.trades<0).any():
        raise ValueError('Noninteger Kraken timestamps/trade counts')
    times=pd.to_datetime(raw.epoch.astype('int64'),unit='s',utc=True)
    # Keep all malformed times as a reported exclusion; no shifting/filling.
    aligned=times.eq(times.dt.floor('5min'))
    raw=raw.loc[aligned].copy();raw['timestamp']=times.loc[aligned];raw['ticker']=TICKER
    raw=raw[(raw.timestamp>=utc(start))&(raw.timestamp+BAR<=utc(end))]
    frame,quality=validate_kraken(raw.drop(columns='epoch'))
    quality['excluded_off_grid_rows']=int((~aligned).sum())
    quality['requested_period']=[start,end]
    return frame,quality


def part_metadata():
    def get(index):
        url=BASE+f'{index:02d}'
        response=requests.head(url,timeout=20,allow_redirects=False)
        if response.status_code!=200:raise ValueError(f'Kraken archive part unavailable: HTTP {response.status_code}')
        return dict(url=url,size=int(response.headers['Content-Length']),etag=response.headers['ETag'])
    with ThreadPoolExecutor(max_workers=5) as pool:return list(pool.map(get,range(5)))


def run(root=ROOT):
    p,rule,cfg,meta=frozen_profile(root)
    out=root/'artifacts/generalization/kraken_ethusd';out.mkdir(parents=True,exist_ok=True)
    data=root/'data/generalization/kraken_ethusd';data.mkdir(parents=True,exist_ok=True)
    plan=dict(name='Kraken ETHUSD fixed venue-transfer check',protocol_sha256=digest(p),
              frozen_version=p['frozen_version'],configuration_sha256=p['frozen_configuration_sha256'],
              rule=asdict(rule),filters=meta['entry_filters'],execution=asdict(cfg),
              period=['2020-01-01','2026-10-01'],allowed_members=['ETHUSD_5.csv','XETHZUSD_5.csv'],
              source=SOURCE,source_archive='Kraken_OHLCVT_Full.zip concatenated five published parts',
              fixed_before_market_data_fetch=True,parameter_selection_permitted=False,
              cost_scenarios_extra_slippage_bps=[2.,4.,8.],
              segmentation='Split actual gaps into independent $50000 accounts and fresh indicator warm-up. Skip segments shorter than 3000 bars. No missing-candle fabrication or timestamp shifts.',
              limitation='ETH/USD spot venue transfer under hypothetical ETH-futures-like fees, leverage, shorting and financing. Not Breakout fills, not independent asset evidence, and not future ETH validation.',
              integrity='TLS and pinned per-part ETags and exact Content-Range; selected ZIP member CRC and local SHA-256. Full multi-part published SHA-256 is not verified without downloading all ~9.5GB.',
              transfer_budget_bytes=128*1024*1024,maximum_member_bytes=256*1024*1024)
    freeze(out/'manifest.json',plan)
    result_path=out/'results.json'
    if result_path.exists():
        result=json.loads(result_path.read_text(encoding='utf-8'))
        for name,key in [('source.csv','member_sha256'),('candles.parquet','dataset_sha256')]:
            if hashlib.sha256((data/name).read_bytes()).hexdigest()!=result[key]:raise ValueError('Consumed Kraken data changed')
        if result['plan']!=plan:raise ValueError('Consumed Kraken audit has a different frozen plan')
        print('Kraken venue audit already consumed; saved source hashes verified, no rerun.',flush=True)
        return result
    if (out/'parts.json').exists():parts=json.loads((out/'parts.json').read_text())
    else:
        parts=part_metadata();freeze(out/'parts.json',parts)
    with RangeZip(parts,data/'ranges',max_bytes=plan['transfer_budget_bytes']) as stream:
        with zipfile.ZipFile(stream) as archive:
            matches=[i for i in archive.infolist() if i.filename.rsplit('/',1)[-1] in plan['allowed_members']]
            write_json(out/'zip_index.json',[dict(name=i.filename,uncompressed_bytes=i.file_size,compressed_bytes=i.compress_size,crc32=i.CRC) for i in matches])
            if len(matches)!=1:raise ValueError('Expected exactly one ETHUSD five-minute ZIP member')
            member=matches[0]
            if member.flag_bits&1 or member.file_size>plan['maximum_member_bytes']:
                raise ValueError('Unexpected encrypted or oversized Kraken member')
            chunks=[];size=0
            with archive.open(member) as handle:
                while True:
                    chunk=handle.read(1024*1024)
                    if not chunk:break
                    size+=len(chunk)
                    if size>plan['maximum_member_bytes']:raise ValueError('Decoded Kraken member exceeds bound')
                    chunks.append(chunk)
            payload=b''.join(chunks)
            if len(payload)!=member.file_size:raise ValueError('Incomplete Kraken ZIP member')
        ledger=stream.ledger;transferred=stream.transferred
    (data/'source.csv').write_bytes(payload)
    frame,quality=parse_csv(payload,*plan['period']);frame.to_parquet(data/'candles.parquet',index=False)
    records=[];skipped=[]
    for index,part in frame.groupby(frame.timestamp.diff().ne(BAR).cumsum()):
        part=part.reset_index(drop=True)
        if len(part)<3000:
            skipped.append(dict(segment=int(index),rows=len(part),start=str(part.timestamp.min()),end=str(part.available_at.max())))
            continue
        signals=apply_filter(prepare_features(part,rule),RegimeFilter(**meta['entry_filters']))
        metrics={}
        location=out/f'segment{index}';location.mkdir(exist_ok=True)
        for bps in plan['cost_scenarios_extra_slippage_bps']:
            m,trades,events=simulate(part,rule,replace(cfg,slippage_bps=bps),signals=signals,validator=validate_kraken)
            metrics[str(bps)]=m
            if bps==2.:
                curve=equity_curve(part,events,cfg)
                if abs(curve.equity.iloc[-1]-m['final_equity'])>1e-6:raise ValueError('Kraken transfer equity mismatch')
                part.to_parquet(location/'bars.parquet',index=False);curve.to_parquet(location/'equity.parquet',index=False)
                trades.to_csv(location/'trades.csv',index=False);events.to_csv(location/'events.csv',index=False)
        records.append(dict(segment=int(index),rows=len(part),start=str(part.timestamp.min()),end=str(part.available_at.max()),cost_metrics=metrics))
        print(f'KRAKEN segment {index}: {len(part)} bars, net=${pnl(metrics["2.0"]):.2f}, entries={metrics["2.0"]["entries"]}',flush=True)
    aggregates={str(bps):dict(sum_independent_account_net=sum(pnl(r['cost_metrics'][str(bps)]) for r in records),
                entries=sum(r['cost_metrics'][str(bps)]['entries'] for r in records),segments=len(records),
                worst_segment_drawdown=max((r['cost_metrics'][str(bps)]['max_intrabar_drawdown'] for r in records),default=None)) for bps in plan['cost_scenarios_extra_slippage_bps']}
    result=dict(plan=plan,member=member.filename,member_crc32=member.CRC,zip_member_crc_verified=True,
                member_sha256=hashlib.sha256(payload).hexdigest(),dataset_sha256=hashlib.sha256((data/'candles.parquet').read_bytes()).hexdigest(),
                range_ledger=ledger,new_bytes_downloaded=transferred,full_archive_sha256_verified=False,
                quality=quality,segments=records,skipped_segments=skipped,aggregates=aggregates,
                data_is_now_inspected=True,prospective_validation=False,ready_for_funded_trading=False)
    freeze(result_path,safe_value(result))
    report=['# Kraken ETH/USD frozen venue-transfer test','',plan['limitation'],'',
            f"Frozen strategy: **{p['frozen_version']}**. Requested 2020-01-01 through 2026-10-01 exclusive. Read **{len(frame):,}** real five-minute spot candles from `{member.filename}`. No parameter search or version promotion occurred.",'',
            plan['segmentation'],'',plan['integrity'],'',
            f"Downloaded {transferred:,} bytes using bounded ranges; member CRC verified and local SHA-256 retained. Full archive checksum verification: **not performed**. Archive part identities and all fetched byte ranges are retained.",'',
            '| Extra slippage bp per side | Sum of independent segment-account net | Entries | Segments | Worst segment drawdown |','| --- | ---: | ---: | ---: | ---: |']
    for bps,row in aggregates.items():
        dd=f"{row['worst_segment_drawdown']:.2%}" if row['worst_segment_drawdown'] is not None else 'N/A'
        report.append(f"| {bps} | ${row['sum_independent_account_net']:,.2f} | {row['entries']} | {row['segments']} | {dd} |")
    retained=sum(r['rows'] for r in records);skipped_rows=sum(r['rows'] for r in skipped)
    actionable_upper=sum(max(0,r['rows']-rule.slow*12) for r in records)
    report+=['',f"Missing real intervals: {quality['missing_bars']}; off-grid rows excluded: {quality['excluded_off_grid_rows']}; skipped short segments: {len(skipped)}. These reset-account sums are **not continuous returns** and are not added to the Binance development score.",'',
             f"Coverage limitation: {retained:,} of {len(frame):,} source rows were in long enough segments; {skipped_rows:,} rows were skipped entirely. After the minimum {rule.slow}-hour warm-up in each retained segment, at most {actionable_upper:,} rows ({actionable_upper/len(frame):.1%}) remained eligible for execution. Partial initial hours can reduce this further. This fragmentary test is not equivalent to continuously trading the full 2020-2026 period.",'',
             'This dataset is now consumed diagnostic evidence. A failed result will not trigger tuning on this test until it passes. Venue and USDT/USD differences, volume construction, fragmentation and hypothetical costs limit comparability. The prospective ETH lock remains unchanged.','',
             f'[Official archive description]({SOURCE}).','']
    (root/'reports/generalization_kraken_ethusd.md').write_text('\n'.join(report),encoding='utf-8')
    return result


def recorded(root=ROOT):
    out=root/'artifacts/generalization/kraken_ethusd';path=out/'results.json'
    if not path.exists():return None
    result=json.loads(path.read_text(encoding='utf-8'))
    p,_,_,_=frozen_profile(root)
    if result['plan']['configuration_sha256']!=p['frozen_configuration_sha256'] or result['plan']['protocol_sha256']!=digest(p):
        raise ValueError('Kraken test does not match the frozen generalization protocol')
    data=root/'data/generalization/kraken_ethusd'
    for name,key in [('source.csv','member_sha256'),('candles.parquet','dataset_sha256')]:
        if hashlib.sha256((data/name).read_bytes()).hexdigest()!=result[key]:raise ValueError('Consumed Kraken source bytes changed')
    return result


def render(root=ROOT):
    import streamlit as st
    from .independent_visuals import performance_chart,monthly_chart,trade_chart
    st.subheader('Kraken ETH/USD venue-transfer test')
    st.caption('Frozen ETH rules on a separate spot feed. No parameter tuning. ETH prices across venues are related; this is not statistically independent future evidence.')
    if st.button('Fetch Kraken member and run frozen venue test'):
        try:
            with st.spinner('Fetching only the ETH/USD ZIP member and replaying fixed rules…'):run(root)
        except (ValueError,OSError,requests.RequestException,zipfile.BadZipFile) as exc:st.error(str(exc))
    try:result=recorded(root)
    except (ValueError,OSError) as exc:st.error(str(exc));return
    if result is None:st.info('No Kraken transfer audit yet.');return
    st.write(f"Frozen **{result['plan']['frozen_version']}** · **{TICKER}** · 2020-01-01 to 2026-10-01 exclusive")
    st.caption(result['plan']['limitation'])
    frame_rows=result['quality']['rows'];retained=sum(r['rows'] for r in result['segments']);skipped=frame_rows-retained
    warmup=result['plan']['rule']['slow']*12
    maximum_active=sum(max(0,r['rows']-warmup) for r in result['segments'])
    st.warning(f"Fragmented coverage: {len(result['segments'])} independent accounts, {result['quality']['missing_bars']:,} missing intervals and {skipped:,} skipped rows. At most {maximum_active/frame_rows:.1%} of source rows remain after minimum warm-up. The sums below are not a continuous return.")
    st.dataframe(pd.DataFrame([dict(extra_slippage_bps=float(bps),**row) for bps,row in result['aggregates'].items()]),hide_index=True)
    st.caption(f"{frame_rows:,} real source candles. Member CRC verified; {result['new_bytes_downloaded']:,} bytes downloaded. The published full multi-part archive SHA-256 was not verified. ETags, bounded ranges, member hash and raw selected CSV are retained.")
    st.caption('This dataset is now consumed diagnostic evidence. Its outcomes do not authorize retuning or version promotion. The locked ETH forward test is unchanged.')
    if not result['segments']:return
    with st.expander('Inspect one independently reset segment',expanded=False):
        options=[r['segment'] for r in result['segments']]
        chosen=st.selectbox('Kraken segment',options,key='kraken_segment')
        location=root/f'artifacts/generalization/kraken_ethusd/segment{chosen}'
        curve=pd.read_parquet(location/'equity.parquet');bars=pd.read_parquet(location/'bars.parquet')
        def csv(path):
            try:return pd.read_csv(path)
            except pd.errors.EmptyDataError:return pd.DataFrame()
        trades=csv(location/'trades.csv');events=csv(location/'events.csv')
        for name in ['entry_bar_open','exit_bar_open','entry_time','exit_time']:
            if name in trades:trades[name]=pd.to_datetime(trades[name],utc=True)
        for name in ['bar_open','effective_at']:
            if name in events:events[name]=pd.to_datetime(events[name],utc=True)
        figure=performance_chart(curve,50000.)
        figure.update_layout(title=f'Kraken ETH/USD · Independent segment {chosen} · Equity and drawdown')
        st.plotly_chart(figure,width='stretch',key='kraken_equity')
        st.plotly_chart(monthly_chart(curve,50000.),width='stretch',key='kraken_monthly')
        if len(trades):
            index=st.selectbox('Inspect Kraken transfer trade',list(range(len(trades))),key='kraken_trade')
            fig,_=trade_chart(bars,trades.iloc[index],events,result['plan']['rule']['reward_r'])
            for trace in fig.data:
                if trace.type=='candlestick':trace.name=TICKER+' candles'
            st.plotly_chart(fig,width='stretch',key='kraken_candles')
        else:st.info('No trades after warm-up in this retained segment.')


if __name__=='__main__':run()

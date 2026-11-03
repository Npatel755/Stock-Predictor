"""Rebuild Coinbase inputs from pinned responses and reproduce every cost replay."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pandas as pd

from .alternative_strategies import simulate
from .coinbase_validation import parse_day,validate_coinbase,recorded,PRODUCTS
from .exit_research import freeze
from .forward_collection import atomic_json
from .generalization_policy import frozen_profile,digest
from .independent_visuals import equity_curve
from .paths import ROOT
from .regime_filters import RegimeFilter,apply_filter,prepare_features
from .reporting import safe_value


def exact_frame(left,right):
    # Parquet stores second-resolution timestamps as millisecond-resolution
    # timestamps. Compare exact UTC instants, not storage-unit spelling; keep
    # every numerical candle/equity value exact with no tolerance or rounding.
    def canonical(frame):
        frame=frame.copy()
        for name in frame.columns:
            if isinstance(frame[name].dtype,pd.DatetimeTZDtype):
                frame[name]=pd.to_datetime(frame[name],utc=True).dt.as_unit('ns')
        return frame
    pd.testing.assert_frame_equal(canonical(left),canonical(right),check_exact=True)


def verify(root=ROOT):
    result=recorded(root,verify_sources=True)
    if result is None:raise ValueError('Complete the Coinbase fixed-rule audit before verification')
    policy,rule,cfg,metadata=frozen_profile(root)
    out=root/'artifacts/generalization/coinbase';data=root/'data/generalization/coinbase'
    checks={}
    for product in PRODUCTS:
        sources=[s for s in result['sources'] if s['product']==product]
        start,end=map(pd.Timestamp,result['plan']['period'])
        expected={str(d.date()) for d in pd.date_range(start,end,inclusive='left',freq='D')}
        if len(sources)!=len(expected) or {s['day'] for s in sources}!=expected:
            raise ValueError('Coinbase source request inventory does not match the frozen period')
        chunks=[]
        for source in sources:
            payload=(data/'responses'/source['response_file']).read_bytes()
            frame,quality=parse_day(payload,product,source['params']['start'],source['params']['end'])
            if quality!=source['parse_quality']:raise ValueError('Pinned response parsing changed')
            if len(frame):chunks.append(frame)
        rebuilt,_=validate_coinbase(pd.concat(chunks,ignore_index=True),product)
        saved=pd.read_parquet(data/f'{product}.parquet')
        exact_frame(rebuilt,saved)
        segments={int(index):part.reset_index(drop=True) for index,part in rebuilt.groupby(rebuilt.timestamp.diff().ne(pd.Timedelta(minutes=5)).cumsum()) if len(part)>=3000}
        product_result=result['products'][product]
        if set(segments)!={r['segment'] for r in product_result['segments']}:
            raise ValueError('Coinbase segment inventory differs')
        verified=[]
        for row in product_result['segments']:
            frame=segments[row['segment']]
            signals=apply_filter(prepare_features(frame,rule),RegimeFilter(**metadata['entry_filters']))
            location=out/product/f"segment{row['segment']}"
            exact_frame(frame,pd.read_parquet(location/'bars.parquet'))
            for bps in result['plan']['cost_scenarios_extra_slippage_bps']:
                execution=replace(cfg,tick_size=.01,slippage_bps=bps)
                m,trades,events=simulate(frame,rule,execution,signals=signals,validator=lambda raw,prod=product:validate_coinbase(raw,prod))
                if safe_value(m)!=row['cost_metrics'][str(bps)]:raise ValueError('Fresh Coinbase broker replay differs from the saved outcome')
                if bps==2.:
                    curve=equity_curve(frame,events,execution)
                    exact_frame(curve,pd.read_parquet(location/'equity.parquet'))
                    if abs(curve.equity.iloc[-1]-m['final_equity'])>1e-6:raise ValueError('Fresh Coinbase visual equity does not reconcile')
                verified.append(dict(segment=row['segment'],slippage_bps=bps,final_equity=m['final_equity']))
        checks[product]=dict(raw_days_rebuilt=len(sources),rows=len(rebuilt),replays=verified)
        print(f'COINBASE VERIFIED {product}: {len(sources)} raw responses, {len(rebuilt)} candles, {len(verified)} cost replays.',flush=True)
    proof=dict(protocol_sha256=digest(policy),configuration_sha256=policy['frozen_configuration_sha256'],
               results_sha256=hashlib.sha256((out/'results.json').read_bytes()).hexdigest(),
               rebuilt_exactly_from_raw_responses=True,reproduced_broker_and_visual_equity=True,
               checks=checks,forward_validation=False,ready_for_funded_trading=False)
    proof_hash=digest(safe_value(proof));path=out/'verification'/f'{proof_hash}.json';path.parent.mkdir(exist_ok=True)
    freeze(path,proof)
    atomic_json(out/'verification_latest.json',dict(path=path.relative_to(root).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),results_sha256=proof['results_sha256'],computational_reproduction_only=True))
    return proof


if __name__=='__main__':verify()

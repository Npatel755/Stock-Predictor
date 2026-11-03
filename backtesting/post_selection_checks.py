"""Fixed-rule older-spot and conditional-bootstrap diagnostics after selection."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .alternative_strategies import SignalRule, simulate
from .config import StrategyConfig
from .exit_research import freeze
from .independent_visuals import equity_curve
from .market_data import BAR, load_history, utc
from .optimize import pnl, write_json
from .paths import ROOT
from .regime_filters import RegimeFilter, apply_filter, prepare_features
from .spot_proxy_data import validate_proxy
from .verify_numbered_research import exact


def paired_interval(daily_difference, seed=1909, draws=2000, block_days=7):
    values=np.asarray(daily_difference,dtype=float)
    if len(values)<block_days or not np.isfinite(values).all():
        raise ValueError('Bootstrap needs finite paired daily differences and a full block')
    rng=np.random.default_rng(seed)
    starts=rng.integers(0,len(values)-block_days+1,size=(draws,int(np.ceil(len(values)/block_days))))
    indices=(starts[:,:,None]+np.arange(block_days)[None,None,:]).reshape(draws,-1)[:,:len(values)]
    interval=np.quantile(values[indices].sum(axis=1),[.025,.975])
    return dict(interval_95=interval.tolist(),observed_difference=float(values.sum()),seed=seed,
                draws=draws,block_days=block_days,conditional_on_selected_rules=True,
                corrects_search_bias=False,forward_validation=False)


def run(directory: Path, version: str):
    selected=json.loads((directory/'selection.json').read_text(encoding='utf-8'))
    verified=json.loads((directory/'verification.json').read_text(encoding='utf-8'))
    search=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if (not verified.get('reproduced_exactly') or not verified.get('passed_frozen_gate')
            or verified['selection_sha256']!=hashlib.sha256((directory/'selection.json').read_bytes()).hexdigest()):
        raise ValueError('Diagnose the freshly reproduced selection before proposing a version')
    parent=json.loads((directory/'parent.json').read_text(encoding='utf-8'))
    scenarios={'parent':parent,'selected':dict(rule=selected['candidate']['rule'],execution=selected['execution_config'],filters=selected['candidate']['filters'])}
    data=ROOT/'data/ethusd/v1_5_spot_2018_2019'
    metadata=json.loads((data/'metadata.json').read_text(encoding='utf-8'))
    if hashlib.sha256((data/'candles.parquet').read_bytes()).hexdigest()!=metadata['dataset_sha256']:
        raise ValueError('Older spot dataset hash differs from its audited source')
    for archive in metadata['archives']:
        path=data/f"ETHUSDT-5m-{archive['month']}.zip"
        if hashlib.sha256(path.read_bytes()).hexdigest()!=archive['sha256']:
            raise ValueError('Raw spot archive changed')
    plan=dict(name=f'Frozen post-selection {version} diagnostics',version=version,parent_version=search['parent_version'],
              scenarios=scenarios,dataset_sha256=metadata['dataset_sha256'],
              selection_sha256=verified['selection_sha256'],verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              parameter_selection_permitted=False,already_inspected_data=True,prospective_validation=False,
              segmentation='Annual boundaries and actual gaps reset accounts and indicators. Skip segments shorter than 2400 bars for both versions. No invented bars or ticker substitution.',
              bootstrap=dict(block_days=7,draws=2000,seed=1909,conditional_on_selected_rules=True,corrects_search_bias=False),
              warning='Spot transfer with hypothetical leveraged costs. Segment sums are not continuous returns or Breakout fills. These diagnostics do not alter the frozen selection gate.')
    freeze(directory/'post_selection_plan.json',plan)
    frame,quality=validate_proxy(pd.read_parquet(data/'candles.parquet'))
    results,skipped=[],[]
    for year,annual in frame.groupby(frame.timestamp.dt.year):
        for index,part in annual.groupby(annual.timestamp.diff().ne(BAR).cumsum()):
            part=part.reset_index(drop=True)
            if len(part)<2400:
                skipped.append(dict(year=int(year),segment=int(index),rows=len(part)))
                continue
            for name,payload in scenarios.items():
                rule=SignalRule(**payload['rule']);cfg=StrategyConfig(**payload['execution']);filters=RegimeFilter(**payload['filters'])
                signals=apply_filter(prepare_features(part,rule),filters)
                metrics,trades,_=simulate(part,rule,cfg,signals=signals,validator=validate_proxy)
                results.append(dict(scenario=name,year=int(year),segment=int(index),rows=len(part),metrics=metrics))
                trades.to_csv(directory/f'spot_{year}_{index}_{name}_trades.csv',index=False)
    aggregates={name:dict(sum_independent_account_pnl=sum(pnl(r['metrics']) for r in results if r['scenario']==name),
                          entries=sum(r['metrics']['entries'] for r in results if r['scenario']==name),
                          segments=sum(r['scenario']==name for r in results)) for name in scenarios}
    bars,_=load_history(ROOT/'data/ethusd/perpetual/candles.parquet')
    bars=bars[(bars.timestamp>=utc('2023-01-01'))&(bars.timestamp<utc('2026-10-28'))].reset_index(drop=True)
    rule=SignalRule(**parent['rule']);cfg=StrategyConfig(**parent['execution']);filters=RegimeFilter(**parent['filters'])
    pm,_,events=simulate(bars,rule,cfg,signals=apply_filter(prepare_features(bars,rule),filters))
    exact(pm,verified['benchmark']['main'],'post-selection parent equity')
    a=equity_curve(bars,events,cfg).set_index('timestamp').equity
    b=pd.read_parquet(directory/'verified_equity.parquet').set_index('timestamp').equity
    if not a.index.equals(b.index) or abs(b.iloc[-1]-verified['metrics']['full_period']['final_equity'])>1e-6:
        raise ValueError('Paired equity curves do not reconcile')
    daily_difference=b.resample('1D').last()-a.resample('1D').last()
    changes=daily_difference.diff()
    changes.iloc[0]=daily_difference.iloc[0]
    differences=changes.to_numpy()
    if abs(differences.sum()-(b.iloc[-1]-a.iloc[-1]))>1e-6:
        raise ValueError('Paired daily differences do not reconcile')
    bootstrap=paired_interval(differences)
    diagnostic=dict(plan=plan,quality=quality,spot_results=results,spot_aggregates=aggregates,
                    skipped_segments=skipped,bootstrap=bootstrap,post_selection_2026_h1_8bp=verified['post_selection_2026_h1_8bp'])
    write_json(directory/'post_selection_diagnostics.json',diagnostic)
    report=[f'# ETH {version} additional diagnostics','',plan['warning'],'',
            'The fixed rules were recorded before running these diagnostics. The 2018-2019 spot dataset and all 24 monthly archives match their stored SHA-256 hashes. The ticker remains BINANCE:ETHUSDT spot; no spot candle is relabeled as a perpetual future. Annual/gap boundaries reset accounts and indicators; short segments are skipped equally for both versions.','',
            '| Rules | Sum of independent spot segment-account net P&L | Entries | Segments |','| --- | ---: | ---: | ---: |']
    for name,value in aggregates.items():
        label=search['parent_version'] if name=='parent' else version
        report.append(f"| {label} | ${value['sum_independent_account_pnl']:,.2f} | {value['entries']} | {value['segments']} |")
    report+=['',f"Skipped short segments: {len(skipped)}. These sums are not a continuous return and are not added to the original perpetual baseline. Hypothetical fees, financing and leverage are held fixed. They do not represent actual spot funding, executable spot shorting or Breakout fills.",'',
             'Older spot data is already inspected. This is a post-selection transfer diagnostic, not fresh validation. The earlier v1.4 spot sum was $6,833.37; see [the original audit](v1_5_spot_proxy.md). A higher original-period result does not imply a universal historical winner.','',
             f"The additional reset 2026 H1 stress check at 8bp extra slippage makes **${pnl(verified['post_selection_2026_h1_8bp']):,.2f}**. This post-selection diagnostic does not change the frozen gate.",'',
             f"A conditional paired seven-day moving-block bootstrap, {bootstrap['draws']} draws with seed {bootstrap['seed']}, gives a 95% interval of **${bootstrap['interval_95'][0]:,.2f} to ${bootstrap['interval_95'][1]:,.2f}** for the historical difference of ${bootstrap['observed_difference']:,.2f}.",'',
             'The interval conditions on already-selected rules, does not correct for the repeated search, and is not a probability of future profit. All 2023-2026 data was used in historical selection. Pine compilation, TradingView matching and funded-account readiness remain unverified.','']
    (ROOT/f"reports/{version.replace('.','_')}_additional_checks.md").write_text('\n'.join(report),encoding='utf-8')
    for name,value in aggregates.items(): print(f"POST-SELECTION SPOT {name}: ${value['sum_independent_account_pnl']:.2f}",flush=True)
    print(f"POST-SELECTION INTERVAL: {bootstrap['interval_95']}",flush=True)
    return diagnostic


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--version',required=True)
    args=parser.parse_args()
    run(args.directory,args.version)

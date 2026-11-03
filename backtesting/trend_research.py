"""Frozen trend-quality search above the new $9,900 / exact v1.5 benchmark."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
from itertools import product
import json
from pathlib import Path

import pandas as pd

from .alternative_strategies import SignalRule, simulate
from .config import StrategyConfig
from .exit_research import freeze
from .market_data import load_history, utc
from .optimize import append, pnl, resume_rows, subset, write_json
from .paths import ROOT, PARQUET
from .regime_filters import RegimeFilter, apply_filter, prepare_features


def candidates(rule, parent_filters):
    return [dict(id=i,label=f'trendgap{gap}_slope{slope}',rule=asdict(rule),
                 filters=asdict(replace(parent_filters,min_trend_gap_bps=gap,min_signed_slope_bps=slope)))
            for i,(gap,slope) in enumerate(product([0.,100.,200.,400.],[None,0.,5.,10.,20.,40.]))]


def eligible(metrics, checks, benchmark, requested):
    return (pnl(metrics)>max(requested,pnl(benchmark['main'])) and metrics['entries']>=100
            and metrics['max_intrabar_drawdown']<=benchmark['main']['max_intrabar_drawdown']
            and all(m['margin_call_events']==0 for m in [metrics,*checks.values()])
            and all(pnl(checks[k])>0 for k in ['2025_h1','2025_h2','2026_h1','2026_h2','earlier_2020_2022'])
            and min(checks[k]['entries'] for k in ['2025_h1','2025_h2','2026_h1','2026_h2'])>=6
            and pnl(checks['full_4bp'])>pnl(benchmark['stress4'])
            and pnl(checks['full_8bp'])>pnl(benchmark['stress8']))


def run(args):
    from .generalization_policy import assert_search_allowed
    assert_search_allowed(ROOT)
    args.output.mkdir(parents=True,exist_ok=True)
    for source,name in [(ROOT/'configs/eth_strategy_v1_5.json','parent_v1_5.json'),(ROOT/'configs/research_baseline.json','baseline.json')]:
        path=args.output/name
        if not path.exists():path.write_bytes(source.read_bytes())
    parent=json.loads((args.output/'parent_v1_5.json').read_text(encoding='utf-8'))
    baseline=json.loads((args.output/'baseline.json').read_text(encoding='utf-8'))
    rule,cfg,filters=SignalRule(**parent['rule']),StrategyConfig(**parent['execution']),RegimeFilter(**parent['filters'])
    universe=candidates(rule,filters)
    earlier_path=ROOT/'data/ethusd/perpetual_2020_2022/candles.parquet'
    protected=[ROOT/'configs/eth_strategy_v1_5.json',ROOT/'configs/eth_strategy_v1_5.metadata.json',ROOT/'reference/ETH_Strategy_v1_5.pine']
    plan=dict(name='ETH v1.5 trend-quality follow-up',candidate_count=len(universe),candidates=universe,
              execution=asdict(cfg),historical_profit_selection=True,prior_search_slots=658,
              selection_window=['2023-01-01','2026-10-28'],shortlist=6,requested_baseline_net=baseline['requested_net_profit_usd'],
              exact_reference_net=baseline['prior_reference_net_profit_usd'],
              source_hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                             ['trend_research.py','alternative_strategies.py','regime_filters.py','engine.py','config.py','indicators.py','market_data.py','optimize.py','exit_research.py']},
              data_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [PARQUET,earlier_path]},
              protected_profile_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected},
              baseline_sha256=hashlib.sha256((args.output/'baseline.json').read_bytes()).hexdigest(),
              gate='Main net above both requested $9900 and saved v1.5 exact replay; drawdown <= parent; >=100 entries; positive reset 2025/2026 halves with >=6 entries each; positive earlier 2020-2022; 4bp/8bp full-period net above parent at identical stressed costs; no margin calls.',
              selection='Rank inspected full-period net; shortlist six changed drawdown/exposure-eligible filters; choose highest complete-gate pass. If none passes, retain best changed diagnostic, not a promoted strategy.',
              warning='All 2023-2026 data including weak 2026 H1 is reused selection history. 2018-2019 spot data has already been inspected but does not select this grid. No independent forward-validation claim. Geometry, RVOL2, risk, account size, fees, financing and fills remain fixed; no saved-version changes.')
    freeze(args.output/'manifest.json',plan)
    bars,_=load_history(PARQUET)
    bars=bars[(bars.timestamp>=utc('2023-01-01'))&(bars.timestamp<utc('2026-10-28'))].reset_index(drop=True)
    earlier,_=load_history(earlier_path)
    features=prepare_features(bars,rule)
    old_features=prepare_features(earlier,rule)
    path=args.output/'benchmark.json'
    if path.exists():
        benchmark=json.loads(path.read_text(encoding='utf-8'))
    else:
        plain=apply_filter(features,filters)
        benchmark={name:simulate(bars,rule,replace(cfg,slippage_bps=bps),signals=plain)[0]
                   for name,bps in [('main',2.),('stress4',4.),('stress8',8.)]}
        write_json(path,benchmark)
    print(f"TARGET requested=${plan['requested_baseline_net']:.2f}; must beat exact parent=${pnl(benchmark['main']):.2f}",flush=True)
    training=resume_rows(args.output/'training.jsonl')
    done={r['id'] for r in training}
    for candidate in universe:
        if candidate['id'] in done:continue
        selected=apply_filter(features,RegimeFilter(**candidate['filters']))
        m=simulate(bars,rule,cfg,signals=selected)[0]
        row=dict(id=candidate['id'],label=candidate['label'],metrics=m,score=pnl(m))
        training.append(row)
        append(args.output/'training.jsonl',row)
        print(f"TREND {len(training)}/{len(universe)} {row['label']}: net=${pnl(m):.2f} DD={m['max_intrabar_drawdown']:.2%}",flush=True)
    ranked=sorted(training,key=lambda r:(-r['score'],r['id']))
    ids=[r['id'] for r in ranked if r['id'] and r['metrics']['entries']>=100 and not r['metrics']['margin_call_events']
         and r['metrics']['max_intrabar_drawdown']<=benchmark['main']['max_intrabar_drawdown']][:plan['shortlist']]
    write_json(args.output/'shortlist.json',dict(candidate_ids=ids,selection_uses='Inspected full-period net/drawdown',requested_baseline=plan['requested_baseline_net']))
    validation=resume_rows(args.output/'validation.jsonl')
    done={r['id'] for r in validation}
    by_id={r['id']:r for r in training}
    for candidate_id in ids:
        if candidate_id in done:continue
        candidate=universe[candidate_id]
        selected_filters=RegimeFilter(**candidate['filters'])
        signals=apply_filter(features,selected_filters)
        checks={}
        for name,start,end in [('2025_h1','2025-01-01','2025-07-01'),('2025_h2','2025-07-01','2026-01-01'),
                               ('2026_h1','2026-01-01','2026-07-01'),('2026_h2','2026-07-01','2026-10-28')]:
            b,f=subset(bars,signals,start,end)
            checks[name]=simulate(b,rule,cfg,signals=f)[0]
        checks['earlier_2020_2022']=simulate(earlier,rule,cfg,signals=apply_filter(old_features,selected_filters))[0]
        for bps in [4.,8.]:
            checks[f'full_{int(bps)}bp']=simulate(bars,rule,replace(cfg,slippage_bps=bps),signals=signals)[0]
        passed=eligible(by_id[candidate_id]['metrics'],checks,benchmark,plan['requested_baseline_net'])
        row=dict(id=candidate_id,label=candidate['label'],checks=checks,passed_historical_gate=passed,score=by_id[candidate_id]['score'])
        validation.append(row)
        append(args.output/'validation.jsonl',row)
        print(f"TREND CHECK {row['label']} gate={passed} H1_2026=${pnl(checks['2026_h1']):.2f} 4bp=${pnl(checks['full_4bp']):.2f} 8bp=${pnl(checks['full_8bp']):.2f}",flush=True)
    passing=[r for r in validation if r['passed_historical_gate']]
    if not validation:raise ValueError('No changed candidate met the initial drawdown/exposure screen; full checkpoints retained')
    winner=max(passing or validation,key=lambda r:(r['score'],-r['id']))
    selection=dict(candidate=universe[winner['id']],execution_config=asdict(cfg),validation=winner,
                   passed_predeclared_validation_gate=bool(passing),selection_is_historical_profit_optimization=True,
                   requested_baseline=plan['requested_baseline_net'],exact_reference_net=pnl(benchmark['main']),
                   independent_validation=False,ready_for_funded_trading=False)
    freeze(args.output/'selection.json',selection)
    signals=apply_filter(features,RegimeFilter(**selection['candidate']['filters']))
    m,trades,events=simulate(bars,rule,cfg,signals=signals)
    trades.to_csv(args.output/'selected_trades.csv',index=False)
    events.to_csv(args.output/'selected_events.csv',index=False)
    write_json(args.output/'summary.json',dict(selection=selection,benchmark=benchmark,evaluation=dict(full_period=m,**winner['checks']),saved_v1_5_unchanged=True))
    pd.DataFrame([dict(id=r['id'],label=r['label'],net_pnl=r['score'],entries=r['metrics']['entries'],drawdown=r['metrics']['max_intrabar_drawdown']) for r in ranked]).to_csv(args.output/'leaderboard.csv',index=False)
    lines=['# Trend-quality follow-up above the $9,900 baseline','',plan['warning'],'',
           f"Requested floor: **${plan['requested_baseline_net']:,.2f}**. Exact saved v1.5 reference: **${pnl(benchmark['main']):,.2f}**. Merely beating the rounded floor does not count as improvement.",'',
           f"Screened {len(universe)} fixed filters. Selected diagnostic: **{selection['candidate']['label']}**. Full historical improvement gate: **{bool(passing)}**.",'',
           '| Same original 2023-01-01 to 2026-10-28 exclusive period | Net P&L | Entries | Intrabar drawdown |','| --- | ---: | ---: | ---: |']
    for name,metrics in [('Saved v1.5',benchmark['main']),('Changed trend candidate',m),('Saved v1.5 at 4bp',benchmark['stress4']),('Candidate at 4bp',winner['checks']['full_4bp']),('Saved v1.5 at 8bp',benchmark['stress8']),('Candidate at 8bp',winner['checks']['full_8bp'])]:
        lines.append(f"| {name} | ${pnl(metrics):,.2f} | {metrics['entries']} | {metrics['max_intrabar_drawdown']:.2%} |")
    lines.extend(['',f"Filters: `{json.dumps(selection['candidate']['filters'],sort_keys=True)}`.",'',
                  '| Reused-data check, independently reset account | Net P&L | Entries |','| --- | ---: | ---: |'])
    for name,metrics in winner['checks'].items():
        if name not in {'full_4bp','full_8bp'}:lines.append(f"| {name} | ${pnl(metrics):,.2f} | {metrics['entries']} |")
    lines.extend(['','Trend distance is direction-signed hourly close versus EMA150; slope is direction-signed change of that EMA over six completed hours. Volume remains at least twice the prior-20-hour average. Signals use the completed hour, not future candles. These are full broker replays rather than deletion of losing trades. Account risk and all costs remain unchanged.','',
                  'Saved v1.5 and its downloads remain unchanged. Fold sums are not continuous account returns. A failed gate is retained even if headline P&L exceeds $9,900. The existing volume-only exporter rejects active trend filters rather than silently dropping them; a faithful export would be needed before any changed candidate can be offered as a TradingView strategy.',''])
    report='\n'.join(lines)
    (args.output/'report.md').write_text(report,encoding='utf-8')
    (ROOT/'reports/v1_5_trend_followup.md').write_text(report,encoding='utf-8')
    for name,digest in plan['protected_profile_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Protected v1.5 changed during search')
    print(f"TREND FINISHED net=${pnl(m):.2f} improvement=${pnl(m)-pnl(benchmark['main']):.2f} gate={bool(passing)}",flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/optimization/round10_v1_5_trend')
    run(parser.parse_args())

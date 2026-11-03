"""Retrospective selection/stability diagnostics; never claim a clean holdout."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json

import numpy as np
import pandas as pd
from scipy.stats import beta

from .alternative_strategies import simulate
from .exit_research import freeze
from .generalization_policy import digest, frozen_profile
from .market_data import BAR,load_history,utc
from .numbered_profiles import load_profile
from .optimize import pnl,subset,write_json
from .paths import ROOT,PARQUET
from .regime_filters import RegimeFilter,prepare_features,apply_filter


def purged_mask(decisions,label_ends,test_start,gap_days=7):
    decisions=pd.to_datetime(decisions,utc=True);ends=pd.to_datetime(label_ends,utc=True)
    cutoff=utc(test_start)-pd.Timedelta(days=gap_days)
    return decisions.lt(cutoff)&ends.lt(cutoff)&ends.ge(decisions)


def robust_choice(rows):
    eligible=[]
    for row in rows:
        folds=row['inner']
        returns=[r['closed_net']/100. for r in folds]
        if (min(r['entries'] for r in folds)<6 or sum(r['entries'] for r in folds)<20
                or any(r['margin_calls'] or r['drawdown']>.05 for r in folds)
                or sum(x>0 for x in returns)<2):continue
        score=float(np.median(returns)-max(0.,-min(returns))-np.median([r['drawdown']*50000/100 for r in folds]))
        if score>0:eligible.append((score,-row['complexity_order'],row['version']))
    return max(eligible)[2] if eligible else None


def multiplicity_check(changes,trials,draws=100000,seed=20261103):
    x=np.asarray(changes,dtype=float)
    if len(x)<14 or not np.isfinite(x).all():raise ValueError('Need finite daily P&L and at least two blocks')
    observed=x.mean();centered=x-observed;rng=np.random.default_rng(seed);exceed=0;block=7
    for offset in range(0,draws,500):
        batch=min(500,draws-offset)
        starts=rng.integers(0,len(x)-block+1,size=(batch,int(np.ceil(len(x)/block))))
        idx=(starts[:,:,None]+np.arange(block)[None,None,:]).reshape(batch,-1)[:,:len(x)]
        exceed+=int((centered[idx].mean(axis=1)>=observed).sum())
    probability=(exceed+1)/(draws+1)
    upper=float(beta.ppf(.95,exceed+1,draws-exceed)) if exceed<draws else 1.
    return dict(one_sided_centered_block_p=probability,monte_carlo_upper95=upper,
                bonferroni_adjusted_p=min(1.,probability*trials),bonferroni_adjusted_upper95=min(1.,upper*trials),
                logged_trial_slots=trials,draws=draws,block_days=block,seed=seed,
                complete_search_history_available=False,forward_validation=False,
                warning='848 logged slots are a trial-count proxy, not a complete independent trial history. Bootstrap stationarity and block assumptions apply. This retrospective diagnostic cannot certify future edge.')


def stability(directory):
    selected=json.loads((directory/'selection.json').read_text())['candidate']
    plan=json.loads((directory/'manifest.json').read_text())
    training={r['id']:r for r in map(json.loads,(directory/'training.jsonl').read_text().splitlines())}
    dimensions=plan.get('campaign',{}).get('rule_dimensions',{})
    net=training[selected['id']]['score'];neighbors=[]
    for name,values in dimensions.items():
        ordered=sorted(set(values));value=selected['rule'][name];position=ordered.index(value)
        adjacent=[ordered[i] for i in [position-1,position+1] if 0<=i<len(ordered)]
        for c in plan['candidates']:
            if c['rule'][name] not in adjacent:continue
            if all(c['rule'][k]==v for k,v in selected['rule'].items() if k!=name) and c['filters']==selected['filters']:
                neighbors.append(dict(label=c['label'],net=training[c['id']]['score'],ratio_to_selected=training[c['id']]['score']/net))
    return dict(neighbors=neighbors,within_10pct_fraction=float(np.mean([r['ratio_to_selected']>=.9 for r in neighbors])) if neighbors else None,
                worst_ratio=min((r['ratio_to_selected'] for r in neighbors),default=None),retrospective_only=True)


def run(root=ROOT):
    policy,_,_,meta=frozen_profile(root);out=root/'artifacts/generalization/retrospective';out.mkdir(parents=True,exist_ok=True)
    versions=['v1.5','v1.8','v1.10','v1.11']
    plan=dict(protocol_sha256=digest(policy),versions=versions,outer_months=6,inner_blocks=3,inner_months=6,gap_days=7,
              selection='Choose only from three preceding inner blocks using closed, purged outcomes. Penalize worst-block loss and drawdown. Require >=6 entries/block, >=20 total, >=2 positive blocks, no margin calls, <=5% drawdown. Use no-trade if none qualify.',
              score='median(closed_net/100)-max(0,-min(closed_net/100))-median(drawdown*50000/100)',
              candidate_pool_previously_selected_on_all_history=True,genuine_out_of_sample=False,
              source_sha256=hashlib.sha256(__file__.encode()).hexdigest() if False else hashlib.sha256(open(__file__,'rb').read()).hexdigest())
    freeze(out/'manifest.json',plan)
    old,_=load_history(root/'data/ethusd/perpetual_2020_2022/candles.parquet');recent,_=load_history(PARQUET)
    recent=recent[recent.timestamp<utc('2026-10-28')]
    bars=pd.concat([old,recent],ignore_index=True)
    profiles={v:load_profile(root,v) for v in versions}
    features={v:apply_filter(prepare_features(bars,r),RegimeFilter(**m['entry_filters'])) for v,(r,c,m,_) in profiles.items()}
    folds=[]
    for test_start in pd.date_range('2023-01-01','2026-07-01',freq='6MS',tz='UTC'):
        test_end=min(test_start+pd.DateOffset(months=6),utc('2026-10-28'));selection_end=test_start-pd.Timedelta(days=7)
        rows=[]
        for order,v in enumerate(versions):
            rule,cfg,_,_=profiles[v];inner=[]
            for offset in [3,2,1]:
                start=selection_end-pd.DateOffset(months=6*offset);end=selection_end-pd.DateOffset(months=6*(offset-1))
                b,f=subset(bars,features[v],start,end)
                metrics,trades,_=simulate(b,rule,cfg,signals=f)
                closed=0.
                if len(trades):
                    known=purged_mask(trades.entry_bar_open,pd.to_datetime(trades.exit_bar_open,utc=True)+BAR,test_start)
                    closed=float(trades.loc[known,'net_pnl'].sum())
                inner.append(dict(start=str(start),end=str(end),closed_net=closed,entries=metrics['entries'],drawdown=metrics['max_intrabar_drawdown'],margin_calls=metrics['margin_call_events']))
            rows.append(dict(version=v,complexity_order=order,inner=inner))
        chosen=robust_choice(rows)
        if chosen:
            rule,cfg,_,_=profiles[chosen];b,f=subset(bars,features[chosen],test_start,test_end)
            metrics,trades,_=simulate(b,rule,cfg,signals=f)
            outcome=dict(net=pnl(metrics),entries=metrics['entries'],drawdown=metrics['max_intrabar_drawdown'])
        else:outcome=dict(net=0.,entries=0,drawdown=0.)
        folds.append(dict(test_start=str(test_start),test_end=str(test_end),selection_end=str(selection_end),chosen=chosen,inner_selection=rows,outcome=outcome))
        write_json(out/'checkpoint.json',dict(folds=folds))
        print('RETROSPECTIVE WALK-FORWARD',test_start.date(),chosen,outcome,flush=True)
    origin=root/f"artifacts/optimization/{meta['experiment']}"
    curve=pd.read_parquet(origin/'verified_equity.parquet').set_index('timestamp').equity
    daily=curve.resample('1D').last().diff().fillna(0)
    correction=multiplicity_check(daily,policy['historical_search_slots_at_freeze'])
    neighbors=stability(origin)
    result=dict(plan=plan,folds=folds,multiplicity=correction,parameter_stability=neighbors,
                prospective_validation_complete=False,ready_for_funded_trading=False)
    write_json(out/'results.json',result)
    report=['# Generalization diagnostics','',
            'The historical candidate pool and all of these dates have already participated in research. This is a retrospective selection-procedure diagnostic, not a new holdout. The frozen strategy is unchanged.','',
            '| Outer period | Chosen only from preceding inner blocks | Test net | Entries | Drawdown |','| --- | --- | ---: | ---: | ---: |']
    for row in folds:report.append(f"| {row['test_start']} to {row['test_end']} | {row['chosen'] or 'No trade'} | ${row['outcome']['net']:,.2f} | {row['outcome']['entries']} | {row['outcome']['drawdown']:.2%} |")
    report+=['','Outer periods reset the account; their sums are not a continuous return. A seven-day chronological gap separates selection from evaluation. Inner scores exclude open and overlapping trade outcomes. No outer-period result changes the choice for that period.','',
             f"Retrospective one-sided centered seven-day-block bootstrap p: {correction['one_sided_centered_block_p']:.6g}. Bonferroni adjustment using {correction['logged_trial_slots']} logged slots: {correction['bonferroni_adjusted_p']:.6g}; adjusted upper Monte Carlo bound: {correction['bonferroni_adjusted_upper95']:.6g}.",'',correction['warning'],'',
             f"Immediate parameter neighbors within 10% of selected net: {neighbors['within_10pct_fraction']}. Worst neighbor/selected ratio: {neighbors['worst_ratio']}.",'',
             'These diagnostics cannot undo earlier inspection or prove a future edge. The locked future window remains pending, and historical profit alone cannot promote a new version.','']
    (root/'reports/generalization_diagnostics.md').write_text('\n'.join(report),encoding='utf-8')
    return result


if __name__=='__main__':run()

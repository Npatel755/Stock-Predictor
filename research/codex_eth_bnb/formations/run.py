"""Frozen formation/activity experiment runner, isolated from previous rounds."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from ..analytics import block_statistics,daily_returns,holm,metric_extras
from ..data_pipeline import HERE,freeze,load,resample,sha
from ..runner import safe,write
from ..strategies import build_features
from .activity import weekly_activity
from .execution import simulate
from .patterns import FAMILIES,detect,library,signalize,value

ROOT=Path(__file__).resolve().parent
SEED=20261104


def hashes():
    sources={str(p.relative_to(HERE)):sha(p) for p in sorted(ROOT.glob('*.py'))}
    sources.update({p:sha(HERE/p) for p in ['data_pipeline.py','analytics.py','strategies.py','runner.py']})
    return sources


def configuration(symbol,**changes):
    cfg=dict(initial_capital=50000.,risk_fraction=.0025,max_leverage=1.,fee_bps=5.,slippage_bps=2.,spread_bps=1.,
             participation_cap=.001,qty_step=.001 if symbol=='ETH' else .01,tick_size=.01,
             funding_bps_daily=0.,stop_atr=2.,reward_r=2.,trail_atr=0.,max_hold_bars=24)
    cfg.update(changes)
    return cfg


class Research:
    def __init__(self):
        self.split=json.loads((HERE/'split_manifest.json').read_text())
        self.code=hashes()
        self.commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        self.frames={};self.events={};self.sources={}
        for symbol in ['ETH','BNB']:
            self.sources[symbol]=load(symbol)
        manifest=dict(specifications=library(),primary_trials=72,baseline_trials=12,cumulative_holm_slots=208,
                      seed=SEED,bootstrap_draws=4999,research_plan_sha256=sha(ROOT/'research_plan.md'),
                      data_manifest_sha256=sha(HERE/'data_manifest.json'),funding_manifest_sha256=sha(HERE/'funding_manifest.json'),
                      split_manifest_sha256=sha(HERE/'split_manifest.json'),code_hashes=self.code,
                      original_execution_sha256=sha(HERE/'execution.py'),
                      test_status='11 formation/activity tests passed before outcomes; parent65tests unchanged',
                      final_access='CONTAMINATED_NOT_PERMITTED',paper='NO_NEW_PROSPECTIVE_RESULTS')
        freeze(ROOT/'manifest.json',manifest)

    def features(self,symbol,timeframe):
        key=(symbol,timeframe)
        if key not in self.frames:
            frame=resample(self.sources[symbol],timeframe,symbol)
            frame.attrs['timeframe']=timeframe
            self.frames[key]=build_features(frame)
        return self.frames[key]

    def detections(self,symbol,timeframe,sensitivity):
        key=(symbol,timeframe,sensitivity)
        if key not in self.events:
            events,pivots=detect(self.features(symbol,timeframe),sensitivity)
            folder=ROOT/'outputs/detections'/symbol/f'{timeframe}_{sensitivity}'
            folder.mkdir(parents=True,exist_ok=True)
            events.to_parquet(folder/'events.parquet',index=False)
            pivots.to_parquet(folder/'pivots.parquet',index=False)
            self.events[key]=events
            print(f'DETECT {symbol} {timeframe} {sensitivity}: {len(events)} geometric breakouts',flush=True)
        return self.events[key]

    def signals(self,symbol,spec):
        frame=self.features(symbol,spec['timeframe'])
        events=None if spec['baseline'] else self.detections(symbol,spec['timeframe'],spec['sensitivity'])
        return signalize(frame,spec,events)

    def trial(self,symbol,spec,start,end,phase,*,signal=None,config=None):
        start,end=pd.Timestamp(start),pd.Timestamp(end)
        if end>pd.Timestamp(self.split['nominal_final'][0]):
            raise ValueError('Contaminated final performance access prohibited')
        signal=self.signals(symbol,spec) if signal is None else signal
        duration=pd.Timedelta(spec['timeframe'])
        frame=signal[(signal.timestamp>=start)&(signal.timestamp+duration<=end)].reset_index(drop=True)
        config=configuration(symbol) if config is None else config
        identity=dict(symbol=symbol,specification=spec,start=str(start),end=str(end),phase=phase,config=config,
                      code_hashes=self.code,data_manifest_sha256=sha(HERE/'data_manifest.json'),seed=SEED)
        key=hashlib.sha256(json.dumps(identity,sort_keys=True,default=str).encode()).hexdigest()[:20]
        folder=ROOT/'outputs'/key
        if (folder/'result.json').exists():
            record=json.loads((folder/'result.json').read_text())
            result=dict(metrics=record['metrics'],equity=pd.read_parquet(folder/'equity.parquet'),trades=pd.read_parquet(folder/'trades.parquet'))
            activity=record['activity']
        else:
            result=simulate(frame,config)
            activity,weeks=weekly_activity(result)
            folder.mkdir(parents=True,exist_ok=True)
            result['equity'].to_parquet(folder/'equity.parquet',index=False)
            result['trades'].to_parquet(folder/'trades.parquet',index=False)
            weeks.to_csv(folder/'weekly_activity.csv',index=False)
            daily_returns(result['equity']).to_csv(folder/'daily_returns.csv',index_label='date')
            attribution=metric_extras(result)
            attribution.pop('daily',None)
            write(folder/'attribution.json',attribution)
            write(folder/'result.json',dict(identity=identity,metrics=result['metrics'],activity=activity))
            path=ROOT/'experiment_registry.csv'
            existed=path.exists()
            fields=['trial_key','symbol','strategy_id','phase','start','end','code_revision','seed','identity_json','metrics_json','activity_json']
            with path.open('a',encoding='utf-8',newline='') as file:
                writer=csv.DictWriter(file,fieldnames=fields)
                if not existed:
                    writer.writeheader()
                writer.writerow(dict(trial_key=key,symbol=symbol,strategy_id=spec['id'],phase=phase,start=str(start),end=str(end),
                                     code_revision=self.commit,seed=SEED,identity_json=json.dumps(safe(identity),sort_keys=True),
                                     metrics_json=json.dumps(safe(result['metrics']),sort_keys=True),activity_json=json.dumps(activity,sort_keys=True)))
        if abs(result['trades'].net_pnl.sum()-(result['equity'].equity.iloc[-1]-config['initial_capital']))>1e-6:
            raise ValueError('Formation trade ledger failed reconciliation')
        if len(result['trades']) and not spec['baseline']:
            groups=result['trades'].groupby('setup_id').entry_time.nunique()
            if (groups>1).any():
                raise ValueError('A formation was entered more than once')
        return dict(folder=str(folder.relative_to(ROOT)),result=result,activity=activity)

    def train(self):
        rows=[]
        for symbol in ['ETH','BNB']:
            for number,spec in enumerate(library()):
                signal=self.signals(symbol,spec)
                folds=[];daily=[];weeks=0.
                for fold in self.split['folds']:
                    outcome=self.trial(symbol,spec,fold['eval_start'],fold['eval_end'],'TRAIN_'+fold['id'],signal=signal)
                    result=outcome['result'];activity=outcome['activity']
                    daily.append(daily_returns(result['equity']))
                    weeks+=(result['equity'].timestamp.iloc[-1]-result['equity'].bar_open.iloc[0])/pd.Timedelta(days=7)
                    folds.append(dict(id=fold['id'],metrics=result['metrics'],activity=activity,output=outcome['folder']))
                profits=[f['metrics']['net_pnl'] for f in folds]
                positive=sum(v>0 for v in profits)
                worst_dd=max(f['metrics']['max_intrabar_drawdown'] for f in folds)
                performance=positive>=2 and worst_dd<=.15 and not any(f['metrics']['liquidation_events'] for f in folds)
                frequency=all(f['activity']['meets_frequency'] for f in folds)
                sharpes=[f['metrics']['sharpe'] if f['metrics']['sharpe'] is not None else -1e9 for f in folds]
                stat=block_statistics(pd.concat(daily),seed=SEED)
                row=dict(symbol=symbol,id=spec['id'],family=spec['family'],timeframe=spec['timeframe'],sensitivity=spec['sensitivity'],baseline=spec['baseline'],
                         train_frequency_qualified=frequency,train_performance_qualified=performance,
                         train_average_weekly_entries=sum(f['activity']['entries'] for f in folds)/weeks,
                         train_minimum_multi_trade_week_fraction=min(f['activity']['multi_trade_week_fraction'] for f in folds),
                         train_entries=sum(f['activity']['entries'] for f in folds),train_positive_folds=positive,
                         train_reset_fold_net=sum(profits),train_worst_intrabar_bound=worst_dd,
                         train_worst_sharpe=min(sharpes),train_median_sharpe=float(np.median(sharpes)),
                         train_block_p=stat['pvalue_centered_1s'],folds=folds)
                rows.append(row)
                print(f'TRAIN {symbol} {number+1}/42 {spec["id"]}: {row["train_average_weekly_entries"]:.2f}/week, profitable folds {positive}/3, frequency={frequency}',flush=True)
                write(ROOT/'outputs/status.json',dict(stage='training',symbol=symbol,completed=number+1,per_asset=42))
        previous=json.loads((HERE/'training_results.json').read_text())
        old=[r['train_block_p'] for r in previous]
        adjusted=holm(old+[r['train_block_p'] for r in rows],family_size=208)
        for row,p in zip(rows,adjusted[len(old):]):
            row['cumulative_holm_p']=p
        write(ROOT/'training_results.json',rows)
        pd.DataFrame([{k:v for k,v in row.items() if k!='folds'} for row in rows]).to_csv(ROOT/'strategy_comparison.csv',index=False)
        pd.DataFrame([dict(symbol=r['symbol'],strategy_id=r['id'],fold=f['id'],**{k:v for k,v in f['metrics'].items() if k!='cost_config'},
                           **f['activity']) for r in rows for f in r['folds']]).to_csv(ROOT/'walkforward_results.csv',index=False)
        return rows

    def select(self,training):
        def rank(row):
            return (row['train_performance_qualified'],row['train_worst_sharpe'],row['train_median_sharpe'])
        selected=[]
        for symbol in ['ETH','BNB']:
            all_rows=[r for r in training if r['symbol']==symbol and not r['baseline']]
            pool=[r for r in all_rows if r['train_frequency_qualified']]
            qualified=bool(pool)
            if qualified:
                pool=sorted(pool,key=rank,reverse=True)
            else:
                pool=sorted(all_rows,key=lambda r:(r['train_average_weekly_entries'],*rank(r)),reverse=True)
            families=set()
            for row in pool:
                if row['family'] not in families:
                    selected.append(dict(symbol=symbol,id=row['id'],family=row['family'],slot='frequency_performance' if qualified else 'frequency_failure_diagnostic'))
                    families.add(row['family'])
                if len(families)==2:
                    break
            hs=[r for r in all_rows if r['family']=='head_shoulders']
            eligible=[r for r in hs if r['train_frequency_qualified']]
            choice=max(eligible,key=rank) if eligible else max(hs,key=lambda r:(r['train_average_weekly_entries'],*rank(r)))
            if not any(s['symbol']==symbol and s['id']==choice['id'] for s in selected):
                selected.append(dict(symbol=symbol,id=choice['id'],family=choice['family'],slot='explicit_head_shoulders_hypothesis'))
        freeze(ROOT/'validation_shortlist.json',dict(selected=selected,training_sha256=sha(ROOT/'training_results.json'),code_hashes=self.code,no_replacements=True))
        return selected

    def validate(self,training,selected):
        specs={s['id']:s for s in library()};rows=[]
        start,end=self.split['validation_eval_start'],self.split['validation'][1]
        for choice in selected:
            symbol,spec=choice['symbol'],specs[choice['id']]
            base=self.trial(symbol,spec,start,end,'VALIDATION')
            adverse=self.trial(symbol,spec,start,end,'VALIDATION_adverse',config=configuration(symbol,fee_bps=7.,slippage_bps=8.,spread_bps=4.))
            source=next(r for r in training if r['symbol']==symbol and r['id']==spec['id'])
            m,a=base['result']['metrics'],adverse['result']['metrics']
            stats=block_statistics(daily_returns(base['result']['equity']),seed=SEED)
            gates=dict(training_frequency=source['train_frequency_qualified'],training_performance=source['train_performance_qualified'],
                       validation_frequency=base['activity']['meets_frequency'],positive_base=m['net_pnl']>0,positive_adverse=a['net_pnl']>0,
                       max_drawdown=max(m['max_intrabar_drawdown'],a['max_intrabar_drawdown'])<=.15,
                       no_liquidation=not(m['liquidation_events'] or a['liquidation_events']),
                       block_lower_positive=stats['mean_daily_lower']>0,cumulative_holm=source['cumulative_holm_p']<=.05)
            row=dict(**choice,timeframe=spec['timeframe'],sensitivity=spec['sensitivity'],phase='VALIDATION',accepted=all(gates.values()),gates=gates,
                     metrics=m,adverse_metrics=a,activity=base['activity'],adverse_activity=adverse['activity'],bootstrap=stats,output=base['folder'])
            rows.append(row)
            print(f'VALIDATION {symbol} {spec["id"]}: {base["activity"]["average_trades_per_week"]:.2f}/week, net ${m["net_pnl"]:.0f}, accepted={row["accepted"]}',flush=True)
        baselines=[]
        for symbol in ['ETH','BNB']:
            for spec in [s for s in library() if s['baseline']]:
                outcome=self.trial(symbol,spec,start,end,'VALIDATION_baseline')
                baselines.append(dict(symbol=symbol,id=spec['id'],metrics=outcome['result']['metrics'],activity=outcome['activity']))
        write(ROOT/'validation_results.json',dict(candidates=rows,baselines=baselines))
        return rows

    def robust(self,validated):
        specs={s['id']:s for s in library()};rows=[]
        start,end=self.split['validation_eval_start'],self.split['validation'][1]
        for symbol in ['ETH','BNB']:
            choices=[r for r in validated if r['symbol']==symbol]
            selected=choices[:1]+[r for r in choices if r['family']=='head_shoulders' and r!=choices[0]]
            for row in selected:
                spec=specs[row['id']];signal=self.signals(symbol,spec)
                scenarios=[('delay_extra_bar',dict(execution_delay_bars=2)),('lower_capacity',dict(participation_cap=.0002)),
                           ('crisis_costs',dict(fee_bps=10.,slippage_bps=20.,spread_bps=10.)),('risk_050',dict(risk_fraction=.005))]
                for label,changes in scenarios:
                    out=self.trial(symbol,spec,start,end,'STRESS_'+label,signal=signal,config=configuration(symbol,**changes))
                    rows.append(dict(symbol=symbol,id=spec['id'],scenario=label,metrics=out['result']['metrics'],activity=out['activity']))
                for label in ['long_only','short_only','lag24h','ATR_brackets','alternate_recognition']:
                    variant=signal.copy()
                    if label=='long_only':
                        variant.signal=variant.signal.clip(lower=0)
                    elif label=='short_only':
                        variant.signal=variant.signal.clip(upper=0)
                    elif label=='lag24h':
                        lag=int(pd.Timedelta(days=1)/pd.Timedelta(spec['timeframe']))
                        for column in ['signal','setup_id','planned_stop','planned_target']:
                            variant[column]=variant[column].shift(lag)
                        variant.signal=variant.signal.fillna(0).astype(int)
                    elif label=='ATR_brackets':
                        events=self.detections(symbol,spec['timeframe'],spec['sensitivity']).copy()
                        features=self.features(symbol,spec['timeframe'])
                        for index,event in events.iterrows():
                            i=int(event['index']);price=float(features.close.iloc[i]);atr=float(features.atr.iloc[i]);d=event.direction
                            events.loc[index,'planned_stop']=price-d*2*atr
                            events.loc[index,'planned_target']=price+d*4*atr
                        variant=signalize(features,spec,events)
                    else:
                        alternate='selective' if spec['sensitivity']=='responsive' else 'responsive'
                        variant=signalize(self.features(symbol,spec['timeframe']),dict(spec,sensitivity=alternate),
                                          self.detections(symbol,spec['timeframe'],alternate))
                    out=self.trial(symbol,spec,start,end,'STRESS_'+label,signal=variant)
                    rows.append(dict(symbol=symbol,id=spec['id'],scenario=label,metrics=out['result']['metrics'],activity=out['activity']))
                peer='BNB' if symbol=='ETH' else 'ETH'
                out=self.trial(peer,spec,start,end,'TRANSFER_from_'+symbol)
                rows.append(dict(symbol=peer,id=spec['id'],scenario='transfer_from_'+symbol,metrics=out['result']['metrics'],activity=out['activity']))
        write(ROOT/'robustness_results.json',rows)
        return rows

    def audit(self):
        registry=pd.read_csv(ROOT/'experiment_registry.csv')
        if registry.trial_key.duplicated().any():
            raise ValueError('Duplicate registry trial identities')
        activity=[];calendar=[]
        for row in registry.itertuples(index=False):
            folder=ROOT/'outputs'/row.trial_key
            outcome=json.loads((folder/'result.json').read_text())
            trades=pd.read_parquet(folder/'trades.parquet');curve=pd.read_parquet(folder/'equity.parquet')
            initial=outcome['metrics']['initial_capital']
            if abs(trades.net_pnl.sum()-(curve.equity.iloc[-1]-initial))>1e-6:
                raise ValueError('Independent ledger audit failed')
            if curve.timestamp.max()>pd.Timestamp(self.split['nominal_final'][0]):
                raise ValueError('Final period leaked into results')
            weeks=pd.read_csv(folder/'weekly_activity.csv')
            for record in weeks.to_dict('records'):
                activity.append(dict(symbol=row.symbol,id=row.strategy_id,phase=row.phase,**record))
            attribution=json.loads((folder/'attribution.json').read_text())
            for frequency in ['monthly','quarterly']:
                for record in attribution[frequency]:
                    calendar.append(dict(symbol=row.symbol,id=row.strategy_id,phase=row.phase,frequency=frequency,**record))
        pd.DataFrame(activity).to_csv(ROOT/'weekly_activity.csv',index=False)
        pd.DataFrame(calendar).to_csv(ROOT/'calendar_performance.csv',index=False)
        write(ROOT/'accounting_audit.json',dict(audited_replays=len(registry),ledger_failures=0,final_performance_access=False,
                                               registry_sha256=sha(ROOT/'experiment_registry.csv')))


def plots(research,validated):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    start=pd.Timestamp(research.split['validation_eval_start'])
    for symbol in ['ETH','BNB']:
        events=research.detections(symbol,'15m','responsive')
        selected=events[(events.family=='head_shoulders')&(pd.to_datetime(events.bar_open,utc=True)>=start)]
        if selected.empty:
            continue
        # Earliest validation example is chosen without regard to outcome.
        event=selected.sort_values('index').iloc[0]
        points=json.loads(event.points);frame=research.features(symbol,'15m')
        i=int(event['index']);begin=max(0,points[0]['index']-8);end=min(len(frame),i+13)
        display=frame.iloc[begin:end]
        fig,ax=plt.subplots(figsize=(11,5),constrained_layout=True)
        ax.plot(display.timestamp,display.close,color='#334155',linewidth=1.2,label='Actual15m close')
        ax.plot([frame.timestamp.iloc[p['index']] for p in points],[p['price'] for p in points],color='#2563eb',marker='o',linewidth=1.5,label='Confirmed pivot structure')
        for number,name in [(0,'Left shoulder'),(2,'Head'),(4,'Right shoulder')]:
            p=points[number]
            ax.annotate(name,(frame.timestamp.iloc[p['index']],p['price']),xytext=(0,12 if event.direction==-1 else -20),textcoords='offset points',ha='center',fontsize=8)
        for p in points:
            when=frame.timestamp.iloc[p['confirmed_at']]+pd.Timedelta('15m')
            ax.scatter([when],[p['price']],facecolors='none',edgecolors='#f59e0b',s=65,zorder=5)
        x1,x2=points[1]['index'],points[3]['index'];slope=(points[3]['price']-points[1]['price'])/(x2-x1)
        xs=[x1,i+5];ys=[points[1]['price']+slope*(x-x1) for x in xs]
        ax.plot([frame.timestamp.iloc[x] for x in xs],ys,'--',color='#0891b2',label='Neckline')
        available=pd.Timestamp(event.available_at)
        ax.axvline(available,color='#b91c1c',linewidth=1.,label='Signal known / earliest next open')
        ax.scatter([frame.timestamp.iloc[i]],[frame.close.iloc[i]],marker='v' if event.direction==-1 else '^',s=90,color='#b91c1c',zorder=6)
        ax.set(title=f'{symbol}: earliest VALIDATION H&S example (illustration, not a selected winner)',ylabel='USDT',xlabel='UTC; hollow orange markers = pivot confirmation availability')
        ax.legend(fontsize=8);ax.grid(alpha=.2)
        fig.savefig(ROOT/f'{symbol.lower()}_head_shoulders_example.png',dpi=150);plt.close(fig)
    if validated:
        fig,axes=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
        for row in validated:
            axes[0].scatter(row['activity']['average_trades_per_week'],row['metrics']['net_return']*100,
                            marker='o' if row['symbol']=='ETH' else '^',s=70)
            label=row['symbol']+' '+row['family']+' '+row['timeframe']
            axes[0].annotate(label,(row['activity']['average_trades_per_week'],row['metrics']['net_return']*100),xytext=(4,4),textcoords='offset points',fontsize=7)
            curve=pd.read_parquet(ROOT/row['output']/'equity.parquet')
            daily=curve.set_index('bar_open').equity.resample('D').last()
            axes[1].plot(daily.index,daily-50000,label=label,linewidth=1.)
        axes[0].axvline(2,linestyle='--',color='#666');axes[0].axhline(0,color='#666',linewidth=.7)
        axes[0].set(xlabel='Executed trades / week',ylabel='Net VALIDATION return (%)',title='Activity and after-cost performance')
        axes[1].set(ylabel='P&L per$50k',xlabel='UTC',title='Frozen shortlisted rules; VALIDATION only')
        axes[1].legend(fontsize=6);axes[1].tick_params(axis='x',rotation=25)
        for ax in axes:
            ax.grid(alpha=.2)
        fig.savefig(ROOT/'validation_comparison.png',dpi=150);plt.close(fig)


def report(training,validated,robust):
    accepted=[r for r in validated if r['accepted']]
    lines=['# Technical formations: activity and robustness','',
           '**No qualifying strategy found.**' if not accepted else '**Retrospective gate passers only; paper evidence still required.**','',
           '72primary hypotheses and12baselines on ETH/BNB.15m,30m,1h; two predeclared pivot-recognition settings. One successful entry per distinct formation. No stopped-out reentries are counted as new setups. Partial exit legs are excluded from activity counts.','',
           'TRAIN: three chronological internal forward folds(2022,2023,2024H1). VALIDATION: July7,2024–August28,2025. Both are already inspected development data. FINAL: contaminated, NOT evaluated. PAPER: no new prospective observations.','',
           '## Frozen VALIDATION shortlist','',
           '| Asset | Formation | Horizon | Trades/week | Median/week | Weeks with2+ | Trades | Net | Adverse net | Intrabar bound | Accepted |',
           '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    for r in validated:
        a,m=r['activity'],r['metrics']
        lines.append(f'| {r["symbol"]} | {r["family"]} | {r["timeframe"]} | {a["average_trades_per_week"]:.2f} | {a["median_trades_per_week"]:g} | {a["multi_trade_week_fraction"]:.1%} | {a["entries"]} | ${m["net_pnl"]:,.0f} | ${r["adverse_metrics"]["net_pnl"]:,.0f} | {m["max_intrabar_drawdown"]:.1%} | {r["accepted"]} |')
    lines+=['','Frequency target requires>=2entries/week on average AND>=50%of complete weeks with2+trades in EVERY training fold and validation. A high annual average alone is insufficient. Zero-trade weeks remain in weekly_activity.csv.','',
            '## Why candidates failed','']
    for r in validated:
        lines.append(f'- {r["symbol"]} `{r["id"]}`: '+', '.join(k for k,v in r['gates'].items() if not v)+'.')
    lines+=['','## Head-and-shoulders across ALL TRAIN configurations','',
            '| Asset | Horizon | Recognition | Average trades/week | Minimum multi-trade-week fraction | Positive folds | Sum of reset-fold net |',
            '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for r in [r for r in training if r['family']=='head_shoulders']:
        lines.append(f'| {r["symbol"]} | {r["timeframe"]} | {r["sensitivity"]} | {r["train_average_weekly_entries"]:.2f} | {r["train_minimum_multi_trade_week_fraction"]:.1%} | {r["train_positive_folds"]}/3 | ${r["train_reset_fold_net"]:,.0f} |')
    lines+=['','## Method and limits','',
            'H&S uses three confirmed extrema with the head beyond similar shoulders; intervening extrema define a sloped neckline. A close must cross that neckline AFTER right-shoulder confirmation. Inverse H&S mirrors the rule. Detectors never mark a trade at the historical pivot timestamp. Synthetic examples and prefix/future-poisoning tests check this delay.','',
            'The first validation example is charted regardless of subsequent profit: [ETH H&S example](eth_head_shoulders_example.png), [BNB H&S example](bnb_head_shoulders_example.png). Orange hollow markers show when pivots became known. Pattern examples illustrate the exact algorithm; they do not validate predictive power. [Validation comparison](validation_comparison.png).','',
            'Targets are projected pattern height; stops lie beyond the shoulder/opposite boundary with a0.25ATR buffer and minimum1ATR. Fixed ATR brackets are tested separately. Flags require an impulse and a bounded8-bar pullback, triangles need three confirmed contacts per side, and rectangles two per side. Numeric tolerances are research definitions, not universal visual-pattern labels.','',
            'Primary fractional risk0.25%, maximum1x entry notional, next-open fills,5bp/side fee,2bp/side slippage,1bp spread, observed signed funding. Adverse scenario7bp fees/8bp slippage/4bp spread. Previous-bar volume caps participation0.1%; partial exits retain risk. Fixed historical filters, mark-price funding/liquidation and order-book depth remain approximations. Larger frequency can amplify costs and need not improve profitability.','',
            'Cumulative Holm uses208slots(previous124+new84);4,999circular7-day blocks, seed20261104. It cannot erase the inherited ETH/BNB/Devin adaptive testing. These are retrospective diagnostics, not independent future success probabilities.','',
            '## Artifacts and reproduction','',
            '`python -m research.codex_eth_bnb.formations.run` from the dedicated worktree. Exact hypotheses, data/dependency hashes and code identities are frozen in manifest.json before performance evaluation. Checkpoints and full trades/equity/weekly activity/calendar attribution live under outputs/. Registry is append-only. strategy_comparison.csv contains every success/failure; walkforward_results.csv retains each fold. validation_shortlist.json freezes choices before validation; diagnostic_configurations.json records explicit rejection/acceptance.','',
            'The original frozen core and Devin’s checkout are not modified. No exchange keys, orders, integration, schedulers or automatic promotion are added.','',
            'Sources: [Fidelity pattern definitions](https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/learning-center/Idenitfying-Chart-Patterns.pdf), [CME continuation patterns](https://www.cmegroup.com/education/courses/technical-analysis/trend-and-continuation-patterns), [Lo/Mamaysky/Wang](https://www.nber.org/papers/w7613). Those sources motivate geometry; they do not demonstrate an intraday crypto edge.']
    (ROOT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    stress=['# Frozen formation robustness diagnostics','',
            '| Asset | Strategy | Scenario | Trades/week | Net | Intrabar bound |',
            '| --- | --- | --- | ---: | ---: | ---: |']
    for r in robust:
        stress.append(f'| {r["symbol"]} | {r["id"]} | {r["scenario"]} | {r["activity"]["average_trades_per_week"]:.2f} | ${r["metrics"]["net_pnl"]:,.0f} | {r["metrics"]["max_intrabar_drawdown"]:.1%} |')
    stress+=['','All runs are predeclared diagnostics; no failure is replaced. The alternate recognition changes pivot lag/tolerance together, so it does not isolate a single causal contribution. Cross-asset transfers reuse jointly inspected markets and are not independent holdouts.']
    (ROOT/'robustness_report.md').write_text('\n'.join(stress)+'\n',encoding='utf-8')
    pd.DataFrame([dict(symbol=r['symbol'],id=r['id'],accepted=r['accepted'],**r['activity'],net_pnl=r['metrics']['net_pnl'],
                       net_return=r['metrics']['net_return'],adverse_net=r['adverse_metrics']['net_pnl'],
                       failed_gates=','.join(k for k,v in r['gates'].items() if not v)) for r in validated]).to_csv(ROOT/'validation_scoreboard.csv',index=False)


def main():
    research=Research()
    training=research.train()
    selected=research.select(training)
    validated=research.validate(training,selected)
    robust=research.robust(validated)
    research.audit()
    plots(research,validated)
    report(training,validated,robust)
    specs={s['id']:s for s in library()}
    freeze(ROOT/'diagnostic_configurations.json',[dict(symbol=r['symbol'],specification=specs[r['id']],execution=configuration(r['symbol']),
            accepted=r['accepted'],gates=r['gates'],ready_for_live_trading=False,mode='paper_only' if r['accepted'] else 'rejected_diagnostic',
            code_hashes=research.code) for r in validated])
    write(ROOT/'outputs/status.json',dict(stage='complete',accepted=sum(r['accepted'] for r in validated),final='CONTAMINATED_NOT_EVALUATED'))
    print('Formation round complete; accepted='+str(sum(r['accepted'] for r in validated)),flush=True)


if __name__=='__main__':
    main()

"""Bounded price-action research; no final-period performance or live orders."""
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
from ..formations.activity import weekly_activity
from ..formations.execution import simulate
from ..runner import safe,write
from ..strategies import build_features
from .signals import detect,library,signalize

ROOT=Path(__file__).resolve().parent
SEED=20261105


def hashes():
    sources={str(p.relative_to(HERE)):sha(p) for p in sorted(ROOT.glob('*.py'))}
    sources.update({p:sha(HERE/p) for p in ['data_pipeline.py','analytics.py','strategies.py','runner.py','formations/execution.py','formations/activity.py']})
    return sources


def configuration(symbol,**changes):
    cfg=dict(initial_capital=50000.,risk_fraction=.0025,max_leverage=1.,fee_bps=5.,slippage_bps=2.,spread_bps=1.,
             participation_cap=.001,qty_step=.001 if symbol=='ETH' else .01,tick_size=.01,
             funding_bps_daily=0.,stop_atr=2.,reward_r=2.,max_hold_bars=24)
    cfg.update(changes)
    return cfg


class Research:
    def __init__(self):
        self.split=json.loads((HERE/'split_manifest.json').read_text())
        self.code=hashes();self.frames={};self.events={}
        self.commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        self.sources={s:load(s) for s in ['ETH','BNB']}
        freeze(ROOT/'manifest.json',dict(specifications=library(),primary_trials=64,baseline_trials=8,cumulative_holm_slots=280,
               seed=SEED,bootstrap_draws=4999,code_hashes=self.code,research_plan_sha256=sha(ROOT/'research_plan.md'),
               data_manifest_sha256=sha(HERE/'data_manifest.json'),funding_manifest_sha256=sha(HERE/'funding_manifest.json'),
               split_manifest_sha256=sha(HERE/'split_manifest.json'),tests_before_search=84,
               final_access='CONTAMINATED_NOT_PERMITTED',prospective_data='SEALED_NO_ACCESS'))

    def features(self,symbol,timeframe):
        key=(symbol,timeframe)
        if key not in self.frames:
            frame=resample(self.sources[symbol],timeframe,symbol);frame.attrs['timeframe']=timeframe
            self.frames[key]=build_features(frame)
        return self.frames[key]

    def detections(self,symbol,timeframe):
        key=(symbol,timeframe)
        if key not in self.events:
            events=detect(self.features(symbol,timeframe));self.events[key]=events
            folder=ROOT/'outputs/detections'/symbol/timeframe;folder.mkdir(parents=True,exist_ok=True)
            events.to_parquet(folder/'events.parquet',index=False)
            print(f'DETECT {symbol} {timeframe}: '+str(events.groupby('family').size().to_dict()),flush=True)
        return self.events[key]

    def signals(self,symbol,spec):
        return signalize(self.features(symbol,spec['timeframe']),spec,None if spec['baseline'] else self.detections(symbol,spec['timeframe']))

    def trial(self,symbol,spec,start,end,phase,*,signal=None,config=None):
        start,end=pd.Timestamp(start),pd.Timestamp(end)
        if end>pd.Timestamp(self.split['nominal_final'][0]):
            raise ValueError('Contaminated final performance access prohibited')
        signal=self.signals(symbol,spec) if signal is None else signal
        span=pd.Timedelta(spec['timeframe'])
        frame=signal[(signal.timestamp>=start)&(signal.timestamp+span<=end)].reset_index(drop=True)
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
            result=simulate(frame,config);activity,weeks=weekly_activity(result)
            folder.mkdir(parents=True,exist_ok=True)
            result['trades'].to_parquet(folder/'trades.parquet',index=False)
            result['equity'].to_parquet(folder/'equity.parquet',index=False)
            daily_returns(result['equity']).to_csv(folder/'daily_returns.csv',index_label='date')
            weeks.to_csv(folder/'weekly_activity.csv',index=False)
            extras=metric_extras(result);extras.pop('daily',None)
            write(folder/'attribution.json',extras)
            write(folder/'result.json',dict(identity=identity,metrics=result['metrics'],activity=activity))
            path=ROOT/'experiment_registry.csv';exists=path.exists()
            with path.open('a',encoding='utf-8',newline='') as file:
                writer=csv.DictWriter(file,fieldnames=['trial_key','symbol','strategy_id','phase','code_revision','seed','identity_json','metrics_json','activity_json'])
                if not exists:
                    writer.writeheader()
                writer.writerow(dict(trial_key=key,symbol=symbol,strategy_id=spec['id'],phase=phase,code_revision=self.commit,seed=SEED,
                       identity_json=json.dumps(safe(identity),sort_keys=True),metrics_json=json.dumps(safe(result['metrics']),sort_keys=True),activity_json=json.dumps(activity,sort_keys=True)))
        trades=result['trades'];curve=result['equity']
        if abs(trades.net_pnl.sum()-(curve.equity.iloc[-1]-config['initial_capital']))>1e-6:
            raise ValueError('Trade cash reconciliation failed')
        if not spec['baseline'] and len(trades) and (trades.groupby('setup_id').entry_time.nunique()>1).any():
            raise ValueError('Setup entered more than once')
        return dict(folder=str(folder.relative_to(ROOT)),result=result,activity=activity)

    def train(self):
        rows=[];specs=library()
        for symbol in ['ETH','BNB']:
            for number,spec in enumerate(specs):
                signal=self.signals(symbol,spec);folds=[];daily=[];weeks=0.
                for fold in self.split['folds']:
                    out=self.trial(symbol,spec,fold['eval_start'],fold['eval_end'],'TRAIN_'+fold['id'],signal=signal)
                    result=out['result'];curve=result['equity']
                    daily.append(daily_returns(curve));weeks+=(curve.timestamp.iloc[-1]-curve.bar_open.iloc[0])/pd.Timedelta(days=7)
                    folds.append(dict(id=fold['id'],metrics=result['metrics'],activity=out['activity'],output=out['folder']))
                positive=sum(f['metrics']['net_pnl']>0 for f in folds)
                dd=max(f['metrics']['max_intrabar_drawdown'] for f in folds)
                performance=positive>=2 and dd<=.15 and not any(f['metrics']['liquidation_events'] for f in folds)
                frequency=all(f['activity']['meets_frequency'] for f in folds)
                sharpes=[f['metrics']['sharpe'] if f['metrics']['sharpe'] is not None else -1e9 for f in folds]
                stat=block_statistics(pd.concat(daily),seed=SEED)
                row=dict(symbol=symbol,id=spec['id'],family=spec['family'],timeframe=spec['timeframe'],reward_r=spec['reward_r'],baseline=spec['baseline'],
                         train_frequency_qualified=frequency,train_performance_qualified=performance,
                         train_average_weekly_entries=sum(f['activity']['entries'] for f in folds)/weeks,
                         train_minimum_multi_trade_week_fraction=min(f['activity']['multi_trade_week_fraction'] for f in folds),
                         train_entries=sum(f['activity']['entries'] for f in folds),train_positive_folds=positive,
                         train_reset_fold_net=sum(f['metrics']['net_pnl'] for f in folds),train_worst_intrabar_bound=dd,
                         train_worst_sharpe=min(sharpes),train_median_sharpe=float(np.median(sharpes)),train_block_p=stat['pvalue_centered_1s'],folds=folds)
                rows.append(row)
                print(f'TRAIN {symbol} {number+1}/{len(specs)} {spec["id"]}: {row["train_average_weekly_entries"]:.2f}/week, profitable folds {positive}/3, frequency={frequency}',flush=True)
                write(ROOT/'outputs/status.json',dict(stage='training',symbol=symbol,completed=number+1,per_asset=len(specs)))
        previous=json.loads((HERE/'training_results.json').read_text())+json.loads((HERE/'formations/training_results.json').read_text())
        old=[r['train_block_p'] for r in previous]
        adjusted=holm(old+[r['train_block_p'] for r in rows],family_size=280)
        for row,p in zip(rows,adjusted[len(old):]):
            row['cumulative_holm_p']=p
        write(ROOT/'training_results.json',rows)
        pd.DataFrame([{k:v for k,v in r.items() if k!='folds'} for r in rows]).to_csv(ROOT/'strategy_comparison.csv',index=False)
        pd.DataFrame([dict(symbol=r['symbol'],strategy_id=r['id'],fold=f['id'],**{k:v for k,v in f['metrics'].items() if k!='cost_config'},**f['activity'])
                      for r in rows for f in r['folds']]).to_csv(ROOT/'walkforward_results.csv',index=False)
        return rows

    def select(self,training):
        def rank(r):
            return (r['train_performance_qualified'],r['train_worst_sharpe'],r['train_median_sharpe'])
        selected=[]
        for symbol in ['ETH','BNB']:
            candidates=[r for r in training if r['symbol']==symbol and not r['baseline']]
            pool=[r for r in candidates if r['train_frequency_qualified']]
            qualified=bool(pool)
            pool=sorted(pool,key=rank,reverse=True) if qualified else sorted(candidates,key=lambda r:(r['train_average_weekly_entries'],*rank(r)),reverse=True)
            families=set()
            for r in pool:
                if r['family'] not in families:
                    selected.append(dict(symbol=symbol,id=r['id'],family=r['family'],slot='frequency_rank' if qualified else 'failed_frequency_diagnostic'))
                    families.add(r['family'])
                if len(families)==3:
                    break
            slow=[r for r in candidates if r['train_performance_qualified'] and not r['train_frequency_qualified'] and r['family'] not in families]
            if slow:
                r=max(slow,key=rank)
                selected.append(dict(symbol=symbol,id=r['id'],family=r['family'],slot='infrequent_performance_diagnostic'))
        freeze(ROOT/'validation_shortlist.json',dict(selected=selected,training_sha256=sha(ROOT/'training_results.json'),no_replacements=True,code_hashes=self.code))
        return selected

    def validate(self,training,selected):
        specs={s['id']:s for s in library()};rows=[]
        start,end=self.split['validation_eval_start'],self.split['validation'][1]
        for choice in selected:
            symbol,spec=choice['symbol'],specs[choice['id']]
            base=self.trial(symbol,spec,start,end,'VALIDATION')
            adverse=self.trial(symbol,spec,start,end,'VALIDATION_adverse',config=configuration(symbol,fee_bps=7.,slippage_bps=8.,spread_bps=4.))
            origin=next(r for r in training if r['symbol']==symbol and r['id']==spec['id'])
            m,a=base['result']['metrics'],adverse['result']['metrics']
            stats=block_statistics(daily_returns(base['result']['equity']),seed=SEED)
            gates=dict(training_frequency=origin['train_frequency_qualified'],training_performance=origin['train_performance_qualified'],
                       validation_frequency=base['activity']['meets_frequency'],positive_base=m['net_pnl']>0,positive_adverse=a['net_pnl']>0,
                       drawdown=max(m['max_intrabar_drawdown'],a['max_intrabar_drawdown'])<=.15,
                       no_liquidation=not(m['liquidation_events'] or a['liquidation_events']),
                       block_lower_positive=stats['mean_daily_lower']>0,cumulative_holm=origin['cumulative_holm_p']<=.05)
            row=dict(**choice,timeframe=spec['timeframe'],reward_r=spec['reward_r'],phase='VALIDATION',accepted=all(gates.values()),gates=gates,
                     metrics=m,adverse_metrics=a,activity=base['activity'],adverse_activity=adverse['activity'],bootstrap=stats,output=base['folder'])
            rows.append(row)
            print(f'VALIDATION {symbol} {spec["id"]}: {base["activity"]["average_trades_per_week"]:.2f}/week, net ${m["net_pnl"]:.0f}, adverse ${a["net_pnl"]:.0f}, accepted={row["accepted"]}',flush=True)
        baselines=[]
        for symbol in ['ETH','BNB']:
            for spec in [s for s in library() if s['baseline']]:
                out=self.trial(symbol,spec,start,end,'VALIDATION_baseline')
                baselines.append(dict(symbol=symbol,id=spec['id'],metrics=out['result']['metrics'],activity=out['activity']))
        write(ROOT/'validation_results.json',dict(candidates=rows,baselines=baselines))
        return rows

    def robustness(self,validated):
        specs={s['id']:s for s in library()};rows=[]
        start,end=self.split['validation_eval_start'],self.split['validation'][1]
        for symbol in ['ETH','BNB']:
            row=next(r for r in validated if r['symbol']==symbol);spec=specs[row['id']];signal=self.signals(symbol,spec)
            for label,changes in [('delay',dict(execution_delay_bars=2)),('capacity',dict(participation_cap=.0002)),
                                  ('crisis',dict(fee_bps=10.,slippage_bps=20.,spread_bps=10.)),('risk_100',dict(risk_fraction=.01))]:
                out=self.trial(symbol,spec,start,end,'STRESS_'+label,signal=signal,config=configuration(symbol,**changes))
                rows.append(dict(symbol=symbol,id=spec['id'],scenario=label,metrics=out['result']['metrics'],activity=out['activity']))
            for label in ['long_only','short_only','lag48h','opposite_target']:
                variant=signal.copy()
                if label=='long_only':
                    variant.signal=variant.signal.clip(lower=0)
                elif label=='short_only':
                    variant.signal=variant.signal.clip(upper=0)
                elif label=='lag48h':
                    lag=int(pd.Timedelta('48h')/pd.Timedelta(spec['timeframe']))
                    for column in ['signal','setup_id','planned_stop','planned_target']:
                        variant[column]=variant[column].shift(lag)
                    variant.signal=variant.signal.fillna(0).astype(int)
                else:
                    variant=signalize(self.features(symbol,spec['timeframe']),dict(spec,reward_r=3. if spec['reward_r']==1.5 else 1.5),self.detections(symbol,spec['timeframe']))
                out=self.trial(symbol,spec,start,end,'STRESS_'+label,signal=variant)
                rows.append(dict(symbol=symbol,id=spec['id'],scenario=label,metrics=out['result']['metrics'],activity=out['activity']))
            peer='BNB' if symbol=='ETH' else 'ETH'
            out=self.trial(peer,spec,start,end,'TRANSFER_from_'+symbol)
            rows.append(dict(symbol=peer,id=spec['id'],scenario='transfer_from_'+symbol,metrics=out['result']['metrics'],activity=out['activity']))
        write(ROOT/'robustness_results.json',rows)
        return rows

    def audit(self):
        registry=pd.read_csv(ROOT/'experiment_registry.csv');weeks=[];calendar=[];costs=[]
        if registry.trial_key.duplicated().any():
            raise ValueError('Duplicate registry replay identities')
        for trial in registry.itertuples(index=False):
            folder=ROOT/'outputs'/trial.trial_key;record=json.loads((folder/'result.json').read_text());m=record['metrics']
            trades=pd.read_parquet(folder/'trades.parquet');curve=pd.read_parquet(folder/'equity.parquet')
            if abs(trades.net_pnl.sum()-(curve.equity.iloc[-1]-m['initial_capital']))>1e-6:
                raise ValueError('Independent ledger audit failed')
            if curve.timestamp.max()>pd.Timestamp(self.split['nominal_final'][0]):
                raise ValueError('Final period entered returns')
            if (curve.intrabar_worst_equity>curve.equity+1e-6).any():
                raise ValueError('Adverse equity bound exceeds close')
            for r in pd.read_csv(folder/'weekly_activity.csv').to_dict('records'):
                weeks.append(dict(symbol=trial.symbol,id=trial.strategy_id,phase=trial.phase,**r))
            attribution=json.loads((folder/'attribution.json').read_text())
            for frequency in ['monthly','quarterly']:
                for r in attribution[frequency]:
                    calendar.append(dict(symbol=trial.symbol,id=trial.strategy_id,phase=trial.phase,frequency=frequency,**r))
            costs.append(dict(symbol=trial.symbol,id=trial.strategy_id,phase=trial.phase,net_pnl=m['net_pnl'],
                              fees=m['total_fees'],signed_funding=m['total_funding'],
                              pnl_before_explicit_fees_funding=m['net_pnl']+m['total_fees']+m['total_funding']))
        pd.DataFrame(weeks).to_csv(ROOT/'weekly_activity.csv',index=False)
        pd.DataFrame(calendar).to_csv(ROOT/'calendar_performance.csv',index=False)
        pd.DataFrame(costs).to_csv(ROOT/'cost_attribution.csv',index=False)
        write(ROOT/'accounting_audit.json',dict(audited_replays=len(registry),ledger_failures=0,final_performance_access=False,
                 registry_sha256=sha(ROOT/'experiment_registry.csv'),code_unchanged=hashes()==self.code))


def report(training,validated,robust):
    accepted=sum(r['accepted'] for r in validated)
    lines=['# Intraday price-action research round','',
           '**No qualifying strategy found.**' if not accepted else '**Retrospective gate passers only; future paper evidence required.**','',
           '64 primary variants plus8 baselines, ETH/BNB,15m/1h,1.5R/3R targets. All choices frozen before validation. One successful entry per setup; no repeated stopped-out reentries.','',
           'TRAIN: three chronological internal forward folds(2022,2023,2024H1). VALIDATION:July7,2024–August28,2025. All are already inspected historical development data. FINAL:contaminated,not evaluated. PAPER:no new prospective observations.','',
           '| Asset | Rule | TF | Target | Trades/week | Weeks with2+ | Net per$50k | Adverse net | Intrabar bound | Accepted |',
           '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    for r in validated:
        a,m=r['activity'],r['metrics']
        lines.append(f'| {r["symbol"]} | {r["family"]} | {r["timeframe"]} | {r["reward_r"]:g}R | {a["average_trades_per_week"]:.2f} | {a["multi_trade_week_fraction"]:.1%} | ${m["net_pnl"]:,.0f} | ${r["adverse_metrics"]["net_pnl"]:,.0f} | {m["max_intrabar_drawdown"]:.1%} | {r["accepted"]} |')
    lines+=['','## Rejection/acceptance gates','']
    for r in validated:
        failed=', '.join(k for k,v in r['gates'].items() if not v)
        lines.append(f'- {r["symbol"]} `{r["id"]}`: {failed or "all retrospective gates passed"}. Slot:{r["slot"]}.')
    lines+=['','## Mechanisms and limits','',
            'Sweep/reclaim and failed-breakout rules test reversal after an observed failed level break. Break/retest tests continuation after a separately confirmed pullback. Opening-range rules use07:00–08:00UTC levels only after complete; entries end before16:00. The three-candle imbalance rule waits for a LATER retracement, shock reversal waits for an opposite close, and VWAP pullbacks require an established trend. See research_plan.md for exact thresholds.','',
            'The terms sweep/liquidity/fair-value gap are OHLCV proxies; no actual stop order, liquidation tape, institutional flow or fundamental fair value is observed. UTC session definitions are fixed conventions for24/7 crypto. Some mechanisms overlap prior research, so they are not eight independent sources of evidence.','',
            'Capital$50k; fractional stop risk0.25%,maximum1x entry notional. Fees5bp/side,slippage2bp/side,spread1bp; actual signed funding. Adverse7/8/4bp and crisis10/20/10bp. Partial capacity-limited exits retain risk; synthetic terminal closes are flagged. Fixed precision, unavailable market depth and last-price proxies are limitations. Cost attribution before explicit fees/funding STILL includes spread/slippage in fills.','',
            'Weekly target:average>=2 executed entries/week and>=50%full UTC weeks with2+entries in every fold and validation. Zero weeks count; partial exits do not. Infrequent training survivors are diagnostic slots only, never a relaxed gate.','',
            'Holm correction includes280 cumulative slots;4,999circular7-day bootstrap draws,seed20261105. The unknown larger inherited adaptive search remains extra exposure. No adjusted statistic can convert this reused history into independent validation.','',
            '## Outputs and reproduction','',
            '`python -m research.codex_eth_bnb.price_action.run` from the dedicated worktree. Read manifest.json, validation_shortlist.json, strategy_comparison.csv, walkforward_results.csv, validation_scoreboard.csv, robustness_report.md and accounting_audit.json. Full trade/equity/daily/weekly/calendar/regime ledgers are under outputs/. Registry is append-only. Frozen diagnostics remain unapproved for live trading. No production integration, services, schedules or orders are added.','',
            'Sources motivate hypotheses, not crypto profits: [CME support/resistance](https://www.cmegroup.com/education/courses/technical-analysis/support-and-resistance), [Fidelity support/resistance](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/support-and-resistance), [NY Fed intraday pattern research](https://libertystreeteconomics.newyorkfed.org/2021/05/the-overnight-drift-in-us-equity-returns/) and [later disappearance](https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/).']
    (ROOT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    stress=['# Predeclared price-action robustness','',
            '| Asset | Frozen rule | Diagnostic | Trades/week | Net | Intrabar bound |',
            '| --- | --- | --- | ---: | ---: | ---: |']
    for r in robust:
        stress.append(f'| {r["symbol"]} | {r["id"]} | {r["scenario"]} | {r["activity"]["average_trades_per_week"]:.2f} | ${r["metrics"]["net_pnl"]:,.0f} | {r["metrics"]["max_intrabar_drawdown"]:.1%} |')
    stress+=['','Diagnostics never replace failed validation candidates. Alternative target was already in the frozen grid. Transfer uses jointly inspected assets and is not independent evidence.']
    (ROOT/'robustness_report.md').write_text('\n'.join(stress)+'\n',encoding='utf-8')
    pd.DataFrame([dict(symbol=r['symbol'],id=r['id'],accepted=r['accepted'],**r['activity'],net_pnl=r['metrics']['net_pnl'],net_return=r['metrics']['net_return'],
                 adverse_net=r['adverse_metrics']['net_pnl'],failed_gates=','.join(k for k,v in r['gates'].items() if not v)) for r in validated]).to_csv(ROOT/'validation_scoreboard.csv',index=False)


def plot(validated):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True,constrained_layout=True)
    for r in validated:
        curve=pd.read_parquet(ROOT/r['output']/'equity.parquet')
        daily=curve.set_index('bar_open').equity.resample('D').last()
        label=f'{r["symbol"]} {r["family"]} {r["timeframe"]} {r["reward_r"]:g}R'
        axes[0].plot(daily.index,daily-50000,label=label,linewidth=1.)
        axes[1].plot(daily.index,(daily/daily.cummax().clip(lower=50000)-1)*100,linewidth=1.)
    axes[0].set(title='Price-action rules: frozen TRAIN shortlist, retrospective VALIDATION',ylabel='P&L per$50k(USD)')
    axes[1].set(ylabel='Close drawdown(%)',xlabel='UTC date')
    axes[0].legend(fontsize=7,ncol=2)
    for ax in axes:
        ax.grid(alpha=.2)
    fig.savefig(ROOT/'validation_performance.png',dpi=150);plt.close(fig)


def main():
    research=Research();training=research.train();selected=research.select(training)
    validated=research.validate(training,selected);robust=research.robustness(validated)
    research.audit();report(training,validated,robust);plot(validated)
    specs={s['id']:s for s in library()}
    freeze(ROOT/'diagnostic_configurations.json',[dict(symbol=r['symbol'],specification=specs[r['id']],execution=configuration(r['symbol']),
                 accepted=r['accepted'],gates=r['gates'],ready_for_live_trading=False,code_hashes=research.code) for r in validated])
    write(ROOT/'outputs/status.json',dict(stage='complete',accepted=sum(r['accepted'] for r in validated),final='CONTAMINATED_NOT_EVALUATED'))
    print('Price-action round complete; accepted='+str(sum(r['accepted'] for r in validated)),flush=True)


if __name__=='__main__':
    main()

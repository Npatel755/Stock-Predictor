"""Predeclared causal entry-quality research; physical TRAIN inputs only.

No validation/test resolver. Existing cash/price-bound simulator stays frozen.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import duckdb
import numpy as np
import pandas as pd
import stack_continuous_train as base
from stack_continuous_core import continuous,reference

ROOT=base.ROOT;RUN=ROOT/'runs/stack_entry_quality_v1'
PARENT=ROOT/'runs/stack_continuous_exposure_fixed_v1'


def feature_frame(bars):
    """Each row available only after its source bar finishes."""
    b=bars.sort_values('timestamp_utc').reset_index(drop=True).copy()
    close=b.close.astype(float);span=b.high-b.low
    b['pressure']=(2*close-b.high-b.low)/span.where(span>0)
    roll_id=b.contract.ne(b.contract.shift()).cumsum()
    for length in (8,16,32):
        travel=close.diff().abs().rolling(length,min_periods=length).sum()
        same=roll_id.eq(roll_id.shift(length))
        b[f'er{length}']=((close-close.shift(length))/travel.where(travel>0)).where(same)
    local=pd.to_datetime(b.timestamp_utc,utc=True).dt.tz_convert('America/New_York')
    slot=local.dt.hour*60+local.dt.minute
    expected=b.volume.groupby(slot).transform(lambda x:x.shift(1).rolling(20,min_periods=10).median())
    b['relative_volume']=b.volume/expected.where(expected>0)
    return b


def eligibility(df,c):
    mask=np.ones(len(df),dtype=np.bool_)
    for field,threshold in ((f"directional_er{c['er_length']}",c['er_min']),('directional_pressure',c['pressure_min']),
                            ('relative_volume',c['volume_min']),('risk_cost_ratio',c['cost_min'])):
        if threshold is not None:
            value=df[field].to_numpy(float);mask&=np.isfinite(value)&(value>=threshold)
    if c['peer_align']:
        v=df.directional_peer_er16.to_numpy(float);mask&=np.isfinite(v)&(v>=0)
    return mask


def freeze():
    active_policy=ROOT/'research/FUNDED_RESEARCH_POLICY.json'
    if active_policy.exists() and json.loads(active_policy.read_text()).get('strict_global_drawdown_required') is False:
        raise RuntimeError('Unrun strict-DD draft superseded by explicit user account-floor/DLL policy; adapt the account simulator before launching.')
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'protocol.json').exists():raise RuntimeError('Frozen protocol exists')
    parent=json.loads((PARENT/'protocol.json').read_text());cells=[]
    efficiencies=[(0,None)]+[(n,t) for n in (8,16,32) for t in (.10,.25)]
    for length,er in efficiencies:
        for pressure in (None,0.,.3):
            for volume in (None,1.,1.5):
                for cost in (None,4.,8.):
                    for peer in (False,True):
                        c=dict(er_length=length,er_min=er,pressure_min=pressure,volume_min=volume,cost_min=cost,peer_align=peer)
                        name=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()[:16]
                        c['name']='eq_'+name;cells.append(c)
    control=next(c for c in cells if c['er_min'] is None and c['pressure_min'] is None and c['volume_min'] is None and c['cost_min'] is None and not c['peer_align'])
    controls=dict(control);controls['name']='UNFILTERED_INCUMBENT'
    alternatives=[c for c in cells if c!=control];assert len(alternatives)==377
    sources={}
    for path in (Path(__file__),Path(__file__).with_name('stack_continuous_core.py'),Path(__file__).with_name('stack_continuous_train.py'),ROOT/'tests/test_stack_entry_quality.py'):
        sources[str(path.relative_to(ROOT))]=base.sha(path)
    code=RUN/'code';code.mkdir(exist_ok=True)
    for rel in sources:shutil.copyfile(ROOT/rel,code/Path(rel).name)
    base.write(RUN/'protocol.json',dict(run_id='stack_entry_quality_v1',frozen_at=str(pd.Timestamp.now(tz='UTC')),
        hypotheses=['Directional efficiency may reduce whipsaw entries.','Directional closes and same-clock relative volume may discriminate sustained participation.','Entry stop-distance relative to costs may reject uneconomic price noise; contemporaneous completed peer trend may confirm direction.'],
        source_hashes=sources,candidates=alternatives,control=controls,training_sources=parent['training_sources'],
        parent_bounds_sha256=base.sha(PARENT/'training_trade_bounds.parquet'),parent_protocol_sha256=base.sha(PARENT/'protocol.json'),
        fixed_allocation=base.INC,
        causal_features='Only fully completed15/30/60minute bars, exact availability timestamp==entry. ER8/16/32 uses backward price changes and resets across contract rolls. Pressure=side*(2close-high-low)/(high-low). Relativevolume=currentcompletedbarvolume / median20prior sameNYclock slots,min10. PeerER16 uses same completed timeframe/clock. Costratio=entry planned stop risk/(1+multiplier). No trade-outcome features.',
        entries='Apply frozen eligibility before routing/sizing: omitted signals never occupy positions. Same source entries/exits, same quote-bound QA, hard integer caps, fees/slippage and dollar accounting. No exit or sizing changes.',
        periods='Exact parent continuous account;8day boundary suppression and2021entryembargo. Prefix2010July-2020 selects one; only frozen choice+incumbent replay2010July-2023, no cash/high-water reset. All TRAIN is reused research.',
        qualify=parent['qualification'],
        ranking='First require all prefix gates AND base/cost2 net>=1.05*unfiltered incumbent prefix. Among these choose highest cost2net, then basenet, smaller conservativeOHLCbound, name. Freeze one before laterTRAIN/full replay. No alternative after failure.',
        adoption='Both prefix and full must qualify and improve base AND cost2net>=5%vs identical unfiltered incumbent. No live/paper deployment or funded certification.',
        stop='Complete all377 new filters. If none passes frozen prefix gates, publish failure and no candidate later evaluation. Do not relax annual/cost/activity thresholds or rank on V/T.',
        limits='Filters share existing signals and are strongly correlated, not377 independent discoveries. Source entry library has historical selection lineage. Conservative wholebar bounds are not exact ticks. E-mini proxies before2019, unknown capacity/impact. Cost2=extra1dollar+1point percontract,notexactdoubleeverylimitfill. No withdrawals/payoutsimulation, no fresh independentholdout evidence.',
        validation_accessed=False,test_accessed=False,paper_outcomes_accessed=False,automatic_holdout_stage=False))
    print('FROZEN377 entry filters +1unfiltered control',flush=True)


def prepare(p):
    target=RUN/'training_entry_features.parquet'
    if target.exists():
        meta=json.loads((RUN/'feature_identity.json').read_text());assert base.sha(target)==meta['sha256'];return pd.read_parquet(target)
    assert base.sha(PARENT/'training_trade_bounds.parquet')==p['parent_bounds_sha256']
    d=pd.read_parquet(PARENT/'training_trade_bounds.parquet').copy();assert d.path_valid.all()
    frames={};reads=[]
    for product,mini in (('MNQ','NQ'),('MES','ES')):
        for minutes in (15,30,60):
            queries=[];args=[]
            for symbol,lo,hi in ((mini,'2010-01-01','2019-05-06'),(product,'2019-05-06','2024-01-01')):
                info=p['training_sources'][symbol];assert info['role']=='train' and base.sha(info['path'])==info['sha256']
                queries.append("SELECT timestamp_utc::TIMESTAMPTZ AS ts,open,high,low,close,volume,contract FROM read_parquet(?) WHERE timestamp_utc::TIMESTAMPTZ>=?::TIMESTAMPTZ AND timestamp_utc::TIMESTAMPTZ<?::TIMESTAMPTZ")
                args.extend([info['path'],lo,hi])
            query="WITH p AS ("+' UNION ALL '.join(queries)+f''') SELECT time_bucket(INTERVAL '{minutes} minutes',ts) AS timestamp_utc,
            arg_min(open,ts) AS open,max(high) AS high,min(low) AS low,arg_max(close,ts) AS close,sum(volume) AS volume,
            arg_min(contract,ts) AS contract,count(DISTINCT contract) AS contracts FROM p GROUP BY1 ORDER BY1'''.replace('GROUP BY1 ORDER BY1','GROUP BY 1 ORDER BY 1')
            con=duckdb.connect();con.execute("SET memory_limit='768MB'");con.execute('SET threads=2');bars=con.execute(query,args).fetch_df();con.close()
            assert pd.to_datetime(bars.timestamp_utc,utc=True).lt(pd.Timestamp('2024-01-01T00:00Z')).all()
            assert not bars.timestamp_utc.duplicated().any()
            f=feature_frame(bars);f['available']=pd.to_datetime(f.timestamp_utc,utc=True)+pd.Timedelta(minutes=minutes)
            for col in ('er8','er16','er32','pressure','relative_volume'):f.loc[f.contracts!=1,col]=np.nan
            frames[(product,minutes)]=f.set_index('available')
            reads.append(dict(product=product,minutes=minutes,role='train',bars=len(f),latest=str(f.available.max())))
            print('TRAIN completed features',product,minutes,len(f),flush=True)
    length=((d.tin-d.dec).dt.total_seconds()/60).astype(int);assert length.isin([15,30,60]).all()
    for field in ('directional_er8','directional_er16','directional_er32','directional_pressure','relative_volume','directional_peer_er16'):d[field]=np.nan
    for product in ('MNQ','MES'):
        peer='MES' if product=='MNQ' else 'MNQ'
        for minutes in (15,30,60):
            ids=d.index[(d.inst==product)&(length==minutes)]
            if not len(ids):continue
            at=pd.DatetimeIndex(pd.to_datetime(d.loc[ids,'tin'],utc=True));own=frames[(product,minutes)].reindex(at);other=frames[(peer,minutes)].reindex(at)
            side=d.loc[ids,'side'].to_numpy(float)
            for n in (8,16,32):d.loc[ids,f'directional_er{n}']=side*own[f'er{n}'].to_numpy(float)
            d.loc[ids,'directional_pressure']=side*own.pressure.to_numpy(float);d.loc[ids,'relative_volume']=own.relative_volume.to_numpy(float)
            d.loc[ids,'directional_peer_er16']=side*other.er16.to_numpy(float)
    d['risk_cost_ratio']=d.entry_risk/(1.+d.multiplier)
    d.to_parquet(target,index=False)
    base.write(RUN/'feature_identity.json',dict(sha256=base.sha(target),rows=len(d),source_TRAIN_loads=reads,
        features_available_before_or_at_entry=True,missing_features={k:int(d[k].isna().sum()) for k in d.columns if k.startswith(('directional_','relative_volume'))},
        no_feature_fits_or_fullsample_normalization=True,validation_accessed=False,test_accessed=False))
    return d


def score(d,c,end,check=False):
    mask=eligibility(d,c);metrics={};raw={}
    allocation=base.INC
    for cost,label in ((1,'base'),(2,'cost2')):
        args=list(base.inputs(d,cost,end));args[4]=args[4]*mask
        tail=(allocation['cap'],allocation['risk_cap'],allocation['fraction'],allocation['target'],allocation['marked'],float(cost))
        a=continuous(*args,*tail);np.testing.assert_allclose(a[0][0],a[1].sum(),atol=1e-7,rtol=0)
        if check:
            b=reference(*args,*tail)
            for x,y in zip(a,b):np.testing.assert_allclose(x,y,atol=1e-7,rtol=0)
        metrics[label]=base.describe(a,end==base.CUT);raw[label]=a
    return metrics,raw


def improve(m,control):return bool(all(m[k]['qualified'] and m[k]['net_pnl']>=1.05*control[k]['net_pnl'] for k in ('base','cost2')))


def main():
    if (RUN/'results.json').exists():print('Frozen completed study preserved');return
    p=json.loads((RUN/'protocol.json').read_text())
    for rel,h in p['source_hashes'].items():assert base.sha(ROOT/rel)==h
    d=prepare(p);control,_=score(d,p['control'],base.CUT,True);rows=[];metrics={}
    for i,c in enumerate(p['candidates']):
        path=RUN/'checkpoints'/f"{c['name']}.json";path.parent.mkdir(exist_ok=True)
        if path.exists():m=json.loads(path.read_text())
        else:m,_=score(d,c,base.CUT);base.write(path,m)
        metrics[c['name']]=m
        rows.append(dict(**c,qualified=m['base']['qualified'] and m['cost2']['qualified'],improved=improve(m,control),net=m['base']['net_pnl'],cost2_net=m['cost2']['net_pnl'],
                         bound=m['base']['conservative_OHLC_drawdown_bound'],cost2_bound=m['cost2']['conservative_OHLC_drawdown_bound'],trades=m['base']['trades'],inactive=m['cost2']['maximum_inactive_days']))
        if (i+1)%75==0:print('PREFIX entry filters',i+1,'/377',flush=True)
    frame=pd.DataFrame(rows).sort_values(['improved','cost2_net','net','bound','name'],ascending=[False,False,False,True,True]);frame.to_csv(RUN/'all_prefix_entry_filters.csv',index=False)
    qualified=frame[frame.improved];lookup={c['name']:c for c in p['candidates']};choice=lookup[qualified.iloc[0]['name']] if len(qualified) else None
    seal=dict(configuration=choice,prefix_metrics=metrics[choice['name']] if choice else None,prefix_improvers=len(qualified),
              protocol_sha256=base.sha(RUN/'protocol.json'),ranking_sha256=base.sha(RUN/'all_prefix_entry_filters.csv'),later_used_for_choice=False,all_TRAIN_reused=True)
    frozen=RUN/'frozen_prefix_choice.json'
    if frozen.exists():assert json.loads(frozen.read_text())==seal
    else:base.write(frozen,seal)
    print('FROZEN',json.dumps(choice),'improvers',len(qualified),flush=True)
    selected={};refs=0
    original_run=base.RUN;base.RUN=RUN
    try:
        for c in [p['control']]+([choice] if choice else []):
            selected[c['name']]={}
            for end,label in ((base.CUT,'prefix'),(base.END,'continuous_full')):
                m,a=score(d,c,end,True);refs+=2;selected[c['name']][label]=m
                base.save_paths(d,c,m,a,label)
                if end==base.CUT:prefix=a
                else:
                    before=base.inputs(d,1,end)[0]<base.CUT
                    for kind in ('base','cost2'):
                        np.testing.assert_array_equal(a[kind][3][before],prefix[kind][3][before]);np.testing.assert_allclose(a[kind][4][before],prefix[kind][4][before],atol=1e-7,rtol=0)
    finally:base.RUN=original_run
    accepted=bool(choice and all(improve(selected[choice['name']][phase],selected[p['control']['name']][phase]) for phase in ('prefix','continuous_full')))
    result=dict(status='TRAIN_ONLY_ENTRY_QUALITY_CHALLENGER' if accepted else 'NO_QUALIFIED_IMPROVEMENT',accepted=accepted,candidates=377,
        prefix_qualifiers=int(frame.qualified.sum()),prefix_improvers=len(qualified),configuration=choice,selected=selected,
        units='Historical rawfill dollars using micro economics; continuous account, no cash/highwater reset.',
        validation_accessed=False,test_accessed=False,paper_outcomes_accessed=False,deployment_changed=False,independent_confirmation=False,
        protocol_sha256=base.sha(RUN/'protocol.json'),frozen_choice_sha256=base.sha(frozen))
    verification=dict(passed=True,selected_independent_reference_cases=refs,cash_trade_annual_conservation=True,full_prefix_states_match=True,
        frozen_source_input_hashes_verified=True,validation_accessed=False,test_accessed=False)
    base.write(RUN/'results.json',result);base.write(RUN/'verification.json',verification)
    if accepted:
        archive=ROOT/'strategy_versions/gemini_triple_stack/v1.4.0-entry-quality-train-challenger';archive.mkdir(parents=True,exist_ok=True)
        base.write(archive/'frozen_candidate.json',dict(result=result,deployed=False));shutil.copyfile(RUN/'protocol.json',archive/'protocol.json');shutil.copytree(RUN/'code',archive/'code',dirs_exist_ok=True)
    publish(result,verification,frame)
    print('FINAL',json.dumps(dict(accepted=accepted,choice=choice,prefix_qualifiers=result['prefix_qualifiers'],prefix_improvers=len(qualified),selected=selected)),flush=True)


def publish(r,v,frame):
    stem='STACK_ENTRY_QUALITY_TRAIN';base.write(ROOT/'reports'/f'{stem}.json',r);base.write(ROOT/'reports'/f'{stem}_verification.json',v)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
    for name in r['selected']:
        for kind in ('base','cost2'):
            d=pd.read_csv(RUN/'selected/continuous_full'/name/(kind+'_trades_and_bounds.csv'))
            if not len(d):continue
            x=pd.to_datetime(d.available_exit,utc=True,format='mixed');label=('Incumbent' if name=='UNFILTERED_INCUMBENT' else 'Frozen filter')+' '+kind
            axes[0].plot(x,d.cash_pnl,label=label);axes[1].plot(x,d.favorable_equity_peak_bound-d.adverse_equity_bound,label=label)
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8);ax.axvline(pd.Timestamp('2021-01-01T00:00Z'),color='gray',ls=':')
    axes[0].set_ylabel('Continuous historical-dollar trading P&L');axes[1].set_ylabel('Conservative OHLC DD bound');axes[1].axhline(2000,color='red',ls='--')
    fig.tight_layout();fig.savefig(ROOT/'reports'/f'{stem}.png',dpi=150);plt.close(fig)
    rows=[]
    for name,phases in r['selected'].items():
        for phase,costs in phases.items():
            for cost,m in costs.items():rows.append(dict(Policy=name,Period=phase,Costs=cost,Net=m['net_pnl'],Cash_DD=m['cash_drawdown'],OHLC_DD_bound=m['conservative_OHLC_drawdown_bound'],Trades=m['trades'],Inactive_days=m['maximum_inactive_days'],Qualified=m['qualified']))
    title='TRAIN entry-quality research: '+('qualifying challenger' if r['accepted'] else 'no qualifying improvement')
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{font:16px/1.6 system-ui;max-width:1400px;margin:32px auto;padding:0 24px;background:#111820;color:#e9edf2}a{color:#94d7ff}table{border-collapse:collapse;font-size:14px}td,th{padding:9px;border-bottom:1px solid #456}.scroll{overflow:auto}pre{white-space:pre-wrap}img{width:100%}.note{padding:18px;background:#382d22}</style><h1>'+title+'</h1><p>377predeclared entry filters, unchanged allocation/exits/fills. Only completed bars at exact entry availability supply directional efficiency, close pressure, same-clock relative volume, cost-risk ratio and peer confirmation. TRAIN-only selection through2020; one frozen candidate may continue through2023 without account reset. No V/T/paper outcomes or deployment.</p><p class="note">Repeated historical TRAIN research, not independent unseen evidence. Pre2019E-mini source quotes with micro economics do not establish historical micro liquidity. Conservative wholebar OHLC bounds are not exact tick order/broker compliance. Cost2 is extra1dollar+1point percontract. No payouts modeled. All attempted filters, including failures, are retained.</p><div class="scroll">'+pd.DataFrame(rows).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div><img src="'+stem+'.png" alt="Continuous TRAIN equity and conservative drawdown"><h2>Frozen choice</h2><pre>'+html.escape(json.dumps(r['configuration'],indent=2))+'</pre><h2>Prefix top20</h2><div class="scroll">'+frame.head(20).to_html(index=False,border=0,float_format=lambda x:f'{x:,.3f}')+'</div><p><a href="../runs/stack_entry_quality_v1/protocol.json">Frozen protocol</a> · <a href="../runs/stack_entry_quality_v1/all_prefix_entry_filters.csv">All377 filters</a> · <a href="../runs/stack_entry_quality_v1/feature_identity.json">Feature provenance</a> · <a href="'+stem+'.json">Full results</a></p></html>'
    (ROOT/'reports'/f'{stem}.html').write_text(page,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if args.freeze:freeze()
    elif args.run:main()
    else:parser.error('Choose --freeze or --run')

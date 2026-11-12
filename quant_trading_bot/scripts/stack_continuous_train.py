"""Frozen historical-dollar TRAIN-only continuous-account research.

Only TRAIN parquet paths are resolved. No protected split/outcome loader exists.
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
from stack_continuous_core import continuous,reference

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/stack_continuous_v1'
BASEFILE=ROOT/'runs/gemini_stack_continuation_v1/causal/raw_base.parquet'
CATALOG=ROOT/'data/catalog_vm.json' if (ROOT/'data/catalog_vm.json').exists() else ROOT/'data/catalog.json'
DAY=86400000000000
START=int(pd.Timestamp('2010-07-01T00:00Z').value)
CUT=int(pd.Timestamp('2021-01-01T00:00Z').value)
END=int(pd.Timestamp('2024-01-01T00:00Z').value)
INC=dict(name='REPRICED_INCUMBENT',cap=1.,risk_cap=225.,fraction=1.,target=1800.,marked=False)
FIELDS=['net_pnl','cash_drawdown','conservative_OHLC_drawdown_bound','trades','profit_factor','maximum_inactive_days','unknown_path_exposures','drawdown_breach']


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,default=str)+'\n',encoding='utf-8')


def freeze():
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'protocol.json').exists():raise RuntimeError('Protocol immutable')
    cat=json.loads(CATALOG.read_text())['instruments'];sources={}
    for symbol in ('ES','NQ','MES','MNQ'):
        meta=cat[symbol]['splits']['train'];assert meta['split_role']=='train' and meta['raw_contract_prices'] and not meta['synthetic']
        p=Path(meta['path']);sources[symbol]=dict(path=str(p),sha256=sha(p),role='train',dataset_version=meta['dataset_version'])
    cells=[]
    for target in (1600.,1750.,1850.,1900.):
        for cap in (1.,2.,3.):
            for risk_cap in (100.,150.,200.,250.,300.,350.):
                for fraction in (.25,.5,.75,1.):
                    for marked in (False,True):
                        cells.append(dict(name=f'T{target:g}_C{cap:g}_R{risk_cap:g}_F{fraction:g}_M{int(marked)}',target=target,cap=cap,risk_cap=risk_cap,fraction=fraction,marked=marked))
    code=RUN/'code';code.mkdir(exist_ok=True);hashes={}
    for p in (Path(__file__),Path(__file__).with_name('stack_continuous_core.py'),ROOT/'tests/test_stack_continuous_core.py'):
        shutil.copyfile(p,code/p.name);hashes[str(p.relative_to(ROOT))]=sha(p)
    write(RUN/'protocol.json',dict(run_id='stack_continuous_v1',frozen_at=str(pd.Timestamp.now(tz='UTC')),candidates=cells,incumbent=INC,
        source_hashes=hashes,training_sources=sources,base_book_sha256=sha(BASEFILE),catalog_sha256=sha(CATALOG),
        hypothesis='Smaller entry-risk fractions and explicit completed-mark risk peaks may avoid the absorbing risk state while preserving a strict2000drawdown ceiling. Test actual historical dollars and a single continuous account, not normalized/reset blocks.',
        data='Existing three-sleeve causal base signals only; no overnight/new entry filters. TRAIN2010July-2023. E-mini bars proxy pre2019; micro contract economics, not historical micro liquidity.',
        boundaries='Entry suppression8days after2010Jul1, before2024Jan1, and either side of internal2021Jan1. Prefix2010-2020 chooses one policy; full2010-2023 replays only frozen choice+incumbent, with no2021state reset. All TRAIN repeatedly used in historical research, not fresh holdouts.',
        prices='Use saved actual entry/exit fill prices and micro multiplier minus1dollarRT fee. Saved fills include0.5point/side slippage. Cost2 subtracts extra1dollar+1point*multiplier; entry fee and entry-risk reserves also stressed. Original normalized reports preserved; profits not directly comparable.',
        mark_bounds='Join source1minuteOHLC from entry through exit-bar confirmation. Full first/last bar can overstate excursions after the true exit; pessimistic favorable-before-adverse order bounds intrabar drawdown. Not exact tick chronology or verified broker trailing-equity rules. Entry quantity fixed before consulting current excursions.',
        QA='Accepted paths require a quote at entry, one contract within the held interval, no duplicate timestamps, validOHLC/nonnegativevolume, and no internal quote gap>5minutes. Bad path cannot become zeroMAE or be silently deleted. Reject policy with attempted bad-data exposure.',
        risk='Risk budgets target1600..1900, never userdrawdownlimit2000. Remaining budget calculated against either completed cash peak or conservative completed mark peak; never reset peaks/cash byyear. Integer qty<=cap*source base size, global6. All gap loss fills fully debited. Reject actual/conservative bound touch2000.',
        qualification='Both base/cost2: positive net, cash and conservativeOHLCdrawdown bound strictly<2000, no bad-path/breach, max inactivity<=180days. Prefix>=300trades,>=15/year,>=8positiveyears of11, positive net in each2010-13/2014-17/2018-20block. Full>=15/year and>=10positiveyears of14;2021-23incrementalnet>0and>=2/3positiveyears.',
        rank='EarlierTRAIN-only: greatest minimum cost2 annualized profit across three chronological blocks; then cost2totalnet, basetotalnet, lower OHLCbound, name. Freeze one before full laterTRAIN replay. No alternative chosen from laterTRAIN.',
        improvement='Chosen policy must qualify on prefix and full, and exceed repriced incumbent base AND cost2 net by>=5% on both prefix and continuous fullTRAIN. Failed baseline paths are stopped/censored at risk rejection; disclose unequal exposure, not a buy-and-hold comparison.',
        uncertainty='576 nominal allocations, unknown historical effective search count. Neighborhood/path counts and descriptive pairedblock uncertainty only; no independent unseen claims or fake significance. No live or payout certification.',
        validation_accessed=False,test_accessed=False,paper_outcomes_accessed=False,automatic_holdout_stage=False))
    print('FROZEN',len(cells),'new allocations',flush=True)


def verify(p):
    for rel,h in p['source_hashes'].items():assert sha(ROOT/rel)==h
    assert sha(BASEFILE)==p['base_book_sha256'] and sha(CATALOG)==p['catalog_sha256']


def prepare(p):
    target=RUN/'training_trade_bounds.parquet'
    if target.exists():
        meta=json.loads((RUN/'training_bounds_identity.json').read_text());assert sha(target)==meta['sha256'];return pd.read_parquet(target)
    df=pd.read_parquet(BASEFILE).copy();df['id']=np.arange(len(df));df['available_exit']=df.tout+(df.tin-df.dec)
    assert df.tin.ge(pd.Timestamp('2010-01-01T00:00Z')).all() and df.available_exit.lt(pd.Timestamp('2024-01-01T00:00Z')).all()
    assert df.tout.ge(df.tin).all() and df.available_exit.gt(df.tin).all()
    bound_rows=[];loads=[]
    for product,mini in (('MES','ES'),('MNQ','NQ')):
        trade=df[df.inst==product][['id','tin','available_exit']].copy()
        trade['tin']=trade.tin.dt.tz_convert('UTC');trade['available_exit']=trade.available_exit.dt.tz_convert('UTC')
        con=duckdb.connect();con.execute("SET memory_limit='2GB'");con.execute('SET threads=2');con.register('trades',trade)
        streams=[];params=[]
        for symbol,lo,hi in ((mini,'2010-01-01','2019-05-06'),(product,'2019-05-06','2024-01-01')):
            source=p['training_sources'][symbol];assert source['role']=='train' and sha(source['path'])==source['sha256']
            streams.append("SELECT timestamp_utc::TIMESTAMPTZ AS ts,open,high,low,close,volume,contract FROM read_parquet(?) WHERE timestamp_utc::TIMESTAMPTZ>=?::TIMESTAMPTZ AND timestamp_utc::TIMESTAMPTZ<?::TIMESTAMPTZ")
            params.extend([source['path'],lo,hi]);loads.append(dict(symbol=symbol,role='train',start=lo,end_exclusive=hi,sha256=source['sha256']))
        query='''WITH p AS ('''+ ' UNION ALL '.join(streams)+'''), joined AS (
          SELECT t.id,p.*,lag(ts) OVER(PARTITION BY t.id ORDER BY ts) AS previous_ts
          FROM trades t JOIN p ON p.ts>=t.tin AND p.ts<t.available_exit)
          SELECT id,min(ts) AS first_ts,max(ts) AS last_ts,count(*) AS bars,count(DISTINCT ts) AS unique_bars,
          count(DISTINCT contract) AS contracts,min(low) AS low,max(high) AS high,
          arg_min(open,ts) AS entry_open,max(date_diff('second',previous_ts,ts)) AS maximum_gap_seconds,
          sum(CASE WHEN high<greatest(open,close,low) OR low>least(open,close,high) OR low<=0 OR volume<0 OR NOT isfinite(high) OR NOT isfinite(low) THEN1 ELSE0 END) AS bad_ohlc
          FROM joined GROUP BY id'''.replace('THEN1 ELSE0','THEN 1 ELSE 0')
        rows=con.execute(query,params).fetch_df();con.close();bound_rows.append(rows)
        print('TRAIN OHLC bounds',product,len(rows),'trades',flush=True)
    marks=pd.concat(bound_rows,ignore_index=True);assert not marks.id.duplicated().any()
    df=df.merge(marks,on='id',how='left',validate='one_to_one')
    df['multiplier']=df.inst.map({'MES':5.,'MNQ':2.})
    # Exact saved fills; original fee was1per roundtrip, adverse fills already
    # contain0.5point on each side. No reference-price normalization remains.
    df['per']=df.side*(df.exit-df.entry)*df.multiplier-1.
    df['entry_risk']=df.stop_pct*df.entry*df.multiplier+1.+.75*df.multiplier
    worst=np.where(df.side>0,df.low,df.high);best=np.where(df.side>0,df.high,df.low)
    df['adverse']=(df.side*(worst-df.entry)-.5)*df.multiplier-1.
    df['favorable']=np.maximum(0.,df.side*(best-df.entry)*df.multiplier-.5)
    entry_match=pd.to_datetime(df.first_ts,utc=True)==df.tin.dt.tz_convert('UTC')
    fill_error=(df.entry-(df.entry_open+df.side*.5)).abs()
    df['path_valid']=entry_match & (df.bars==df.unique_bars) & (df.contracts==1) & (df.bad_ohlc==0) & (df.maximum_gap_seconds.fillna(0)<=300) & (fill_error<=.250001)
    mask=(df.tin.dt.as_unit('ns').astype('int64')>=START+8*DAY)&(df.tin.dt.as_unit('ns').astype('int64')<END-8*DAY)
    clock=df.tin.dt.as_unit('ns').astype('int64');mask&=(clock<CUT-8*DAY)|(clock>=CUT+8*DAY)
    df=df.loc[mask].sort_values(['tin','prio'],kind='stable').reset_index(drop=True)
    assert np.isfinite(df[['per','entry_risk','n_contracts']]).all().all() and df.entry_risk.gt(0).all()
    df.to_parquet(target,index=False)
    meta=dict(sha256=sha(target),rows=len(df),valid_paths=int(df.path_valid.sum()),invalid_paths=int((~df.path_valid).sum()),
        invalid_ids=df.loc[~df.path_valid,'id'].astype(int).tolist(),source_training_loads=loads,
        no_holdout_prices=True,partial_first_last_bars_conservative=True,exact_intrabar_order_unknown=True,
        prices='Raw historical contract fills with micro economics; no normalized price reference.',
        boundary_suppression='8days; continuous2021accountstate preserved')
    write(RUN/'training_bounds_identity.json',meta);print('TRAIN QA',json.dumps({k:meta[k] for k in ('rows','valid_paths','invalid_paths')}),flush=True)
    return df


def inputs(df,cost,end):
    mult=df.multiplier.to_numpy(float);extra=(cost-1)*(1.+mult)
    return (df.tin.dt.as_unit('ns').astype('int64').to_numpy(),df.available_exit.dt.as_unit('ns').astype('int64').to_numpy(),
        df.per.to_numpy(float)-extra,df.entry_risk.to_numpy(float)+extra,df.n_contracts.to_numpy(float),mult,
        df.adverse.to_numpy(float)-extra,df.favorable.to_numpy(float)-.5*(cost-1),df.path_valid.to_numpy(),
        (df.available_exit.dt.year-2010).to_numpy(np.int64),START,end)


def describe(a,prefix):
    m={k:float(v) for k,v in zip(FIELDS,a[0])};m['annual_net']=a[1].tolist();m['annual_trades']=a[2].astype(int).tolist()
    groups=[(0,4),(4,8),(8,11)];m['chronological_block_net']=[float(a[1][lo:hi].sum()) for lo,hi in groups]
    m['worst_cost_block_annualized']=min(v/n for v,n in zip(m['chronological_block_net'],(3.5,4.,3.)))
    n=11 if prefix else 14
    m['qualified']=bool(m['net_pnl']>0 and m['cash_drawdown']<2000 and m['conservative_OHLC_drawdown_bound']<2000 and
        m['unknown_path_exposures']==m['drawdown_breach']==0 and m['maximum_inactive_days']<=180 and
        m['trades']>=300 and np.min(a[2][:n])>=15 and np.sum(a[1][:n]>0)>=(8 if prefix else 10) and
        all(v>0 for v in m['chronological_block_net']) and (prefix or (a[1][11:].sum()>0 and np.sum(a[1][11:]>0)>=2)))
    return m


def evaluate(df,c,end,check=False):
    metrics={};raw={}
    for cost,label in ((1,'base'),(2,'cost2')):
        args=inputs(df,cost,end);tail=(c['cap'],c['risk_cap'],c['fraction'],c['target'],c['marked'],float(cost))
        a=continuous(*args,*tail);np.testing.assert_allclose(a[0][0],a[1].sum(),atol=1e-7,rtol=0)
        if check:
            b=reference(*args,*tail)
            for x,y in zip(a,b):np.testing.assert_allclose(x,y,atol=1e-7,rtol=0)
        metrics[label]=describe(a,end==CUT);raw[label]=a
    return metrics,raw


def save_paths(df,c,m,raw,label):
    folder=RUN/'selected'/label/c['name'];folder.mkdir(parents=True,exist_ok=True)
    for cost,kind in ((1,'base'),(2,'cost2')):
        a=raw[kind];live=a[3]>0;d=df.loc[live,['id','sleeve','inst','tin','available_exit','entry','exit','path_valid']].copy()
        d['quantity']=a[3][live];d['per_net']=inputs(df,cost,END)[2][live];d['net_pnl']=d.per_net*d.quantity
        for j,col in enumerate(('cash_pnl','adverse_equity_bound','favorable_equity_peak_bound','cash_drawdown_to_date')):d[col]=a[4][live,j]
        np.testing.assert_allclose(d.net_pnl.sum(),m[kind]['net_pnl'],atol=1e-7,rtol=0)
        d.to_csv(folder/(kind+'_trades_and_bounds.csv'),index=False)


def main():
    if (RUN/'results.json').exists():print('Completed run preserved');return
    p=json.loads((RUN/'protocol.json').read_text());verify(p);df=prepare(p)
    rows=[];all_metrics={}
    for i,c in enumerate([INC]+p['candidates']):
        path=RUN/'checkpoints'/f"{c['name']}.json";path.parent.mkdir(exist_ok=True)
        if path.exists():m=json.loads(path.read_text())
        else:m,_=evaluate(df,c,CUT);write(path,m)
        all_metrics[c['name']]=m
        rows.append(dict(**c,qualified=m['base']['qualified'] and m['cost2']['qualified'],net=m['base']['net_pnl'],cost2_net=m['cost2']['net_pnl'],
            bound=m['base']['conservative_OHLC_drawdown_bound'],cost2_bound=m['cost2']['conservative_OHLC_drawdown_bound'],
            worst_block=m['cost2']['worst_cost_block_annualized'],max_inactive_days=m['cost2']['maximum_inactive_days'],bad_path_exposures=m['base']['unknown_path_exposures']))
        if (i+1)%100==0:print('PREFIX TRAIN',i+1,'/577',flush=True)
    frame=pd.DataFrame(rows).sort_values(['qualified','worst_block','cost2_net','net','bound','name'],ascending=[False,False,False,False,True,True])
    frame.to_csv(RUN/'all_prefix_training_allocations.csv',index=False)
    viable=frame[frame.qualified & (frame.name!=INC['name'])];lookup={c['name']:c for c in p['candidates']}
    choice=lookup[viable.iloc[0]['name']] if len(viable) else None
    seal=dict(configuration=choice,metrics=all_metrics[choice['name']] if choice else None,qualified_allocations=len(viable),
        protocol_sha256=sha(RUN/'protocol.json'),ranking_sha256=sha(RUN/'all_prefix_training_allocations.csv'),later_used_for_choice=False,previous_later_TRAIN_reuse=True)
    freeze_path=RUN/'frozen_prefix_choice.json'
    if freeze_path.exists():assert json.loads(freeze_path.read_text())==seal
    else:write(freeze_path,seal)
    print('FROZEN CHOICE',json.dumps(choice),'prefix qualifiers',len(viable),flush=True)
    selected={};references=0
    for c in [INC]+([choice] if choice else []):
        selected[c['name']]={}
        for end,label in ((CUT,'prefix'),(END,'continuous_full')):
            m,a=evaluate(df,c,end,True);references+=2;selected[c['name']][label]=m;save_paths(df,c,m,a,label)
            # Prefix trades/state must be identical in the continuous replay.
            if end==CUT:prefix_raw=a
            else:
                for kind in ('base','cost2'):
                    prior=prefix_raw[kind][3]>0
                    np.testing.assert_array_equal(a[kind][3][prior],prefix_raw[kind][3][prior])
                    np.testing.assert_allclose(a[kind][4][prior],prefix_raw[kind][4][prior],atol=1e-7,rtol=0)
    accepted=bool(choice and all(selected[choice['name']][phase][cost]['qualified'] and
        selected[choice['name']][phase][cost]['net_pnl']>=1.05*selected[INC['name']][phase][cost]['net_pnl']
        for phase in ('prefix','continuous_full') for cost in ('base','cost2')))
    result=dict(status='TRAIN_ONLY_CONTINUOUS_RESEARCH_CHALLENGER' if accepted else 'NO_QUALIFIED_IMPROVEMENT',accepted=accepted,
        candidates=len(p['candidates']),prefix_qualifiers=len(viable),configuration=choice,selected=selected,
        units='Historical raw fill dollars using micro multipliers; not old normalized dollars and not withdrawals.',
        exact_intrabar_order_known=False,conservative_fullbar_excursions=True,independent_confirmation=False,
        prior_TRAIN_reused=True,validation_accessed=False,test_accessed=False,forward_paper_accessed=False,deployment_changed=False,
        protocol_sha256=sha(RUN/'protocol.json'),frozen_choice_sha256=sha(freeze_path))
    verification=dict(passed=True,selected_reference_cases=references,cash_trade_annual_conservation=True,prefix_state_matches_continuous=True,
        frozen_source_input_hashes_match=True,losses_not_clipped=True,peak_never_reset=True,validation_accessed=False,test_accessed=False,
        verified_broker_funded_compliance=False)
    write(RUN/'results.json',result);write(RUN/'verification.json',verification)
    if accepted:
        folder=ROOT/'strategy_versions/gemini_triple_stack/v1.3.0-continuous-train-challenger';folder.mkdir(parents=True,exist_ok=True)
        write(folder/'frozen_candidate.json',dict(result=result,promoted=False));shutil.copyfile(RUN/'protocol.json',folder/'protocol.json');shutil.copytree(RUN/'code',folder/'code',dirs_exist_ok=True)
    publish(result,verification,frame)
    print('FINAL',json.dumps(dict(accepted=accepted,choice=choice,prefix_qualifiers=len(viable),results=selected)),flush=True)


def publish(r,v,frame):
    stem='STACK_CONTINUOUS_TRAIN';write(ROOT/'reports'/f'{stem}.json',r);write(ROOT/'reports'/f'{stem}_verification.json',v)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
    if r['configuration']:
        for kind in ('base','cost2'):
            d=pd.read_csv(RUN/'selected/continuous_full'/r['configuration']['name']/(kind+'_trades_and_bounds.csv'))
            x=pd.to_datetime(d.available_exit,utc=True,format='mixed');axes[0].plot(x,d.cash_pnl,label=kind)
            axes[1].plot(x,d.favorable_equity_peak_bound-d.adverse_equity_bound,label=kind)
    axes[0].axvline(pd.Timestamp('2021-01-01T00:00Z'),color='grey',ls=':');axes[0].set(ylabel='Continuous historical-dollar net P&L')
    axes[1].axhline(2000,color='red',ls='--');axes[1].set(ylabel='Conservative OHLC DD bound ($)')
    for ax in axes:ax.grid(alpha=.2);ax.legend()
    fig.tight_layout();fig.savefig(ROOT/'reports'/f'{stem}.png',dpi=150);plt.close(fig)
    rows=[]
    for name,periods in r['selected'].items():
        for phase,sc in periods.items():
            for cost,m in sc.items():rows.append(dict(Policy=name,Period=phase,Costs=cost,Net=m['net_pnl'],Cash_DD=m['cash_drawdown'],OHLC_DD_bound=m['conservative_OHLC_drawdown_bound'],Trades=m['trades'],Inactivity=m['maximum_inactive_days'],Qualified=m['qualified']))
    title='Continuous TRAIN research: '+('qualifying challenger' if r['accepted'] else 'no qualifying improvement')
    text='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{font:16px/1.6 system-ui;max-width:1400px;margin:32px auto;padding:0 24px;background:#111820;color:#e9edf2}a{color:#9bd7ff}table{border-collapse:collapse;font-size:14px}td,th{padding:9px;border-bottom:1px solid #456}pre{white-space:pre-wrap}.scroll{overflow:auto}.note{background:#382d22;padding:18px}img{width:100%}</style><h1>'+title+'</h1><p>576 predeclared allocations, prefix TRAIN selection through2020, one frozen choice then continuous replay through2023 without cash/peak reset. Validation/test/forward-paper outcomes remained closed. These periods are reused TRAIN, not unseen confirmation.</p><p class="note">Raw historical fill dollars with micro multipliers; source E-mini proxies before2019 do not establish historical micro liquidity. Payouts are not simulated. Conservative minute-OHLC bounds include entire exit bars and pessimistic high-before-low ordering; these are bounds, not exact tick execution or verified broker rules. Candidate risk budgets never consult the current trade outcome.</p><div class="scroll">'+pd.DataFrame(rows).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div><img src="'+stem+'.png" alt="Continuous TRAIN equity and conservative drawdown"><h2>Frozen choice</h2><pre>'+html.escape(json.dumps(r['configuration'],indent=2))+'</pre><h2>Prefix TRAIN top20</h2><div class="scroll">'+frame.head(20).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div><p><a href="../runs/stack_continuous_v1/protocol.json">Frozen protocol</a> · <a href="../runs/stack_continuous_v1/training_bounds_identity.json">TRAIN data QA</a> · <a href="../runs/stack_continuous_v1/all_prefix_training_allocations.csv">All577 rows</a> · <a href="'+stem+'.json">Full results</a></p></html>'
    (ROOT/'reports'/f'{stem}.html').write_text(text,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if args.freeze:freeze()
    elif args.run:main()
    else:parser.error('Choose --freeze or --run')

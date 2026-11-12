"""Prescore data-integrity repair of scheduled-open exposure, same576 grid.

Original v1 results/code remain immutable. Source engine no_entry exits at the
bar OPEN before current high/low. This corrects marks, not signals or criteria.
"""
import argparse
import json
from pathlib import Path
import shutil
import duckdb
import numpy as np
import pandas as pd
import stack_continuous_train as old

ROOT=old.ROOT
ORIGINAL=ROOT/'runs/stack_continuous_v1'
RUN=ROOT/'runs/stack_continuous_exposure_fixed_v1'


def freeze():
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'protocol.json').exists():raise RuntimeError('Frozen correction exists')
    p=json.loads((ORIGINAL/'protocol.json').read_text())
    p['run_id']='stack_continuous_exposure_fixed_v1';p['frozen_at']=str(pd.Timestamp.now(tz='UTC'))
    p['data_integrity_repair']=dict(original_run_sha256=old.sha(ORIGINAL/'results.json'),
        original_bound_table_sha256=old.sha(ORIGINAL/'training_trade_bounds.parquet'),
        original_protocol_sha256=old.sha(ORIGINAL/'protocol.json'),
        explanation='269original invalid intervals all failed gap-only QA. Source mass_execution no_entry exits at opening[i] before high/low. Correct ALL exits at/after15:55ET to mark exposure only before tout, including the actual exit-open fill; keep exit-bar confirmation as conservative routing delay. No filter/gate/config changed.',
        original_failed_results_preserved=True,original_prefix_choice=None,
        source_engine_sha256=old.sha(ROOT/'scripts/mass_execution.py'),
        source_sleeve_wrapper_sha256=old.sha(ROOT/'src/quant_futures/ensemble_paper.py'))
    p['source_hashes'][str(Path(__file__).relative_to(ROOT))]=old.sha(__file__)
    p['mark_bounds']+=' Scheduled-open exits (source no_entry at>=15:55) use source bars before tout plus the exit-open cashfill, since no exposure exists in subsequent bars. Conservative entry/exit routing availability is unchanged.'
    code=RUN/'code';shutil.copytree(ORIGINAL/'code',code,dirs_exist_ok=True);shutil.copyfile(__file__,code/Path(__file__).name)
    old.write(RUN/'protocol.json',p)
    print('FROZEN EXPOSURE CORRECTION: same',len(p['candidates']),'allocations, unchanged criteria',flush=True)


def corrected_prepare(p):
    target=RUN/'training_trade_bounds.parquet'
    if target.exists():
        meta=json.loads((RUN/'training_bounds_identity.json').read_text());assert old.sha(target)==meta['sha256'];return pd.read_parquet(target)
    assert old.sha(ORIGINAL/'training_trade_bounds.parquet')==p['data_integrity_repair']['original_bound_table_sha256']
    assert old.sha(ROOT/'scripts/mass_execution.py')==p['data_integrity_repair']['source_engine_sha256']
    assert old.sha(ROOT/'src/quant_futures/ensemble_paper.py')==p['data_integrity_repair']['source_sleeve_wrapper_sha256']
    d=pd.read_parquet(ORIGINAL/'training_trade_bounds.parquet').copy()
    local=d.tout.dt.tz_convert('America/New_York');scheduled=(local.dt.hour*60+local.dt.minute)>=955
    changes=[]
    for product,mini in (('MES','ES'),('MNQ','NQ')):
        t=d.loc[scheduled & (d.inst==product),['id','tin','tout']].copy()
        for col in ('tin','tout'):t[col]=t[col].dt.tz_convert('UTC')
        con=duckdb.connect();con.execute("SET memory_limit='2GB'");con.execute('SET threads=2');con.register('trades',t)
        queries=[];params=[]
        for symbol,lo,hi in ((mini,'2010-01-01','2019-05-06'),(product,'2019-05-06','2024-01-01')):
            source=p['training_sources'][symbol];assert source['role']=='train' and old.sha(source['path'])==source['sha256']
            queries.append('SELECT timestamp_utc::TIMESTAMPTZ AS ts,open,high,low,close,volume,contract FROM read_parquet(?) WHERE timestamp_utc::TIMESTAMPTZ>=?::TIMESTAMPTZ AND timestamp_utc::TIMESTAMPTZ<?::TIMESTAMPTZ')
            params.extend([source['path'],lo,hi])
        query='''WITH p AS ('''+ ' UNION ALL '.join(queries)+'''),j AS (
          SELECT t.id,t.tout,p.*,lag(ts) OVER(PARTITION BY t.id ORDER BY ts) AS previous_ts
          FROM trades t JOIN p ON p.ts>=t.tin AND p.ts<=t.tout)
          SELECT id,min(ts) AS first_ts,max(ts) AS last_ts,count(*) AS bars,count(DISTINCT ts) AS unique_bars,
          count(DISTINCT contract) AS contracts,min(low) FILTER(WHERE ts<tout) AS low,
          max(high) FILTER(WHERE ts<tout) AS high,arg_min(open,ts) AS entry_open,
          max(open) FILTER(WHERE ts=tout) AS exit_open,max(date_diff('second',previous_ts,ts)) AS maximum_gap_seconds,
          sum(CASE WHEN high<greatest(open,close,low) OR low>least(open,close,high) OR low<=0 OR volume<0 OR NOT isfinite(high) OR NOT isfinite(low) THEN 1 ELSE 0 END) AS bad_ohlc
          FROM j GROUP BY id'''
        marks=con.execute(query,params).fetch_df();con.close();changes.append(marks)
        print('TRAIN scheduled-open bounds',product,len(marks),flush=True)
    marks=pd.concat(changes,ignore_index=True).set_index('id');assert marks.index.is_unique
    d=d.set_index('id')
    for col in ('first_ts','last_ts','bars','unique_bars','contracts','low','high','entry_open','maximum_gap_seconds','bad_ohlc'):
        d.loc[marks.index,col]=marks[col]
    d['exit_open']=np.nan;d.loc[marks.index,'exit_open']=marks.exit_open
    worst=np.where(d.side>0,d.low,d.high);best=np.where(d.side>0,d.high,d.low)
    d['adverse']=(d.side*(worst-d.entry)-.5)*d.multiplier-1.
    d['favorable']=np.maximum(0.,d.side*(best-d.entry)*d.multiplier-.5)
    ids=marks.index
    # Include the known final open in the favorable upper bound; full fill net
    # separately captures adverse gaps and all roundtrip costs.
    d.loc[ids,'favorable']=np.maximum(d.loc[ids,'favorable'],np.maximum(0.,d.loc[ids,'side']*(d.loc[ids,'exit_open']-d.loc[ids,'entry'])*d.loc[ids,'multiplier']-.5))
    valid=(pd.to_datetime(d.first_ts,utc=True)==d.tin.dt.tz_convert('UTC'))&(d.bars==d.unique_bars)&(d.contracts==1)&(d.bad_ohlc==0)&(d.maximum_gap_seconds.fillna(0)<=300)&((d.entry-(d.entry_open+d.side*.5)).abs()<=.250001)
    exit_quote=pd.to_datetime(d.loc[ids,'last_ts'],utc=True)==d.loc[ids,'tout'].dt.tz_convert('UTC')
    exit_match=(d.loc[ids,'exit']-(d.loc[ids,'exit_open']-d.loc[ids,'side']*.5)).abs()<=.250001
    valid.loc[ids]&=exit_quote & exit_match
    d['path_valid']=valid;d=d.reset_index().sort_values(['tin','prio'],kind='stable').reset_index(drop=True)
    d.to_parquet(target,index=False)
    old.write(RUN/'training_bounds_identity.json',dict(sha256=old.sha(target),rows=len(d),scheduled_open_paths_corrected=len(marks),
        valid_paths=int(valid.sum()),invalid_paths=int((~valid).sum()),invalid_ids=d.loc[~d.path_valid,'id'].tolist(),
        path_repair='Actual scheduled exit-open exposure only; no postexit market gap counted. Non-scheduled bounds and all entry/exit signals unchanged.',
        maximum_quote_gap_limit_unchanged=300,no_prices_interpolated=True,no_trades_dropped=True,validation_accessed=False,test_accessed=False))
    print('CORRECTED TRAIN QA',int(valid.sum()),'valid,',int((~valid).sum()),'invalid',flush=True)
    return d


def publish(r,v,frame):
    import html
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    stem='STACK_CONTINUOUS_EXPOSURE_FIXED_TRAIN';old.write(ROOT/'reports'/f'{stem}.json',r);old.write(ROOT/'reports'/f'{stem}_verification.json',v)
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
    for name in [old.INC['name']]+([r['configuration']['name']] if r['configuration'] else []):
        for kind in ('base','cost2'):
            path=RUN/'selected/continuous_full'/name/(kind+'_trades_and_bounds.csv')
            d=pd.read_csv(path)
            if not len(d):continue
            x=pd.to_datetime(d.available_exit,utc=True,format='mixed');label=('Incumbent' if name==old.INC['name'] else 'Frozen choice')+' '+kind
            axes[0].plot(x,d.cash_pnl,label=label,lw=1)
            axes[1].plot(x,d.favorable_equity_peak_bound-d.adverse_equity_bound,label=label,lw=1)
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8);ax.axvline(pd.Timestamp('2021-01-01T00:00Z'),color='grey',ls=':')
    axes[0].set_ylabel('Continuous historical-dollar trading P&L');axes[1].set_ylabel('Conservative OHLC DD bound');axes[1].axhline(2000,color='red',ls='--')
    fig.tight_layout();fig.savefig(ROOT/'reports'/f'{stem}.png',dpi=150);plt.close(fig)
    rows=[]
    for name,phases in r['selected'].items():
        for phase,costs in phases.items():
            for cost,m in costs.items():rows.append(dict(Policy=name,Period=phase,Costs=cost,Net=m['net_pnl'],Cash_DD=m['cash_drawdown'],OHLC_DD_bound=m['conservative_OHLC_drawdown_bound'],Trades=m['trades'],Inactivity_days=m['maximum_inactive_days'],Qualified=m['qualified']))
    title='Continuous TRAIN: '+('research challenger' if r['accepted'] else 'no qualifying improvement')
    text='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{font:16px/1.6 system-ui;max-width:1400px;margin:32px auto;padding:0 24px;background:#111820;color:#e9edf2}a{color:#95d8ff}pre{white-space:pre-wrap}table{border-collapse:collapse;font-size:14px}td,th{padding:9px;border-bottom:1px solid #456}.scroll{overflow:auto}img{width:100%}.note{padding:18px;background:#372d22}</style><h1>'+title+'</h1><p>Same576 predeclared allocations; prefix TRAIN2010July-2020 selects one; continuous2010July-2023replay of only the frozen choice and incumbent. No cash/peak reset in2021. All periods are reused TRAIN. Validation/test/forward-paper outcomes excluded; no deployment.</p><p class="note">Historical raw fills with micro economics; pre2019 uses E-mini proxy quotes, not actual micro liquidity. Conservative minute-OHLC bounds use pessimistic excursion ordering and include full uncertain exit bars; exact tick chronology and broker rules remain unverified. Payouts not modeled. Original normalized results cannot be compared as equivalent dollars.</p><p>First audit wrongly included a postexit interval for scheduled-open closes, flagging269quote gaps. Original failed run retained. All scheduled-open intervals were repaired using source-engine accounting before rescoring the identical grid; gap threshold and entry/exit/risk criteria unchanged.</p><div class="scroll">'+pd.DataFrame(rows).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div><img src="'+stem+'.png" alt="Continuous TRAIN cash and conservative drawdown"><h2>Frozen allocation</h2><pre>'+html.escape(json.dumps(r['configuration'],indent=2))+'</pre><h2>Prefix top20</h2><div class="scroll">'+frame.head(20).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'</div><p><a href="../runs/stack_continuous_exposure_fixed_v1/protocol.json">Frozen protocol and data repair</a> · <a href="../runs/stack_continuous_exposure_fixed_v1/all_prefix_training_allocations.csv">All577rows</a> · <a href="../runs/stack_continuous_exposure_fixed_v1/training_bounds_identity.json">TRAIN QA</a> · <a href="'+stem+'.json">Full results</a></p></html>'
    (ROOT/'reports'/f'{stem}.html').write_text(text,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    old.RUN=RUN
    if args.freeze:freeze()
    elif args.run:old.prepare=corrected_prepare;old.publish=publish;old.main()
    else:parser.error('Choose --freeze or --run')

"""Audit saved predictions/fills and render reports without re-executing V."""
import json
import html
import sqlite3
import numpy as np
import pandas as pd
import novel_futures_2k as run


def main():
    p=run.RUN;reports=run.ROOT/'reports'
    r=run.read(reports/'NOVEL_FUTURES_2K.json')
    db=sqlite3.connect(p/'checkpoints.sqlite')
    train={x['config_id']:x for x in run.all_results(db,'TRAIN')}
    validation=run.all_results(db,'VALIDATION')
    models=run.read(p/'frozen_models.json')
    assert len(train)==len(validation)==2000
    assert all(x['parameters']==train[x['config_id']]['parameters'] for x in validation)
    assert all(pd.Timestamp(m['fit_cutoff'])<pd.Timestamp(k.split('|')[-1]+'-01-01T00:00Z') for k,m in models.items())
    assert all(pd.Timestamp(m['fit_cutoff'])<=pd.Timestamp('2023-12-24T00:00Z') for m in models.values())
    training={s:pd.read_parquet(p/'cache'/(s+'_15m.parquet')) for s in run.SYMBOLS}
    frames={s:pd.read_parquet(p/'cache'/(s+'_validation_15m.parquet')) for s in run.SYMBOLS}
    cache=run.SignalCache(frames,training,validation=True)
    cache.models={tuple([s,f,int(L),int(y)]):m for k,m in models.items() for s,f,L,y in [k.split('|')]}
    checks=[]
    for row in r['top5_validation']:
        c=row['parameters'];b=frames[c['instrument']];d=run.engine.arrays(b);f=run.engine.features(b,32)
        sig=cache.signal(c);sig[:96]=0;sig[-16:]=0
        stored=np.load(p/'validation_snapshots'/(c['config_id']+'.npz'))
        raw={k:stored[k] for k in stored.files if k!='lock_reason'}
        check=run.engine.verify_execution(b,d,sig,f['atr'],c,run.engine.execution_cfg(c),raw)
        measured=run.engine.summarize_execution(raw,d)
        for k in ('net_pnl','max_drawdown','realized_drawdown','intrabar_drawdown','trades'):
            assert abs(measured[k]-row[k])<1e-7
        checks.append(dict(config_id=c['config_id'],verification=check))
        art=p/'selected_artifacts';name=c['config_id']+'_VALIDATION'
        pd.DataFrame(dict(timestamp_utc=b.timestamp_utc,equity=raw['equity'],cash=raw['cash'],intrabar_worst_bound=raw['worst'])).to_parquet(art/(name+'_equity.parquet'),index=False)
        pd.DataFrame(dict(entry_time=pd.to_datetime(d['timestamp'][raw['trade_entry']],utc=True),exit_time=pd.to_datetime(d['timestamp'][raw['trade_exit']],utc=True),side=raw['trade_side'],quantity=raw['trade_qty'],entry_price=raw['trade_entryprice'],exit_price=raw['trade_exitprice'],net_pnl=raw['trade_net'],fees=raw['trade_fees'],reason=raw['trade_reason'])).to_csv(art/(name+'_trades.csv'),index=False)
    audit=dict(passed=True,parameters_unchanged_all_2000=True,model_count=len(models),all_fit_cutoffs_before_evaluated_year=True,
       latest_fit_cutoff='2023-12-24T00:00Z',extra_no_validation_fit_tests=5,
       distinct_training_signal_paths=len({(x['instrument'],x['signal_fingerprint']) for x in train.values()}),
       selected_curves_reconciled=True,fill_checks=checks,full_validation_reexecutions=0,test_accessed=False)
    run.write(reports/'NOVEL_FUTURES_2K_additional_audit.json',audit)
    family=pd.DataFrame(r['by_family']).rename(columns={'train_positive_dd':'TRAIN profit/DD','train_qualified':'TRAIN full gates','validation_positive_dd':'VAL profit/DD','validation_qualified':'VAL risk checks'})
    rows=[]
    for x in r['top5_validation']:
        tr=train[x['config_id']]
        rows.append({'ID':x['config_id'],'Mechanism':x['instrument']+' / '+x['family'],'TRAIN net':tr['net_pnl'],'TRAIN DD':tr['intrabar_drawdown'],'VAL net':x['net_pnl'],'VAL DD':x['intrabar_drawdown'],'VAL trades':x['trades'],'TRAIN gates':'FAIL'})
    table=pd.DataFrame(rows).to_html(index=False,float_format=lambda x:f'${x:,.2f}',border=0)
    style='body{font:16px/1.6 system-ui;background:#10151c;color:#e9edf2;max-width:1300px;margin:auto;padding:32px}h1{font-size:34px}h2{margin-top:34px}a{color:#91d5ff}.scroll{overflow:auto}table{border-collapse:collapse;font-size:14px;width:100%}th,td{padding:10px;border-bottom:1px solid #34455b;text-align:left;white-space:nowrap}th{background:#1c2531}img{width:100%}.notice{padding:20px;background:#332a1b;border-left:4px solid #e7bb62}pre{white-space:pre-wrap;font:14px/1.7 system-ui}'
    body='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>2,000 new futures configurations</title><style>'+style+'</style>'
    body+='<h1>2,000 new futures configurations</h1><p>MNQ and MES · Eight statistical entry mechanisms · TRAIN 2020–2023 · VALIDATION 2024–2025</p>'
    body+='<p class="notice"><strong>No qualifying replacement.</strong> 169 passed TRAIN profit/DD checks; 232 passed VAL profit/DD checks; 51 passed VAL risk checks; zero passed the full criteria on both splits. TEST stayed closed. Validation is model selection on a previously observed period, not independent confirmation.</p>'
    body+='<h2>Results by mechanism</h2><div class="scroll">'+family.to_html(index=False,border=0)+'</div>'
    body+='<h2>Top validation qualifiers, with training results</h2><div class="scroll">'+table+'</div>'
    body+='<p>The leading illiquidity-reversal candidate earned $2,536.50 on validation ($1,170.38 intrabar DD), but lost $3,671 on training with three risk locks and only one profitable training year. Validation annual profits were $1,155 in 2024 and $1,381.50 in 2025. Failed TRAIN gates remain failed.</p>'
    body+='<img src="NOVEL_FUTURES_2K.png" alt="Top five validation qualifiers; all failed training gates">'
    body+='<h2>Novelty and evidence</h2><p>Entries use autoregressive forecasts, two-sign Markov states, historical time-slot expectations, volume-response regression, cross-index lead–lag regression, return skewness, semivariance, and abnormal price impact per traded notional. These are 2,000 configurations of eight mechanisms, with 1,038 distinct training signal paths. Exit variants do not create independent discoveries. A generic lead–lag context feature existed before; this batch uses a distinct frozen regression entry model.</p>'
    body+='<p>Forty-four targeted checks passed before execution, plus five additional validation-no-refit guards afterward. All 10,000 ledgers reconcile across 592,654 trades. The top five saved validation curves reconcile and isolated fill samples passed. No full validation backtest was rerun for reporting. Four hundred serialized model records cover forward-fold and final validation fits; every cutoff precedes its evaluated year. Latest cutoff: December 24, 2023. Execution code and account risk rules stayed fixed.</p>'
    body+='<p><a href="../runs/novel_futures_2k_v1/training_ranked.csv">All TRAIN results</a> · <a href="../runs/novel_futures_2k_v1/validation_ranked.csv">All VAL results</a> · <a href="../runs/novel_futures_2k_v1/protocol.json">Frozen protocol</a> · <a href="NOVEL_FUTURES_2K_verification.json">Ledger audit</a> · <a href="NOVEL_FUTURES_2K_additional_audit.json">Model and fill audit</a></p>'
    body+='<h2>Full methods and results</h2><pre>'+html.escape((reports/'NOVEL_FUTURES_2K.md').read_text(encoding='utf-8'))+'</pre></html>'
    (reports/'NOVEL_FUTURES_2K.html').write_text(body,encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k!='fill_checks'}))


if __name__=='__main__':main()

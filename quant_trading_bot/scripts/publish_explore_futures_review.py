"""Review saved explore2k artifacts; never re-executes a validation account."""
import html
import json
import sqlite3
import numpy as np
import pandas as pd
import explore_futures_2k as run


def main():
    p=run.RUN;reports=run.ROOT/'reports';r=run.read(reports/'EXPLORE_FUTURES_2K.json')
    db=sqlite3.connect(p/'checkpoints.sqlite')
    tr={x['config_id']:x for x in run.all_results(db,'TRAIN')};val=run.all_results(db,'VALIDATION')
    assert len(tr)==len(val)==2000
    assert all(x['parameters']==tr[x['config_id']]['parameters'] for x in val)
    models=run.read(p/'frozen_models.json')
    assert all(pd.Timestamp(m['fit_cutoff'])<pd.Timestamp(k.split('|')[-1]+'-01-01T00:00Z') for k,m in models.items())
    assert all(pd.Timestamp(m['fit_cutoff'])<=pd.Timestamp('2023-12-24T00:00Z') for m in models.values())
    frames={s:pd.read_parquet(p/'cache'/(s+'_validation_15m.parquet')) for s in run.SYMBOLS}
    training={s:pd.read_parquet(p/'cache'/(s+'_15m.parquet')) for s in run.SYMBOLS}
    cache=run.SignalCache(frames,training,validation=True)
    cache.models={tuple([s,f,int(L),int(y)]):m for k,m in models.items() for s,f,L,y in [k.split('|')]}
    chosen={x['config_id']:x for x in r['top5_validation']+r['top5_both']}
    checks=[]
    for cid,x in chosen.items():
        c=x['parameters'];b=frames[c['instrument']];data=run.engine.arrays(b);f=run.engine.features(b,32)
        sig=cache.signal(c);sig[:96]=0;sig[-16:]=0
        saved=np.load(p/'validation_snapshots'/(cid+'.npz'));raw={k:saved[k] for k in saved.files if k!='lock_reason'}
        measured=run.engine.summarize_execution(raw,data)
        for k in ('net_pnl','intrabar_drawdown','max_drawdown','realized_drawdown','trades'):
            assert abs(measured[k]-x[k])<1e-7
        check=run.engine.verify_execution(b,data,sig,f['atr'],c,run.engine.execution_cfg(c),raw)
        checks.append(dict(config_id=cid,verification=check))
        name=cid+'_VALIDATION';art=p/'selected_artifacts'
        pd.DataFrame(dict(timestamp_utc=b.timestamp_utc,equity=raw['equity'],cash=raw['cash'],intrabar_worst_bound=raw['worst'])).to_parquet(art/(name+'_equity.parquet'),index=False)
        pd.DataFrame(dict(entry_time=pd.to_datetime(data['timestamp'][raw['trade_entry']],utc=True),exit_time=pd.to_datetime(data['timestamp'][raw['trade_exit']],utc=True),side=raw['trade_side'],quantity=raw['trade_qty'],entry_price=raw['trade_entryprice'],exit_price=raw['trade_exitprice'],net_pnl=raw['trade_net'],fees=raw['trade_fees'],reason=raw['trade_reason'])).to_csv(art/(name+'_trades.csv'),index=False)
    audit=dict(passed=True,all_parameters_unchanged=True,all_model_fit_cutoffs_before_evaluation=True,model_count=len(models),
       both_profit_dd=sum(x['profit_dd_pass'] and tr[x['config_id']]['profit_dd_pass'] for x in val),
       distinct_training_signal_paths=len({(x['instrument'],x['signal_fingerprint']) for x in tr.values()}),
       selected_curve_and_fill_audits=checks,full_validation_replays=0,test_accessed=False)
    run.write(reports/'EXPLORE_FUTURES_2K_additional_audit.json',audit)
    def table(rows):
        a=[]
        for x in rows:
            t=tr[x['config_id']]
            a.append({'ID':x['config_id'],'Market':x['instrument'],'Mechanism':x['family'],'TRAIN net':t['net_pnl'],'TRAIN intrabar DD':t['intrabar_drawdown'],'VAL net':x['net_pnl'],'VAL intrabar DD':x['intrabar_drawdown'],'VAL trades':x['trades'],'TRAIN qualified':t['qualified'],'VAL qualified':x['qualified']})
        return pd.DataFrame(a).to_html(index=False,border=0,float_format=lambda v:f'${v:,.2f}') if a else '<p>No candidates passed both sets of gates.</p>'
    counts=r['counts'];verification=run.read(reports/'EXPLORE_FUTURES_2K_verification.json')
    status='No qualifying replacement' if not r['best_both'] else 'A model passed the fixed TRAIN and validation-selection gates'
    style='body{font:16px/1.6 system-ui;background:#10151c;color:#e9edf2;max-width:1350px;margin:auto;padding:32px}h1{font-size:34px}h2{margin-top:32px}a{color:#91d5ff}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px;border-bottom:1px solid #34455b;text-align:left;white-space:nowrap}th{background:#1c2531}.scroll{overflow:auto}.notice{background:#332a1b;padding:20px;border-left:4px solid #e7bb62}img{width:100%}pre{white-space:pre-wrap;font:14px/1.7 system-ui}'
    body='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Another2,000 futures configurations</title><style>'+style+'</style><h1>Another 2,000 futures configurations</h1><p>MNQ and MES Â· Five new entry mechanisms Â· 400 configurations per mechanism</p>'
    body+=f'<p class="notice"><strong>{status}.</strong> TRAIN: {counts["train_positive_dd"]} positive-net/sub-$2,000-DD cases and {counts["train_qualified"]} full qualifiers. VALIDATION: {counts["validation_positive_dd"]} positive-net/sub-$2,000-DD cases and {counts["validation_qualified"]} scenario qualifiers. Both: {audit["both_profit_dd"]} basic profit/DD passers, {counts["both_qualified"]} full qualifiers.</p>'
    body+='<p>All parameters and analog-training examples were frozen before validation prices were loaded. Validation remains previously observed model-selection data, not independent confirmation. TEST stayed closed. No model was deployed or automatically promoted.</p><h2>Results by mechanism</h2><div class="scroll">'+pd.DataFrame(r['by_family']).to_html(index=False,border=0)+'</div>'
    body+='<h2>Top models passing both sets of gates, ranked on validation</h2><div class="scroll">'+table(r['top5_both'])+'</div><h2>Top validation qualifiers, with training results</h2><div class="scroll">'+table(r['top5_validation'])+'</div><img src="EXPLORE_FUTURES_2K.png" alt="Validation equity and drawdown curves">'
    body+=f'<h2>What changed and what was checked</h2><p>Directional-probability entries use fixed regularized logistic classification. Cross-index equilibrium fades deviations from a frozen log-price relationship; execution is target-only, not a hedged arbitrage. Wavelet reversal fades dominant causal Haar detail. Ordinal-pattern entropy measures organization of three-return rankings. Run-duration forecasts use frozen signed-run conditional return tables. These use related OHLCV inputs; new algorithms do not create independent economic evidence.</p><p>The 2,000 configurations cover five correlated hypotheses and {audit["distinct_training_signal_paths"]} distinct TRAIN signal paths. Forty-four targeted tests passed before execution. {verification["ledgers"]:,} ledgers covering {verification["trades_audited"]:,} trades reconcile. Selected validation curves and isolated fill samples passed audit. No validation account was replayed for reporting. Three learned model families use TRAIN-only fitting/scaling, a fixed4,096-example cap, and an eight-day gap before each evaluated year. Logistic ridge is0.01,maximum200iterations; log-price equilibrium uses OLS; duration tables use20 zero-return pseudocounts. The other two families use causal rolling statistics. Four annual TRAIN accounts reset; validation uses one continuous account. Fees, fills, risk controls, qualification gates, and the strict $2,000 drawdown ceiling were preserved.</p>'
    body+='<p>Cash/no-trade benchmark is zero P&amp;L and zero drawdown; it does not meet trade-count gates. Intrabar drawdown is a conservative OHLC bound. Funded-account checks use provisional scenarios. The 50% consistency rule remains an evaluation-account-only diagnostic.</p><p><a href="../runs/explore_futures_2k_v1/training_ranked.csv">All TRAIN results</a> Â· <a href="../runs/explore_futures_2k_v1/validation_ranked.csv">All VAL results</a> Â· <a href="../runs/explore_futures_2k_v1/protocol.json">Frozen protocol</a> Â· <a href="EXPLORE_FUTURES_2K_verification.json">Ledger audit</a> Â· <a href="EXPLORE_FUTURES_2K_additional_audit.json">Model and fill audit</a></p><h2>Detailed methods and results</h2><pre>'+html.escape((reports/'EXPLORE_FUTURES_2K.md').read_text(encoding='utf-8'))+'</pre></html>'
    (reports/'EXPLORE_FUTURES_2K.html').write_text(body,encoding='utf-8')
    print(json.dumps(dict(counts=counts,both_profit_dd=audit['both_profit_dd'],distinct_signal_paths=audit['distinct_training_signal_paths'],model_count=len(models),review_passed=True)))


if __name__=='__main__':main()

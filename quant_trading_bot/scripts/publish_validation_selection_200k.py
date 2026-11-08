"""Rank all saved validation cases, audit ledgers and publish; no backtest replay."""
import csv
import html
import json
from pathlib import Path
import shutil
import sqlite3
import zlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import validation_selection_200k as batch
from e57_refinement_parameters import fingerprint,scaled_cfg
from quant_futures.config import file_hash,digest
from quant_futures.research import json_write
from build_light_dashboard_charts import sampled_ids

FIELDS=('validation_rank','config_id','family','training_qualified','training_net','training_intrabar_dd','validation_scenario_pass','validation_profit_dd_pass','validation_net','validation_cash_dd','validation_closing_dd','validation_intrabar_dd','validation_trades','validation_profit_factor','validation_expectancy','validation_consistency','evaluation_account_pass','validation_lock','funded_breaches','beats_baseline','parameters')


def money(n):return ('−' if n<0 else '')+f'${abs(n):,.2f}'


def csv_row(rank,row):
    m=row['fold_metrics'][0]
    return dict(zip(FIELDS,(rank,row['config_id'],row['family'],row['training_qualified'],row['training_net'],row['training_intrabar_drawdown'],row['qualified'],row['profit_dd_pass'],row['net_pnl'],row['realized_drawdown'],row['max_drawdown'],row['intrabar_drawdown'],row['trades'],row['profit_factor'],row['expectancy'],m['consistency'],row['evaluation_phase_qualified'],m['lock'],row['funded_breaches'],row['beats_baseline'],json.dumps(row['parameters'],sort_keys=True))))


def selected_artifacts(row,bars,data,masks):
    cid=row['config_id'];c=row['parameters'];path=batch.RUN/'snapshots'/(cid+'.npz')
    with np.load(path,allow_pickle=False) as archive:raw={k:(archive[k].item() if archive[k].ndim==0 else archive[k]) for k in archive.files}
    assert len(raw['trade_net'])==row['trades']
    eq=raw['equity'];cash=raw['cash'];peak=np.maximum.accumulate(np.r_[50000.,eq])[1:];cp=np.maximum.accumulate(np.r_[50000.,cash])[1:]
    for actual,expected in ((eq[-1]-50000,row['net_pnl']),(raw['trade_net'].sum(),row['net_pnl']),((peak-eq).max(),row['max_drawdown']),((cp-cash).max(),row['realized_drawdown']),((peak-raw['worst']).max(),row['intrabar_drawdown'])):
        np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)
    f=batch.training.engine.features(bars,c['lookback']);s=batch.training.cached_signal(c,f,masks,{})
    s[:96]=0;s[-16:]=0
    verification=batch.training.engine.verify_execution(bars,data,s,f['atr'],c,scaled_cfg(batch.training.engine.execution_cfg(c),c),raw)
    assert verification['passed']
    dest=batch.RUN/'selected_artifacts';dest.mkdir(exist_ok=True)
    curve=pd.DataFrame(dict(timestamp_utc=bars.timestamp_utc,equity=eq,cash=cash,intrabar_worst_bound=raw['worst'],quantity=raw['quantity']))
    trades=pd.DataFrame(dict(entry_time=pd.to_datetime(data['timestamp'][raw['trade_entry']],unit='ns',utc=True),exit_time=pd.to_datetime(data['timestamp'][raw['trade_exit']],unit='ns',utc=True),side=raw['trade_side'],quantity=raw['trade_qty'],entry_price=raw['trade_entryprice'],exit_price=raw['trade_exitprice'],net_pnl=raw['trade_net'],fees=raw['trade_fees'],reason=[batch.training.engine.TRADE_REASONS[int(r)] for r in raw['trade_reason']]))
    curve.to_parquet(dest/(cid+'_equity.parquet'),index=False);trades.to_csv(dest/(cid+'_trades.csv'),index=False)
    return curve,verification


def main():
    protocol=batch.verify();run=batch.RUN;root=batch.ROOT
    training_seal=batch.read(run/'training_complete.json');validation_seal=batch.read(run/'validation_complete.json');policy=batch.read(run/'validation_policy.json');reservation=batch.read(run/'validation_reservation.json')
    assert training_seal['completed']==validation_seal['completed']==batch.TARGET==200000
    assert training_seal['training_csv_sha256']==file_hash(run/'training_results.csv')
    assert reservation['training_complete_sha256']==validation_seal['training_complete_sha256']==file_hash(run/'training_complete.json')
    assert reservation['validation_policy_sha256']==validation_seal['validation_policy_sha256']==file_hash(run/'validation_policy.json')
    global_reservation=batch.read(reservation['global_reservation'])
    assert all(reservation[k]==v for k,v in global_reservation.items())
    # Independent active-configuration audit includes other jobs' entire reserved manifests.
    prior=set();prior_raw=0
    for p,expected in protocol['prior_manifest_hashes'].items():
        assert file_hash(p)==expected
        with Path(p).open(encoding='utf-8') as stream:
            for line in stream:prior.add(fingerprint(json.loads(line)));prior_raw+=1
    assert len(prior)==protocol['prior_unique_excluded'] and prior_raw==protocol['prior_raw_cases']
    planned=set();active=set();parameters={}
    with (run/'configurations.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            c=json.loads(line);key=fingerprint(c)
            assert key not in prior and key not in active and c['config_id'] not in planned
            active.add(key);planned.add(c['config_id']);parameters[c['config_id']]=digest(c)
    assert len(active)==len(planned)==200000
    db=sqlite3.connect('file:'+(run/'checkpoints.sqlite').as_posix()+'?mode=ro',uri=True)
    try:
        training_ids={r[0] for r in db.execute('SELECT config_id FROM train')};val_ids={r[0] for r in db.execute('SELECT config_id FROM val')}
        assert planned==training_ids==val_ids
        states=dict(db.execute('SELECT state,COUNT(*) FROM validation_attempts GROUP BY state'));assert states=={'done':200000}
        assert db.execute('SELECT COUNT(DISTINCT reservation_key) FROM validation_attempts').fetchone()[0]==200000
        training_summary={cid:(bool(q),net,dd) for cid,q,net,dd in db.execute('SELECT config_id,qualified,net,dd FROM train')}
        counts=dict(evaluated=0,positive_net=0,positive_and_all_dd_under2000=0,validation_scenario_pass=0,both_training_and_validation_pass=0,better_than_baseline=0,evaluation_account_pass=0,locked=0,zero_trades=0)
        top=[];both=[];previous=None;trade_count=0
        fields=FIELDS
        with (run/'validation_ranked.csv').open('w',encoding='utf-8',newline='') as stream,(run/'top100_validation.csv').open('w',encoding='utf-8',newline='') as short,(run/'top100_train_and_validation.csv').open('w',encoding='utf-8',newline='') as good:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();shorter=csv.DictWriter(short,fieldnames=fields);shorter.writeheader();good_writer=csv.DictWriter(good,fieldnames=fields);good_writer.writeheader()
            query='SELECT payload,ledger FROM val ORDER BY qualified DESC,net DESC,dd,config_id'
            for rank,(payload,blob) in enumerate(db.execute(query),1):
                row=json.loads(payload);cid=row['config_id'];m=row['fold_metrics'][0]
                assert digest(row['parameters'])==parameters[cid]
                tq,tn,td=training_summary[cid]
                assert (row['training_qualified'],row['training_net'],row['training_intrabar_drawdown'])==(tq,tn,td)
                primary,scenario=batch.validation_checks(row)
                assert primary==row['profit_dd_pass'] and scenario==row['qualified']
                assert row['beats_baseline']==bool(tq and scenario and row['net_pnl']>policy['baseline_validation_net'])
                key=batch.order_key(row);assert previous is None or previous<=key;previous=key
                # Every case's stored ledger is audited without a second validation execution.
                ledger=json.loads(zlib.decompress(blob));n=len(ledger['trade_net']);assert n==row['trades'];trade_count+=n
                entries=np.asarray(ledger['trade_entry']);exits=np.asarray(ledger['trade_exit']);quantities=np.asarray(ledger['trade_qty']);sides=np.asarray(ledger['trade_side'])
                assert np.all(entries>=1) and np.all(exits>=entries) and np.all(quantities>=1) and np.all(quantities<=row['parameters']['max_contracts']) and np.all(np.isin(sides,[-1,1]))
                assert np.all(entries[1:]>exits[:-1]) and np.all(np.asarray(ledger['trade_fees'])>=0)
                net=np.asarray(ledger['trade_side'])*np.asarray(ledger['trade_qty'])*(np.asarray(ledger['trade_exitprice'])-np.asarray(ledger['trade_entryprice']))*2.-np.asarray(ledger['trade_fees'])
                np.testing.assert_allclose(net,np.asarray(ledger['trade_net']),rtol=0,atol=1e-7);np.testing.assert_allclose(net.sum(),row['net_pnl'],rtol=0,atol=1e-7)
                counts['evaluated']+=1;counts['positive_net']+=int(row['net_pnl']>0);counts['positive_and_all_dd_under2000']+=int(primary);counts['validation_scenario_pass']+=int(scenario);counts['both_training_and_validation_pass']+=int(tq and scenario);counts['better_than_baseline']+=int(row['beats_baseline']);counts['evaluation_account_pass']+=int(row['evaluation_phase_qualified']);counts['locked']+=int(row['locks']>0);counts['zero_trades']+=int(n==0)
                output=csv_row(rank,row);writer.writerow(output)
                if rank<=100:shorter.writerow(output)
                if len(top)<10:top.append(row)
                if tq and scenario and len(both)<100:
                    good_writer.writerow(output);both.append(row)
        assert counts['evaluated']==200000
        curves={};verifications=[]
        bars=batch.load_validation(policy);data=batch.training.engine.arrays(bars);masks=batch.training.session_masks(bars)
        selected_rows={r['config_id']:r for r in [*top,*both[:10]]}
        for row in selected_rows.values():
            curve,verification=selected_artifacts(row,bars,data,masks);curves[row['config_id']]=curve;verifications.append(dict(config_id=row['config_id'],verification=verification))
        best=both[0] if both else None;accepted=bool(best and best['beats_baseline'])
        decision='BETTER_THAN_BASELINE_ON_VALIDATION_SELECTION_SET' if accepted else 'NO_BETTER_QUALIFIED_MODEL_THAN_BASELINE'
        selected_file=None
        if best:
            frozen=dict(parameters=best['parameters'],validation=best,selection_rule=protocol['ranking'],decision=decision,validation_used_for_model_selection=True,parameters_changed_during_validation=False,independent_confirmation=False,test_status='NOT_EVALUATED',source_hashes=protocol['source_hashes'],configuration_sha256=protocol['configuration_sha256'],validation_seal_sha256=file_hash(run/'validation_complete.json'),execution_config=scaled_cfg(batch.training.engine.execution_cfg(best['parameters']),best['parameters']),training_source=batch.read(run/'training_source.json'))
            selected_file=run/'frozen_validation_selected_candidate.json'
            if selected_file.exists():assert batch.read(selected_file)==frozen
            else:json_write(selected_file,frozen)
        fig,axes=plt.subplots(2,1,figsize=(13,9),layout='constrained')
        plot_rows=both[:5] if both else top[:5]
        for i,row in enumerate(plot_rows,1):
            curve=curves[row['config_id']];eq=curve.equity.to_numpy();peak=np.maximum.accumulate(np.r_[50000.,eq])[1:];dd=peak-curve.intrabar_worst_bound.to_numpy();ids=np.unique(np.r_[sampled_ids(curve.equity,limit=400),dd.argmax()])
            x=curve.timestamp_utc.iloc[ids];label=f'#{i} {row["config_id"][-8:]} net {money(row["net_pnl"])}'
            axes[0].plot(x,eq[ids]-50000,label=label,linewidth=1);axes[1].plot(x,-dd[ids],label=label,linewidth=1)
        axes[1].axhline(-2000,color='red',linestyle='--',linewidth=.7)
        for ax in axes:ax.grid(alpha=.15);ax.set_ylabel('USD');ax.legend(fontsize=8)
        axes[0].set_title('Validation net P&L');axes[1].set_title('Validation intrabar drawdown bound')
        fig.suptitle('Top validation-selected fixed strategies'+(' passing both TRAIN/validation gates' if both else '')+'\nOne continuous $50k account per validation case; selection set, not independent confirmation')
        fig.savefig(run/'validation_top5.png',dpi=125);plt.rcParams['svg.fonttype']='none';fig.savefig(run/'validation_top5.svg');plt.close(fig)
        lines=['# 200,000 new strategies: train, evaluate every configuration on validation, then rank','',
            '**All200,000 frozen configurations completed TRAIN and exactly one base-cost VALIDATION evaluation each. Ranking uses validation outcomes, as requested; no parameters, indicators, filters, sizing, costs or risk rules were changed from those outcomes. No test data or test outcomes were opened by this batch.**','',
            'Validation is explicitly used for model selection across200,000 correlated trials. Its top-ranked performance is therefore optimistically selected and is not independent confirmation of a profitable edge. These periods have been used in prior work; their independence cannot be restored by relabeling. The original parent was also selected after earlier holdout observations.','',
            '## Counts','', '| Check | Configurations |','|---|---:|']
        for label,key in (('Evaluated on validation','evaluated'),('Positive validation net','positive_net'),('Positive validation net + every DD strictly below$2,000','positive_and_all_dd_under2000'),('Validation scenario pass including>=30 trades/no locks/no funded breach','validation_scenario_pass'),('Both TRAIN and validation qualification','both_training_and_validation_pass'),('Both gates + validation net above original-v1 benchmark','better_than_baseline'),('Evaluation-account scenario including50% consistency','evaluation_account_pass'),('Permanent validation lock','locked'),('Zero validation trades','zero_trades')):lines.append(f'| {label} | {counts[key]:,} |')
        lines+=['','## Acceptance decision','',f'**{decision}**. Original v1 archived validation net reference: **{money(policy["baseline_validation_net"])}**. The acceptance threshold and validation ranking rules were frozen before either training or new validation prices.','']
        if best:lines+=[f'Best model passing both TRAIN and validation gates: `{best["config_id"]}`, validation net **{money(best["net_pnl"])}**, cash DD {money(best["realized_drawdown"])}, closing DD {money(best["max_drawdown"])}, intrabar DD **{money(best["intrabar_drawdown"])}**, {best["trades"]} trades. TRAIN net {money(best["training_net"])} and worst annual TRAIN intrabar DD {money(best["training_intrabar_drawdown"])}. Evaluation-account50% consistency diagnostic: {best["evaluation_phase_qualified"]}.','']
        for title,records in (('Top10 by validation results, with training flags',top),('Top10 meeting both training and validation gates',both[:10])):
            lines+=['## '+title,'','| Order | ID | Validation net | Intrabar DD | Trades | TRAIN qualifies | Validation qualifies | Beats original validation net with both gates |','|---:|---|---:|---:|---:|---|---|---|']
            for i,row in enumerate(records,1):lines.append(f'| {i} | `{row["config_id"]}` | {money(row["net_pnl"])} | {money(row["intrabar_drawdown"])} | {row["trades"]} | {row["training_qualified"]} | {row["qualified"]} | {row["beats_baseline"]} |')
            lines+=['']
        lines+=['## Frozen workflow and limits','',
            f'The new200k configurations are active-parameter/risk-budget unique and disjoint from{protocol["prior_unique_excluded"]:,} prior completed/reserved configurations across{protocol["prior_raw_cases"]:,} raw prior records. Original prior files and the concurrently running job were preserved. Same previously registered MNQ momentum/risk domains, new seed{protocol["seed"]}. All hypotheses, parameters, source hashes and ranking/acceptance criteria were frozen before prices. No training failure excluded a case from validation. All TRAIN results were sealed before validation prices were loaded.', '',
            'TRAIN: four annual2020–2023 accounts reset to$50,000, sum net and worst annual DD, with causal earlier TRAIN warmup and96/16 entry suppression. TRAIN qualification: all4 years positive,>=30trades/year,PF>=1.30,<=800total trades,no permanent/funded breach and allDD<2000. These are training metrics and historical development gates, not independent out-of-sample claims.', '',
            'VALIDATION: existing physical MNQ2024–2025 prices, one continuous$50,000 account per fixed case, split-local causal warmup and96/16 entry suppression. Rank validation-scenario passes first, then net descending,intrabarDD ascending,ID. Scenario pass requires positive net,all cash/closing/intrabar DD strictly<2000,>=30trades,no permanent lock and no funded-floor breach. Models failing training remain in the complete validation ranking with explicit flags. Good-model qualification additionally requires TRAIN qualification; superiority to baseline requires validation net above the frozen original-v1 validation reference. These are validation-selection criteria, not proof of future superiority.', '',
            'Execution and risk: unchanged completed15m raw-contract OHLCV, next-open entries, stops before ambiguous targets, strict target trade-through, adverse gaps, original volume/roll safeguards and modeled fees/spread/slippage/size impact. Registered risk scaling changes per-trade/open/daily budgets explicitly;1800 internal hard stop and2000 provisional funded floor remain. A permanent gap/risk lock fails qualification even if terminal profit is positive and DD remains below2000. Flat marks after a lock are not continued trading. Actual fees, holiday schedules and exact account contract permissions remain unverified.', '',
            'The user scopes50% consistency only to account evaluation phase; it is shown as a separate diagnostic and did not change executions. No doubled-cost validation variants were run. No follow-up configurations, retries for passing validation, or test evaluations are authorized/triggered by these rankings. The frozen selected model is RESEARCH-ONLY, not automatically promoted or deployed. Fresh forward observations are necessary for independent confirmation.', '',
            f'All{trade_count:,} stored validation trades were independently reconciled to contract P&L minus fees and case totals. Exactly200,000 unique consumed SQLite attempt reservations are linked to the immutable cohort/global reservation and data version; all states are done. Ranked CSV/configuration/metadata/source/database identities reconcile. Raw account paths for final top10 overall and top10 both-qualified cases were captured during their single execution, not regenerated by backtesting. Their curves reconcile and up to25 fixed chronological shared-simulator fills were checked from saved outputs. Full risk-path equivalence to that older simulator is not claimed.', '',
            '## Artifacts','', '- Full200k validation ranking: `../runs/validation_selection_200k_v1/validation_ranked.csv`','- Top100 overall: `../runs/validation_selection_200k_v1/top100_validation.csv`','- Top100 passing both sets of gates: `../runs/validation_selection_200k_v1/top100_train_and_validation.csv`','- All detailed metrics and compressed trade ledgers: `../runs/validation_selection_200k_v1/checkpoints.sqlite` (`val.ledger` contains zlib-compressed JSON of frozen bar entry/exit indexes, side, quantity, prices, net and fees)','- Frozen configurations, source, ranking/acceptance policy, phase seals and selected model: `../runs/validation_selection_200k_v1/`','- Top model curves and trade CSVs: `../runs/validation_selection_200k_v1/selected_artifacts/`','- Charts: `../runs/validation_selection_200k_v1/validation_top5.png` / `.svg`','']
        report=root/'reports/VALIDATION_SELECTION_200K.md';report.write_text('\n'.join(lines),encoding='utf-8')
        table='<table><tr><th>Order</th><th>ID</th><th>Validation net</th><th>Intrabar DD</th><th>Trades</th><th>TRAIN pass</th><th>Validation pass</th></tr>'
        for i,row in enumerate(both[:20] if both else top,1):table+=f'<tr><td>{i}</td><td><code>{html.escape(row["config_id"])}</code></td><td>{money(row["net_pnl"])}</td><td>{money(row["intrabar_drawdown"])}</td><td>{row["trades"]}</td><td>{row["training_qualified"]}</td><td>{row["qualified"]}</td></tr>'
        table+='</table>'
        page='<!doctype html><meta charset="utf-8"><title>200k validation model selection</title><style>body{font:15px/1.6 system-ui;background:#111820;color:#e8eef5;max-width:1250px;margin:36px auto;padding:0 24px}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #354154;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}img{width:100%;background:white}</style><h1>200,000 strategies: validation model selection</h1><p>'+html.escape(decision)+'. Validation used for selection; no independent confirmation. Test remains unopened by this batch.</p>'+table+'<h2>Top validation-selected curves</h2><img alt="Top fixed strategies: validation equity and drawdown" src="../runs/validation_selection_200k_v1/validation_top5.png"><details><summary>Complete report and audit details</summary><pre>'+html.escape('\n'.join(lines))+'</pre></details>'
        (root/'reports/VALIDATION_SELECTION_200K.html').write_text(page,encoding='utf-8')
        summary=dict(completed_new_configurations=200000,training_executions=200000,validation_executions=200000,counts=counts,decision=decision,baseline_validation_net=policy['baseline_validation_net'],best_both_qualified=best,top10_validation=top,top10_both_qualified=both[:10],validation_used_for_model_selection=True,parameters_changed_during_validation=False,test_accessed=False,independent_confirmation=False)
        json_write(root/'reports/VALIDATION_SELECTION_200K.json',summary)
        receipt=dict(passed=True,config_train_validation_ids_match=True,unique_new_configs=200000,prior_unique_excluded=len(prior),validation_attempts_done_once=200000,all_trade_ledgers_reconciled=True,trades_audited=trade_count,top_case_curves_reconciled=True,fill_verifications=verifications,ranking_rule_verified=True,acceptance_policy_frozen_and_preserved=True,source_hashes_match=True,test_accessed=False,independent_confirmation=False,report_sha256=file_hash(report),ranking_sha256=file_hash(run/'validation_ranked.csv'),completed_at=batch.now())
        json_write(root/'reports/VALIDATION_SELECTION_200K_verification.json',receipt)
        print(json.dumps(dict(passed=True,counts=counts,decision=decision,best_id=best['config_id'] if best else None,report=str(report))))
    finally:db.close()


if __name__=='__main__':main()

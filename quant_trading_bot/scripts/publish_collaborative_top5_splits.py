"""Publish/reconcile saved top-five validation/test artifacts without re-execution."""
import csv
import html
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import evaluate_collaborative_top5_splits as evaluation
from quant_futures.config import file_hash
from quant_futures.research import json_write
from build_light_dashboard_charts import sampled_ids

REASONS={0:'none',1:'maximum drawdown',2:'gap in usable bars',3:'unreconciled rollover',4:'funded scenario floor'}


def main():
    manifest,frozen=evaluation.verify();folder=evaluation.DIRECTORY;root=evaluation.ROOT
    records=[];all_trades=[];summary=[];checks=[]
    fig,axes=plt.subplots(5,4,figsize=(19,16),layout='constrained')
    lines=['# Frozen top five: validation and test without tuning','',
        '**All five displayed training candidates were frozen before new price access. Each was evaluated once on validation and once on test, at identical base costs. No parameter, feature, filter, sizing, stop, cost or candidate selection changed between stages.**','',
        'Validation: existing2024–2025 physical MNQ partition. Test: existing2026 partition through its saved coverage end. Each candidate/split uses one continuous$50,000 account, split-local feature warmup and the original96-bar entry embargo/16-bar terminal entry purge. Training totals shown below sum four separate2020–2023 annual accounts; those training drawdowns are worst-year figures. Validation/test drawdown covers the entire respective continuous split account.','',
        '**These periods have been observed in earlier work. This is an explicitly requested reused-period evaluation, not independent unseen confirmation.**','',
        '| Training rank / ID | Family | Training net | Validation net | Validation intrabar DD | Val trades | Val permanent lock | Test net | Test intrabar DD | Test trades | Both profit/DD checks |',
        '|---|---|---:|---:|---:|---:|---|---:|---:|---:|---|']
    reservations=[]
    for i,c in enumerate(frozen['candidates']):
        phases={}
        for j,phase in enumerate(evaluation.PHASES):
            path=evaluation.case_path(c,phase);r=evaluation.read(path);m=r['metrics']
            completed=evaluation.read(folder/(phase+'_complete.json'))
            assert completed['cohort_hash']==manifest['cohort_hash'] and completed['result_hashes'][str(path)]==file_hash(path)
            assert r['cohort_hash']==manifest['cohort_hash'] and r['parameters']==c['parameters']
            assert r['parameter_variants_evaluated']==r['cost_variants_evaluated']==1 and r['no_tuning']
            assert m['execution_verification']['passed']
            reservation=evaluation.read(r['reservation']);reservations.append(r['reservation'])
            assert reservation['candidate_id']==c['candidate_id'] and reservation['parameters']==c['parameters'] and reservation['cohort_hash']==manifest['cohort_hash']
            assert reservation['cost_variants']==reservation['parameter_variants']==1
            if phase=='test':
                assert reservation['validation_result_hashes']==evaluation.validation_hashes(manifest,frozen)
            curve=pd.read_parquet(folder/r['curve_file']);trades=pd.read_parquet(folder/r['trade_file'])
            assert len(trades)==m['trades']
            equity=curve.equity.to_numpy();cash=curve.cash.to_numpy()
            peaks=np.maximum.accumulate(np.r_[50000.,equity])[1:]
            cashpeaks=np.maximum.accumulate(np.r_[50000.,cash])[1:]
            dd=peaks-curve.intrabar_worst_bound.to_numpy()
            for actual,expected in ((equity[-1]-50000,m['net_pnl']),(trades.net_pnl.sum(),m['net_pnl']),((peaks-equity).max(),m['max_drawdown']),((cashpeaks-cash).max(),m['realized_drawdown']),(dd.max(),m['intrabar_drawdown'])):
                np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)
            ids=np.unique(np.r_[sampled_ids(curve.equity,limit=300),dd.argmax()])
            x=curve.timestamp_utc.iloc[ids]
            ax=axes[i,j*2];ax.plot(x,equity[ids]-50000,linewidth=.9)
            ax.set_title(f'#{i+1} {phase}: net ${m["net_pnl"]:,.2f}')
            ax=axes[i,j*2+1];ax.plot(x,-dd[ids],color='#af4a5a',linewidth=.9)
            ax.axhline(-2000,color='red',linestyle='--',linewidth=.6)
            ax.set_title(f'#{i+1} {phase}: intrabar DD ${m["intrabar_drawdown"]:,.2f}')
            for ax in axes[i,j*2:j*2+2]:
                ax.grid(alpha=.15);ax.set_ylabel('USD');ax.tick_params(axis='both',labelsize=7)
            export=trades.copy();export.insert(0,'phase',phase);export.insert(0,'candidate_id',c['candidate_id']);export.insert(0,'training_rank',i+1);all_trades.append(export)
            last_exit=str(trades.exit_time.iloc[-1]) if len(trades) else None
            row=dict(training_rank=i+1,candidate_id=c['candidate_id'],family=c['parameters']['family'],phase=phase,**{k:m[k] for k in ('net_pnl','realized_drawdown','max_drawdown','intrabar_drawdown','trades','profit_factor','expectancy','consistency','lock')},lock_reason=REASONS[m['lock']],last_trade_exit=last_exit,profit_and_dd_pass=r['profit_and_dd_pass'],post_evaluation_scenario_checks_pass=r['post_evaluation_scenario_checks_pass'],evaluation_phase_checks_pass=r['evaluation_phase_checks_pass'])
            records.append(row);phases[phase]=r
            checks.append(dict(candidate_id=c['candidate_id'],phase=phase,execution_verification=m['execution_verification'],curve_and_trade_reconciliation=True))
        v=phases['validation'];t=phases['test'];vm=v['metrics'];tm=t['metrics']
        both=v['profit_and_dd_pass'] and t['profit_and_dd_pass']
        summary.append(dict(training_rank=i+1,candidate_id=c['candidate_id'],validation=v,test=t,both_profit_dd_pass=both,both_post_evaluation_scenario_pass=v['post_evaluation_scenario_checks_pass'] and t['post_evaluation_scenario_checks_pass'],both_evaluation_phase_pass=v['evaluation_phase_checks_pass'] and t['evaluation_phase_checks_pass']))
        lines.append(f'| {i+1}: `{c["candidate_id"]}` | {c["parameters"]["family"]} | ${c["training"]["net_pnl"]:,.2f} | ${vm["net_pnl"]:,.2f} | ${vm["intrabar_drawdown"]:,.2f} | {vm["trades"]} | {REASONS[vm["lock"]]} | ${tm["net_pnl"]:,.2f} | ${tm["intrabar_drawdown"]:,.2f} | {tm["trades"]} | {"PASS" if both else "FAIL"} |')
    assert len(records)==len(reservations)==len(set(reservations))==10
    val_pass=sum(r['profit_and_dd_pass'] for r in records if r['phase']=='validation')
    test_pass=sum(r['profit_and_dd_pass'] for r in records if r['phase']=='test')
    both=sum(r['both_profit_dd_pass'] for r in summary)
    scenario=sum(r['both_post_evaluation_scenario_pass'] for r in summary)
    eval_pass=sum(r['both_evaluation_phase_pass'] for r in summary)
    lines+=['','## Outcome','',f'Profitability plus all three drawdown measures strictly below$2,000: **{val_pass}/5 on validation, {test_pass}/5 on test, {both}/5 on both**. Additional scenario checks on both splits (at least30 trades, no permanent risk lock or funded-floor breach): **{scenario}/5**. Including the50% evaluation-account consistency diagnostic on both splits: **{eval_pass}/5**.','',
        'All reported test outcomes were produced after every validation evaluation finished, on the same frozen versions, irrespective of validation gains/losses. A positive test does not erase a validation loss. The original$1,800 internal drawdown stop can lock an account before the outer$2,000 reporting threshold; a positive-net/sub-$2,000 case with a permanent lock still fails the additional scenario checks. Flat marks after a lock do not represent continued trading.','',
        '## Complete split metrics','', '| Rank | Split | Net | Cash DD | Closing DD | Intrabar DD | Trades | 50% consistency | Scenario without50% | Evaluation-account scenario | Last trade exit UTC |','|---:|---|---:|---:|---:|---:|---:|---|---|---|---|']
    for r in records:
        ratio='undefined' if r['consistency'] is None else f'{r["consistency"]:.2%}'
        lines.append(f'| {r["training_rank"]} | {r["phase"]} | ${r["net_pnl"]:,.2f} | ${r["realized_drawdown"]:,.2f} | ${r["max_drawdown"]:,.2f} | ${r["intrabar_drawdown"]:,.2f} | {r["trades"]} | {ratio} | {r["post_evaluation_scenario_checks_pass"]} | {r["evaluation_phase_checks_pass"]} | {r["last_trade_exit"]} |')
    lines+=['','The user-provided50% consistency rule applies only to the account evaluation phase. Chronological validation/test partitions are not account phases, so both account-phase interpretations are reported without modifying execution. Actual account contract terms, all-in fees, holidays and operational eligibility remain unverified.','',
        '## Frozen rules and audit','',
        'Original completed15-minute raw-contract bars, causal indicators, next-open fills, adverse stop gaps, conservative stop-first ambiguity, strict target trade-through, volume/contract safeguards and fees/spread/slippage remained unchanged. Each of the10 executions has an exclusive per-candidate/split reservation, trade ledger, equity/cash/intrabar curve, execution verification and result hash. Test reservations record all five completed validation-result hashes, verified again after testing. Frozen code/configuration hashes and prior training artifacts reconcile. No holdout result guided changes or further candidates.','',
        f'Cohort hash: `{manifest["cohort_hash"]}`. Three reservation/order/tamper guard tests passed before any evaluation. All10 ledgers and curves reconcile to their reported net and drawdowns. This publication only reads saved artifacts; it does not replay strategies.','',
        'Test coverage: '+str(frozen['partitions']['test']['metadata']['coverage'])+'. Validation coverage: '+str(frozen['partitions']['validation']['metadata']['coverage'])+'.','',
        'Results retain the original training order. They do not authorize a new selection/tuning cycle on these observed periods. Fresh forward observations are required for independent confirmation.','',
        '## Frozen configurations','', '```json',json.dumps([{k:c[k] for k in ('display_rank','candidate_id','parameters')} for c in frozen['candidates']],indent=2),'```','',
        'Artifacts: `../runs/collaborative_top5_splits_v1/frozen_cohort.json`, `split_metrics.csv`, `all_trades.csv`, per-candidate result JSON/curve/trade Parquet, `top5_split_curves.png`, `top5_split_curves.svg`. Machine summary: `COLLABORATIVE_TOP5_SPLITS.json`. Verification: `COLLABORATIVE_TOP5_SPLITS_verification.json`.','']
    fig.suptitle('Five frozen MNQ strategies: validation then test, no tuning\nOne continuous $50k account per candidate/split; reused periods; curves sampled',fontsize=13)
    plt.rcParams['svg.fonttype']='none'
    fig.savefig(folder/'top5_split_curves.png',dpi=115);fig.savefig(folder/'top5_split_curves.svg');plt.close(fig)
    pd.DataFrame(records).to_csv(folder/'split_metrics.csv',index=False)
    pd.concat(all_trades,ignore_index=True).to_csv(folder/'all_trades.csv',index=False)
    report=root/'reports/COLLABORATIVE_TOP5_SPLITS.md';report.write_text('\n'.join(lines),encoding='utf-8')
    cards=''
    for r in summary:
        v=r['validation']['metrics'];t=r['test']['metrics']
        cards+=f'<tr><td>{r["training_rank"]}</td><td><code>{html.escape(r["candidate_id"])}</code></td><td>${v["net_pnl"]:,.2f}</td><td>${v["intrabar_drawdown"]:,.2f}</td><td>{REASONS[v["lock"]]}</td><td>${t["net_pnl"]:,.2f}</td><td>${t["intrabar_drawdown"]:,.2f}</td><td>{"PASS" if r["both_profit_dd_pass"] else "FAIL"}</td></tr>'
    page='<!doctype html><meta charset="utf-8"><title>Frozen top five split evaluation</title><style>body{font:15px/1.6 system-ui;background:#111820;color:#e8eef5;max-width:1300px;margin:36px auto;padding:0 20px}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #3d4c60;text-align:left}img{width:100%;background:white}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#9acbff}</style>'
    page+=f'<h1>Five frozen strategies: validation and test</h1><p>No tuning. {both}/5 passed positive net and all DD &lt;$2,000 on both splits; {scenario}/5 also passed additional scenario checks on both. Previously observed periods; independent confirmation remains unavailable.</p><table><tr><th>Training rank</th><th>ID</th><th>Validation net</th><th>Val intrabar DD</th><th>Val lock</th><th>Test net</th><th>Test intrabar DD</th><th>Both profit/DD</th></tr>'+cards+'</table><h2>Equity and drawdown curves</h2><img alt="Five frozen strategies: validation and test equity and drawdown" src="../runs/collaborative_top5_splits_v1/top5_split_curves.png"><details><summary>Complete report and audit details</summary><pre>'+html.escape('\n'.join(lines))+'</pre></details>'
    (root/'reports/COLLABORATIVE_TOP5_SPLITS.html').write_text(page,encoding='utf-8')
    counts=dict(validation_profit_dd_pass=val_pass,test_profit_dd_pass=test_pass,both_profit_dd_pass=both,both_post_evaluation_scenario_pass=scenario,both_evaluation_phase_pass=eval_pass)
    json_write(root/'reports/COLLABORATIVE_TOP5_SPLITS.json',dict(cohort_hash=manifest['cohort_hash'],frozen_ids=list(evaluation.IDS),summary=summary,counts=counts,no_tuning=True,validation_executions=5,test_executions=5,independent_confirmation=False,operational_eligibility=False))
    json_write(root/'reports/COLLABORATIVE_TOP5_SPLITS_verification.json',dict(passed=True,publication_only_no_replay=True,frozen_parameters_and_sources_identical=True,exclusive_reservations=10,all_validation_completed_before_test=True,validation_hashes_preserved=True,all10_curves_and_trade_ledgers_reconciled=True,execution_checks=checks,counts=counts,report_sha256=file_hash(report),independent_confirmation=False))
    print(json.dumps(dict(passed=True,counts=counts,report=str(report))))


if __name__=='__main__': main()

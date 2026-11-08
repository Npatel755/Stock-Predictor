"""Reconcile/report the unchanged refined version's saved split evaluations."""
import html
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import evaluate_e57_refined_splits as evaluation
from quant_futures.config import file_hash
from quant_futures.research import json_write
from build_light_dashboard_charts import sampled_ids

REASONS={0:'none',1:'maximum drawdown',2:'gap in usable market data',3:'unreconciled rollover',4:'funded scenario floor'}


def main():
    manifest,frozen=evaluation.verify();folder=evaluation.DIRECTORY;root=evaluation.ROOT
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained');results={};rows=[];logs=[]
    for i,phase in enumerate(('validation','test')):
        path=folder/(phase+'_result.json');r=evaluation.read(path);m=r['metrics'];results[phase]=r
        assert r['parameters']==frozen['parameters'] and r['frozen_candidate_hash']==manifest['candidate_hash']
        assert r['parameter_variants_evaluated']==r['cost_variants_evaluated']==1 and r['no_tuning']
        assert evaluation.read(folder/(phase+'_complete.json'))['result_sha256']==file_hash(path)
        reservation=evaluation.read(r['reservation'])
        assert reservation['parameters']==frozen['parameters'] and reservation['frozen_candidate_hash']==manifest['candidate_hash']
        if phase=='test':assert reservation['validation_result_sha256']==file_hash(folder/'validation_result.json')
        assert m['execution_verification']['passed']
        curve=pd.read_parquet(folder/r['curve_file']);trades=pd.read_parquet(folder/r['trade_file'])
        equity=curve.equity.to_numpy();cash=curve.cash.to_numpy()
        peak=np.maximum.accumulate(np.r_[50000.,equity])[1:];cashpeak=np.maximum.accumulate(np.r_[50000.,cash])[1:]
        dd=peak-curve.intrabar_worst_bound.to_numpy()
        assert len(trades)==m['trades']
        for actual,expected in ((equity[-1]-50000,m['net_pnl']),(trades.net_pnl.sum(),m['net_pnl']),((peak-equity).max(),m['max_drawdown']),((cashpeak-cash).max(),m['realized_drawdown']),(dd.max(),m['intrabar_drawdown'])):
            np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)
        ids=np.unique(np.r_[sampled_ids(curve.equity,limit=400),dd.argmax()]);x=curve.timestamp_utc.iloc[ids]
        axes[i,0].plot(x,equity[ids]-50000,linewidth=1);axes[i,0].set_title(phase.title()+' net P&L')
        axes[i,1].plot(x,-dd[ids],color='#af4a5a',linewidth=1);axes[i,1].axhline(-2000,color='red',linestyle='--',linewidth=.7);axes[i,1].set_title(phase.title()+' intrabar drawdown bound')
        for ax in axes[i]:ax.grid(alpha=.15);ax.set_ylabel('USD');ax.tick_params(axis='x',labelsize=8)
        row=dict(phase=phase,**{k:m[k] for k in ('net_pnl','realized_drawdown','max_drawdown','intrabar_drawdown','trades','profit_factor','expectancy','consistency','lock')},lock_reason=REASONS[m['lock']],last_trade_exit=str(trades.exit_time.iloc[-1]) if len(trades) else None,profit_and_dd_pass=r['profit_and_dd_pass'],post_evaluation_scenario_checks_pass=r['post_evaluation_scenario_checks_pass'],evaluation_phase_checks_pass=r['evaluation_phase_checks_pass'])
        rows.append(row);logs.append(trades.assign(phase=phase))
    fig.suptitle('Refined MNQ momentum v1.2.0: validation then test, no tuning\nOne continuous $50k account per split; previously observed periods; curves sampled')
    plt.rcParams['svg.fonttype']='none';fig.savefig(folder/'split_curves.png',dpi=130);fig.savefig(folder/'split_curves.svg');plt.close(fig)
    pd.DataFrame(rows).to_csv(folder/'split_metrics.csv',index=False);pd.concat(logs,ignore_index=True).to_csv(folder/'all_trades.csv',index=False)
    both=all(r['profit_and_dd_pass'] for r in results.values())
    lines=['# Refined v1.2.0: validation then test without tuning','',f'Frozen strategy `{evaluation.ID}` (`{frozen["version"]}`). **Exactly one base-cost evaluation per split. No parameters, features, filters, sizing, costs, exits or risk limits changed between validation and test.**','',
        '| Split | Net P&L | Realized-cash DD | Closing DD | Intrabar DD | Trades | Permanent lock | Profit/DD result |','|---|---:|---:|---:|---:|---:|---|---|']
    for r in rows:lines.append(f'| {r["phase"]} | ${r["net_pnl"]:,.2f} | ${r["realized_drawdown"]:,.2f} | ${r["max_drawdown"]:,.2f} | ${r["intrabar_drawdown"]:,.2f} | {r["trades"]} | {r["lock_reason"]} | {"PASS" if r["profit_and_dd_pass"] else "FAIL"} |')
    lines+=['','## Conclusion','',f'Positive net P&L with cash, closing and intrabar DD each strictly below$2,000 on both splits: **{"PASS" if both else "FAIL"}**. A positive test does not cancel a validation loss or permanent data/risk lock.','',
        'Validation ended with a small loss and a permanent market-data-gap lock. Flat equity after that lock does not represent continued trading. The frozen risk guard was preserved; it was not removed to obtain more trades or a better result. Test was run afterward on the same version regardless of validation outcome.','',
        '| Split | Last trade exit UTC | 50% consistency ratio | Scenario without evaluation-only50% gate | Evaluation-account scenario |','|---|---|---|---|']
    for r in rows:
        ratio='undefined (nonpositive net)' if r['consistency'] is None else f'{r["consistency"]:.2%}'
        lines.append(f'| {r["phase"]} | {r["last_trade_exit"]} | {ratio} | {r["post_evaluation_scenario_checks_pass"]} | {r["evaluation_phase_checks_pass"]} |')
    lines+=['','The50% consistency diagnostic applies only to the account evaluation phase, per user instruction; it does not define the chronological validation/test split. Both account-phase scenarios are reported on identical executions. Test consistency exceeds50%, so that evaluation-account scenario fails even though test profit/DD/no-lock checks pass. Actual account contract terms and all-in costs remain unverified.','',
        '## Data separation and verification','',
        'Validation uses the existing physical MNQ2024–2025 partition; test uses the existing physical MNQ2026 partition. Both periods were observed in earlier work and cannot provide independent unseen confirmation. The parent was selected after old holdout observations, and this refined version was selected using training only. No new outcome was used to change any rule or evaluate alternatives.','',
        'Frozen parameters, execution settings, risk adapter, code hashes and both data identities were saved before split-price access. Exclusive per-split reservations record one parameter/cost case and consume the version even on failure. Validation completed before test prices were loaded; the validation result hash was recorded before test and verified afterward. Restart behavior reuses completed results. The immutable original/refined version archives remain unchanged.','',
        'Each split uses one continuous$50,000 account, split-local causal indicator warmup, the original first96/last16 entry suppression, complete15-minute raw-contract bars and original next-open execution/fill/risk semantics. No annual resets occur within these split accounts. All saved net, cash/closing/intrabar drawdowns and trade counts reconcile to both ledgers and curves. Independent ledger/fill checks passed; full account-path equivalence with the older comparison simulator is not claimed. Two reservation/order/tamper guard tests passed before evaluation. This publication only reads saved results and does not replay trades.','',
        'Coverage:','']
    for phase in ('validation','test'):lines.append(f'- {phase}: {results[phase]["source_coverage"]}')
    lines+=['','Frozen parameters:','', '```json',json.dumps(frozen['parameters'],indent=2),'```','',f'Frozen candidate hash: `{manifest["candidate_hash"]}`.','',
        'Artifacts: `../runs/e57_refined_validation_test_v1/frozen_candidate.json`, `validation_result.json`, `test_result.json`, `split_metrics.csv`, `validation_trades.csv`, `test_trades.csv`, `all_trades.csv`, `split_curves.png`, `split_curves.svg`, and archived code.','',
        '**Status: RESEARCH-ONLY; fails profitability/no-lock requirements on validation. No strategy promotion or live execution. Further development must remain training-only and cannot use these consumed outcomes to tune.**','']
    report=root/'reports/E57_REFINED_VALIDATION_TEST.md';report.write_text('\n'.join(lines),encoding='utf-8')
    page='<!doctype html><meta charset="utf-8"><title>Refined v1.2.0 validation/test</title><style>body{font:15px/1.6 system-ui;background:#111820;color:#e8eef5;max-width:1200px;margin:40px auto;padding:0 24px}pre{white-space:pre-wrap;overflow-wrap:anywhere}img{width:100%;background:white}</style><h1>Refined v1.2.0: validation and test</h1><pre>'+html.escape('\n'.join(lines))+'</pre><img alt="Validation and test equity and intrabar drawdown" src="../runs/e57_refined_validation_test_v1/split_curves.png">'
    (root/'reports/E57_REFINED_VALIDATION_TEST.html').write_text(page,encoding='utf-8')
    summary=dict(candidate_id=evaluation.ID,version=frozen['version'],frozen_candidate_hash=manifest['candidate_hash'],metrics=rows,both_profit_dd_pass=both,no_tuning=True,validation_evaluations=1,test_evaluations=1,independent_confirmation=False,operational_eligibility=False)
    json_write(root/'reports/E57_REFINED_VALIDATION_TEST.json',summary)
    json_write(root/'reports/E57_REFINED_VALIDATION_TEST_verification.json',dict(passed=True,frozen_configuration_execution_and_source_unchanged=True,validation_before_test=True,validation_hash_preserved=True,each_split_once=True,ledger_curve_metrics_reconciled=True,version_archives_preserved=True,publication_only_no_replay=True,report_sha256=file_hash(report),independent_confirmation=False))
    registry=root/'research/strategy_memory/events.jsonl'
    with registry.open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(schema_version=1,record_type='result',strategy_id=evaluation.ID,version=frozen['version'],run_id='e57_refined_validation_test_v1',result=summary,decision='VALIDATION_FAILURE_RESEARCH_ONLY',lesson='Preserve validation loss and data-gap lock; do not tune or remove risk guard from holdout outcomes.',artifact=str(report),recorded_at=evaluation.now()))+'\n')
    print(json.dumps(summary))


if __name__=='__main__':main()

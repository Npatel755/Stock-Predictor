"""Report the saved training candidate's unchanged validation/test evaluations."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import evaluate_saved_50k_candidate as evaluation
from quant_futures.config import file_hash
from quant_futures.research import json_write
from build_light_dashboard_charts import svg

ROOT=evaluation.ROOT
REASONS={0:None,1:'maximum drawdown',2:'gap in usable bars',3:'unreconciled rollover',4:'funded scenario floor'}


def main():
    manifest,frozen=evaluation.verify();folder=evaluation.DIRECTORY
    phases={};summary={}
    for phase in ('validation','test'):
        r=evaluation.read(folder/(phase+'_result.json'));m=r['metrics']
        assert r['parameters']==frozen['parameters'] and r['frozen_candidate_hash']==manifest['candidate_hash']
        assert r['parameter_variants_evaluated']==r['cost_variants_evaluated']==1
        curve=pd.read_parquet(folder/r['curve_file']);trades=pd.read_parquet(folder/r['trade_file'])
        assert len(trades)==m['trades']
        peaks=np.maximum.accumulate(np.r_[50000.,curve.equity.to_numpy()])[1:]
        cp=np.maximum.accumulate(np.r_[50000.,curve.cash.to_numpy()])[1:]
        for actual,expected in [(curve.equity.iloc[-1]-50000,m['net_pnl']),(trades.net_pnl.sum(),m['net_pnl']),
            (max(peaks-curve.equity),m['max_drawdown']),(max(cp-curve.cash),m['realized_drawdown']),
            (max(peaks-curve.intrabar_worst_bound),m['intrabar_drawdown'])]:
            np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)
        image,_=svg(curve,m,'Saved MNQ trend strategy · '+phase+' · reused period')
        (ROOT/'dashboard/assets'/('saved-50k-'+phase+'.svg')).write_text(image,encoding='utf-8')
        last=str(trades.exit_time.iloc[-1]) if len(trades) else None
        summary[phase]=dict(metrics={k:m[k] for k in ('net_pnl','realized_drawdown','max_drawdown','intrabar_drawdown','trades','consistency','lock')},
            checks=r['checks'],profit_and_dd_pass=r['profit_and_dd_pass'],evaluation_phase_checks_pass=r['evaluation_phase_checks_pass'],
            post_evaluation_scenario_checks_pass=r['post_evaluation_scenario_checks_pass'],lock_reason=REASONS[m['lock']],
            last_trade_exit=last,source_coverage=r['source_coverage'])
        phases[phase]=r
    test_reservation=evaluation.read(phases['test']['reservation'])
    assert test_reservation['validation_result_sha256']==file_hash(folder/'validation_result.json')
    lines=['# Saved MNQ trend strategy: unchanged validation then test','',
        f"Candidate `{evaluation.ID}` is permanently saved with its original training parameters and source hashes. It was the highest base-qualified net-profit candidate in the new50k training search. Its stored training net was$9,972.50 and worst annual intrabar DD$1,478. Training totals cover four separate yearly2020–2023 accounts.",'',
        '**Both later stages used the exact frozen configuration: validation once, followed by test once, at base costs. No tuning, fitting, parameter changes, cost variants or alternate candidates were evaluated between outcomes.**','',
        '| Metric | Validation 2024–2025 | Test 2026 |','|---|---:|---:|']
    for label,key in [('Net P&L','net_pnl'),('Realized-cash DD','realized_drawdown'),('Closing-equity DD','max_drawdown'),('Intrabar DD bound','intrabar_drawdown')]:
        lines.append(f"| {label} | ${phases['validation']['metrics'][key]:,.2f} | ${phases['test']['metrics'][key]:,.2f} |")
    for label,key in [('Trades','trades'),('Profit + DD checks','profit_and_dd_pass'),('Evaluation-phase scenario checks','evaluation_phase_checks_pass'),('Post-evaluation scenario checks','post_evaluation_scenario_checks_pass')]:
        a=phases['validation']['metrics'][key] if key=='trades' else phases['validation'][key]
        b=phases['test']['metrics'][key] if key=='trades' else phases['test'][key]
        lines.append(f'| {label} | {a} | {b} |')
    lines+=['','## Outcome and safety locks','',
        'Validation **failed profitability and the no-permanent-lock check**. It stayed below$2,000 drawdown, but the original$1,800 internal safety margin triggered a maximum-drawdown lock. Later flat marks are not additional trading performance. Test was evaluated afterward on the identical configuration, as authorized; it returned a positive net and passed the recorded scenario checks. A positive test does not conceal the validation failure.','']
    for phase,data in summary.items():
        lines.append(f"{phase.title()}: last recorded trade exit {data['last_trade_exit']}; permanent lock: {data['lock_reason'] or 'none'}. Source coverage: {data['source_coverage']['start']} through {data['source_coverage']['end']} UTC.")
    lines+=['','## Account phase versus data split','',
        'Per the user instruction, the50% consistency rule is scoped to the **account evaluation phase only**. A chronological validation/test split is not itself an account phase. Both phase scenarios are therefore reported on each split, with the same executions. Consistency remains visible as a diagnostic, and the earlier doubled-cost training failure is preserved. This phase preference did not change entries, exits, stops, sizing or costs.', '',
        f"Validation consistency ratio: {phases['validation']['metrics']['consistency']} (undefined when total net is nonpositive). Test consistency ratio: {phases['test']['metrics']['consistency']:.2%}.",'',
        'The phase scope is user-provided, not an independently verified current account agreement. Exact funded-account eligibility, actual all-in fees and operational permission are not established.','',
        '## Data separation and reproducibility','',
        'Both periods had previously been observed during earlier research. These are explicitly requested reused-period diagnostics, not independent confirmation. Candidate selection and all parameters were frozen before either new evaluation. Separate exclusive reservations were written before price access; failures also consume the attempt. The validation result hash was recorded before test access and verified afterward. Prior training and test artifacts remain unchanged.', '',
        'Original complete15-minute aggregation, causal indicators, next-open execution, prior-volume participation, original risk limits and first96/last16 entry suppression were preserved. Each split uses one continuous$50,000 account with warmup within that split only.', '',
        'Frozen parameters:','', '```json',json.dumps(frozen['parameters'],indent=2),'```','',
        '[Saved frozen strategy](/saved50k/frozen_candidate.json) · [Validation trade CSV](/saved50k/validation_trades.csv) · [Test trade CSV](/saved50k/test_trades.csv) · [Dashboard](http://127.0.0.1:8511/#saved-50k-results)','']
    (ROOT/'reports/SAVED_50K_CANDIDATE_SPLITS.md').write_text('\n'.join(lines),encoding='utf-8')
    result=dict(candidate_id=evaluation.ID,path=str(folder),saved_candidate=str(ROOT/'reports/saved_training_candidates'/evaluation.ID/'candidate.json'),
        training_base_net=frozen['training_candidate']['net_pnl'],training_base_intrabar_dd=frozen['training_candidate']['intrabar_drawdown'],
        phase_policy=frozen['phase_policy'],frozen_candidate_hash=manifest['candidate_hash'],validation=summary['validation'],test=summary['test'],
        no_tuning=True,validation_evaluations=1,test_evaluations=1,parameters_identical=True,prior_artifacts_preserved=True,
        independent_confirmation=False,operational_eligibility=False)
    json_write(ROOT/'reports/saved_50k_candidate_summary.json',result)
    json_write(ROOT/'reports/saved_50k_candidate_verification.json',dict(passed=True,publication_only_no_replay=True,
        frozen_parameters_identical=True,validation_then_test_order_verified=True,each_stage_once=True,
        saved_curves_and_trades_reconciled=True,prior_artifacts_preserved=True,independent_confirmation=False))
    print(json.dumps({phase:summary[phase]['metrics'] for phase in ('validation','test')}))


if __name__=='__main__': main()

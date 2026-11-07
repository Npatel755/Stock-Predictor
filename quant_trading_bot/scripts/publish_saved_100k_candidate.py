"""Report the saved 100k training candidate's unchanged validation evaluation.

Strictly preserves test data untouched: no test evaluation, reservation, or data access.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import evaluate_saved_100k_candidate as evaluation
from quant_futures.config import file_hash
from quant_futures.research import json_write
from build_light_dashboard_charts import svg

ROOT=evaluation.ROOT
REASONS={0:None,1:'maximum drawdown',2:'gap in usable bars',3:'unreconciled rollover',4:'funded scenario floor'}


def main():
    manifest,frozen=evaluation.verify();folder=evaluation.DIRECTORY
    phase='validation'
    r=evaluation.read(folder/(phase+'_result.json'));m=r['metrics']
    assert r['parameters']==frozen['parameters'] and r['frozen_candidate_hash']==manifest['candidate_hash']
    assert r['parameter_variants_evaluated']==r['cost_variants_evaluated']==1
    assert r['test_data_accessed'] is False
    curve=pd.read_parquet(folder/r['curve_file']);trades=pd.read_parquet(folder/r['trade_file'])
    assert len(trades)==m['trades']
    peaks=np.maximum.accumulate(np.r_[50000.,curve.equity.to_numpy()])[1:]
    cp=np.maximum.accumulate(np.r_[50000.,curve.cash.to_numpy()])[1:]
    for actual,expected in [(curve.equity.iloc[-1]-50000,m['net_pnl']),(trades.net_pnl.sum(),m['net_pnl']),
        (max(peaks-curve.equity),m['max_drawdown']),(max(cp-curve.cash),m['realized_drawdown']),
        (max(peaks-curve.intrabar_worst_bound),m['intrabar_drawdown'])]:
        np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)
    image,_=svg(curve,m,'Saved 100k Candidate ('+evaluation.ID+') · Validation 2024-2025 · Reused Period')
    (ROOT/'dashboard/assets'/('saved-100k-'+phase+'.svg')).write_text(image,encoding='utf-8')
    last=str(trades.exit_time.iloc[-1]) if len(trades) else None
    validation_summary=dict(metrics={k:m[k] for k in ('net_pnl','realized_drawdown','max_drawdown','intrabar_drawdown','trades','consistency','lock')},
        checks=r['checks'],profit_and_dd_pass=r['profit_and_dd_pass'],evaluation_phase_checks_pass=r['evaluation_phase_checks_pass'],
        post_evaluation_scenario_checks_pass=r['post_evaluation_scenario_checks_pass'],lock_reason=REASONS[m['lock']],
        last_trade_exit=last,source_coverage=r['source_coverage'])
    validation_reservation=evaluation.read(r['reservation'])
    assert validation_reservation['phase']=='validation' and validation_reservation['no_tuning'] is True

    lines=['# Saved 100k MNQ trend candidate: unchanged validation evaluation','',
        f"Candidate `{evaluation.ID}` was selected from the 100k training search over 2020–2023 data. It was the highest base-qualified net-profit candidate ($13,920.50 training net, worst annual intrabar DD $1,593.00, surviving 2x costs at $6,677.50 net), topping the saved benchmark ($9,972.50).",'',
        '**Validation evaluation used the exact frozen configuration on MNQ 2024–2025 at base costs. No tuning, fitting, parameter variants, or alternatives were tested. Test data (2026) was strictly NOT touched or opened.**','',
        '| Metric | Training (2020–2023) | Validation (2024–2025) |',
        '|---|---:|---:|',
        f"| Net P&L | ${frozen['training_candidate']['net_pnl']:,.2f} | ${m['net_pnl']:,.2f} |",
        f"| Realized-cash DD | ${frozen['training_candidate']['realized_drawdown']:,.2f} | ${m['realized_drawdown']:,.2f} |",
        f"| Closing-equity DD | ${frozen['training_candidate']['max_drawdown']:,.2f} | ${m['max_drawdown']:,.2f} |",
        f"| Intrabar DD bound | ${frozen['training_candidate']['intrabar_drawdown']:,.2f} | ${m['intrabar_drawdown']:,.2f} |",
        f"| Trades | {frozen['training_candidate']['trades']} | {m['trades']} |",
        f"| Profit + DD checks (<$2,000 DD) | PASS | {'PASS' if r['profit_and_dd_pass'] else 'FAIL'} |",
        f"| Evaluation-phase scenario checks | {frozen['training_candidate']['evaluation_phase_qualified']} | {r['evaluation_phase_checks_pass']} |",
        f"| Post-evaluation scenario checks | {frozen['training_candidate']['qualified']} | {r['post_evaluation_scenario_checks_pass']} |",
        '','## Outcome and safety locks','',
        f"Validation net P&L: **${m['net_pnl']:,.2f}**. Intrabar drawdown: **${m['intrabar_drawdown']:,.2f}**. Trades: **{m['trades']}**.",
        f"Permanent lock: **{validation_summary['lock_reason'] or 'None'}**.",
        f"Last recorded trade exit: {last}. Source coverage: {r['source_coverage']['start']} through {r['source_coverage']['end']} UTC.",'',
        '## Account phase versus data split','',
        'Per the user instruction, the 50% consistency rule is scoped to the **account evaluation phase only**. A chronological validation/test split is not itself an account phase. Consistency remains visible as a diagnostic: ' + (f"{m['consistency']:.2%}" if m['consistency'] is not None else "undefined (nonpositive net)"),'',
        '## Data separation and test data protection','',
        'Per user instructions, **TEST DATA WAS NOT TOUCHED**. No test partition was resolved, no test reservation was made, and no 2026 test prices were opened. Validation was evaluated once on the frozen candidate without tuning.','',
        'Frozen parameters:','', '```json',json.dumps(frozen['parameters'],indent=2),'```','',
        f"[Saved frozen candidate](../runs/saved_100k_candidate_{evaluation.ID}/frozen_candidate.json) · [Validation trade CSV](../runs/saved_100k_candidate_{evaluation.ID}/validation_trades.csv) · [Dashboard](http://127.0.0.1:8511/#training-100k)",'']
    (ROOT/'reports/SAVED_100K_CANDIDATE_VALIDATION.md').write_text('\n'.join(lines),encoding='utf-8')
    result=dict(candidate_id=evaluation.ID,path=str(folder),saved_candidate=str(ROOT/'reports/saved_training_candidates'/evaluation.ID/'candidate.json'),
        training_base_net=frozen['training_candidate']['net_pnl'],training_base_intrabar_dd=frozen['training_candidate']['intrabar_drawdown'],
        phase_policy=frozen['phase_policy'],frozen_candidate_hash=manifest['candidate_hash'],validation=validation_summary,
        test_data_accessed=False,test_data_authorized=False,
        no_tuning=True,validation_evaluations=1,parameters_identical=True,prior_artifacts_preserved=True,
        independent_confirmation=False,operational_eligibility=False)
    json_write(ROOT/'reports/saved_100k_candidate_summary.json',result)
    json_write(ROOT/'reports/saved_100k_candidate_verification.json',dict(passed=True,publication_only_no_replay=True,
        frozen_parameters_identical=True,validation_evaluated_once=True,test_untouched=True,
        saved_curves_and_trades_reconciled=True,prior_artifacts_preserved=True,independent_confirmation=False))
    print(json.dumps(dict(validation=validation_summary['metrics'],test_untouched=True),indent=2))


if __name__=='__main__': main()

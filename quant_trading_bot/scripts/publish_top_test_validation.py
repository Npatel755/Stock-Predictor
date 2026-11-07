"""Reconcile/publish the requested #1 validation record, without replay."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import evaluate_top_test_validation as evaluation
from build_light_dashboard_charts import svg
from quant_futures.config import file_hash
from quant_futures.research import json_write

ROOT=evaluation.ROOT


def main():
    manifest,frozen=evaluation.verify()
    result=evaluation.read(ROOT/'reports/top_test_number1_validation.json')
    assert result['frozen_candidate_hash']==manifest['candidate_hash'] and result['parameters']==frozen['parameters']
    folder=Path(result['path']);m=result['metrics']
    curve=pd.read_parquet(folder/result['curve_file']);trades=pd.read_parquet(folder/result['trade_file'])
    assert len(trades)==m['trades']
    peaks=np.maximum.accumulate(np.r_[50000.,curve.equity.to_numpy()])[1:]
    cashpeaks=np.maximum.accumulate(np.r_[50000.,curve.cash.to_numpy()])[1:]
    for actual,expected in [(curve.equity.iloc[-1]-50000,m['net_pnl']),(trades.net_pnl.sum(),m['net_pnl']),
        (max(peaks-curve.equity),m['max_drawdown']),(max(cashpeaks-curve.cash),m['realized_drawdown']),
        (max(peaks-curve.intrabar_worst_bound),m['intrabar_drawdown'])]:
        np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)
    image,points=svg(curve,m,'#1 test-ranked MNQ breakout · reused validation 2024–2025')
    (ROOT/'dashboard/assets/top1-validation.svg').write_text(image,encoding='utf-8')
    saved_test=evaluation.read(frozen['saved_test_result'])
    reasons={0:None,1:'maximum drawdown',2:'gap in usable market bars',3:'unreconciled raw contract rollover',4:'funded scenario floor'}
    last_exit=str(trades.exit_time.iloc[-1]) if len(trades) else None
    note=(f"A permanent safety lock was triggered by {reasons[m['lock']]}. Last trade closed at {last_exit}. "
        'All later equity marks are flat because new entries were disabled. This is not uninterrupted trading over the full validation period.') if m['killed'] else 'No permanent safety lock occurred.'
    json_write(ROOT/'reports/top1_validation_dashboard.json',dict(candidate_id=result['candidate_id'],metrics=m,checks=result['checks'],
        permanent_lock_reason=reasons[m['lock']],last_trade_exit=last_exit,limitation=note,no_tuning=True,test_replayed=False,
        test_selected=True,validation_previously_observed=True,independent_confirmation=False,chart_points=points))
    lines=['# Displayed number1 strategy: requested validation diagnostic','',
        f"`{result['candidate_id']}` was ranked #1 by recorded test net P&L before validation access. Exactly that fixed MNQ breakout was evaluated once at base costs. No fitting, parameter changes, cost alternatives, validation-guided substitutions or test replay were performed.",'',
        '| Metric | Validation 2024–2025 | Saved test 2026 |','|---|---:|---:|']
    for label,key in [('Net P&L','net_pnl'),('Realized-cash drawdown','realized_drawdown'),('Closing-equity drawdown','max_drawdown'),('Intrabar drawdown bound','intrabar_drawdown')]:
        lines.append(f"| {label} | ${m[key]:,.2f} | ${saved_test['metrics'][key]:,.2f} |")
    lines.append(f"| Trades | {m['trades']} | {saved_test['metrics']['trades']} |")
    lines+=['','**Positive validation net and drawdowns below$2,000: PASS on the requested observations. Overall recorded risk scenario: FAIL because of the permanent safety lock.**','',note,'',
        'The supplied validation source covers '+result['source_coverage']['start']+' through '+result['source_coverage']['end']+' UTC. '
        'Only exact complete15-minute windows were aggregated; first96/last16 entry bars were suppressed under the unchanged protocol. One continuous$50,000 account was replayed. A missing usable quote cannot be replaced with an invented flattening fill.', '',
        'The validation period was previously viewed, and this candidate was selected using test outcomes. This is a reused-validation diagnostic, not independent confirmation or funded-account eligibility. The original training robustness failure and safety lock remain disclosed. Saved tests and earlier reservations remain byte-identical.', '',
        'Frozen parameters:','', '```json',json.dumps(result['parameters'],indent=2),'```','',
        'Recorded checks:','', '```json',json.dumps(result['checks'],indent=2),'```','',
        '[Dashboard](http://127.0.0.1:8511/#top1-validation) · [Saved result](top_test_number1_validation.json)','']
    (ROOT/'reports/TOP_TEST_NUMBER1_VALIDATION.md').write_text('\n'.join(lines),encoding='utf-8')
    receipt=dict(passed=True,publication_only_no_replay=True,parameters_match_frozen_test=True,
        saved_curve_and_trade_metrics_reconciled=True,prior_artifacts_preserved=True,validation_cases=1,cost_cases=1,
        test_replayed=False,independent_confirmation=False,result_sha256=file_hash(ROOT/'reports/top_test_number1_validation.json'))
    json_write(ROOT/'reports/top1_validation_verification.json',receipt);print(json.dumps(receipt))


if __name__=='__main__': main()

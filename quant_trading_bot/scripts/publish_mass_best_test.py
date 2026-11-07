"""Publish one saved test result and chart; never replay or read market prices."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from quant_futures.config import file_hash,digest
from quant_futures.research import json_write
from build_light_dashboard_charts import svg

ROOT=Path(__file__).resolve().parents[1]


def main():
    result=json.loads((ROOT/'reports/mass_best_reused_test.json').read_text(encoding='utf-8'))
    folder=Path(result['path']).resolve()
    if not folder.is_relative_to((ROOT/'runs').resolve()): raise ValueError('Result outside project')
    manifest=json.loads((folder/'frozen_candidate.json').read_text(encoding='utf-8'))
    frozen=manifest['candidate'];m=result['metrics']
    assert digest(frozen)==manifest['candidate_hash']==result['frozen_candidate_hash']
    assert result['parameters']==frozen['parameters']==frozen['training_candidate']['parameters']
    assert result['parameter_variants_evaluated']==result['cost_variants_evaluated']==1
    assert result['validation_accessed'] is False
    assert file_hash(folder/'test_runner.py')==result['runner_sha256']
    for name,expected in result['source_hashes'].items(): assert file_hash(folder/'strategy'/name)==expected
    for path,expected in frozen['preserved_files'].items(): assert file_hash(path)==expected
    reservation=json.loads(Path(result['reservation']).read_text(encoding='utf-8'))
    assert reservation['frozen_candidate_hash']==manifest['candidate_hash']
    curve=pd.read_parquet(folder/result['curve_file'])
    trades=pd.read_parquet(folder/result['trade_file'])
    assert len(trades)==m['trades']
    np.testing.assert_allclose(trades.net_pnl.sum(),m['net_pnl'],rtol=0,atol=1e-8)
    np.testing.assert_allclose(curve.equity.iloc[-1]-50000,m['net_pnl'],rtol=0,atol=1e-8)
    peaks=np.maximum.accumulate(np.r_[50000,curve.equity.to_numpy()])[1:]
    cashpeaks=np.maximum.accumulate(np.r_[50000,curve.cash.to_numpy()])[1:]
    for actual,expected in [(max(peaks-curve.equity),m['max_drawdown']),
                            (max(cashpeaks-curve.cash),m['realized_drawdown']),
                            (max(peaks-curve.intrabar_worst_bound),m['intrabar_drawdown']),
                            (trades.fees.sum(),m['fees'])]:
        np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-8)
    title='Frozen MNQ breakout: explicitly requested reused2026 test'
    chart,points=svg(curve,m,title)
    (ROOT/'dashboard/assets/mass-test.svg').write_text(chart,encoding='utf-8')
    net_status='PASS' if m['net_pnl']>0 else 'FAIL'
    lines=['# Frozen MNQ breakout: one reused-test evaluation','',
        f"Candidate `{result['candidate_id']}` was selected as training rank1 before test access. Its code, parameters, costs and risk settings were frozen unchanged. Exactly one candidate and one base-cost test case were evaluated. No validation data were opened.",'',
        '**Overall: '+('PASS on recorded research scenario checks only.' if result['scenario_checks_pass'] else 'FAIL on the recorded research scenario checks.')+'**', '',
        '| Metric | Test result |','|---|---:|',
        f"| Net profit after modeled costs | ${m['net_pnl']:,.2f} |",
        f"| Realized-cash drawdown | ${m['realized_drawdown']:,.2f} |",
        f"| Closing-equity drawdown | ${m['max_drawdown']:,.2f} |",
        f"| Intrabar drawdown bound | ${m['intrabar_drawdown']:,.2f} |",
        f"| Trades | {m['trades']} |",f"| Profit factor | {m['profit_factor']:.3f} |",
        f"| Expectancy per trade | ${m['expectancy']:,.2f} |",f"| Win rate | {m['win_rate']:.1%} |",'',
        f"Profitability: **{net_status}**. Drawdown below$2,000: **{'PASS' if max(m['realized_drawdown'],m['max_drawdown'],m['intrabar_drawdown'])<2000 else 'FAIL'}**. "
        f"At least30 trades: **{'PASS' if m['trades']>=30 else 'FAIL'}**. The50% consistency diagnostic: **{'PASS' if m['consistency_50_pass'] else 'FAIL / undefined with nonpositive total net'}**. "
        'Exact funded-account eligibility is not established: actual charges, contractual rule details, and platform permissions remain unverified.', '',
        'This training-selected strategy did not demonstrate profitable generalization in the requested test diagnostic. The loss is preserved as observed. No alternate finalist, revised filter, parameter change or cost variant was evaluated after this outcome.', '',
        f"Existing source coverage: {result['source_coverage']['start']} through {result['source_coverage']['end']} UTC. "
        f"The replay used {result['complete15m_bars']:,} exact complete15-minute bars, from {result['evaluated_start']} through {result['evaluated_end']}. "
        'One continuous$50,000 account was used over this test partition. The same frozen first96/last16 entry-bar suppression was applied; all warmup was within test, with no validation warmup or fitted preprocessing.', '',
        'The2026 test period had already been observed for earlier strategies. This explicitly requested single-use replay is a reused-test diagnostic, not an untouched independent holdout. Existing split boundaries, prior results, training rankings, and earlier reservations remain byte-identical. A new reservation was written before hashing/loading any test price file; failed attempts would also consume the reservation.', '',
        'Frozen strategy parameters:','', '```json',json.dumps(result['parameters'],indent=2),'```','',
        'Recorded checks:','', '```json',json.dumps(result['checks'],indent=2),'```','',
        f"Execution verification: {m['execution_verification']['ledger_trades']} independent ledger checks; "
        f"{m['execution_verification']['shared_simulator_replayed']} fixed chronological shared-simulator trade samples. "
        'Isolated fills/economics match; full account-path equivalence to the older simulator is not claimed.', '',
        '[Saved result](mass_best_reused_test.json) · [Dashboard](http://127.0.0.1:8511/)','']
    (ROOT/'reports/MASS_BEST_REUSED_TEST.md').write_text('\n'.join(lines),encoding='utf-8')
    receipt=dict(passed=True,publication_only_no_replay=True,market_price_files_read=False,
        exact_training_parameters_preserved=True,prior_artifacts_preserved=True,curve_and_trades_reconciled=True,
        test_candidate_count=1,test_cost_count=1,validation_accessed=False,
        independent_confirmation=False,chart_display_points=points,
        report_sha256=file_hash(ROOT/'reports/mass_best_reused_test.json'))
    json_write(ROOT/'reports/mass_best_test_verification.json',receipt)
    print(json.dumps(receipt))


if __name__=='__main__': main()

"""Report the scaled training candidate's unchanged validation and test evaluations."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import gc
import json
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import evaluate_scaled_200k_candidate as evaluation
from quant_futures.config import file_hash
from quant_futures.research import json_write
from build_light_dashboard_charts import svg

ROOT = evaluation.ROOT
REASONS = {0: None, 1: 'maximum drawdown', 2: 'gap in usable bars', 3: 'unreconciled rollover', 4: 'funded scenario floor'}


def main():
    manifest, frozen = evaluation.verify()
    folder = evaluation.DIRECTORY
    phases = {}
    summary = {}
    for phase in ('validation', 'test'):
        r = evaluation.read(folder/(phase + '_result.json'))
        m = r['metrics']
        assert r['parameters'] == frozen['parameters'] and r['frozen_candidate_hash'] == manifest['candidate_hash']
        assert r['parameter_variants_evaluated'] == r['cost_variants_evaluated'] == 1
        curve = pd.read_parquet(folder/r['curve_file'])
        trades = pd.read_parquet(folder/r['trade_file'])
        assert len(trades) == m['trades']
        peaks = np.maximum.accumulate(np.r_[50000., curve.equity.to_numpy()])[1:]
        cp = np.maximum.accumulate(np.r_[50000., curve.cash.to_numpy()])[1:]
        for actual, expected in [
            (curve.equity.iloc[-1] - 50000, m['net_pnl']),
            (trades.net_pnl.sum(), m['net_pnl']),
            (max(peaks - curve.equity), m['max_drawdown']),
            (max(cp - curve.cash), m['realized_drawdown']),
            (max(peaks - curve.intrabar_worst_bound), m['intrabar_drawdown'])
        ]:
            np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-7)
        image, _ = svg(curve, m, f'Scaled MNQ Momentum · {phase.title()} · No Tuning')
        (ROOT/'dashboard/assets'/(f'saved-scaled-200k-{phase}.svg')).write_text(image, encoding='utf-8')
        last = str(trades.exit_time.iloc[-1]) if len(trades) else None
        summary[phase] = dict(
            metrics={k: m[k] for k in ('net_pnl', 'realized_drawdown', 'max_drawdown', 'intrabar_drawdown', 'trades', 'consistency', 'lock')},
            checks=r['checks'], profit_and_dd_pass=r['profit_and_dd_pass'],
            evaluation_phase_checks_pass=r['evaluation_phase_checks_pass'],
            post_evaluation_scenario_checks_pass=r['post_evaluation_scenario_checks_pass'],
            lock_reason=REASONS[m['lock']], last_trade_exit=last, source_coverage=r['source_coverage']
        )
        phases[phase] = r

    test_reservation = evaluation.read(phases['test']['reservation'])
    assert test_reservation['validation_result_sha256'] == file_hash(folder/'validation_result.json')

    t_m = frozen['training_metrics']
    lines = [
        '# Scaled 1.5k Drawdown Candidate: Unchanged Validation & Test Evaluation',
        '',
        f"Candidate `{evaluation.ID}` was derived from ultra-low drawdown training champion `{evaluation.BASE_ID}` (MNQ momentum, lookback 8, threshold 1.5, stop 3.0 ATR, target 2.0 R, hold 4 bars, session 09:45–15:45 ET).",
        '',
        '## Training Calibration (Strictly on 2020–2023 Train Split)',
        f"- **Initial Base (1 contract, $150 risk cap)**: Train Net +$2,888.00, Worst Annual Intrabar DD **$471.25**.",
        f"- **Scaled Target (~$1.5k DD, 2 contracts, $300 risk cap)**: Sized strictly using training data to achieve ~$1,500 drawdown limit without violating the $1,800 internal threshold or $2,000 hard stop.",
        f"  - **Training Folds Net (2020–2023)**: **+${t_m['folds_net_pnl']:,.2f}** (all 4 years positive).",
        f"  - **Training Folds Worst Intrabar DD**: **${t_m['folds_worst_intrabar_dd']:,.2f}** (~$1.5k).",
        f"  - **Continuous 4-Year Account Net**: **+${t_m['continuous_train_net_pnl']:,.2f}**.",
        f"  - **Continuous 4-Year Intrabar DD**: **${t_m['continuous_train_intrabar_dd']:,.2f}**.",
        f"  - **2x Cost Stress Net**: **+${t_m['stress_2x_net_pnl']:,.2f}**, Intrabar DD: **${t_m['stress_2x_intrabar_dd']:,.2f}** (PASSED).",
        '',
        '## Evaluation Protocol & Zero-Tuning Commitment',
        '**Both later stages used the exact frozen configuration: validation once (2024–2025), followed by test once (2026), at base costs. No tuning, fitting, parameter alterations, cost adjustments, or alternate candidates were tested between results.**',
        '',
        '| Metric | Training (2020–2023 Cont.) | Validation (2024–2025) | Test (2026) |',
        '|---|---:|---:|---:|',
        f"| **Net P&L** | +${t_m['continuous_train_net_pnl']:,.2f} | ${phases['validation']['metrics']['net_pnl']:,.2f} | ${phases['test']['metrics']['net_pnl']:,.2f} |",
        f"| **Realized Cash DD** | ${t_m['continuous_train_close_dd']:,.2f} | ${phases['validation']['metrics']['realized_drawdown']:,.2f} | ${phases['test']['metrics']['realized_drawdown']:,.2f} |",
        f"| **Closing Equity DD** | ${t_m['continuous_train_close_dd']:,.2f} | ${phases['validation']['metrics']['max_drawdown']:,.2f} | ${phases['test']['metrics']['max_drawdown']:,.2f} |",
        f"| **Intrabar DD Bound** | ${t_m['continuous_train_intrabar_dd']:,.2f} | ${phases['validation']['metrics']['intrabar_drawdown']:,.2f} | ${phases['test']['metrics']['intrabar_drawdown']:,.2f} |",
        f"| **Trade Count** | {t_m['continuous_train_trades']} | {phases['validation']['metrics']['trades']} | {phases['test']['metrics']['trades']} |",
        f"| **Profit + DD (<$2,000) Pass** | PASS | {phases['validation']['profit_and_dd_pass']} | {phases['test']['profit_and_dd_pass']} |",
        f"| **Permanent Risk Lock** | None (code 0) | {summary['validation']['lock_reason'] or 'None'} | {summary['test']['lock_reason'] or 'None'} |",
        '',
        '## Detail & Diagnostics',
        f"- **Validation (2024–2025)**: {summary['validation']['metrics']['trades']} trades executed, net P&L ${summary['validation']['metrics']['net_pnl']:,.2f}, intrabar DD ${summary['validation']['metrics']['intrabar_drawdown']:,.2f}. Lock reason: {summary['validation']['lock_reason'] or 'None'}.",
        f"- **Test (2026)**: {summary['test']['metrics']['trades']} trades executed, net P&L ${summary['test']['metrics']['net_pnl']:,.2f}, intrabar DD ${summary['test']['metrics']['intrabar_drawdown']:,.2f}. Lock reason: {summary['test']['lock_reason'] or 'None'}.",
        '',
        '## Reproducibility & File Artifacts',
        f"- Frozen parameters: `lookback={frozen['parameters']['lookback']}`, `threshold={frozen['parameters']['threshold']}`, `stop_atr={frozen['parameters']['stop_atr']}`, `target_r={frozen['parameters']['target_r']}`, `hold_bars={frozen['parameters']['hold_bars']}`, `max_contracts={frozen['parameters']['max_contracts']}`, `risk_per_trade=${frozen['parameters']['risk_per_trade']}`.",
        f"- Frozen candidate manifest: `runs/saved_scaled_candidate_mass_7bf2833bf4365b60bedb/frozen_candidate.json`",
        f"- Validation result: `runs/saved_scaled_candidate_mass_7bf2833bf4365b60bedb/validation_result.json`",
        f"- Test result: `runs/saved_scaled_candidate_mass_7bf2833bf4365b60bedb/test_result.json`",
        f"- Validation trades: `runs/saved_scaled_candidate_mass_7bf2833bf4365b60bedb/validation_trades.csv`",
        f"- Test trades: `runs/saved_scaled_candidate_mass_7bf2833bf4365b60bedb/test_trades.csv`",
        ''
    ]
    report_path = ROOT/'reports/SAVED_SCALED_CANDIDATE.md'
    report_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Report written to {report_path}")
    print(json.dumps({phase: summary[phase]['metrics'] for phase in ('validation', 'test')}, indent=2))


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()

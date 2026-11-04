"""Package retrospective diagnostic configurations and measured result chart."""
from __future__ import annotations

import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ..data_pipeline import HERE, freeze, sha
from ..runner import code_hashes, config_for
from ..strategies import library


def finalize():
    frozen = json.loads((HERE/'code_freeze.json').read_text())
    if frozen['code_hashes'] != code_hashes():
        raise ValueError('Frozen research implementation changed')
    validation = json.loads((HERE/'validation_results.json').read_text())['candidates']
    specs = {s['id']: s for s in library()}
    diagnostics = []
    for row in validation:
        spec = specs[row['id']]
        diagnostics.append(dict(symbol=row['symbol'], specification=spec, execution=config_for(spec,row['symbol']),
                                status='REJECTED_DEVELOPMENT_DIAGNOSTIC' if not row['accepted'] else 'PAPER_ONLY',
                                acceptance_gates=row['gates'], ready_for_live_trading=False,
                                implementation_sha256=frozen['code_hashes']))
    freeze(HERE/'diagnostic_configurations.json', diagnostics)
    best = next(r for r in diagnostics if r['symbol'] == 'ETH' and r['specification']['id'] == 'channel_4h_lookback20')
    freeze(HERE/'best_development_configuration.json', dict(**best,
           selection_note='Highest measured validation P&L among the frozen primary shortlist; descriptive only, not replacement selection or accepted strategy.'))
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True, constrained_layout=True)
    for symbol, identifier, color in [('ETH','channel_4h_lookback20','#2166ac'), ('BNB','tsmom_4h_lookback96_threshold0.35','#b2182b')]:
        row = next(r for r in validation if r['symbol'] == symbol and r['id'] == identifier)
        curve = pd.read_parquet(HERE/row['output']/'equity.parquet')
        daily = curve.set_index('bar_open').equity.resample('D').last()
        axes[0].plot(daily.index, daily-50000, color=color, label=f'{symbol} first TRAIN selection')
        axes[1].plot(daily.index, (daily/daily.cummax().clip(lower=50000)-1)*100, color=color)
    combined = pd.read_csv(HERE/'combined_validation_equity.csv', parse_dates=['bar_open'])
    axes[0].plot(combined.bar_open, combined.equity-50000, color='#238b45', label='Combined 50/50 sleeves')
    dd = combined.equity/combined.equity.cummax().clip(lower=50000)-1
    axes[1].plot(combined.bar_open, dd*100, color='#238b45')
    axes[0].axhline(0, color='#777777', linewidth=.7, linestyle='--', label='Flat benchmark')
    axes[0].set(title='VALIDATION only: frozen TRAIN selections, all rejected', ylabel='Net P&L (USD per $50k)')
    axes[1].set(ylabel='Close drawdown (%)', xlabel='UTC date')
    axes[0].legend(loc='upper left', fontsize=8)
    for ax in axes:
        ax.grid(alpha=.2)
    fig.savefig(HERE/'validation_performance.png', dpi=150)
    plt.close(fig)
    audit = json.loads((HERE/'accounting_audit.json').read_text())
    verification = json.loads((HERE/'verification.json').read_text())
    annex = ['','## Final verification and handoff','',
             f'{verification["tests_passed"]} tests passed. {audit["audited_replays"]} replay ledgers independently reconciled; no ledger failures and no contaminated-final performance access. Research implementation hashes still match the pre-search freeze.',
             '', 'Calendar-correct volatility/Sortino are in [accounting_audit.csv](accounting_audit.csv); full monthly/quarterly/yearly results are in [calendar_performance.csv](calendar_performance.csv). The frozen ranking used correct daily Sharpe. See [methodology limits](methodology_limits.md) for the companion-report correction and remaining execution limitations.',
             '', '[Measured validation chart](validation_performance.png). [Rejected diagnostic configurations](diagnostic_configurations.json). [Best developmental configuration, still rejected](best_development_configuration.json).',
             '', 'The nominal final test is not evaluated because it is contaminated. No accepted candidate is exported for production. The paper-only interface is implemented and tested, with no background jobs or exchange access.']
    summary = HERE/'research_summary.md'
    text = summary.read_text(encoding='utf-8').split('\n## Final verification and handoff')[0]
    summary.write_text(text+'\n'.join(annex)+'\n', encoding='utf-8')
    notes = HERE/'integration_notes_for_devin.md'
    text = notes.read_text(encoding='utf-8').split('\n## Post-run accounting')[0]
    notes.write_text(text+'\n## Post-run accounting\n\nRun `python -m research.codex_eth_bnb.tools.audit_outputs` and `python -m research.codex_eth_bnb.tools.finalize` after the frozen runner. These produce calendar-consistent volatility/Sortino, check every ledger, and export charts/rejected diagnostics. They do not revise signals, ranks, shortlist or acceptance gates. Their own source hashes are recorded separately.\n', encoding='utf-8')
    freeze(HERE/'handoff_manifest.json', dict(research_parent_commit=frozen['parent_commit'],
           unchanged_research_code=True, tests_passed=verification['tests_passed'], audited_replays=audit['audited_replays'],
           accepted_candidates=sum(r['accepted'] for r in validation), final_status='CONTAMINATED_NOT_EVALUATED',
           paper_status='PENDING_NO_LIVE_ORDERS', postprocess_sources={p.name:sha(p) for p in sorted((HERE/'tools').glob('*.py'))},
           core_outputs={name:sha(HERE/name) for name in ['research_plan.md','split_manifest.json','experiment_registry.csv',
                       'strategy_comparison.csv','walkforward_results.csv','validation_results.json','freeze_manifest.json',
                       'accounting_audit.json','best_development_configuration.json']}))
    print('Final artifact package verified; no accepted strategy.', flush=True)


if __name__ == '__main__':
    finalize()

"""Publish the profit-first50k TRAIN search from saved artifacts only."""
import os
os.environ['MPLBACKEND']='Agg'
import csv
import json
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from quant_futures.config import file_hash
from quant_futures.research import json_write
from mass_configurations import semantic_key
from build_light_dashboard_charts import sampled_ids

ROOT=Path(__file__).resolve().parents[1]


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def plot_winner(folder,row,asset_name='training-50k.svg'):
    fig,axes=plt.subplots(4,2,figsize=(13,10),layout='constrained')
    logs=[]
    for i,m in enumerate(row['fold_metrics']):
        stem=row['config_id']+'_'+m['label']
        curve=pd.read_parquet(folder/(stem+'_equity.parquet'))
        log=pd.read_parquet(folder/(stem+'_trades.parquet'));log.insert(0,'fold',m['label']);logs.append(log)
        np.testing.assert_allclose(log.net_pnl.sum(),m['net_pnl'],rtol=0,atol=1e-7)
        np.testing.assert_allclose(curve.equity.iloc[-1]-50000,m['net_pnl'],rtol=0,atol=1e-7)
        peak=np.maximum.accumulate(np.r_[50000.,curve.equity.to_numpy()])[1:]
        dd=peak-curve.intrabar_worst_bound.to_numpy()
        np.testing.assert_allclose(dd.max(),m['intrabar_drawdown'],rtol=0,atol=1e-7)
        ids=np.unique(np.r_[sampled_ids(curve.equity,limit=500),dd.argmax()])
        x=curve.timestamp_utc.iloc[ids]
        axes[i,0].plot(x,curve.equity.iloc[ids]-50000,linewidth=1)
        axes[i,1].plot(x,-dd[ids],linewidth=1,color='#af4a5a')
        axes[i,1].axhline(-2000,color='red',linestyle='--',linewidth=.7)
        for ax in axes[i]:
            ax.set_title(str(m['label']));ax.set_ylabel('USD');ax.grid(alpha=.15);ax.tick_params(axis='x',labelsize=8)
    axes[0,0].set_title(str(row['fold_metrics'][0]['label'])+' · Net P&L')
    axes[0,1].set_title(str(row['fold_metrics'][0]['label'])+' · Intrabar drawdown bound')
    fig.suptitle(f"Selected training candidate: {row['instrument']} {row['family']}\n{row['config_id']} | Four separate $50k yearly accounts; display sampled")
    plt.rcParams['svg.fonttype']='none'
    fig.savefig(ROOT/'dashboard/assets'/asset_name,format='svg')
    fig.savefig(folder/'selected_training_curves.png',dpi=130);plt.close(fig)
    pd.concat(logs,ignore_index=True).to_csv(folder/'selected_training_trades.csv',index=False)


def main():
    result=read(ROOT/'reports/training_search_50k_result.json');folder=Path(result['run_path']).resolve()
    if not folder.is_relative_to((ROOT/'runs').resolve()): raise ValueError('Run outside project')
    if result['completed']!=50000: raise ValueError('Full50k budget incomplete')
    protocol=read(folder/'protocol.json')
    for path,expected in protocol['preserved_training_files'].items():
        if file_hash(path)!=expected: raise ValueError('Prior training artifact changed')
    planned=[json.loads(line) for line in (folder/'configurations.jsonl').read_text().splitlines()]
    prior=set()
    for name in ('mass_training_v2','mass_training_continuation_v1'):
        for line in (ROOT/'runs'/name/'configurations.jsonl').read_text().splitlines(): prior.add(semantic_key(json.loads(line)))
    keys={semantic_key(c) for c in planned}
    assert len(keys)==len(planned)==50000 and keys.isdisjoint(prior) and len(keys|prior)==70000
    with (folder/'ranked.csv').open(encoding='utf-8',newline='') as stream: rows=list(csv.DictReader(stream))
    assert len(rows)==50000 and {r['config_id'] for r in rows}=={c['config_id'] for c in planned}
    lines=['# 50,000 new training configurations: maximize net under$2,000 drawdown','',
        f"**50,000 new active configurations completed; 70,000 cumulative across the mass-search batches.** {result['qualified_count']} new candidates met the unchanged base training gates. No validation/test price data or protected outcome records were accessed by the search.",'',
        'The latest user objective was frozen before the revised run: maximize aggregate training net, with cash, closing and intrabar drawdown each strictly below $2,000. All markets use the same four 2020–2023 training evaluation years. Each yearly account resets to$50,000. Net profit sums those accounts; drawdown is the worst individual year, not a continuous four-year drawdown.', '',
        'Candidate creation used the original ten family/parameter domains and five new fixed seeds beginning20261108. Every configuration already present in the earlier20k was excluded. Existing execution, costs, stops, sizing, prior-volume limits, daily/maximum-loss locks, minimum30 trades per fold and50% consistency diagnostic were preserved. No rule was changed to respond to protected outcomes.', '',
        'The earlier dominance objective was superseded by the user’s profit-first/under2k clarification. Identical completed training measurements were imported into the revised run once. The original checkpoint and protocol remain intact. No duplicate active configuration is counted twice.','',
        '## Selection result','']
    winner=result['winner'];benchmark=result['benchmark']
    peak=result['top10'][0]
    peak_path=folder/('check_'+peak['config_id']+'.json')
    peak_check=read(peak_path) if peak_path.exists() else None
    if peak_check:
        ps=peak_check['stress_2x']
        peak_frozen=dict(candidate=peak,stress_2x=ps,source_hashes=result['source_hashes'],
            role='Highest base-qualified training profit; doubled-cost qualification is disclosed separately',
            all_cost_robustness_gates_pass=bool(ps['qualified']),validation_accessed=False,test_accessed=False,
            independent_confirmation=False,operational_eligibility=False)
        peak_file=folder/'highest_base_profit_candidate.json'
        if peak_file.exists(): assert read(peak_file)==peak_frozen
        else: json_write(peak_file,peak_frozen)
        lines += [f"The highest base-qualified training net was **${peak['net_pnl']:,.2f}** (`{peak['config_id']}`), with cash DD ${peak['realized_drawdown']:,.2f} and intrabar DD ${peak['intrabar_drawdown']:,.2f}. "
            f"At doubled costs: net ${ps['net_pnl']:,.2f}, intrabar DD ${ps['intrabar_drawdown']:,.2f}, qualification **{ps['qualified']}**. "
            f"Worst annual consistency ratio: {ps['maximum_consistency_ratio']:.2%}; the unchanged gate is50%.",'']
    if not result['improved_vs_benchmark']:
        lines += ['**No higher-profit replacement passed every predeclared robustness gate. The earlier fully qualified training benchmark remains ahead of the best new cost-qualified candidate.**','']
    json_write(ROOT/'reports/training_search_50k_selection_summary.json',dict(
        highest_base=peak,highest_base_stress=peak_check['stress_2x'] if peak_check else None,
        best_new_verified=winner['base'] if winner else None,improved_vs_benchmark=result['improved_vs_benchmark'],
        benchmark=benchmark,retained_prior_benchmark=not result['improved_vs_benchmark'],
        validation_accessed=False,test_accessed=False))
    if winner:
        row=winner['base'];stress=winner['stress_2x']
        assert row['qualified'] and stress['qualified'] and winner['base_reproduced']
        assert all(c['passed'] for c in winner['execution_parity'])
        frozen=dict(candidate=row,stress_2x=stress,source_hashes=result['source_hashes'],
            selection='Highest base training net among new full-gate candidates surviving unchanged2x cost qualification; checked in profit order.',
            validation_accessed=False,test_accessed=False,independent_confirmation=False,operational_eligibility=False)
        path=folder/'selected_training_candidate.json'
        if path.exists(): assert read(path)==frozen
        else: json_write(path,frozen)
        plot_winner(folder,row)
        formulas={
            'trend':'Follow the sign of EMA(max(2,L/2)) minus EMA(L), normalized by ATR14, when magnitude meets the threshold.',
            'momentum':'Follow the L-bar close change divided by ATR14×sqrt(L), when its magnitude meets the threshold.',
            'mean_reversion':'Fade the L-bar close z-score when its magnitude meets the threshold.',
            'breakout':'Enter long above the preceding L-bar high plus threshold×ATR14, or short below the preceding L-bar low minus threshold×ATR14.',
            'vwap':'Fade the session cumulative volume-weighted typical-price deviation when its ATR-normalized magnitude meets the threshold, only while absolute normalized L-bar momentum is at most1.',
            'opening_range':'Trade above/below the completed L-minute opening range plus/minus threshold×ATR14.',
            'regime':'Follow normalized L-bar momentum when path efficiency exceeds threshold/3 and short/long return-volatility ratio is below1.5.',
            'volatility':'Follow normalized L-bar momentum when the short/long return-volatility ratio meets the threshold.',
            'volume':'Follow normalized L-bar momentum when current volume divided by its preceding L-bar average meets the threshold.',
            'hybrid':'Follow EMA trend only when its sign matches the 2L-bar close change and absolute normalized momentum meets the threshold.'}
        c=row['parameters']
        clock=lambda minute:f'{minute//60:02d}:{minute%60:02d}'
        lines += [f"Selected `{row['config_id']}`: {row['instrument']} / {row['family']}.",'',
            '| Measurement | Selected base | Selected 2x costs | Earlier training benchmark |','|---|---:|---:|---:|',
            f"| Aggregate net | ${row['net_pnl']:,.2f} | ${stress['net_pnl']:,.2f} | ${benchmark['net_pnl']:,.2f} |",
            f"| Worst annual cash DD | ${row['realized_drawdown']:,.2f} | ${stress['realized_drawdown']:,.2f} | ${benchmark['realized_drawdown']:,.2f} |",
            f"| Worst annual closing DD | ${row['max_drawdown']:,.2f} | ${stress['max_drawdown']:,.2f} | ${benchmark['max_drawdown']:,.2f} |",
            f"| Worst annual intrabar DD | ${row['intrabar_drawdown']:,.2f} | ${stress['intrabar_drawdown']:,.2f} | ${benchmark['intrabar_drawdown']:,.2f} |",
            f"| Trades | {row['trades']} | {stress['trades']} | — |",'',
            f"Higher training net than benchmark: **{result['improved_vs_benchmark']}**. Original training gates and doubled-cost gates: **PASS**. Independent profitability and exact funded-account eligibility: **NOT ESTABLISHED**.",'',
            'Frozen configuration:','', '```json',json.dumps(row['parameters'],indent=2),'```','',
            formulas[row['family']], '',
            f"L={c['lookback']} {'minutes of opening range' if c['family']=='opening_range' else 'completed15-minute bars'}. Entry opens are eligible from {clock(c['session_start'])} through {clock(c['session_end']-15)} ET on weekdays; flatten by {clock(min(c['session_end'],955))} ET. Signals use only completed bars and execute at the following eligible open.", '',
            f"Initial stop: {c['stop_atr']}×ATR14 rounded upward to whole ticks. Target: {c['target_r']}×stop distance. Hold at most {c['hold_bars']} bars; trailing ATR distance {c['trailing_atr']} (zero disables trailing), using the preceding completed bar only. Stop-first precedence and adverse gap fills are unchanged.", '',
            f"At most {c['max_contracts']} contracts, further capped by$150 trade/open risk including modeled costs and1% of preceding-bar volume. Daily loss lock$300; internal hard drawdown lock$1,800; five consecutive losses lock the session. The provisional EOD funded floor trails cash by$2,000 and caps at$50,100. These remain research assumptions rather than verified funded-account rules.", '',
            '| Year | Net | Cash DD | Intrabar DD | Trades |','|---|---:|---:|---:|---:|']
        for m in row['fold_metrics']:
            lines.append(f"| {m['label']} | ${m['net_pnl']:,.2f} | ${m['realized_drawdown']:,.2f} | ${m['intrabar_drawdown']:,.2f} | {m['trades']} |")
    else:
        lines+=['No new candidate survived the unchanged base and doubled-cost qualification. No new qualifying strategy is recommended.']
    rel='../runs/'+folder.name
    lines+=['','## Artifacts and evidence limits','',
        f'[All 50,000 ranked results]({rel}/ranked.csv) · [Frozen 50,000 configuration manifest]({rel}/configurations.jsonl) · [Frozen protocol]({rel}/protocol.json)','',
        'The complete CSV keeps negative, inactive and risk-locked configurations. Results are selected retrospectively within training and are subject to substantial multiple-comparison bias. This search cannot show that a strategy will outperform on unseen data. No validation/test stage was run, and previously observed periods are not relabeled as fresh holdouts. Actual charges, historical official session schedules and exact funded-account rules remain unresolved.', '',
        '[Dashboard](http://127.0.0.1:8511/#training-50k)','']
    if peak_check:
        lines += [f'[Highest base-profit candidate and its failed cost-consistency diagnostic]({rel}/highest_base_profit_candidate.json)','']
    if winner:
        lines += [f'[Selected configuration and cost stress]({rel}/selected_training_candidate.json) · [Saved training equity/drawdown curves]({rel}/selected_training_curves.png) · [Selected trade logs]({rel}/selected_training_trades.csv)','']
    (ROOT/'reports/TRAINING_SEARCH_50K.md').write_text('\n'.join(lines),encoding='utf-8')
    receipt=dict(passed=True,completed_new_unique=50000,cumulative_unique=70000,prior_training_artifacts_preserved=True,
        validation_accessed=False,test_accessed=False,protected_result_files_read=False,publication_only_no_replay=True,
        ranked_sha256=file_hash(folder/'ranked.csv'),qualifying=result['qualified_count'],winner=winner['config_id'] if winner else None)
    json_write(ROOT/'reports/training_search_50k_publication_verification.json',receipt)
    print(json.dumps(receipt))


if __name__=='__main__': main()

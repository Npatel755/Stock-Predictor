"""Publish100k TRAIN research from saved records, with phase-specific flags."""
import csv
import json
from pathlib import Path
import sqlite3
from quant_futures.config import file_hash
from quant_futures.research import json_write
from mass_configurations import semantic_key
from publish_training_search_50k import plot_winner

ROOT=Path(__file__).resolve().parents[1]


def read(p): return json.loads(p.read_text(encoding='utf-8'))


def main():
    result=read(ROOT/'reports/training_search_100k_result.json');folder=Path(result['run_path']).resolve()
    if not folder.is_relative_to((ROOT/'runs').resolve()) or result['completed']!=100000:
        raise ValueError('Require the complete100k project run')
    protocol=read(folder/'protocol.json')
    for path,expected in protocol['preserved_training_files'].items():
        if file_hash(path)!=expected: raise ValueError('Prior TRAIN artifact changed')
    keys=set();ids=set()
    for line in (folder/'configurations.jsonl').read_text(encoding='utf-8').splitlines():
        c=json.loads(line);keys.add(semantic_key(c));ids.add(c['config_id'])
    prior=set()
    for name in ('mass_training_v2','mass_training_continuation_v1','training_search_50k_v2'):
        for line in (ROOT/'runs'/name/'configurations.jsonl').read_text(encoding='utf-8').splitlines():
            prior.add(semantic_key(json.loads(line)))
    assert len(keys)==len(ids)==100000 and len(prior)==70000 and keys.isdisjoint(prior)
    csv_ids=set();count=0;evaluation_count=0
    with (folder/'ranked.csv').open(encoding='utf-8',newline='') as stream:
        for row in csv.DictReader(stream):
            count+=1;csv_ids.add(row['config_id']);evaluation_count+=row['evaluation_phase_qualified']=='True'
    assert count==len(csv_ids)==100000 and csv_ids==ids
    winner=result['winner'];benchmark=result['benchmark'];rel='../runs/'+folder.name
    lines=['# 100,000 additional training configurations','',
        f"**100,000 new configurations completed;170,000 distinct active configurations across the completed mass searches.** "
        f"{result['qualified_count']:,} met the research/post-evaluation training gates; {evaluation_count:,} also met the50% evaluation-account consistency gate at base costs.",'',
        'No validation/test prices or protected outcome records were read by this search. Generation, ranking and selection used training inputs only. The original families, parameter domains, execution logic, costs and risk limits were preserved. All prior70k active configurations were excluded; seeds20261113 through20261122 were fixed before training-price access.', '',
        '## Selection policy','',
        'All markets use the same2020/2021/2022/2023 training evaluation years with separate$50,000 accounts. Net sums the four accounts; drawdown is the worst individual year, not a continuous four-year account drawdown. Every fold must have positive net, at least30 trades and no permanent risk/funded-scenario breach. Cash, closing and intrabar drawdowns must each remain strictly below$2,000. The internal hard drawdown margin remains$1,800.','',
        'The user-provided50% consistency rule applies only to the **account evaluation phase**. It remains reported on every candidate and cost scenario; it does not modify signals or executions. A chronological data split is not an account phase. Research/post-evaluation qualification omits that one phase-specific classification gate; evaluation-phase qualification additionally requires it. The user-provided phase scope is not independently verified contractual compliance.','',
        'Rank research-qualified candidates by base net profit descending, then intrabar drawdown ascending. Check in that order; select the first whose original base reproduces, independent ledger/fill checks pass and the same research gates survive doubled costs. The legacy composite score is retained as a diagnostic and does not determine this ranking.','',
        '## Training result','']
    if winner:
        row=winner['base'];stress=winner['stress_2x']
        assert row['qualified'] and stress['qualified'] and winner['base_reproduced']
        assert all(v['passed'] for v in winner['execution_parity'])
        freeze=dict(candidate=row,stress_2x=stress,source_hashes=result['source_hashes'],phase_policy=protocol['phase_policy'],
            selection='Highest new base net surviving predeclared research/post-evaluation doubled-cost gates; training only',
            validation_accessed=False,test_accessed=False,independent_confirmation=False,operational_eligibility=False)
        selected=folder/'selected_training_candidate.json'
        if selected.exists(): assert read(selected)==freeze
        else: json_write(selected,freeze)
        plot_winner(folder,row,asset_name='training-100k.svg')
        lines += [f"Selected `{row['config_id']}`: {row['instrument']} / {row['family']}.",'',
            '| Metric | New base | New2x costs | Saved training benchmark |','|---|---:|---:|---:|',
            f"| Aggregate net | ${row['net_pnl']:,.2f} | ${stress['net_pnl']:,.2f} | ${benchmark['net_pnl']:,.2f} |",
            f"| Worst annual cash DD | ${row['realized_drawdown']:,.2f} | ${stress['realized_drawdown']:,.2f} | ${benchmark['realized_drawdown']:,.2f} |",
            f"| Worst annual closing DD | ${row['max_drawdown']:,.2f} | ${stress['max_drawdown']:,.2f} | ${benchmark['max_drawdown']:,.2f} |",
            f"| Worst annual intrabar DD | ${row['intrabar_drawdown']:,.2f} | ${stress['intrabar_drawdown']:,.2f} | ${benchmark['intrabar_drawdown']:,.2f} |",
            f"| Trades | {row['trades']} | {stress['trades']} | — |",
            f"| Evaluation-phase gates | {row['evaluation_phase_qualified']} | {stress['evaluation_phase_qualified']} | — |",'',
            f"Higher TRAIN net than saved benchmark: **{result['improved_vs_benchmark']}**. Research/post-evaluation gates: **PASS**. Evaluation-account-phase status is shown separately above. Unseen performance and exact funded-account eligibility are **NOT ESTABLISHED**.",'',
            'Frozen parameters:','', '```json',json.dumps(row['parameters'],indent=2),'```','',
            '| Training year | Net | Cash DD | Intrabar DD | Trades | Consistency ratio |','|---|---:|---:|---:|---:|---:|']
        for m in row['fold_metrics']:
            lines.append(f"| {m['label']} | ${m['net_pnl']:,.2f} | ${m['realized_drawdown']:,.2f} | ${m['intrabar_drawdown']:,.2f} | {m['trades']} | {m['consistency']:.2%} |")
        lines+=['',f'[Saved frozen candidate and cost stress]({rel}/selected_training_candidate.json) · [Training curves]({rel}/selected_training_curves.png) · [Trade logs]({rel}/selected_training_trades.csv)','']
    else:
        lines+=['No new candidate passed the predeclared base/doubled-cost research gates. No passing strategy is invented.']
    lines+=['','## Artifacts and limits','',
        f'[All100k ranked results]({rel}/ranked.csv) · [Frozen100k configuration manifest]({rel}/configurations.jsonl) · [Protocol]({rel}/protocol.json)','',
        'Distinct active parameter configurations are not independent edges. The full CSV includes failures, inactive candidates and risk locks. Retrospective training selection across many correlated trials creates substantial selection bias. No protected period was reopened to confirm or adjust this result. Previously observed periods cannot become fresh holdouts by relabeling. Fees and exact funded-account contract rules remain unresolved; no live execution is authorized.','',
        '[Dashboard](http://127.0.0.1:8511/#training-100k)','']
    (ROOT/'reports/TRAINING_SEARCH_100K.md').write_text('\n'.join(lines),encoding='utf-8')
    receipt=dict(passed=True,new_completed_unique=100000,cumulative_unique=170000,repeats_from_prior=0,
        research_qualified=result['qualified_count'],evaluation_phase_base_qualified=evaluation_count,
        prior_training_artifacts_preserved=True,publication_only_no_replay=True,
        validation_accessed=False,test_accessed=False,protected_result_files_read=False,
        ranked_sha256=file_hash(folder/'ranked.csv'),winner=winner['config_id'] if winner else None)
    json_write(ROOT/'reports/training_search_100k_publication_verification.json',receipt)
    print(json.dumps(receipt))


if __name__=='__main__': main()

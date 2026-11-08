"""Reconcile and publish saved TRAIN artifacts; never load market prices."""
import csv
import html
import json
import math
from pathlib import Path
import sqlite3
from collections import Counter
import collaborative_200k as study
from mass_configurations import config_id
from training_500k_universe import create_bitset, config_to_index, is_bit_set, set_bit
from quant_futures.config import file_hash
from quant_futures.research import json_write


def main():
    folder=study.RUN; root=study.ROOT
    protocol=json.loads((folder/'protocol.json').read_text())
    result=json.loads((folder/'results.json').read_text())
    assert result['completed']==study.TARGET==200000
    assert not any(result[k] for k in ('validation_accessed','test_accessed','protected_result_files_read','independent_confirmation'))
    assert protocol['source_hashes']=={p.name:file_hash(p) for p in study.sources()}
    assert file_hash(folder/'configurations.jsonl')==result['configuration_sha256']==protocol['configuration_sha256']
    assert file_hash(folder/'ranked.csv')==result['ranked_sha256']
    seen=create_bitset(); prior_count=0; ids=set(); groups=Counter()
    for p,expected in protocol['exclusion_manifest_hashes'].items():
        assert file_hash(p)==expected
        with Path(p).open(encoding='utf-8') as stream:
            for line in stream:
                idx=config_to_index(json.loads(line)); assert not is_bit_set(seen,idx)
                set_bit(seen,idx); prior_count+=1
    assert prior_count==870000
    with (folder/'configurations.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            c=json.loads(line); idx=config_to_index(c)
            assert not is_bit_set(seen,idx); set_bit(seen,idx)
            assert c['config_id']==config_id(c) and c['config_id'] not in ids
            ids.add(c['config_id']); groups[(c['instrument'],c['family'])]+=1
    assert len(ids)==200000 and len(groups)==40 and set(groups.values())=={5000}
    counts=Counter(); bymarket={s:Counter() for s in study.INSTRUMENTS}; byfamily={f:Counter() for f in study.FAMILIES}; csv_ids=set(); previous=None
    eligible_csv=folder/'positive_under_2000.csv'
    top=[]
    with (folder/'ranked.csv').open(encoding='utf-8',newline='') as stream, eligible_csv.open('w',encoding='utf-8',newline='') as output:
        reader=csv.DictReader(stream); writer=csv.DictWriter(output,fieldnames=reader.fieldnames); writer.writeheader()
        for r in reader:
            assert r['config_id'] not in csv_ids; csv_ids.add(r['config_id'])
            net=float(r['net_pnl']); dd=float(r['intrabar_drawdown'])
            parameters=json.loads(r['parameters'])
            assert config_id(parameters)==r['config_id']
            assert parameters['instrument']==r['instrument'] and parameters['family']==r['family']
            assert math.isfinite(net) and all(math.isfinite(float(r[k])) and float(r[k])>=0 for k in study.DD_FIELDS)
            key=(-net,dd,r['config_id'])
            assert previous is None or previous<=key; previous=key
            yes=net>0 and all(float(r[k])<2000 for k in study.DD_FIELDS)
            assert (r['positive_under_2000']=='True')==yes
            passes={'evaluated':True,'positive_under_2000':yes,'positive_under_2000_no_locks':yes and int(r['locks'])==0 and int(r['funded_breaches'])==0,'research_qualified':r['qualified']=='True','evaluation_phase_qualified':r['evaluation_phase_qualified']=='True'}
            for k,v in passes.items():
                counts[k]+=int(v); bymarket[r['instrument']][k]+=int(v); byfamily[r['family']][k]+=int(v)
            if yes:
                writer.writerow(r)
                if len(top)<10: top.append(r)
    assert csv_ids==ids and dict(counts)==result['totals']
    assert {s:dict(v) for s,v in bymarket.items()}==result['by_market']
    with sqlite3.connect(f'file:{(folder/"checkpoints.sqlite").as_posix()}?mode=ro',uri=True) as db:
        assert db.execute('SELECT COUNT(*) FROM results').fetchone()[0]==200000
        assert {r[0] for r in db.execute('SELECT config_id FROM results')}==ids
        checks=[json.loads(r[0]) for r in db.execute('SELECT payload FROM checks')]
    winner=result['winner']; row=winner['base'] if winner else None
    if winner:
        assert row['qualified'] and winner['stress_qualified'] and winner['base_reproduced']
        assert all(c['passed'] for c in winner['execution_parity'])
        assert study.positive_under_limit(winner['stress_2x'])
        # All higher-profit qualified candidates must have a saved failed stress.
        ordering=lambda r:(-float(r['net_pnl']),float(r['intrabar_drawdown']),r['config_id'])
        checkmap={c['config_id']:c for c in checks}
        with sqlite3.connect(f'file:{(folder/"checkpoints.sqlite").as_posix()}?mode=ro',uri=True) as db:
            for (payload,) in db.execute("SELECT payload FROM results WHERE json_extract(payload,'$.qualified')=1"):
                candidate=json.loads(payload)
                if ordering(candidate)<ordering(row):
                    assert candidate['config_id'] in checkmap and not checkmap[candidate['config_id']]['stress_qualified']
        frozen=dict(candidate=row,stress_2x=winner['stress_2x'],configuration_sha256=result['configuration_sha256'],source_hashes=protocol['source_hashes'],validation_accessed=False,test_accessed=False,independent_confirmation=False,classification='RESEARCH_ONLY')
        p=folder/'selected_training_candidate.json'
        if p.exists(): assert json.loads(p.read_text())==frozen
        else: json_write(p,frozen)
        from publish_training_search_50k import plot_winner
        plot_winner(folder,row,asset_name='collaborative-200k.svg')
    n=counts['positive_under_2000']; clean=counts['positive_under_2000_no_locks']; q=counts['research_qualified']
    lines=['# Another 200,000 training configurations: results','',f'**Completed: 200,000 new unique configurations. {n:,} ({n/200000:.2%}) had positive net P&L and cash, closing, and intrabar drawdown each strictly below $2,000.**','',f'{clean:,} of those had no permanent risk lock or funded-floor breach. {n-clean:,} met the requested profit/DD arithmetic but had a lock or breach. {q:,} met the additional frozen quality gates; {counts["evaluation_phase_qualified"]:,} also met the 50% evaluation-account consistency diagnostic. These counts are base-cost results; doubled costs were checked only for the selected candidate and any higher-ranked rejected candidates.','',
        'Net P&L is the sum of four separate annual training accounts (2020, 2021, 2022, 2023), reset to $50,000 each year. Drawdown is the worst individual annual account, including a conservative intrabar bound. These are not continuous four-year drawdown results. Zero-trade and zero-profit cases do not count; a $2,000 drawdown touch fails.','',
        '## Counts by market','', '| Market | Evaluated | Positive net + DD < $2k | Also no locks/breaches | Additional research gates |','|---|---:|---:|---:|---:|']
    for s in study.INSTRUMENTS:
        g=bymarket[s]; lines.append(f'| {s} | {g["evaluated"]:,} | {g["positive_under_2000"]:,} | {g["positive_under_2000_no_locks"]:,} | {g["research_qualified"]:,} |')
    lines+=['','## Counts by family','','| Family | Evaluated | Positive net + DD < $2k | Additional research gates |','|---|---:|---:|---:|']
    for f in study.FAMILIES:
        g=byfamily[f]; lines.append(f'| {f} | {g["evaluated"]:,} | {g["positive_under_2000"]:,} | {g["research_qualified"]:,} |')
    lines+=['','## Highest training net meeting the requested two conditions','','| Configuration | Market/family | Net | Intrabar DD | Trades | Permanent locks | Additional research gates |','|---|---|---:|---:|---:|---:|---|']
    for r in top:
        lines.append(f'| `{r["config_id"]}` | {r["instrument"]} {r["family"]} | ${float(r["net_pnl"]):,.2f} | ${float(r["intrabar_drawdown"]):,.2f} | {r["trades"]} | {r["locks"]} | {r["qualified"]} |')
    if winner:
        stress=winner['stress_2x']
        lines+=['','## Highest-profit quality-qualified candidate surviving doubled costs','',f'`{row["config_id"]}` — {row["instrument"]} {row["family"]}: **${row["net_pnl"]:,.2f} net**, ${row["realized_drawdown"]:,.2f} cash DD, ${row["max_drawdown"]:,.2f} closing DD, **${row["intrabar_drawdown"]:,.2f} intrabar DD**, {row["trades"]} trades. At doubled modeled costs: **${stress["net_pnl"]:,.2f} net**, ${stress["intrabar_drawdown"]:,.2f} intrabar DD; quality qualification {stress["qualified"]}.','', 'Frozen parameters:','', '```json',json.dumps(row['parameters'],indent=2),'```','', '| Training account | Net | Intrabar DD | Trades | Largest-day/net ratio |','|---|---:|---:|---:|---:|']
        for f in row['fold_metrics']:
            consistency='undefined' if f['consistency'] is None else f'{f["consistency"]:.2%}'
            lines.append(f'| {f["label"]} | ${f["net_pnl"]:,.2f} | ${f["intrabar_drawdown"]:,.2f} | {f["trades"]} | {consistency} |')
    else: lines+=['','No quality-qualified candidate survived the predefined doubled-cost verification.']
    if winner:
        stress=winner['stress_2x']
        lines+=['','Account evaluation-phase consistency: **'+('PASS' if row['evaluation_phase_qualified'] else 'FAIL')+f' at base costs** (worst annual largest-day/net ratio {row["maximum_consistency_ratio"]:.2%}); **'+('PASS' if stress['evaluation_phase_qualified'] else 'FAIL')+f' at doubled costs** ({stress["maximum_consistency_ratio"]:.2%}). The user limits this gate to the account evaluation phase; it is not part of the broader post-evaluation research count. No account eligibility is certified.','']
        if row['family']=='trend':
            c=row['parameters']
            lines += ['For this selected trend configuration, the completed15-minute-bar signal follows the sign of EMA('+str(max(2,c['lookback']//2))+') minus EMA('+str(c['lookback'])+'), divided by ATR14, once its absolute value reaches '+str(c['threshold'])+'. Eligible decisions use the frozen session window; entries execute at the next eligible open with modeled costs. The frozen ATR stop, target multiple, holding cap, trailing stop and maximum contracts are listed above; risk sizing, daily limits, data-gap/roll safeguards and permanent account locks remain in force.','']
    review=root/'reports/GEMINI_COLLABORATIVE_200K_REVIEW.md'
    lines+=['','## Separation, provenance, and limits','',
        'All 200,000 active configurations are distinct and disjoint from the 370,000 completed historical configurations and all 500,000 configurations reserved by Gemini. Each market has 50,000 cases; each market/family has 5,000. A market rename does not count as a new active strategy. Different parameters can still produce correlated or identical trades; 200,000 configurations are not 200,000 independent hypotheses. Seed20270101 through20270120; fixed manifest/source hashes before price access.',
        '', 'Only verified physical TRAIN partitions and their validated cached15-minute raw-contract bars were loaded. Existing split boundaries were preserved. This run did not resolve, read, reserve, or evaluate validation/test prices or protected outcomes. Prior observations of those periods elsewhere cannot be erased; no independent confirmation is claimed.',
        '', 'Original next-open execution, causal completed-bar signals, conservative stop-first ambiguity, strict target trade-through, adverse gaps, contract/volume safeguards, modeled fees/spread/slippage and risk locks were retained. Micro and mini executions use their own contract economics. The 96-bar entry embargo and16-bar terminal entry purge remain. Holiday schedules, actual all-in fees and exact funded-account rule terms remain unverified. The 50% account-phase policy is user-provided and diagnostic, not contractual certification.',
        '', 'Additional research gates: no risk/funded breach, positive aggregate net, positive at least3/4 annual folds, profit factor>=1.30,80–800 trades and allDD<2000. They are historical filters, not proof against overfitting. The main requested count intentionally does not require these extra gates. Hundreds of thousands of selected trials entail substantial selection bias; training profitability does not establish an unseen edge.',
        '', 'Collaboration: Gemini’s separate500k process and frozen manifest were observed and preserved. Shared handoff: CODEX_GEMINI_COORDINATION.md. '+('A Gemini review file is present; inspect it separately for its scope and conclusions.' if review.exists() else 'A direct UI handoff could not be submitted because the Antigravity window repeatedly became unavailable/minimized. No Gemini acknowledgement or independent review is claimed.'),
        '', '**Conclusion: requested profit/DD arithmetic is reported above on TRAIN only. Unseen profitability and funded-account eligibility are UNPROVEN; status RESEARCH-ONLY.**',
        '', '## Saved artifacts','', '- Full ranked results: `../runs/collaborative_200k_v1/ranked.csv`','- Requested profit/DD subset: `../runs/collaborative_200k_v1/positive_under_2000.csv`','- Frozen universe/protocol/source: `../runs/collaborative_200k_v1/configurations.jsonl`, `protocol.json`, `code/`','- Selected candidate, reconciled trade logs and curves: `../runs/collaborative_200k_v1/selected_training_candidate.json`, `selected_training_trades.csv`, `selected_training_curves.png`','- Machine-readable counts: `COLLABORATIVE_200K_result.json`','']
    report=root/'reports/COLLABORATIVE_200K.md'; report.write_text('\n'.join(lines),encoding='utf-8')
    # Self-contained lightweight report opens without a server or browser libraries.
    page='<!doctype html><meta charset="utf-8"><title>200,000 strategy research results</title><style>body{background:#111820;color:#e8eef5;font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 24px}pre{white-space:pre-wrap;overflow-wrap:anywhere}img{width:100%;background:white}</style>'
    page+='<h1>200,000 new TRAIN configurations</h1><h2>'+f'{n:,} profitable with all annual drawdowns below $2,000 ({n/200000:.2%})'+'</h2><p>Training only. No validation or test evaluation. Worst annual drawdown; four separate accounts.</p>'
    page+='<pre>'+html.escape('\n'.join(lines))+'</pre>'
    if winner: page+='<img alt="Annual training equity and drawdown curves" src="../runs/collaborative_200k_v1/selected_training_curves.png">'
    (root/'reports/COLLABORATIVE_200K.html').write_text(page,encoding='utf-8')
    receipt=dict(passed=True,completed=200000,prior_reserved_unique_verified=870000,new_active_unique_verified=200000,total_reserved_unique=1070000,manifest_csv_database_ids_match=True,counts_recomputed_from_csv=True,counts=dict(counts),by_family={f:dict(v) for f,v in byfamily.items()},frozen_sources_match=True,profit_rank_and_stress_selection_verified=True,selected_trade_curve_reconciliation=bool(winner),validation_accessed=False,test_accessed=False,gemini_review_file_present=review.exists(),report_sha256=file_hash(report),ranked_sha256=result['ranked_sha256'],verified_at=study.engine.now())
    json_write(root/'reports/COLLABORATIVE_200K_verification.json',receipt)
    print(json.dumps(dict(passed=True,counts=dict(counts),report=str(report))))


if __name__=='__main__': main()

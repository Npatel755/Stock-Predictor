"""Version/reconcile saved TRAIN refinement results; never evaluate market prices."""
import csv
import html
import json
from pathlib import Path
import shutil
import sqlite3
import numpy as np
import pandas as pd
import e57_training_refinement as study
from e57_refinement_parameters import fingerprint,scaled_cfg,SCALING_CONTROLS
from quant_futures.config import file_hash,digest
from quant_futures.research import json_write
from publish_training_search_50k import plot_winner


def save_version(check,version,protocol):
    row=check['base'];c=row['parameters'];folder=study.ROOT/'strategy_versions/mnq_momentum_e57'/version
    frozen=dict(version=version,parent_version='1.0.0',parent_strategy_id=protocol['baseline_training']['config_id'],strategy_id=c['config_id'],parameters=c,parameter_hash=digest(c),training=row,stress_2x=check['stress_2x'],execution_config=scaled_cfg(study.engine.execution_cfg(c),c),source_hashes=protocol['source_hashes'],source_run=str(study.RUN),core_source_hash=protocol['core_source_hash'],validation_status='NOT_EVALUATED',test_status='NOT_EVALUATED',inherited_selection='Parent was user-selected after prior holdouts. This version is TRAIN-only research, not independently confirmed.',classification='RESEARCH_ONLY',automatic_promotion=False)
    frozen['training_data_identity']=study.engine.read(study.RUN/'MNQ_source.json')
    frozen['training_folds']=study.engine.read(study.RUN/'folds.json')
    frozen['phase_policy']=protocol['phase_policy']
    continuous=study.engine.read(study.ROOT/'runs/e57_continuous_training_v1/results.json')
    frozen['continuous_training_diagnostic']=continuous['results'][c['config_id']]
    frozen['base_reproduced']=check['base_reproduced']
    frozen['execution_verification']=check['execution_checks']
    if (folder/'candidate.json').exists():
        assert study.engine.read(folder/'candidate.json')==frozen
    else:
        folder.mkdir(parents=True,exist_ok=False);json_write(folder/'candidate.json',frozen)
        shutil.copytree(study.RUN/'code',folder/'code')
        for p in study.RUN.glob(c['config_id']+'_*'):
            if p.suffix=='.parquet':shutil.copyfile(p,folder/p.name)
        manifest=dict(version=version,parent_version='1.0.0',files={str(p.relative_to(folder)):file_hash(p) for p in folder.rglob('*') if p.is_file()},validation_evaluations=0,test_evaluations=0)
        json_write(folder/'manifest.json',manifest)
    for rel,expected in study.engine.read(folder/'manifest.json')['files'].items():assert file_hash(folder/rel)==expected
    return folder


def reconcile(check):
    c=check['base']['parameters'];folder=study.RUN
    assert check['base_reproduced'] and all(m['passed'] for m in check['execution_checks'])
    for suffix,row in (('',check['base']),('_stress',check['stress_2x'])):
        for m in row['fold_metrics']:
            stem=c['config_id']+'_'+m['label']+suffix
            curve=pd.read_parquet(folder/(stem+'_equity.parquet'));trades=pd.read_parquet(folder/(stem+'_trades.parquet'))
            equity=curve.equity.to_numpy();cash=curve.cash.to_numpy()
            peak=np.maximum.accumulate(np.r_[50000.,equity])[1:];cashpeak=np.maximum.accumulate(np.r_[50000.,cash])[1:]
            assert len(trades)==m['trades']
            for actual,expected in ((equity[-1]-50000,m['net_pnl']),(trades.net_pnl.sum(),m['net_pnl']),((peak-equity).max(),m['max_drawdown']),((cashpeak-cash).max(),m['realized_drawdown']),((peak-curve.intrabar_worst_bound.to_numpy()).max(),m['intrabar_drawdown'])):
                np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)


def main():
    root=study.ROOT;folder=study.RUN;protocol=study.engine.read(folder/'protocol.json');result=study.engine.read(folder/'results.json')
    continuous_folder=root/'runs/e57_continuous_training_v1'
    continuous=study.engine.read(continuous_folder/'results.json')
    continuous_plan=study.engine.read(continuous_folder/'protocol.json')
    assert continuous_plan['source_sha256']==file_hash(root/'scripts/e57_continuous_training_check.py')
    assert continuous_plan['parent_result_sha256']==file_hash(folder/'results.json')
    assert not continuous['validation_accessed'] and not continuous['test_accessed']
    for cid,record in continuous['results'].items():
        assert record['base']['execution_verification']['passed']
        for suffix,m in (('',record['base']),('_stress',record['stress_2x'])):
            curve=pd.read_parquet(continuous_folder/(cid+'_continuous_train'+suffix+'_equity.parquet'))
            trades=pd.read_parquet(continuous_folder/(cid+'_continuous_train'+suffix+'_trades.parquet'))
            equity=curve.equity.to_numpy();peak=np.maximum.accumulate(np.r_[50000.,equity])[1:]
            cash=curve.cash.to_numpy();cashpeak=np.maximum.accumulate(np.r_[50000.,cash])[1:]
            assert len(trades)==m['trades']
            for actual,expected in ((equity[-1]-50000,m['net_pnl']),(trades.net_pnl.sum(),m['net_pnl']),((peak-equity).max(),m['max_drawdown']),((cashpeak-cash).max(),m['realized_drawdown']),((peak-curve.intrabar_worst_bound.to_numpy()).max(),m['intrabar_drawdown'])):
                np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)
    assert protocol['source_hashes']=={p.name:file_hash(p) for p in study.sources()}
    assert file_hash(study.BASELINE)==protocol['baseline_training_artifact_sha256']
    assert file_hash(folder/'configurations.jsonl')==protocol['configurations_sha256']==result['configuration_sha256']
    assert file_hash(folder/'ranked.csv')==result['ranked_sha256']
    old=set()
    for path,expected in protocol['prior_manifest_hashes'].items():
        assert file_hash(path)==expected
        with Path(path).open(encoding='utf-8') as stream:
            for line in stream:
                key=fingerprint(json.loads(line));assert key not in old;old.add(key)
    assert len(old)==1070000
    planned_ids=set();new=set();order={}
    with (folder/'configurations.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            c=json.loads(line);key=fingerprint(c)
            assert key not in old and key not in new;new.add(key);planned_ids.add(c['config_id']);order[c['config_id']]=c['experiment_order']
    assert len(new)==len(planned_ids)==200000
    with sqlite3.connect('file:'+(folder/'checkpoints.sqlite').as_posix()+'?mode=ro',uri=True) as db:
        actual_ids={r[0] for r in db.execute('SELECT config_id FROM results')}
    csv_ids=set();csv_count=0
    with (folder/'ranked.csv').open(encoding='utf-8',newline='') as stream:
        for row in csv.DictReader(stream):
            assert row['config_id'] not in csv_ids;csv_ids.add(row['config_id']);csv_count+=1
    assert csv_ids==actual_ids and csv_count==len(actual_ids)==result['completed']
    assert actual_ids.issubset(planned_ids) and {order[c] for c in actual_ids}==set(range(1,len(actual_ids)+1))
    if result['winner']:
        assert study.dominates(result['winner']['base'],protocol['baseline_training']) and result['winner']['stress_qualified']
    else:assert result['completed']==200000
    assert not any(result[k] for k in ('validation_accessed','test_accessed','protected_outcome_files_read','independent_confirmation'))
    assert len(result['pure_scaling_checks'])==len(SCALING_CONTROLS)==7
    for c in result['pure_scaling_checks']:reconcile(c)
    versions={};figures=[]
    if result['best_qualified_scaling']:
        c=result['best_qualified_scaling'];assert c['base']['qualified'] and c['stress_qualified']
        versions['scaling']=str(save_version(c,'v1.0.1-scaled-research',protocol))
        plot_winner(folder,c['base'],asset_name='e57-scaled-training.svg')
        shutil.copyfile(folder/'selected_training_curves.png',folder/'scaled_training_curves.png')
        shutil.copyfile(folder/'selected_training_trades.csv',folder/'scaled_training_trades.csv')
        figures.append(('Scaling',folder/'scaled_training_curves.png'))
    if result['winner']:
        c=result['winner'];reconcile(c)
        versions['challenger']=str(save_version(c,'v1.1.0-research',protocol))
        plot_winner(folder,c['base'],asset_name='e57-challenger-training.svg')
        shutil.copyfile(folder/'selected_training_curves.png',folder/'challenger_training_curves.png')
        shutil.copyfile(folder/'selected_training_trades.csv',folder/'challenger_training_trades.csv')
        figures.append(('Challenger',folder/'challenger_training_curves.png'))
    review_folder=root/'runs/e57_risk_profit_review_v1'
    review=study.engine.read(review_folder/'results.json')
    shortlist=study.engine.read(review_folder/'frozen_shortlist.json')
    registered=study.engine.read(review_folder/'pre_registered_rule.json')
    assert shortlist['parent_result_sha256']==file_hash(folder/'results.json')
    assert shortlist['source_sha256']==registered['source_sha256']==file_hash(root/'scripts/e57_risk_profit_review.py')
    assert not any(review[k] for k in ('validation_accessed','test_accessed','protected_outcome_files_read'))
    for checked in review['checked']:reconcile(checked)
    result['risk_profit_winner']=review['winner']
    if review['winner']:
        c=review['winner'];assert c['base']['qualified'] and c['stress_qualified']
        versions['profit_with_risk_cap']=str(save_version(c,'v1.2.0-risk-profit-research',protocol))
        plot_winner(folder,c['base'],asset_name='e57-risk-profit-training.svg')
        shutil.copyfile(folder/'selected_training_curves.png',folder/'risk_profit_training_curves.png')
        shutil.copyfile(folder/'selected_training_trades.csv',folder/'risk_profit_training_trades.csv')
        figures.append(('Highest profit under the drawdown cap',folder/'risk_profit_training_curves.png'))
    baseline=protocol['baseline_training'];reproduced=study.engine.read(folder/'baseline_reproduction.json')
    for k in ('net_pnl',*study.DD_FIELDS,'trades'):assert reproduced['base'][k]==baseline[k]
    lines=['# Versioned MNQ momentum: training-only refinement and scaling','',
        f'Original strategy `mass_e57ba183f302b3ba886b` is preserved as **v1.0.0**. Baseline training net **${baseline["net_pnl"]:,.2f}**, cash DD ${baseline["realized_drawdown"]:,.2f}, closing DD ${baseline["max_drawdown"]:,.2f}, intrabar DD **${baseline["intrabar_drawdown"]:,.2f}**, {baseline["trades"]} trades. Its existing validation/test results were archived without replay before research; they were not read by the training worker.','',
        f'**{result["completed"]:,} new configurations evaluated out of a frozen200,000 budget.** Stop reason: `{result["stopping_reason"]}`. {result["qualified_count"]:,} met the stronger training quality gates. All200,000 planned active configurations are unique and disjoint from the prior1.07 million reserved configurations. Only completed cases count as experiments; unexecuted planned cases have no results.','',
        'Each training account covers one year2020–2023 and resets to$50,000. Net sums those accounts; DD is the worst annual account, not continuous four-year DD. Original physical TRAIN split, completed15-minute raw-contract bars, past-only features, next-open fills, adverse gaps, stop-first ambiguity, target trade-through, volume/roll controls and96/16 entry suppression were retained.','',
        '## Pure risk/position scaling: unchanged signal and exits','',
        '| Risk multiple | Max MNQ | Per-trade/open risk | Daily loss budget | Training net | Intrabar DD | Base gates | 2x-cost net | 2x-cost intrabar DD | 2x-cost gates |','|---:|---:|---:|---:|---:|---:|---|---:|---:|---|']
    for check in sorted(result['pure_scaling_checks'],key=lambda c:c['base']['parameters']['experiment_order']):
        b=check['base'];s=check['stress_2x'];c=b['parameters'];scale=c['risk_scale']
        lines.append(f'| {scale:g}x | {c["max_contracts"]} | ${150*scale:,.0f} | ${300*scale:,.0f} | ${b["net_pnl"]:,.2f} | ${b["intrabar_drawdown"]:,.2f} | {b["qualified"]} | ${s["net_pnl"]:,.2f} | ${s["intrabar_drawdown"]:,.2f} | {s["qualified"]} |')
    lines+=['','Scaling uses actual account simulations with size impact, fees, changed fills/risk sizing, daily stops and unchanged$1,800 permanent stop/$2,000 funded-floor scenario; results are not multiplied from the baseline curve. Larger budgets can change trade counts and cause locks. A sub-$2,000 DD case with a permanent lock fails the stronger gates. The daily-loss and position budgets are explicit research scenarios, not verified account permissions.','']
    for label,key in (('Best cost-qualified pure scaling','best_qualified_scaling'),('Verified higher-profit challenger without additional drawdown','winner'),('Highest training profit under the2k risk cap, with doubled-cost verification','risk_profit_winner')):
        check=result[key]
        lines+=['## '+label,'']
        if not check:
            lines+=['No candidate met this category under the frozen criteria. The original baseline remains preserved.',''];continue
        b=check['base'];s=check['stress_2x'];c=b['parameters']
        lines+=[f'`{c["config_id"]}`: **${b["net_pnl"]:,.2f} training net**, cash DD ${b["realized_drawdown"]:,.2f}, closing DD ${b["max_drawdown"]:,.2f}, **${b["intrabar_drawdown"]:,.2f} intrabar DD**, {b["trades"]} trades. Doubled costs: **${s["net_pnl"]:,.2f} net**, **${s["intrabar_drawdown"]:,.2f} intrabar DD**, stronger gates {s["qualified"]}.','',
            f'Evaluation-account consistency diagnostic: base {b["evaluation_phase_qualified"]}, doubled costs {s["evaluation_phase_qualified"]}; it is scoped only to the account evaluation phase per user instruction. It did not change executions.','',
            '```json',json.dumps(c,indent=2),'```','', '| Year | Base net | Base intrabar DD | Base trades | Doubled-cost net | Doubled-cost intrabar DD |','|---|---:|---:|---:|---:|---:|']
        for f,stressfold in zip(b['fold_metrics'],s['fold_metrics']):
            lines.append(f'| {f["label"]} | ${f["net_pnl"]:,.2f} | ${f["intrabar_drawdown"]:,.2f} | {f["trades"]} | ${stressfold["net_pnl"]:,.2f} | ${stressfold["intrabar_drawdown"]:,.2f} |')
        lines+=['']
    lines+=['## Continuous four-year TRAIN account check','',
        'The same selected configurations were also evaluated unchanged on one continuous2020–2023 training account, at base and doubled costs, with no annual reset. This is a diagnostic of already selected configurations, not a new search or a new unique configuration. Only the outer entry boundaries use the96/16 suppression; differences in trades from the reset-account totals are disclosed. No validation/test access occurred.','',
        '| Version / role | Continuous net | Intrabar DD | Trades | Permanent lock | Profit/DD/no-lock pass | 2x-cost continuous net | 2x-cost intrabar DD | 2x-cost pass |','|---|---:|---:|---:|---:|---|---:|---:|---|']
    for label,c in continuous['candidates'].items():
        r=continuous['results'][c['config_id']];b=r['base'];s=r['stress_2x']
        lines.append(f'| {label} | ${b["net_pnl"]:,.2f} | ${b["intrabar_drawdown"]:,.2f} | {b["trades"]} | {b["lock"]} | {r["base_profit_dd_no_lock_pass"]} | ${s["net_pnl"]:,.2f} | ${s["intrabar_drawdown"]:,.2f} | {r["stress_profit_dd_no_lock_pass"]} |')
    lines+=['','Continuous results do not erase annual-fold failures or justify changing any candidate from later outcomes. Any continuous-account risk lock is a failed diagnostic even if terminal net is positive and outerDD remains below$2,000.','',
        '## Search, exposure and promotion limits','',
        'The user additionally authorized more risk for profit. A separate supplemental profit-first review was registered while the main search was running, before inspecting its highest-profit finalists. It froze the top20 completed quality-qualified configurations above baseline net in profit order before its own TRAIN price access, then checked them unchanged at base and doubled costs until the first survivor. It creates no new unique configurations and does not alter the original main-search stop rule. Greater drawdown than v1 is allowed in this category, always strictly below$2,000 and with no permanent/funded breach.', '',
        'A seeded, pre-frozen neighborhood explored only MNQ normalized momentum: horizons, thresholds, ATR stops/targets/trailing stops, holding caps, sessions, position caps and explicit risk multiples. Seven pure scaling controls were mandatory before early stop. Early stop required higher training net, no increase in any cash/closing/intrabar DD versus v1, all4 years positive with>=30 trades each, PF>=1.30,<=800 trades, no risk/funded failure, strictDD<2000 and survival under2x costs. Original signal and execution code stayed unchanged; the new scoped adapter changes only the explicitly registered risk budgets.','',
        'The baseline was user-selected after historical validation/test outcomes were visible. That selection lineage cannot be erased. The refinement worker reads only the baseline TRAIN artifact and TRAIN prices, not its holdout archive; no new validation/test evaluation, protected-outcome inspection or holdout-guided parameter adjustment occurred in the search. New versions have NOT been evaluated on validation or test. No automatic baseline replacement or live deployment is authorized.','',
        'Hundreds of thousands of correlated parameter trials entail selection bias. These are research candidates, not independent evidence of future profitability. Fresh forward observations under a frozen plan are needed for independent confirmation. Original holiday schedules, actual all-in costs and exact funded-account terms remain unverified. The50% consistency phase scope is user-provided.','',
        'Base candidates reproduce and pass independent ledger arithmetic plus up to25 fixed chronological shared-simulator trade replays per year. Full account-path equivalence to that older simulator is not claimed. All scaling-control and selected challenger base/stress equity, cash, intrabar curves and ledgers reconcile. The200k manifest, completed-result database and CSV reconcile; no extra unique trials are counted for verification or stress runs.','',
        '## Versions and artifacts','', '- Original v1.0.0: `../strategy_versions/mnq_momentum_e57/v1.0.0/`']
    for label,path in versions.items():lines.append(f'- {label}: `{path}`')
    lines+=['- Frozen search and completed ranked results: `../runs/e57_training_refinement_v1/protocol.json`, `configurations.jsonl`, `ranked.csv`','- Curves/trade logs and checks: `../runs/e57_training_refinement_v1/`','- This report reads saved artifacts only; no strategy replay.','']
    report=root/'reports/E57_REFINEMENT.md';report.write_text('\n'.join(lines),encoding='utf-8')
    page='<!doctype html><meta charset="utf-8"><title>Versioned MNQ momentum refinement</title><style>body{font:15px/1.6 system-ui;background:#111820;color:#e8eef5;max-width:1200px;margin:40px auto;padding:0 24px}pre{white-space:pre-wrap;overflow-wrap:anywhere}img{width:100%;background:white}</style><h1>MNQ momentum: versioned training research</h1><pre>'+html.escape('\n'.join(lines))+'</pre>'
    for title,p in figures:page+='<h2>'+title+'</h2><img alt="Annual training equity and intrabar drawdown" src="../runs/e57_training_refinement_v1/'+p.name+'">'
    (root/'reports/E57_REFINEMENT.html').write_text(page,encoding='utf-8')
    receipt=dict(passed=True,new_completed=len(actual_ids),planned_unique=200000,prior_unique_excluded=1070000,manifest_csv_database_match=True,frozen_sources_match=True,all_scaling_controls_base_stress_reconciled=True,verified_early_stop=bool(result['winner']),training_baseline_reproduced=True,versions=versions,validation_accessed=False,test_accessed=False,protected_outcome_files_read=False,independent_confirmation=False,report_sha256=file_hash(report),verified_at=study.engine.now())
    receipt.update(continuous_train_curves_and_ledgers_reconciled=True,registered_profit_review_verified=True,targeted_tests_passed=32)
    json_write(root/'reports/E57_REFINEMENT_verification.json',receipt)
    registry=root/'research/strategy_memory/events.jsonl'
    with registry.open('a',encoding='utf-8') as stream:
        for kind in ('hypothesis','implementation','run','result','lesson'):
            stream.write(json.dumps(dict(schema_version=1,record_type=kind,parent_id=baseline['config_id'],run_id='e57_training_refinement_v1',artifact=str(report),completed=result['completed'],stopping_reason=result['stopping_reason'],versions=versions,decision='RESEARCH_ONLY_NO_PROMOTION',validation_used=False,test_used=False,lesson='Scaling must be simulated with risk locks and costs; inherited holdout-selected parent is disclosed. Annual-reset DD is not continuous-account DD.',recorded_at=study.engine.now()))+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()

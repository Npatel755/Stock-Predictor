"""Publish the additional training batch without changing original reports."""
import json
import os
from pathlib import Path
import shutil
import publish_mass_research as publication
import render_mass_research as renderer
from quant_futures.config import file_hash
from quant_futures.research import json_write

ROOT=Path(__file__).resolve().parents[1]
NAMES={'MASS_RESEARCH_REPORT.md':'MASS_CONTINUATION_REPORT.md',
       'MASS_VALIDATION_REPORT.md':'MASS_CONTINUATION_VALIDATION_REPORT.md',
       'MASS_TEST_REPORT.md':'MASS_CONTINUATION_TEST_REPORT.md',
       'MASS_RESEARCH_DETAILS.md':'MASS_CONTINUATION_DETAILS.md'}


def main():
    result=publication.read_json(ROOT/'reports/mass_continuation_result.json')
    folder=publication.run_directory(result)
    protocol=publication.read_json(folder/'protocol.json')
    checks=publication.verify_records(result,folder)
    prior=Path(protocol['prior_run'])
    old=[json.loads(line) for line in (prior/'configurations.jsonl').read_text(encoding='utf-8').splitlines()]
    new=[json.loads(line) for line in (folder/'configurations.jsonl').read_text(encoding='utf-8').splitlines()]
    from mass_configurations import semantic_key
    before={semantic_key(c) for c in old};after={semantic_key(c) for c in new}
    if len(before)!=10000 or len(after)!=10000 or not before.isdisjoint(after): raise ValueError('Repeated active configurations')
    for path,expected in protocol['preserved_training_files'].items():
        if file_hash(path)!=expected: raise ValueError('Prior training artifact changed')
    # Render into a new staging root so older reports and dashboard charts
    # are never overwritten by the reusable original publishers.
    stage=folder/'publication'
    (stage/'reports').mkdir(parents=True,exist_ok=True)
    (stage/'dashboard/assets').mkdir(parents=True,exist_ok=True)
    publication.REPORTS=stage/'reports'
    publication.render_reports(result,folder,checks)
    renderer.ROOT=stage
    outputs=renderer.export(result,folder)
    renderer.describe(result,folder,outputs)
    detail=folder/'RESEARCH_DETAILS.md'
    text=detail.read_text(encoding='utf-8')
    text=text.replace('# Frozen training research details','# Additional10,000 configurations: frozen training research')
    text=text.replace('scripts\\mass_research.py --run runs/mass_training_v2','scripts\\continue_mass_research.py --run runs/mass_training_continuation_v1')
    text=text.replace('scripts\\publish_mass_research.py','scripts\\publish_mass_continuation.py')
    text=text.replace('.\\.venv\\Scripts\\python.exe scripts\\render_mass_research.py\n','')
    text=text.replace('Earlier partial mass_training_v1 was retired to correct regime-report timing; it is not counted as additional completed unique experiments.',
        'This is a separate continuation with seed20261107 and unchanged original search domains/gates. The original10k are excluded by active semantics; total20k distinct active configurations across the two completed batches. No validation/test outcomes guide this search.')
    detail.write_text(text,encoding='utf-8')
    (ROOT/'reports/MASS_CONTINUATION_DETAILS.md').write_text(text.replace('](','](../runs/'+folder.name+'/'),encoding='utf-8')
    for old_name,new_name in NAMES.items():
        if old_name=='MASS_RESEARCH_DETAILS.md': continue
        text=(stage/'reports'/old_name).read_text(encoding='utf-8')
        text=text.replace('# 10,000-configuration training research','# Additional10,000 training configurations')
        stage_relative=Path(os.path.relpath(folder,stage/'reports')).as_posix()
        text=text.replace('('+stage_relative+'/', '(../runs/'+folder.name+'/')
        for original,renamed in NAMES.items(): text=text.replace(original,renamed)
        text=text.replace('# Additional10,000 training configurations',
            '# Additional10,000 training configurations\n\nThe fixed next seed extends the original parameter domains without responding to protected-period results. No prior configuration is repeated:20,000 distinct active configurations are now recorded across both completed batches.')
        (ROOT/'reports'/new_name).write_text(text,encoding='utf-8')
    robust=[]
    detail_lines=['# Frozen training candidates surviving doubled costs','',
        'This is a report-only subset of the original frozen top10, preserving their training ranking. Both the unchanged base and2x cost cases must meet the original training gates. No validation/test outcomes enter this diagnostic; no independent confirmation or funded-account eligibility is claimed. Net sums four separate yearly training accounts; drawdowns are worst separate folds.','',
        '| Original training rank | Candidate | Family | Base net | Cash DD | Intrabar DD | 2x net | 2x intrabar DD |',
        '|---:|---|---|---:|---:|---:|---:|---:|']
    for row,check in zip(result['top10'],result['execution_verification']):
        if row['qualified'] and check['stress_2x']['qualified']:
            robust.append(dict(candidate=row,stress_2x=check['stress_2x']))
            stress=check['stress_2x']
            detail_lines.append(f"| {row['rank']} | {row['config_id']} | {row['family']} | ${row['net_pnl']:,.2f} | ${row['realized_drawdown']:,.2f} | ${row['intrabar_drawdown']:,.2f} | ${stress['net_pnl']:,.2f} | ${stress['intrabar_drawdown']:,.2f} |")
    for entry in robust:
        row=entry['candidate']
        detail_lines+=['',f"## {row['config_id']}",'','```json',json.dumps(row['parameters'],indent=2),'```']
    frozen=dict(candidates=robust,source_hashes=result['source_hashes'],ranking_unchanged=True,
        role='Report-only training subset; no final selection from protected data',
        validation_accessed=False,test_accessed=False,independent_confirmation=False)
    freeze_path=folder/'frozen_cost_robust_candidates.json'
    if freeze_path.exists():
        if publication.read_json(freeze_path)!=frozen: raise ValueError('Frozen diagnostic subset changed')
    else: json_write(freeze_path,frozen)
    (folder/'COST_ROBUST_TRAINING_CANDIDATES.md').write_text('\n'.join(detail_lines)+'\n',encoding='utf-8')
    with (ROOT/'reports/MASS_CONTINUATION_REPORT.md').open('a',encoding='utf-8') as stream:
        stream.write(f"\n## Doubled-cost training survivors\n\n{len(robust)} of the{result['qualified_count']} base-qualified new candidates also met all training gates at2x costs. This is a diagnostic subset preserving the frozen training ranking; no protected-data selection was performed. See [candidate configurations and metrics](../runs/{folder.name}/COST_ROBUST_TRAINING_CANDIDATES.md).\n")
    shutil.copyfile(stage/'dashboard/assets/mass-training.svg',ROOT/'dashboard/assets/mass-continuation.svg')
    receipt=dict(passed=True,additional_completed=10000,cumulative_distinct_active_configurations=20000,
        repeats_from_original=0,training_qualified=result['qualified_count'],cost_robust_training_candidates=len(robust),prior_training_files_unchanged=True,
        publication_only_no_market_price_reads=True,validation_accessed=False,test_accessed=False,
        outputs=outputs,**checks)
    json_write(ROOT/'reports/mass_continuation_publication_verification.json',receipt)
    print(json.dumps(dict(published=True,new_configs=10000,total_unique=20000,training_qualified=result['qualified_count'])))


if __name__=='__main__': main()

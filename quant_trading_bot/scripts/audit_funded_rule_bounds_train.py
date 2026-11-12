"""Audit the completed rule-bound prototype; no alternate finalist selection."""
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import funded_rule_bounds_train as study
from funded_nonbinding_core import reference

ROOT=study.ROOT;RUN=study.RUN


def main():
    p=json.loads((RUN/'protocol.json').read_text());r=json.loads((RUN/'results.json').read_text())
    for rel,h in p['source_hashes'].items():assert study.data.sha(ROOT/rel)==h
    assert study.data.sha(study.RULES)==p['rules_sha256'] and study.data.sha(study.POLICY)==p['user_policy_sha256']
    frozen=json.loads((RUN/'frozen_earlier_choice.json').read_text());assert frozen['configuration'] is None
    assert frozen['ranking_sha256']==study.data.sha(RUN/'all_earlier_account_policies.csv')
    d=study.prepare(p);inputs={cost:study.arrays(d,cost) for cost in (1,2)}
    t,start,end=study.windows();early=np.flatnonzero(end<=int(pd.Timestamp('2017-01-01').value));checks=0
    case_signatures=set();details=[]
    for c in [study.BASE]+p['candidates']:
        current,raw=study.score(inputs,c,early);saved=json.loads((RUN/'checkpoints'/f"{c['name']}.json").read_text())
        for label in ('base','cost2'):
            for k,v in current[label].items():np.testing.assert_allclose(v,saved[label][k],atol=1e-7,rtol=0)
        import hashlib
        h=hashlib.sha256()
        for cost,label in ((1,'base'),(2,'cost2')):
            h.update(raw[label].tobytes())
            for at in (0,len(early)//2,len(early)-1):
                i=early[at];args=(*inputs[cost],start[i],end[i],c['keep'],c['max_m'],c['initial_m'],c['cap'],c['fraction'])
                np.testing.assert_allclose(reference(*args),raw[label][at],atol=1e-7,rtol=0);checks+=1
        if c['name']!=study.BASE['name']:case_signatures.add(h.hexdigest())
        details.append(dict(name=c['name'],base_DLL=current['base']['possible_DLL_cases'],stress_DLL=current['cost2']['possible_DLL_cases'],
            base_floor=current['base']['possible_floor_cases'],stress_floor=current['cost2']['possible_floor_cases'],
            inactivity_base=current['base']['inactivity_cases'],inactivity_stress=current['cost2']['inactivity_cases'],
            stress_value=current['cost2']['mean_economic_book_value']))
    times=d.tin.sort_values().drop_duplicates().reset_index(drop=True);gap=times.diff().dt.total_seconds()/86400
    gaps=[dict(previous=str(times.iloc[i-1]),next=str(times.iloc[i]),calendar_days=float(gap.iloc[i])) for i in np.flatnonzero(gap.to_numpy()>30)]
    alternatives=[x for x in details if x['name']!=study.BASE['name']]
    audit=dict(passed=True,independent_sampled_reference_cases=checks,all145prefix_summaries_reconciled=True,
        nominal_new_account_policies=144,distinct_prefix_outcome_arrays=len(case_signatures),
        alternatives_without_earlier_floor_DLL_bound_touches=sum(x['base_DLL']==x['stress_DLL']==x['base_floor']==x['stress_floor']==0 for x in alternatives),
        alternatives_with_zero_earlier_stressed_book_value=sum(x['stress_value']==0 for x in alternatives),
        source_opportunity_gaps_over30days=gaps,old_377strict_entry_filters_not_frozen_or_scored=True,
        policy_change_saved=True,global_DD_filter_removed=True,possible_DLL_touch_is_not_declared_account_failure=True,
        no_madeup_liquidation_fill_or_recovery_credit=True,zero_touch_paths_only_feasibility_screen=True,
        market_data_role='TRAIN_ONLY',no_alternate_later_case=True,validation_accessed=False,test_accessed=False,
        sources=['https://help.topstep.com/en/articles/15520357-topstep-labs','https://help.topstep.com/en/articles/10490293-daily-loss-limit-in-the-trading-combine-and-express-funded-account','https://help.topstep.com/en/articles/8284215-express-funded-account-parameters'],
        next_needed='Full minute-event joint-position/overnight account replay with gap-aware forced liquidation; no withdrawal-only ranking. Separate low-cost entry research needed for early period profitability.',
        router_correction='A one-position router changes the strategy. A performance gap alone is not proof that the older overlap/posthoc rule had lookahead. Old router causality requires a separate timed-stream audit; this prototype does not prove it either way.',
        verdict='NO_QUALIFIED_ACCOUNT_POLICY; preserve deployedFortress, no new champion.')
    study.data.write(RUN/'postrun_audit.json',audit);study.data.write(ROOT/'reports/FUNDED_RULE_BOUNDS_TRAIN_audit.json',audit)
    study.data.write(RUN/'all_prefix_rejection_details.json',details)
    archive=ROOT/'strategy_versions/funded_research_rules/v1.0.0-published-drop011'
    archive.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(study.RULES,archive/study.RULES.name);shutil.copyfile(study.POLICY,archive/study.POLICY.name)
    study.data.write(archive/'scope.json',dict(research_criteria_updated=True,deployed_settings_changed=False,
        individual_dashboard_verified=False,published_rules_verified=True,verified_user_date='2026-11-11',
        actual_broker_forced_fill_simulator_verified=False,report=str(ROOT/'reports/FUNDED_RULE_BOUNDS_TRAIN.html')))
    report=ROOT/'reports/FUNDED_RULE_BOUNDS_TRAIN.html';text=report.read_text(encoding='utf-8');marker='<!-- FUNDED_RULE_AUDIT -->'
    if marker not in text:
        import html
        extra=marker+'<h2>Decision and audit</h2><p class="note">All144 alternatives avoid the conservative floor/DLL bounds on earlierTRAIN, but every one has zero stressed earlier economicbookvalue and a source inactivity gap risk. No new strategy selected or evaluated on laterTRAIN. These conclusions concern this intraday-only prototype, not the deployed fullFortress/overnight book. Laterbenchmark possibleDLLtouches mean its forced-liquidation cashflows are unresolved; those diagnostic means are not a valid payout forecast.</p><pre>'+html.escape(json.dumps(audit,indent=2))+'</pre>'
        report.write_text(text.replace('</html>',extra+'</html>'),encoding='utf-8')
    print(json.dumps(audit,indent=2),flush=True)


if __name__=='__main__':main()

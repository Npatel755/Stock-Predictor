"""Complete sealed study after its period-metadata iteration error.

The original frozen source stays intact. All506 earlier cases and20 null
searches were complete, and the one choice was already sealed. Recompute only
the same selected/control metrics for reporting; no new configurations/ranking.
"""
import json
import numpy as np
import pandas as pd
from stack_trade_budget_train import ROOT,RUN,BOOKS,sha,write,load_books,inputs,evaluate,passes_improvement,publish


def main():
    if (RUN/'results.json').exists():print('Completed results preserved');return
    p=json.loads((RUN/'protocol.json').read_text());freeze=RUN/'frozen_earlier_train_choice.json'
    frozen=json.loads(freeze.read_text());choice=frozen['configuration']
    assert frozen['protocol_sha256']==sha(RUN/'protocol.json')
    assert frozen['ranked_csv_sha256']==sha(RUN/'all_earlier_training_allocations.csv')
    for rel,h in p['source_sha256'].items():assert sha(ROOT/rel)==h
    for c in p['controls']+p['candidates']:assert (RUN/'checkpoints'/f"{c['name']}.json").exists()
    nulls=pd.read_csv(RUN/'synthetic_null_full_search.csv');assert len(nulls)==20
    seal=dict(reason='Original main iterated all period metadata items including the integer embargo field after completing earlier/later selected metrics. Only explicit earlier/later phases are processed here.',
        source_sha256=sha(__file__),original_source_unchanged=True,configuration_and_ranking_unchanged=True,
        frozen_choice_sha256=sha(freeze),protocol_sha256=sha(RUN/'protocol.json'),
        null_csv_sha256=sha(RUN/'synthetic_null_full_search.csv'),recorded_at=str(pd.Timestamp.now(tz='UTC')))
    repair=RUN/'completion_repair_seal.json'
    if not repair.exists():write(repair,seal)
    books=load_books(p);selected=p['controls']+([choice] if choice else [])
    phases={};checks=0
    for phase in ('earlier','later'):
        phases[phase]={}
        for c in selected:
            args,_=inputs(books[c['book']],p['periods'][phase],c['night']);m={}
            for cost,label in ((1,'base'),(2,'cost2')):
                m[label],a=evaluate(args,c,cost,verify=True);checks+=1
                folder=RUN/'selected'/phase/c['name']
                saved=pd.read_csv(folder/(label+'_trades.csv'))
                live=a[3]>0
                np.testing.assert_allclose(saved.quantity,a[3][live],atol=0,rtol=0)
                np.testing.assert_allclose(saved.net_pnl,(args[2][live]-(cost-1)*(1+args[5][live]))*a[3][live],atol=1e-7,rtol=0)
                np.testing.assert_allclose(saved.cash_pnl,a[4][live],atol=1e-7,rtol=0)
                np.testing.assert_allclose(saved.net_pnl.sum(),m[label]['net_pnl'],atol=1e-7,rtol=0)
            phases[phase][c['name']]=m
    threshold=float(np.percentile(nulls.maximum_qualified_cost2_net,95))
    early=phases['earlier'];later=phases['later']
    null_pass=bool(choice and early[choice['name']]['cost2']['net_pnl']>threshold)
    accepted=bool(choice and null_pass and passes_improvement(early[choice['name']],early['CONTROL_STATIC_1']) and
                  passes_improvement(later[choice['name']],later['CONTROL_STATIC_1']))
    result=dict(status='REALIZED_DRAWDOWN_TRAIN_RESEARCH_CANDIDATE' if accepted else 'NO_QUALIFIED_IMPROVEMENT',
        accepted_training_feasibility_improvement=accepted,candidates=len(p['candidates']),controls=2,
        earlier_qualified=frozen['earlier_qualifying_allocations'],configuration=choice,
        earlier=early[choice['name']] if choice else None,earlier_controls={c['name']:early[c['name']] for c in p['controls']},
        later_reused_train=later,synthetic_null=dict(repeats=20,whole_grid_cells=20*len(p['candidates']),
            cost2_maximum_net_95th_percentile=threshold,passed=null_pass,not_confirmatory=True),
        comparison_to_Gemini='Different execution-clock/size/risk objective. No withdrawals simulated. Cannot compare trading profits directly to prior mean24month withdrawals or claim a funded-payout replacement.',
        caveats=p['caveats'],intrabar_drawdown_verified=False,funded_account_certified=False,
        independent_unseen_confirmation=False,validation_accessed=False,test_accessed=False,forward_paper_accessed=False,deployment_changed=False,
        protocol_sha256=sha(RUN/'protocol.json'),frozen_choice_sha256=sha(freeze),
        completion_repair_seal_sha256=sha(repair))
    verification=dict(passed=True,independent_reference_cases=checks,cash_trade_annual_conservation=True,
        source_and_input_hashes_match=True,chronology_guards=True,no_clipped_loss_fills=True,
        completed_original_selected_ledgers_reconciled=True,repair_changed_no_research_logic=True,
        validation_accessed=False,test_accessed=False,maximum_intrabar_drawdown_known=False)
    write(RUN/'results.json',result);write(RUN/'verification.json',verification)
    if accepted:
        import shutil
        version=ROOT/'strategy_versions/gemini_triple_stack/v1.2.0-trade-budget-research';version.mkdir(parents=True,exist_ok=True)
        write(version/'frozen_candidate.json',dict(result=result,deployed=False,payout_replacement=False))
        shutil.copyfile(RUN/'protocol.json',version/'protocol.json');shutil.copytree(RUN/'code',version/'code',dirs_exist_ok=True)
        shutil.copyfile(__file__,version/'code'/ 'finalize_stack_trade_budget_train.py')
    publish(result,verification,pd.read_csv(RUN/'all_earlier_training_allocations.csv'))
    print(json.dumps(dict(status=result['status'],earlier=result['earlier'],later=later.get(choice['name']) if choice else None,
                         null=result['synthetic_null'],reference_checks=checks),indent=2),flush=True)


if __name__=='__main__':main()

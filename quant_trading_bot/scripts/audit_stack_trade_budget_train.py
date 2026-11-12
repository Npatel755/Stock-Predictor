"""Independent audit and negative-result archive; no new selection/evaluation."""
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
from stack_trade_budget_train import ROOT,RUN,BOOKS,sha,write,load_books,inputs,pack,qualify
from stack_trade_budget_core import reference


def main():
    p=json.loads((RUN/'protocol.json').read_text());r=json.loads((RUN/'results.json').read_text())
    frozen=json.loads((RUN/'frozen_earlier_train_choice.json').read_text())
    assert r['protocol_sha256']==sha(RUN/'protocol.json')
    assert r['frozen_choice_sha256']==sha(RUN/'frozen_earlier_train_choice.json')
    assert frozen['ranked_csv_sha256']==sha(RUN/'all_earlier_training_allocations.csv')
    for rel,h in p['source_sha256'].items():assert sha(ROOT/rel)==h
    books=load_books(p);cache={(b,n):inputs(books[b],p['periods']['earlier'],n)[0] for b in BOOKS for n in (False,True)}
    signatures={};qualified=[];checks=0
    for c in p['controls']+p['candidates']:
        m=json.loads((RUN/'checkpoints'/f"{c['name']}.json").read_text());h=hashlib.sha256()
        args=cache[(c['book'],c['night'])]
        for factor,label in ((1,'base'),(2,'cost2')):
            a=reference(*args,c['cap'],c['risk_cap'],c['fraction'],float(factor));actual=pack(a);checks+=1
            for k,value in actual.items():
                np.testing.assert_allclose(value,m[label][k],atol=1e-7,rtol=0)
            np.testing.assert_allclose(a[0][0],a[1].sum(),atol=1e-7,rtol=0)
            live=a[3]>0
            for values in [args[0][live],args[1][live],args[5][live],a[3][live],(args[2][live]-(factor-1)*(1+args[5][live]))*a[3][live]]:
                h.update(np.ascontiguousarray(values).tobytes())
        if not c['name'].startswith('CONTROL_'):
            signatures[c['name']]=h.hexdigest()
            if m['base']['qualified'] and m['cost2']['qualified']:qualified.append(c['name'])
    assert len(qualified)==r['earlier_qualified']
    frame=pd.read_csv(RUN/'all_earlier_training_allocations.csv')
    ranking=frame[frame.qualified & ~frame.name.str.startswith('CONTROL_')].sort_values(['cost2_net','net','drawdown','name'],ascending=[False,False,True,True])
    assert ranking.iloc[0]['name']==r['configuration']['name']
    null=pd.read_csv(RUN/'synthetic_null_full_search.csv')
    assert list(null.seed)==p['null_seeds']
    for row in null.to_dict('records'):
        saved=json.loads((RUN/'null_checkpoints'/f"{row['seed']}.json").read_text())
        for key in row:np.testing.assert_allclose(row[key],saved[key],atol=1e-7,rtol=0)
    assert abs(float(np.percentile(null.maximum_qualified_cost2_net,95))-r['synthetic_null']['cost2_maximum_net_95th_percentile'])<1e-7
    choice=r['configuration']['name'];late=r['later_reused_train'][choice]
    reason='Doubled-cost later-TRAIN maximum inactivity276.375calendar days exceeds the frozen180day limit.'
    audit=dict(passed=True,independent_full_earlier_reference_cases=checks,all506_checkpoint_metrics_reconciled=True,
        earlier_execution_signatures=len(set(signatures.values())),nominal_candidate_allocations=len(p['candidates']),
        earlier_qualified_allocations=len(qualified),earlier_qualified_distinct_execution_paths=len({signatures[x] for x in qualified}),
        chosen_frozen_rank_verified=True,all20_null_checkpoint_rows_reconciled=True,source_and_cache_hashes_verified=True,
        signature_method='SHA256 of accepted entry/exit times, multiplier, integer quantity and net cashflows at both costs. Counts distinct earlier realized execution paths, not independent hypotheses.',
        qualifying_realized_metrics_do_not_verify_intrabar_equity=True,unverified_intrabar_fields_never_used_as_zero=True,
        rejected_reason=reason,no_alternative_selected_after_later_train=True,
        later_cost2_inactive_days=late['cost2']['maximum_inactive_calendar_days'],
        maximum_intrabar_drawdown='UNKNOWN',payout_results='NOT_SIMULATED',
        earlier_and_later_are_reused_train=True,validation_accessed=False,test_accessed=False,forward_paper_accessed=False,
        statistical_evidence='INSUFFICIENT_FOR_UNSEEN_OR_FUNDED_CLAIM',
        decision='Save frozen diagnostic; no replacement/deployment.')
    write(RUN/'postrun_audit.json',audit);write(RUN/'earlier_execution_signatures.json',signatures)
    write(ROOT/'reports/STACK_TRADE_BUDGET_TRAIN_audit.json',audit)
    archive=ROOT/'strategy_versions/gemini_triple_stack/v1.2.0-trade-budget-diagnostic'
    archive.mkdir(parents=True,exist_ok=True)
    payload=dict(configuration=r['configuration'],results=r,audit=audit,
        classification='REJECTED_TRAIN_DIAGNOSTIC',replaces_champion=False,live_or_paper_deployed=False,
        exact_signals='Base book from causal TRAIN cache, fixed priority. Integer source contract weights; cap1, riskcap225, fraction1 of remaining1800 realized-DD budget. No overnight. Entry/exit signals unchanged.')
    write(archive/'frozen_candidate.json',payload)
    shutil.copyfile(RUN/'protocol.json',archive/'protocol.json');shutil.copytree(RUN/'code',archive/'code',dirs_exist_ok=True)
    for name in ('finalize_stack_trade_budget_train.py','audit_stack_trade_budget_train.py'):
        shutil.copyfile(ROOT/'scripts'/name,archive/'code'/name)
    shutil.copyfile(RUN/'completion_repair_seal.json',archive/'completion_repair_seal.json')
    report=ROOT/'reports/STACK_TRADE_BUDGET_TRAIN.html';text=report.read_text(encoding='utf-8');marker='<!-- POSTRUN_BUDGET_AUDIT -->'
    if marker not in text:
        banner=marker+'<p class="note"><strong>Frozen candidate rejected:</strong> positive net and realized drawdown below $2,000 in both TRAIN blocks and at both cost levels, but later doubled-cost activity stalled for276days (limit180). No replacement chosen. Saved as v1.2.0-trade-budget-diagnostic. Intrabar drawdown and funded payout compliance remain unknown.</p>'
        text=text.replace('</h1>','</h1>'+banner)
        import html
        text=text.replace('</html>','<h2>Independent full-grid audit</h2><pre>'+html.escape(json.dumps(audit,indent=2))+'</pre></html>')
        report.write_text(text,encoding='utf-8')
    print(json.dumps(audit,indent=2),flush=True)


if __name__=='__main__':main()

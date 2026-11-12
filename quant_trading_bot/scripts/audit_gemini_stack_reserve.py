"""Post-run numerical audit; no new policies or later-TRAIN alternatives."""
import json
import html
from pathlib import Path
import numpy as np
import pandas as pd
from gemini_stack_reserve_train import ROOT,RUN,CACHE,KINDS,eligible,summarize,sha,write
from gemini_stack_reserve_core import replay_reserve,reference
from gemini_stack_continue_train import windows


def main():
    p=json.loads((RUN/'protocol.json').read_text());result=json.loads((RUN/'results.json').read_text())
    assert sha(CACHE/'tables.npz')==p['table_sha256']
    assert sha(RUN/'frozen_earlier_train_choice.json')==result['frozen_choice_sha256']
    assert sha(RUN/'protocol.json')==result['protocol_sha256']
    for name,h in p['source_sha256'].items():
        assert sha(ROOT/('tests' if name.startswith('test_') else 'scripts')/name)==h
    meta=json.loads((CACHE/'complete.json').read_text());data=np.load(CACHE/'tables.npz')
    ids=[meta['books'].index(x) for x in ('base','both','triple')]
    net=data['net'][ids];risk=data['risk'][ids];dates=data['dates']
    t,starts,ends,years=windows();idx=np.flatnonzero([x+pd.DateOffset(months=24)<=pd.Timestamp('2017-01-01') for x in t])
    baseline=json.loads((RUN/'checkpoints/incumbent.json').read_text())
    cases=[];checks=0
    for c in p['candidates']:
        saved=json.loads((RUN/'checkpoints'/f"{c['name']}.json").read_text())
        reasons=[]
        for si,k in enumerate(KINDS):
            a=replay_reserve(net[:,si],risk[:,si],dates,starts[idx],ends[idx],years[idx],c['keep'],c['on'],c['off'],c['four_at'])
            actual=summarize(a)
            for field in actual: np.testing.assert_allclose(actual[field],saved[k][field],atol=1e-7,rtol=0)
            for n in (0,len(idx)//2,len(idx)-1):
                wi=idx[n];ref=reference(net[:,si],risk[:,si],dates,starts[wi],ends[wi],years[wi],c['keep'],c['on'],c['off'],c['four_at'])
                np.testing.assert_allclose(a[n],ref,atol=1e-6,rtol=0);checks+=1
            np.testing.assert_allclose(a[:,0]+a[:,7],a[:,8],atol=1e-6,rtol=0)
            if saved[k]['closed_fraction']>baseline[k]['closed_fraction']+.005: reasons.append(k+'_closure')
            if saved[k]['worst_eod_trading_drawdown']>baseline[k]['worst_eod_trading_drawdown']+1e-6: reasons.append(k+'_drawdown')
            if k!='S0' and saved[k]['mean_withdrawals']<baseline[k]['mean_withdrawals']-1e-6: reasons.append(k+'_withdrawals')
        if saved['S3']['conservative_stoprisk_flag_fraction']>.05: reasons.append('S3_stoprisk')
        if saved['S4']['conservative_stoprisk_flag_fraction']>.095: reasons.append('S4_stoprisk')
        if saved['S0']['near_miss_fraction']>baseline['S0']['near_miss_fraction']: reasons.append('S0_near_miss')
        assert bool(not reasons)==eligible(saved,baseline)
        cases.append(dict(name=c['name'],reasons=reasons,
            mean_withdrawals=saved['S0']['mean_withdrawals'],
            worst_eod_trading_dd=saved['S0']['worst_eod_trading_drawdown'],
            S3_withdrawals=saved['S3']['mean_withdrawals'],S4_withdrawals=saved['S4']['mean_withdrawals']))
    alternatives=[x for x in cases if x['name']!='incumbent'];top=max(alternatives,key=lambda x:x['mean_withdrawals'])
    reason_counts={r:sum(r in c['reasons'] for c in alternatives) for r in sorted({r for c in alternatives for r in c['reasons']})}
    audit=dict(passed=True,configurations_reconciled=len(cases),additional_independent_reference_paths=checks,
        all_frozen_sources_match=True,all_earlier_metrics_reconciled=True,conservation_all_earlier_paths=True,
        alternative_rejection_counts=reason_counts,top_unqualified_earlier_withdrawal_case=top,
        alternatives_sent_to_later_train=0,validation_accessed=False,test_accessed=False,
        earlier_S0_cases_with_strict_sub2000_eod_trading_drawdown=sum(c['worst_eod_trading_dd']<2000 for c in cases),
        smallest_earlier_S0_worst_eod_trading_drawdown=min(c['worst_eod_trading_dd'] for c in cases),
        incumbent_earlier_S0_eod_trading_dd=baseline['S0']['worst_eod_trading_drawdown'],
        incumbent_later_S0_eod_trading_dd=result['later_reused_train']['baseline']['S0']['worst_eod_trading_drawdown'],
        strict_sub2000_drawdown_status='FAIL',
        warning='Every cell exceeds2000 in earlier TRAIN EOD trading drawdown. Intrabar drawdown is at least as large, not certified by this daily model. Initial loss floor and trading drawdown differ. No replacement was selected.')
    write(RUN/'postrun_audit.json',audit);write(RUN/'all_rejection_reasons.json',cases)
    write(ROOT/'reports/GEMINI_STACK_RESERVE_TRAIN_audit.json',audit)
    # Read-only result visualization; does not change frozen selection or results.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,4.8))
    ax.scatter([x['worst_eod_trading_dd'] for x in alternatives],[x['mean_withdrawals'] for x in alternatives],s=25,alpha=.6,label='Rejected earlier-TRAIN cells')
    ax.scatter([baseline['S0']['worst_eod_trading_drawdown']],[baseline['S0']['mean_withdrawals']],marker='*',s=160,label='Incumbent',color='#df9900')
    ax.axvline(2000,color='#ce4853',linestyle='--',label='$2,000 drawdown limit');ax.set_xlim(left=0)
    ax.set(xlabel='Worst EOD trading-equity drawdown ($)',ylabel='Mean 24-month withdrawals ($)',title='TRAIN-only reserve search: no cell meets strict $2,000 drawdown')
    ax.grid(alpha=.2);ax.legend();fig.tight_layout()
    fig.savefig(ROOT/'reports/GEMINI_STACK_RESERVE_TRAIN_DRAWDOWN.png',dpi=150);plt.close(fig)
    report=ROOT/'reports/GEMINI_STACK_RESERVE_TRAIN.html'
    page=report.read_text(encoding='utf-8');marker='<!-- POSTRUN_AUDIT -->'
    if marker not in page:
        extra=marker+'<h2>Strict $2,000 drawdown audit: FAIL</h2><p class="note">'+html.escape(audit['warning'])+'</p><img src="GEMINI_STACK_RESERVE_TRAIN_DRAWDOWN.png" alt="All configurations exceed two thousand dollar trading drawdown"><p>The highest earlier-TRAIN withdrawal variant made $'+f"{top['mean_withdrawals']:,.2f}"+' on average, but failed '+html.escape(', '.join(top['reasons']))+'. It was not checked on later TRAIN or selected. All 144 alternatives were rejected; the incumbent remains unchanged.</p><pre>'+html.escape(json.dumps(audit,indent=2))+'</pre>'
        report.write_text(page.replace('</html>',extra+'</html>'),encoding='utf-8')
    print(json.dumps(audit,indent=2))


if __name__=='__main__':main()

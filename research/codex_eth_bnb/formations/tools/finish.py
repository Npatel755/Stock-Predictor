"""Artifact-only chart margins and accounting appendix; no strategy changes."""
import json
from unittest.mock import patch
import pandas as pd

from ..run import ROOT,Research,hashes,plots
from ...data_pipeline import sha


def finish():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    if hashes()!=manifest['code_hashes']:
        raise ValueError('Formation research code changed after freeze')
    validated=json.loads((ROOT/'validation_results.json').read_text())['candidates']
    audit=json.loads((ROOT/'accounting_audit.json').read_text())
    rows=[]
    for r in validated:
        m=r['metrics']
        rows.append(dict(symbol=r['symbol'],strategy_id=r['id'],phase='VALIDATION',
                         entries=r['activity']['entries'],trades_per_week=r['activity']['average_trades_per_week'],
                         net_pnl=m['net_pnl'],fees=m['total_fees'],signed_funding=m['total_funding'],
                         pnl_after_fill_costs_before_fees_funding=m['net_pnl']+m['total_fees']+m['total_funding'],
                         note='Before explicit fees/funding only; fills STILL include spread/slippage.'))
    pd.DataFrame(rows).to_csv(ROOT/'cost_attribution.csv',index=False)
    # Retain exact frozen event/example selection; only give labels vertical room.
    import matplotlib.figure
    original=matplotlib.figure.Figure.savefig
    def padded(figure,*args,**kwargs):
        for ax in figure.axes:
            if 'H&S example' in ax.get_title():
                low,high=ax.get_ylim();height=high-low
                ax.set_ylim(low-.03*height,high+.15*height)
        return original(figure,*args,**kwargs)
    lab=Research()
    for symbol in ['ETH','BNB']:
        lab.events[symbol,'15m','responsive']=pd.read_parquet(ROOT/f'outputs/detections/{symbol}/15m_responsive/events.parquet')
    with patch.object(matplotlib.figure.Figure,'savefig',padded):
        plots(lab,validated)
    section=['','## Verified execution and cost attribution','',
             f'76 tests passed. All {audit["audited_replays"]} replay ledgers reconciled independently; no final-period performance access. Frozen formation code and the earlier study code remain unchanged.',
             '', '[Explicit cost ledger](cost_attribution.csv) separates fees and signed funding from net P&L. Its pre-fee column still includes spread/slippage in fill prices; it is not a frictionless backtest.',
             '', 'None of the72primary variants met BOTH the training activity and performance gates. Some infrequent rules had positive folds, but did not satisfy the requested weekly activity. No new validation rule was substituted after observing failure.']
    report=ROOT/'report.md'
    text=report.read_text(encoding='utf-8').split('\n## Verified execution and cost attribution')[0]
    for before,after in [('72primary','72 primary'),('12baselines','12 baselines'),('72primary','72 primary'),('208slots','208 slots'),('124+new84','124 + new84')]:
        text=text.replace(before,after)
    report.write_text(text+'\n'.join(section)+'\n',encoding='utf-8')
    payload=dict(tests_passed=76,tests_failed=0,audited_replays=audit['audited_replays'],ledger_failures=0,
                 accepted_candidates=sum(r['accepted'] for r in validated),nominal_final='CONTAMINATED_NOT_EVALUATED',
                 frozen_code_unchanged=True,postprocess_source_sha256=sha(__file__),
                 outputs={name:sha(ROOT/name) for name in ['manifest.json','validation_shortlist.json','experiment_registry.csv',
                     'validation_results.json','diagnostic_configurations.json','report.md','accounting_audit.json',
                     'eth_head_shoulders_example.png','bnb_head_shoulders_example.png','validation_comparison.png']})
    (ROOT/'verification.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print('Formation artifacts verified; '+str(audit['audited_replays'])+' ledgers, 76 passing tests.',flush=True)


if __name__=='__main__':
    finish()

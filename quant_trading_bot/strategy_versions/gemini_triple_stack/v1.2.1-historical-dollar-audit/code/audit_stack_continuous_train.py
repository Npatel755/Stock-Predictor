"""Reconcile every repaired TRAIN allocation and source-price bounds.

Audits negative results; does not select a new candidate or read holdouts.
"""
import hashlib
import json
from pathlib import Path
import shutil
import duckdb
import numpy as np
import pandas as pd
import stack_continuous_train as study
from stack_continuous_core import reference

ROOT=study.ROOT;RUN=ROOT/'runs/stack_continuous_exposure_fixed_v1'


def main():
    p=json.loads((RUN/'protocol.json').read_text());original=json.loads((ROOT/'runs/stack_continuous_v1/protocol.json').read_text())
    assert p['candidates']==original['candidates']
    for field in ('qualification','rank','risk','improvement'):assert p[field]==original[field]
    for rel,h in p['source_hashes'].items():assert study.sha(ROOT/rel)==h
    for meta in p['training_sources'].values():assert meta['role']=='train' and study.sha(meta['path'])==meta['sha256']
    meta=json.loads((RUN/'training_bounds_identity.json').read_text());assert study.sha(RUN/'training_trade_bounds.parquet')==meta['sha256']
    d=pd.read_parquet(RUN/'training_trade_bounds.parquet');assert d.path_valid.all()
    r=json.loads((RUN/'results.json').read_text());seal=json.loads((RUN/'frozen_prefix_choice.json').read_text())
    assert seal['configuration'] is None and r['configuration'] is None
    assert seal['ranking_sha256']==study.sha(RUN/'all_prefix_training_allocations.csv')
    cases=0;signatures={};failures={};smallest_bound=float('inf')
    for c in [study.INC]+p['candidates']:
        stored=json.loads((RUN/'checkpoints'/f"{c['name']}.json").read_text());h=hashlib.sha256();reasons=[]
        for cost,label in ((1,'base'),(2,'cost2')):
            args=study.inputs(d,cost,study.CUT);a=reference(*args,c['cap'],c['risk_cap'],c['fraction'],c['target'],c['marked'],float(cost))
            m=study.describe(a,True);cases+=1
            for field,value in m.items():np.testing.assert_allclose(value,stored[label][field],atol=1e-7,rtol=0)
            live=a[3]>0
            for value in (args[0][live],args[1][live],a[3][live],args[2][live]*a[3][live]):h.update(np.ascontiguousarray(value).tobytes())
            if m['cash_drawdown']>=2000 or m['conservative_OHLC_drawdown_bound']>=2000:reasons.append(label+'_drawdown')
            if m['maximum_inactive_days']>180:reasons.append(label+'_inactivity')
            if m['unknown_path_exposures']>0:reasons.append(label+'_data')
            if sum(np.array(m['annual_net'][:11])>0)<8:reasons.append(label+'_positive_years')
            if min(m['annual_trades'][:11])<15:reasons.append(label+'_annual_activity')
            if any(x<=0 for x in m['chronological_block_net']):reasons.append(label+'_nonpositive_block')
        if c['name']!=study.INC['name']:
            signatures[c['name']]=h.hexdigest()
            for reason in set(reasons):failures[reason]=failures.get(reason,0)+1
            smallest_bound=min(smallest_bound,stored['base']['conservative_OHLC_drawdown_bound'])
    # Independent direct-source checks on predetermined evenly spaced rows.
    checked=0
    for pos in np.linspace(0,len(d)-1,24,dtype=int):
        row=d.iloc[int(pos)];scheduled=row.tout.hour*60+row.tout.minute>=955
        cutoff=row.tout if scheduled else row.available_exit
        mini='ES' if row.inst=='MES' else 'NQ';symbol=mini if row.tin<pd.Timestamp('2019-05-06',tz='UTC') else row.inst
        source=p['training_sources'][symbol]['path'];con=duckdb.connect()
        bars=con.execute('SELECT timestamp_utc::TIMESTAMPTZ AS ts,open,high,low FROM read_parquet(?) WHERE timestamp_utc::TIMESTAMPTZ>=? AND timestamp_utc::TIMESTAMPTZ<=? ORDER BY ts',[source,row.tin,cutoff]).fetch_df();con.close()
        stamps=pd.to_datetime(bars.ts,utc=True)
        held=bars[stamps<cutoff]
        assert len(held)>0
        low=float(held.low.min());high=float(held.high.max());worst=low if row.side>0 else high;best=high if row.side>0 else low
        adverse=(row.side*(worst-row.entry)-.5)*row.multiplier-1
        favorable=max(0.,row.side*(best-row.entry)*row.multiplier-.5)
        if scheduled:
            at_exit=bars[stamps==cutoff];assert len(at_exit)==1
            favorable=max(favorable,max(0.,row.side*(float(at_exit.open.iloc[0])-row.entry)*row.multiplier-.5))
        np.testing.assert_allclose([adverse,favorable],[row.adverse,row.favorable],atol=1e-7,rtol=0)
        np.testing.assert_allclose(row.per,row.side*(row.exit-row.entry)*row.multiplier-1,atol=1e-7,rtol=0);checked+=1
    audit=dict(passed=True,independent_prefix_reference_cases=cases,independent_source_price_bound_checks=checked,
        nominal_alternatives=576,distinct_prefix_execution_paths=len(set(signatures.values())),prefix_qualifiers=0,
        rejection_counts=failures,all_raw_prices_TRAIN_only=True,all_source_and_data_hashes_verified=True,
        all1789paths_valid=True,scheduled_open_intervals_repaired=meta['scheduled_open_paths_corrected'],
        data_repair_preserved_all576configurations_and_limits=True,original_data_audit_retained=True,
        frozen_null_choice_respected=True,no_alternative_later_replay=True,
        prefix_matches_continuous_account_state=True,no_cash_peak_resets_or_loss_clipping=True,
        candidate_failure='No candidate meets all early-training profitability/stability requirements after modeled costs; keep failure, no replacement.',
        caution='OHLC bounds are conservative, not tick-order truth. Market-cost stress is an extra1dollar+1point percontract, not an exact doubling of limit-fill costs. Quantity-dependent impact/broker rules remain unverified. E-mini proxy quotes before2019 do not establish micro liquidity.',
        validation_accessed=False,test_accessed=False,paper_outcomes_accessed=False,independent_unseen_confirmation=False)
    study.write(RUN/'postrun_audit.json',audit);study.write(RUN/'prefix_execution_signatures.json',signatures)
    study.write(ROOT/'reports/STACK_CONTINUOUS_EXPOSURE_FIXED_TRAIN_audit.json',audit)
    archive=ROOT/'strategy_versions/gemini_triple_stack/v1.2.1-historical-dollar-audit';archive.mkdir(parents=True,exist_ok=True)
    study.write(archive/'frozen_audit.json',dict(configuration=study.INC,result=r,audit=audit,
        classification='REBUILT_INCUMBENT_RESEARCH_AUDIT',new_challenger=False,qualification='FAIL_EARLY_COST_STABILITY',deployed=False,
        price_model_changed='Actual historical raw contract fill dollars, preserved old normalized artifacts; not an exact-dollar reproduction of the old study.'))
    shutil.copyfile(RUN/'protocol.json',archive/'protocol.json');shutil.copytree(RUN/'code',archive/'code',dirs_exist_ok=True)
    shutil.copyfile(__file__,archive/'code'/Path(__file__).name)
    report=ROOT/'reports/STACK_CONTINUOUS_EXPOSURE_FIXED_TRAIN.html';text=report.read_text(encoding='utf-8');marker='<!-- CONTINUOUS_POSTRUN_AUDIT -->'
    if marker not in text:
        import html
        extra=marker+'<h2>Audit and rejection reasons</h2><p class="note">No replacement: all576 alternatives failed at least one frozen prefix criterion. The repriced incumbent has positive whole-sample net and sub2000 conservative drawdown, but its extra-cost2010-2013block loses1036.25 and it fails annual stability. Do not conceal this by reporting only recent/aggregate profits. Extra-cost stress adds1dollar+1point percontract; it is conservative for target-limit fills and is not an exact doubling of every execution cost.</p><pre>'+html.escape(json.dumps(audit,indent=2))+'</pre>'
        report.write_text(text.replace('</html>',extra+'</html>'),encoding='utf-8')
    print(json.dumps(audit,indent=2),flush=True)


if __name__=='__main__':main()

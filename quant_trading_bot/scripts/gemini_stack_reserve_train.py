"""Frozen, bounded TRAIN-only search; never opens market or holdout files."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import sys
import numpy as np
import pandas as pd
from gemini_stack_account_core import replay, summary
from gemini_stack_reserve_core import replay_reserve, reference
from gemini_stack_continue_train import windows

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'runs/gemini_stack_reserve_v1'
CACHE = ROOT/'runs/gemini_stack_continuation_v1/causal'
BASE = dict(name='incumbent',keep=8600.,on=8700.,off=8700.,four_at=5400.)
KINDS = ('S0','S3','S4')
COLUMNS = ['withdrawn','closed','stoprisk_flag','near_miss','first_days','year1_payouts',
           'year1_withdrawn','ending_balance','trading_pnl','payouts','trading_drawdown_eod',
           'minimum_eod_floor_room','book_switches']


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x): Path(p).write_text(json.dumps(x,indent=2,default=str)+'\n',encoding='utf-8')


def freeze():
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'protocol.json').exists(): raise RuntimeError('Existing protocol is immutable')
    cells = [BASE]
    for keep in (7800.,8200.,8600.,9000.,9400.):
        for on in (8000.,8500.,9000.,9500.,10000.):
            if on <= keep: continue
            for distance in (0.,500.,1000.):
                for four in (5400.,6500.,7500.):
                    cells.append(dict(name=f'K{int(keep)}_ON{int(on)}_H{int(distance)}_M4{int(four)}',
                        keep=keep,on=on,off=on-distance,four_at=four))
    keys=[(c['keep'],c['on'],c['off'],c['four_at']) for c in cells]
    assert len(keys)==len(set(keys))
    code = RUN/'code'; code.mkdir(exist_ok=True)
    hashes = {}
    for name in ('gemini_stack_reserve_core.py','gemini_stack_reserve_train.py',
                 'gemini_stack_account_core.py','gemini_stack_continue_train.py'):
        src=ROOT/'scripts'/name; shutil.copyfile(src,code/name); hashes[name]=sha(src)
    test=ROOT/'tests/test_gemini_stack_reserve_core.py';shutil.copyfile(test,code/test.name)
    hashes[test.name]=sha(test)
    write(RUN/'protocol.json',dict(run='gemini_stack_reserve_v1',frozen_at=pd.Timestamp.now(tz='UTC'),
        hypothesis='A reserve before 4x sizing and separate activation/release thresholds may reduce stack churn and preserve compounding capital.',
        data='Only existing causal TRAIN cache, 2010-2023; no new market data reads. Same base and triple sleeves, same costs, union calendar and normalization.',
        discovery='55 monthly starts 2010-07 to 2015-01; 24-month windows end by 2017. Later starts >=2017 reserved for a single frozen comparison within this run.',
        chronology_warning='Both earlier and later TRAIN were examined in previous research. Later TRAIN is a reused internal robustness check, not fresh confirmation. 23 crossing windows excluded from choice/check.',
        candidates=cells,table_sha256=sha(CACHE/'tables.npz'),metadata_sha256=sha(CACHE/'complete.json'),source_sha256=hashes,
        select='Choose highest S0 mean 24-month withdrawals among earlier-TRAIN risk-eligible, stress-nondegrading cells, tie lower S3 flag then name; freeze before later TRAIN. No replacement on failure.',
        risk_gates=dict(S3_stoprisk_fraction_max=.05,S4_stoprisk_fraction_max=.095,
            closure_tolerance_vs_baseline=.005,S0_near_miss='no increase',worst_eod_trading_drawdown='no increase in every scenario'),
        promotion='At least 5% higher S0 withdrawals on BOTH earlier and later TRAIN, stress S3/S4 mean withdrawals >= incumbent on BOTH, and all risk gates on BOTH. Research archive only; no deployment.',
        fixed_assumptions='First withdrawal500 at balance6000; later cap1500, minimum250 excess; floor -2000 then0; daily loss clipping -1000; night threshold500; size2at4000,size3at4600. Unverified payout assumptions unchanged.',
        limits='Daily P&L clipping, EOD closure and largest-stop-risk proxy are approximate. Not intrabar funded compliance. Normalized reference prices, dependent overlapping windows and repeated search limit inference.',
        validation_accessed=False,test_accessed=False,forward_paper_accessed=False))
    print('FROZEN',len(cells),'configurations',sha(RUN/'protocol.json'),flush=True)


def summarize(a):
    x=summary(a[:,:10]);x.update(worst_eod_trading_drawdown=float(a[:,10].max()),
        mean_eod_trading_drawdown=float(a[:,10].mean()),minimum_eod_floor_room=float(a[:,11].min()),
        mean_book_switches=float(a[:,12].mean()),median_withdrawals=float(np.median(a[:,0])),
        tenth_percentile_withdrawals=float(np.percentile(a[:,0],10)))
    return x


def eligible(m,b):
    return bool(m['S3']['conservative_stoprisk_flag_fraction']<=.05 and
        m['S4']['conservative_stoprisk_flag_fraction']<=.095 and
        m['S0']['near_miss_fraction']<=b['S0']['near_miss_fraction'] and
        all(m[k]['closed_fraction']<=b[k]['closed_fraction']+.005 and
            m[k]['worst_eod_trading_drawdown']<=b[k]['worst_eod_trading_drawdown']+1e-6 and
            (k=='S0' or m[k]['mean_withdrawals']>=b[k]['mean_withdrawals']-1e-6) for k in KINDS))


def paired_range(a,b):
    # Descriptive dependent-start bootstrap, not selection-adjusted confidence.
    rng=np.random.default_rng(20261111);n=len(a);v=[]
    for _ in range(5000):
        # Circular 12-start blocks retain local dependence but truncate24m overlap.
        ids=np.concatenate([(rng.integers(n)+np.arange(12))%n for _ in range((n+11)//12)])[:n]
        v.append(float((a[ids]-b[ids]).mean()))
    return dict(paired_mean_withdrawal_difference=float((a-b).mean()),
        descriptive_5_95_percentile_dollar_range=np.percentile(v,[5,95]).tolist(),
        block_monthly_starts=12,replicates=5000,selection_adjusted=False,
        warning='Exploratory uncertainty only: overlapping24monthwindows, circular12monthblocks and repeated selection; not a confidence guarantee.')


def run():
    if (RUN/'results.json').exists(): print('Completed immutable run preserved');return
    p=json.loads((RUN/'protocol.json').read_text())
    for name,h in p['source_sha256'].items():
        src=ROOT/('tests' if name.startswith('test_') else 'scripts')/name
        if sha(src)!=h: raise ValueError('Frozen source changed: '+name)
    assert sha(CACHE/'tables.npz')==p['table_sha256']
    assert sha(CACHE/'complete.json')==p['metadata_sha256']
    meta=json.loads((CACHE/'complete.json').read_text())
    assert meta['mode']=='causal'
    assert all(x['role']=='train' and pd.Timestamp(x['end'])<=pd.Timestamp('2024-01-01') for x in meta['training_loads'])
    with np.load(CACHE/'tables.npz') as z:
        dates=z['dates']; ids=[meta['books'].index(x) for x in ('base','both','triple')]
        net=z['net'][ids].copy(); risk=z['risk'][ids].copy()
    assert dates.max()<int(pd.Timestamp('2024-01-01').value//86400000000000)
    t,starts,ends,years=windows()
    earlier=np.flatnonzero([x+pd.DateOffset(months=24)<=pd.Timestamp('2017-01-01') for x in t])
    later=np.flatnonzero(t>=pd.Timestamp('2017-01-01'))
    checks=0

    def score(c,indices,verify=False):
        nonlocal checks
        m={}; raw={}
        for si,k in enumerate(KINDS):
            a=replay_reserve(net[:,si],risk[:,si],dates,starts[indices],ends[indices],years[indices],
                c['keep'],c['on'],c['off'],c['four_at'])
            np.testing.assert_allclose(a[:,0]+a[:,7],a[:,8],atol=1e-6,rtol=0)
            if verify:
                for i,wi in enumerate(indices):
                    expected=reference(net[:,si],risk[:,si],dates,starts[wi],ends[wi],years[wi],
                        c['keep'],c['on'],c['off'],c['four_at'])
                    np.testing.assert_allclose(a[i],expected,atol=1e-6,rtol=0);checks+=1
            m[k]=summarize(a);raw[k]=a
        return m,raw

    baseline,baseline_raw=score(BASE,earlier,True)
    # Exact unchanged incumbent comparison against the original core.
    for si,k in enumerate(KINDS):
        old=replay(net[:,si],risk[:,si],dates,starts[earlier],ends[earlier],years[earlier],8600.,8700.,8700.,1500.)
        np.testing.assert_allclose(old,baseline_raw[k][:,:10],atol=1e-6,rtol=0)
    rows=[]; metrics={}
    for c in p['candidates']:
        check=RUN/'checkpoints'/f"{c['name']}.json";check.parent.mkdir(exist_ok=True)
        if check.exists(): m=json.loads(check.read_text())
        else:
            m,_=score(c,earlier);write(check,m)
        metrics[c['name']]=m
        row={**c,'eligible':eligible(m,baseline),'S0_withdrawals':m['S0']['mean_withdrawals'],
             'S0_lift':m['S0']['mean_withdrawals']/baseline['S0']['mean_withdrawals']-1}
        for k in KINDS:
            row[k+'_withdrawals']=m[k]['mean_withdrawals'];row[k+'_closed']=m[k]['closed_fraction']
            row[k+'_stoprisk']=m[k]['conservative_stoprisk_flag_fraction'];row[k+'_worst_eod_trading_dd']=m[k]['worst_eod_trading_drawdown']
        rows.append(row)
    frame=pd.DataFrame(rows).sort_values(['eligible','S0_withdrawals','S3_stoprisk','name'],ascending=[False,False,True,True])
    frame.to_csv(RUN/'all_earlier_training_candidates.csv',index=False)
    names={c['name']:c for c in p['candidates']}
    qualified=frame[frame['eligible']]
    choice=names[qualified.iloc[0]['name']] if len(qualified) else BASE
    freeze_path=RUN/'frozen_earlier_train_choice.json'
    frozen=dict(configuration=choice,earlier_metrics=metrics[choice['name']],
                protocol_sha256=sha(RUN/'protocol.json'),ranked_csv_sha256=sha(RUN/'all_earlier_training_candidates.csv'),
                later_train_used_for_this_choice=False,previous_later_train_exposure=True)
    if freeze_path.exists(): assert json.loads(freeze_path.read_text())==frozen
    else: write(freeze_path,frozen)
    print('FROZEN TRAIN CHOICE',json.dumps(choice),'eligible',len(qualified),flush=True)
    chosen_early,chosen_early_raw=score(choice,earlier,True)
    base_later,base_later_raw=score(BASE,later,True)
    chosen_later,chosen_later_raw=score(choice,later,True)
    early_lift=chosen_early['S0']['mean_withdrawals']/baseline['S0']['mean_withdrawals']-1
    later_lift=chosen_later['S0']['mean_withdrawals']/base_later['S0']['mean_withdrawals']-1
    passed=bool(choice['name']!='incumbent' and early_lift>=.05 and later_lift>=.05 and
                eligible(chosen_early,baseline) and eligible(chosen_later,base_later))
    for phase,indices,books in [('earlier',earlier,[('baseline',baseline_raw),('choice',chosen_early_raw)]),
                               ('later',later,[('baseline',base_later_raw),('choice',chosen_later_raw)])]:
        for label,raw in books:
            for k,a in raw.items():
                df=pd.DataFrame(a,columns=COLUMNS);df.insert(0,'start',t[indices])
                df.to_csv(RUN/f'{phase}_{label}_{k}_paths.csv',index=False)
    result=dict(classification='TRAIN_ONLY_RESEARCH_CHALLENGER' if passed else 'NO_QUALIFIED_IMPROVEMENT',
        accepted_training_challenger=passed,candidates=len(rows),earlier_eligible=len(qualified),configuration=choice,
        earlier=dict(baseline=baseline,choice=chosen_early,lift=early_lift),
        later_reused_train=dict(baseline=base_later,choice=chosen_later,lift=later_lift,risk_and_stress_gate=eligible(chosen_later,base_later)),
        paired_later_uncertainty=paired_range(chosen_later_raw['S0'][:,0],base_later_raw['S0'][:,0]),
        model_limits=p['limits'],chronology_warning=p['chronology_warning'],
        protocol_sha256=sha(RUN/'protocol.json'),frozen_choice_sha256=sha(freeze_path),
        validation_accessed=False,test_accessed=False,forward_paper_accessed=False,deployment_changed=False,
        independent_unseen_confirmation=False)
    verification=dict(passed=True,independent_reference_paths=checks,original_baseline_parity_paths=3*len(earlier),
        conservation_all_candidates=True,source_hashes_match=True,cache_hash_verified=True,
        only_input_data_files=[str(CACHE/'complete.json'),str(CACHE/'tables.npz')],
        training_roles_and_end_dates_verified=True,dates_before_2024=True,later_choice_freeze_verified=True,
        candidates=len(rows),unique_configs=len({(c['keep'],c['on'],c['off'],c['four_at']) for c in p['candidates']}),
        validation_accessed=False,test_accessed=False,actual_intrabar_funded_certification=False)
    write(RUN/'results.json',result);write(RUN/'verification.json',verification)
    if passed:
        archive=ROOT/'strategy_versions/gemini_triple_stack/v1.1.0-reserve-train-challenger';archive.mkdir(parents=True,exist_ok=True)
        write(archive/'frozen_candidate.json',dict(configuration=choice,result=result,deployed=False))
        shutil.copyfile(RUN/'protocol.json',archive/'protocol.json')
        shutil.copytree(RUN/'code',archive/'code',dirs_exist_ok=True)
    publish(result,verification,frame,t,earlier,later,baseline_raw,chosen_early_raw,base_later_raw,chosen_later_raw)
    print('FINAL',json.dumps(dict(candidates=len(rows),eligible=len(qualified),accepted=passed,earlier_lift=early_lift,later_lift=later_lift,reference_checks=checks)),flush=True)


def publish(result,verification,frame,t,earlier,later,be,ce,bl,cl):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    stem='GEMINI_STACK_RESERVE_TRAIN'
    write(ROOT/'reports'/f'{stem}.json',result);write(ROOT/'reports'/f'{stem}_verification.json',verification)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for ax,idx,b,c,title in zip(axes,[earlier,later],[be,bl],[ce,cl],['Earlier TRAIN selection','Later TRAIN — reused internal check']):
        ax.plot(t[idx],b['S0'][:,0],label='Corrected incumbent');ax.plot(t[idx],c['S0'][:,0],label='Frozen choice')
        ax.set_title(title);ax.set_ylabel('Simulated 24-month withdrawals ($)');ax.tick_params(axis='x',rotation=30);ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(ROOT/'reports'/f'{stem}.png',dpi=150);plt.close(fig)
    rows=[]
    for phase,key in [('Earlier TRAIN','earlier'),('Later reused TRAIN','later_reused_train')]:
        for label in ('baseline','choice'):
            for k in KINDS:
                m=result[key][label][k]
                rows.append(dict(Period=phase,Policy=label,Scenario=k,Starts=m['windows'],
                    Mean_withdrawals=m['mean_withdrawals'],Trading_PnL=m['mean_net_trading_pnl'],
                    EOD_trading_DD_max=m['worst_eod_trading_drawdown'],Closed_pct=100*m['closed_fraction'],
                    Stoprisk_flag_pct=100*m['conservative_stoprisk_flag_fraction']))
    title='Reserve controller: '+('TRAIN-only improvement' if result['accepted_training_challenger'] else 'no qualifying improvement')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>'''+title+'''</title><style>body{font:16px/1.6 system-ui;margin:32px auto;padding:0 24px;max-width:1400px;background:#111820;color:#e7edf2}a{color:#8dd5ff}table{border-collapse:collapse;font-size:14px}th,td{padding:9px;border-bottom:1px solid #456}img{width:100%}.scroll{overflow:auto}pre{white-space:pre-wrap}.note{background:#352d21;padding:18px}</style>
    <h1>'''+title+'''</h1><p>'''+str(result['candidates'])+''' predeclared configurations; TRAIN-only ranking. One choice frozen before this run's later-TRAIN check. External validation/test and deployed settings unchanged.</p>
    <p class="note">'''+html.escape(result['chronology_warning'])+''' All amounts below are model scenarios, not verified funded-account returns. Withdrawals are different from trading P&amp;L.</p>
    <img src="'''+stem+'''.png" alt="Withdrawals by historical training start date"><h2>Matched comparisons</h2><div class="scroll">'''+pd.DataFrame(rows).to_html(index=False,border=0,float_format=lambda x:f'{x:,.2f}')+'''</div>
    <h2>Frozen rules</h2><p>The unchanged base book trades below activation. The triple book activates at the on threshold and deactivates only below the off threshold; decisions use the prior balance. Size2 at4000, size3 at4600, size4 at the configured threshold. First withdrawal500 at6000; later withdrawals capped1500 with minimum250 excess over keep. Night threshold500 and all signals/costs unchanged.</p><pre>'''+html.escape(json.dumps(result['configuration'],indent=2))+'''</pre>
    <p>Acceptance requires at least5% higher S0 withdrawals in both earlier and later TRAIN; no lower S3/S4 withdrawals, no worse maximum EOD trading drawdown in each scenario, exact stop-risk gates, and closure/near-miss gates. A failed later check cannot select a replacement.</p>
    <h2>Limits and uncertainty</h2><p>'''+html.escape(result['model_limits'])+''' EOD trading drawdown excludes withdrawals and includes the initial equity peak. It is not intrabar drawdown; the $2,000 initial loss floor is different from total trading-equity drawdown after capital accumulates. The stop-risk flag is a conservative proxy, not an observed floor breach.</p><pre>'''+html.escape(json.dumps(result['paired_later_uncertainty'],indent=2))+'''</pre>
    <h2>All earlier-TRAIN configurations</h2><div class="scroll">'''+frame.head(20).to_html(index=False,border=0,float_format=lambda x:f'{x:,.3f}')+'''</div>
    <p><a href="../runs/gemini_stack_reserve_v1/protocol.json">Frozen protocol</a> · <a href="../runs/gemini_stack_reserve_v1/all_earlier_training_candidates.csv">All configurations</a> · <a href="'''+stem+'''.json">Full results</a> · <a href="'''+stem+'''_verification.json">Verification</a></p></html>'''
    (ROOT/'reports'/f'{stem}.html').write_text(page,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if args.freeze: freeze()
    elif args.run: run()
    else: parser.error('Choose --freeze or --run')

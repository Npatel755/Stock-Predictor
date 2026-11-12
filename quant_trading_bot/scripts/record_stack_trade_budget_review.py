"""Persist audited TRAIN-only research findings and visible drawdown curves."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from stack_trade_budget_train import ROOT,RUN,sha,write


def main():
    r=json.loads((RUN/'results.json').read_text());audit=json.loads((RUN/'postrun_audit.json').read_text())
    c=r['configuration'];name=c['name']
    later_ledger=pd.read_csv(RUN/'selected/later'/name/'cost2_closed_equity.csv',parse_dates=['timestamp_utc'])
    dd=max(0,float(later_ledger.cash_pnl.max()))-float(later_ledger.cash_pnl.iloc[-1])
    stall=dict(last_completed_cost2_trade=str(later_ledger.timestamp_utc.iloc[-1]),
        final_closed_cash_drawdown=dd,remaining_1800_budget=1800-dd,
        interpretation='Budget shrank to about2.29 dollars, too small for a micro contract. Low observed drawdown partly reflects stopping trading. The frozen activity gate correctly rejects it; do not reset the equity peak or relax the gate after seeing this.')
    write(RUN/'training_stall_diagnosis.json',stall)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for ax,phase,end in zip(axes,('earlier','later'),('2017-01-01','2024-01-01')):
        last_cost=None
        for factor,label in ((1,'base'),(2,'cost2')):
            ledger=pd.read_csv(RUN/'selected'/phase/name/(label+'_trades.csv'))
            for column in ('tin','available_exit'):ledger[column]=pd.to_datetime(ledger[column],utc=True,format='mixed')
            times=[];values=[];balance=0.
            for trade in ledger.itertuples():
                times.extend([trade.tin,trade.available_exit]);values.extend([balance-.5*factor*trade.quantity,trade.cash_pnl]);balance=trade.cash_pnl
            times.append(pd.Timestamp(end,tz='UTC'));values.append(balance)
            v=np.asarray(values);peak=np.maximum.accumulate(np.r_[0.,v])[1:]
            expected=(r['earlier'] if phase=='earlier' else r['later_reused_train'][name])[label]['maximum_realized_cash_drawdown']
            np.testing.assert_allclose(float((peak-v).max()),expected,atol=1e-7,rtol=0)
            ax.plot(times,peak-v,label='Base costs' if factor==1 else 'Doubled costs',lw=1)
            if factor==2:last_cost=ledger.available_exit.iloc[-1]
        ax.axhline(2000,color='red',ls='--',label='$2,000 limit')
        if phase=='later':ax.axvspan(last_cost,pd.Timestamp(end,tz='UTC'),color='#db9e48',alpha=.2,label='Doubled-cost inactivity')
        ax.set(title=phase+' TRAIN — frozen choice',ylabel='Transaction/closed-cash drawdown ($)',ylim=(0,2200));ax.legend(fontsize=9);ax.grid(alpha=.2);ax.tick_params(axis='x',rotation=25)
    fig.tight_layout();fig.savefig(ROOT/'reports/STACK_TRADE_BUDGET_TRAIN_DRAWDOWN.png',dpi=150);plt.close(fig)
    report=ROOT/'reports/STACK_TRADE_BUDGET_TRAIN.html';text=report.read_text(encoding='utf-8');marker='<!-- STALL_DIAGNOSIS -->'
    if marker not in text:
        import html
        extra=marker+'<h2>Drawdown and inactivity diagnosis</h2><img src="STACK_TRADE_BUDGET_TRAIN_DRAWDOWN.png" alt="Cash drawdown and later doubled-cost inactivity"><pre>'+html.escape(json.dumps(stall,indent=2))+'</pre>'
        report.write_text(text.replace('</html>',extra+'</html>'),encoding='utf-8')
    memo='''# Stack trade-budget research: rejected diagnostic

504 nominal allocations produced150 distinct earlier TRAIN execution paths;
8 qualifying allocations represent4 distinct paths. Both matched controls
stopped after the observed $2,000 drawdown breach; their reported terminal
profits are censored at that stop. Do not compare their shortened exposure as
though it were a full-period buy-and-hold return.

The chosen base/no-night allocation was frozen before later TRAIN. It remains
profitable and below $2,000 realized-cash drawdown at both cost levels in both
internal blocks. The later doubled-cost inactivity276days fails the frozen
180day gate. Only about$2.29 remained in its $1,800 planning budget after the
last March2023 trade. No candidate was substituted after that result.

These are separate initial-zero TRAIN accounts,2010July–2016 and2017–2023,
with8day boundary entry suppression. Do not add their profits and call the sum
a continuous-account simulation. All historical periods are reused research.

No intratrade marked-equity path was reconstructed. No payouts were simulated.
Historical percent moves are normalized at inherited fixed reference prices,
not actual historical contract-level dollar results. No independent unseen
evidence, funded-account certification or live/paper deployment is claimed.
The20 whole-grid synthetic null searches are falsification diagnostics, not
tradable strategies or a confirmatory probability of a genuine market edge.
Historical search multiplicity is incompletely known; confidence remains
INSUFFICIENT for prospective-profit claims.

Next highest-information work, if requested:
1. Reconstruct TRAIN-only bar-by-bar intratrade marks for this frozen version,
   including rolls, gaps, partial exit bars and actual contract prices.
2. Independently reconcile inherited normalized returns against source fills
   and actual historical dollar accounting; quantify the modeling difference.
3. Audit the entry-risk distribution during the frozen policy's inactive
   interval before designing a separate preregistered TRAIN-only hypothesis.

Do not repeat reserve-only sweeps, relax activity gates, treat missing MAE as
zero, reset the drawdown peak, or mine old validation/test outcomes for fixes.
'''
    (RUN/'research_memo.md').write_text(memo,encoding='utf-8')
    evidence=ROOT/'research/audits';evidence.mkdir(parents=True,exist_ok=True)
    (evidence/'stack_trade_budget_v1-evidence.md').write_text(memo,encoding='utf-8')
    archive=ROOT/'strategy_versions/gemini_triple_stack/v1.2.0-trade-budget-diagnostic'
    import shutil
    for source in (RUN/'research_memo.md',RUN/'training_stall_diagnosis.json',RUN/'postrun_audit.json'):
        shutil.copyfile(source,archive/source.name)
    events=ROOT/'research/strategy_memory/events.jsonl'
    known=set()
    for line in events.read_text(encoding='utf-8-sig').splitlines():
        try:x=json.loads(line)
        except ValueError:continue
        if x.get('run_id')=='stack_trade_budget_v1':known.add(x.get('record_type'))
    common=dict(schema_version=1,run_id='stack_trade_budget_v1',strategy_id='stack_budget_'+hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()[:20],
        parent_id='gemini_triple_stack/v1.0.0-research',recorded_at=datetime.now(timezone.utc).isoformat(),
        artifact=str(report),protocol_sha256=sha(RUN/'protocol.json'),split_role='TRAIN_ONLY',
        validation_accessed=False,test_accessed=False)
    records=[('hypothesis',dict(hypothesis='Entry risk allocation using remaining realized-DD budget can replace capital-only leverage; registered before scoring in protocol.')),
        ('implementation',dict(configuration=c,code_hashes=json.loads((RUN/'protocol.json').read_text())['source_sha256'])),
        ('run',dict(candidates=504,controls=2,distinct_earlier_execution_paths=150,synthetic_null_grid_evaluations=10080)),
        ('result',dict(earlier=r['earlier'],later=r['later_reused_train'][name],decision='REJECTED_TRAIN_DIAGNOSTIC',reason=audit['rejected_reason'])),
        ('lesson',dict(lesson='Remaining drawdown room2.29 cannot fund a micro, producing276day later cost2 inactivity. Retain gate failure despite positive net/sub2000 realized DD. Intrabar/payout unknown; no V/T tuning, no replacement.'))]
    with events.open('a',encoding='utf-8') as f:
        for kind,details in records:
            if kind not in known:f.write(json.dumps(dict(**common,record_type=kind,**details),ensure_ascii=True)+'\n')
    lesson='\n- stack_trade_budget_v1: 504 frozen TRAIN-only allocations (150 distinct earlier executions),8 earlier qualifiers/4 distinct paths. Chosen base/no-night cap1 risk225 fraction1: earlier+17600.88/realizedDD1409.71;cost2+16070.35/DD1638.21. Later+22564.09/DD1551.59;cost2+17757.18/DD1797.71, but276.375day inactivity fails180day gate. Remaining budget2.29 after2023-03-30 explains stalled trading. Rejected, saved v1.2.0-trade-budget-diagnostic; no alternative chosen.10tests+1024 full reference cases,20 full-grid null diagnostics. Missing intratrade marks/payout model mean no funded/intrabar PASS. Reused TRAIN, no V/T/paper outcomes or deployment. Installed ZIP skills56new/6backed-up updates/12existing (74total). Reports STACK_TRADE_BUDGET_TRAIN.html and audit/memo.\n'
    lessons=ROOT/'research/strategy_memory/lessons.md'
    if 'stack_trade_budget_v1:' not in lessons.read_text(encoding='utf-8-sig'):
        with lessons.open('a',encoding='utf-8') as f:f.write(lesson)
    agents=ROOT/'AGENTS.md'
    if 'Run stack_trade_budget_v1 completed' not in agents.read_text(encoding='utf-8-sig'):
        with agents.open('a',encoding='utf-8') as f:
            f.write('\n- User requested further improvement, use project history, install three supplied ZIP skill packs, strict no V/T tuning. Local installer installed56new/updated6with backups/verified12existing=74skills, source hashes in reports/SKILL_ARCHIVE_INSTALL_20261111.json. Only skill directories activated; archive install prompts/scripts not executed. Backups in user .codex/skill-install-backups. Training-history inventory covers255static research headers and73existing journal records; mixed holdout/paper outcomes excluded from design. Run stack_trade_budget_v1 completed504 TRAIN-only allocations+2controls,10,080synthetic null grid cells;150distinct earlier execution paths;8earlier qualifying allocations/4distinct paths. Choice frozen earlier:base_N0_C1_R225_F1; earlier2010Jul-2016 net17600.88/transaction-closedcashDD1409.71,cost2net16070.35/DD1638.21; later2017-23 net22564.09/DD1551.59,cost2net17757.18/DD1797.71. Latercost2inactivity276.375days>180gate -> REJECTED_TRAIN_DIAGNOSTIC;noalternate selected/adopted. Remaining1800budget2.29afterMarch30,2023halts integer micros;donotresetpeak/relaxgate toclaimpass. Saved separately strategy_versions/gemini_triple_stack/v1.2.0-trade-budget-diagnostic. These are separate reset TRAIN blocks,not continuous14year PnL;no withdrawals simulated,not comparabletoprior24monthpayoutmeans. Added exit-bar confirmation occupancy,full gap losses,no loss clipping. Missing intratrade OHLC/MAE means intrabarDD UNKNOWN,no funded/payout compliance. Fixed inherited normalization ratherthanactual historical dollars;oldperiods repeatedly selected,unknownhistoricalmultiplicity.10tests+1012allcase independentearlier references+12selected/controlreferences pass;all506metrics/hashes/nullrecords/ledgersverified. Original frozen script had integer period-metadata loop bug after calculations; source preserved, completion_repair_seal+separatefinalizer changed no config/rank/researchlogic. Reports STACK_TRADE_BUDGET_TRAIN.html/.json/.png/_DRAWDOWN.png/_audit.json and runmemo/code/checkpoints/selectedtrades. No V/Tmarketdata/outcomes,forwardpaperselection,newremotecommunications ordeployment. Defaultstrict TRAIN-onlycontinues.\n')
    print(json.dumps(dict(saved_diagnostic=str(archive),stall=stall,memory_updated=True),indent=2))


if __name__=='__main__':main()

"""Reconcile saved cohort test artifacts and report all outcomes without replay."""
import csv
from collections import Counter,defaultdict
import json
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import evaluate_positive_training_cohort as batch
from quant_futures.config import file_hash
from quant_futures.research import json_write

ROOT=batch.ROOT


def row_for(c,state,record):
    row={k:c[k] for k in ('training_order','config_id','instrument','family','training_source','source_rank',
        'training_net','training_cash_dd','training_closing_dd','training_intrabar_dd','full_training_qualified')}
    row.update(status=state,result_path='',error=record.get('error',''))
    if state=='error': return row
    m=record['metrics']
    dd=max(m[k] for k in batch.DD_KEYS)
    simple=m['net_pnl']>0 and dd<2000
    full=simple and not m['killed'] and not m['funded_failed'] and m['trades']>=30 and m['consistency_50_pass']
    row.update(test_net=m['net_pnl'],test_cash_dd=m['realized_drawdown'],test_closing_dd=m['max_drawdown'],
        test_intrabar_dd=m['intrabar_drawdown'],test_trades=m['trades'],test_profit_factor=m['profit_factor'],
        test_expectancy=m['expectancy'],test_consistency=m['consistency'],positive_test_net=m['net_pnl']>0,
        test_dd_under_2000=dd<2000,user_test_checks_pass=simple,full_test_scenario_checks_pass=full,
        test_lock=m['lock'],test_funded_failed=m['funded_failed'],
        result_path=str(batch.CACHED if state=='cached' else batch.DIRECTORY/'results'/(c['config_id']+'.json')))
    return row


def report_text(summary,rows,folder):
    lines=['# All positive, sub-$2,000-drawdown training configurations: frozen test diagnostic','',
        f"**{summary['completed']:,} results: {summary['new_evaluations']:,} newly evaluated configurations and {summary['cached_results']} prior completed result reused without rerunning.** Technical failures: {summary['failed']}. The full cohort of {summary['target']:,} was fixed before new test-price access.",'',
        'Eligibility was exactly the user request across the two completed20k training batches: positive aggregate training net and maximum closing, realized-cash and intrabar fold drawdown strictly below$2,000. No additional minimum-trade, consistency or per-fold-profit gate was silently added. Those stronger flags remain visible separately.', '',
        f"Test results: **{summary['positive_and_dd_under_2000']:,}** had positive net and all three drawdowns below$2,000; "
        f"**{summary['full_test_scenario_pass']:,}** also met the recorded minimum30 trades, consistency50%, no-lock and provisional funded-floor checks. "
        f"**{summary['zero_trade_cases']:,}** produced no trades. These counts are observations, not independent significance or deployment approval. "
        f"Among the10 candidates that passed every original training gate, {summary['full_training_and_user_test_pass']} passed the user's two test filters, but **{summary['full_training_and_full_test_pass']} passed all recorded test scenario gates**.",'',
        '| Market | Frozen cohort | Completed | Positive net and DD<2000 | Full scenario checks |',
        '|---|---:|---:|---:|---:|']
    for symbol,s in summary['by_market'].items():
        lines.append(f"| {symbol} | {s['target']} | {s['completed']} | {s['simple_pass']} | {s['full_pass']} |")
    lines+=['','## Candidates that also passed every original training gate','',
        'Rows retain their pre-test training order. This is not a ranking by test performance. All other eligible cases, including every negative/zero outcome and failure, are retained in the full CSV.','',
        '| Candidate | Family | Training net | Test net | Test cash DD | Test intrabar DD | Trades | Positive test + DD<2000 | Full test scenario |',
        '|---|---|---:|---:|---:|---:|---:|---|---|']
    def money(x): return 'unavailable' if x is None else f'${x:,.2f}'
    for r in rows:
        if r['full_training_qualified']:
            values=[r['config_id'],r['family'],money(r['training_net']),money(r.get('test_net')),
                money(r.get('test_cash_dd')),money(r.get('test_intrabar_dd')),r.get('test_trades','unavailable'),
                r.get('user_test_checks_pass',False),r.get('full_test_scenario_checks_pass',False)]
            lines.append('| '+' | '.join(str(v) for v in values)+' |')
    rel='../runs/'+folder.name
    lines+=['','## Protocol and limitations','',
        'Each configuration was replayed once with its original execution/risk parameters and base costs on its own existing2026 test partition, using a single continuous$50,000 account. Exact complete15-minute bars, causal indicators, next-open entries, original risk locks, first96/last16 entry-bar suppression and all costs were unchanged. No validation data or warmup were accessed. No fitting, revised parameters, alternate cost scenarios or feedback from outcomes were used.', '',
        'The2026 period was already observed for earlier strategies. Evaluating3,243 correlated configurations on this reused period creates substantial selection bias. The full report is an exploratory comparison, not an untouched final test or evidence to select/deploy a winner. Exact account compliance and actual all-in charges remain unverified. Earlier failed tests and all reservations remain preserved. No strategy was selected or modified from these results.', '',
        'The initial launcher stopped on an omitted sys import before new price access or candidate execution. An archived launcher supplied that standard-library import only; the frozen cohort, strategy, original runner bytes and reservations were not changed. Subsequent candidate attempts were protected by exclusive reservations, an OS execution lock and a SQLite primary key; interrupted/failed attempts cannot silently replay.', '',
        f"Independent reconciliation covered all saved trades and curves. The evaluation performed {summary['shared_trade_samples']:,} shared-simulator trade samples and {summary['ledger_trade_checks']:,} arithmetic trade checks, including the reused completed record. Verification replays use identical fixed trades; they are not parameter searches.",'',
        f'[Full results CSV]({rel}/test_results.csv) · [All trade logs CSV]({rel}/test_trades.csv) · [Frozen cohort and parameters]({rel}/frozen_cohort.json)', '',
        'Full-resolution equity/drawdown curves and per-candidate result JSON/trade Parquet files remain in curves/, results/ and trades/ under the run folder. No negative outcomes are removed. The full CSV remains in the frozen training order.','',
        '[Dashboard](http://127.0.0.1:8511/)','']
    return '\n'.join(lines)


def main():
    manifest,frozen=batch.verify();folder=batch.DIRECTORY
    db=sqlite3.connect(folder/'checkpoints.sqlite')
    attempts={cid:(state,json.loads(payload)) for cid,state,payload in db.execute('SELECT config_id,state,payload FROM attempts')}
    db.close()
    if len(attempts)!=frozen['target'] or any(s not in ('completed','cached','error') for s,p in attempts.values()):
        raise ValueError('Cohort incomplete; cannot claim completion')
    rows=[];ledger_checks=shared=0
    trade_fields=['config_id','instrument','family','entry_time','exit_time','side','quantity','entry_price','exit_price','net_pnl','fees','reason']
    with (folder/'test_trades.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=trade_fields);writer.writeheader()
        for c in frozen['cohort']:
            state,p=attempts[c['config_id']]
            row=row_for(c,state,p);rows.append(row)
            if state=='error': continue
            if p['parameters']!=c['parameters']: raise ValueError('Candidate changed')
            if state=='cached':
                curves=Path(p['path'])/p['curve_file'];trades=Path(p['path'])/p['trade_file']
            else:
                curves=folder/'curves'/(c['config_id']+'.parquet');trades=folder/'trades'/(c['config_id']+'.parquet')
            curve=pd.read_parquet(curves);log=pd.read_parquet(trades);m=p['metrics']
            peak=np.maximum.accumulate(np.r_[50000.,curve.equity.to_numpy()])[1:]
            cp=np.maximum.accumulate(np.r_[50000.,curve.cash.to_numpy()])[1:]
            if len(log)!=m['trades']: raise ValueError('Trade count mismatch')
            for actual,expected in [(log.net_pnl.sum(),m['net_pnl']),(curve.equity.iloc[-1]-50000,m['net_pnl']),
                    (max(peak-curve.equity),m['max_drawdown']),(max(cp-curve.cash),m['realized_drawdown']),
                    (max(peak-curve.intrabar_worst_bound),m['intrabar_drawdown']),(log.fees.sum(),m['fees'])]:
                np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)
            v=m['execution_verification'];assert v['passed']
            ledger_checks+=v['ledger_trades'];shared+=v['shared_simulator_replayed']
            for t in log.to_dict('records'):
                writer.writerow(dict(config_id=c['config_id'],instrument=c['instrument'],family=c['family'],**t))
    with (folder/'test_results.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=batch.FIELDS);writer.writeheader();writer.writerows(rows)
    groups={}
    for symbol in ('ES','NQ','MES','MNQ'):
        cases=[r for r in rows if r['instrument']==symbol]
        groups[symbol]=dict(target=len(cases),completed=sum(r['status']!='error' for r in cases),
            simple_pass=sum(bool(r.get('user_test_checks_pass')) for r in cases),full_pass=sum(bool(r.get('full_test_scenario_checks_pass')) for r in cases))
    summary=dict(run_path=str(folder),target=frozen['target'],completed=sum(r['status']!='error' for r in rows),
        new_evaluations=sum(r['status']=='completed' for r in rows),cached_results=sum(r['status']=='cached' for r in rows),
        failed=sum(r['status']=='error' for r in rows),positive_test_net=sum(bool(r.get('positive_test_net')) for r in rows),
        positive_and_dd_under_2000=sum(bool(r.get('user_test_checks_pass')) for r in rows),
        full_test_scenario_pass=sum(bool(r.get('full_test_scenario_checks_pass')) for r in rows),
        full_training_and_user_test_pass=sum(r['full_training_qualified'] and bool(r.get('user_test_checks_pass')) for r in rows),
        full_training_and_full_test_pass=sum(r['full_training_qualified'] and bool(r.get('full_test_scenario_checks_pass')) for r in rows),
        zero_trade_cases=sum(r.get('test_trades')==0 for r in rows),by_market=groups,
        full_training_gate_cases=[r for r in rows if r['full_training_qualified']],
        cohort_hash=manifest['candidate_hash'],no_tuning=True,validation_accessed=False,period_previously_consumed=True,
        independent_confirmation=False,operational_eligibility=False,prior_artifacts_preserved=True,
        ledger_trade_checks=ledger_checks,shared_trade_samples=shared,
        results_csv_sha256=file_hash(folder/'test_results.csv'),trade_csv_sha256=file_hash(folder/'test_trades.csv'))
    json_write(folder/'summary.json',summary)
    json_write(ROOT/'reports/positive_cohort_test_summary.json',summary)
    (ROOT/'reports/POSITIVE_TRAINING_COHORT_TEST.md').write_text(report_text(summary,rows,folder),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('full_training_gate_cases',)}))


if __name__=='__main__': main()

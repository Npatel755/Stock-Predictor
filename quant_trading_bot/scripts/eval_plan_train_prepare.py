"""Export a frozen TRAIN-only PLAN book, never access holdout or paper data."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
os.environ['TRAIN_MINI_UNTIL']='2019-05-06'
import hashlib
import json
from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/eval_plan_risk_refinement_v1'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    RUN.mkdir(parents=True,exist_ok=True)
    if not (RUN/'protocol.json').exists():raise RuntimeError('Freeze protocol before TRAIN data access')
    if (RUN/'training_book.parquet').exists():
        print('Frozen TRAIN book already exists; preserving it.',flush=True);return
    sys.path.insert(0,str(ROOT/'src'))
    import mass_1m_search as m1
    original=m1.load_bars;loads=[]
    def guarded(symbol,minutes,start,end,role,*args,**kwargs):
        if role!='train' or pd.Timestamp(end)>pd.Timestamp('2024-01-01'):raise PermissionError('Only fixed TRAIN history allowed')
        b=original(symbol,minutes,start,end,role,*args,**kwargs)
        if len(b) and not pd.to_datetime(b.timestamp_utc,utc=True).lt(pd.Timestamp('2024-01-01T00:00Z')).all():raise PermissionError('TRAIN observations crossed2024')
        loads.append(dict(symbol=symbol,minutes=minutes,start=start,end=end,role=role,rows=len(b),first=str(b.timestamp_utc.min()),last=str(b.timestamp_utc.max())))
        print(f'TRAIN loaded {symbol}@{minutes}: {len(b):,} rows',flush=True)
        return b
    m1.load_bars=guarded
    import eval_harness as eh
    print('Building corrected causal PLAN book from TRAIN only...',flush=True)
    H=eh.Harness();book=H.build_book(H.PRE,strict='causal').copy()
    assert book.tout.max()<pd.Timestamp('2024-01-01',tz='America/New_York')
    assert book.tin.min()>=pd.Timestamp('2010-01-01',tz='America/New_York')
    intra=book[book.sleeve!='NIGHT'].sort_values('tin')
    # Fixed baseline routes one accepted intraday position at a time; overnight
    # ends before the first RTH entry. Do not alter priorities from outcomes.
    assert all(intra.tin.iloc[i]>=intra.tout.iloc[i-1] for i in range(1,len(intra)))
    book.to_parquet(RUN/'training_book.parquet',index=False)
    pd.DataFrame(dict(start=H.SESS)).to_csv(RUN/'training_starts.csv',index=False)
    H.PRE.to_parquet(RUN/'pre_route_training_book.parquet',index=False)
    provenance=dict(phase='TRAIN_ONLY',data_loads=loads,book_sha256=sha(RUN/'training_book.parquet'),
      starts_sha256=sha(RUN/'training_starts.csv'),book_rows=len(book),intraday_rows=len(intra),sleeves=book.sleeve.value_counts().to_dict(),
      current_price_normalization=H.pl.TODAY,normalization_note='Frozen incumbent scenario normalizes historical percentage moves to fixed reference prices,not historical dollar P&L. No current prices fetched.',
      floor_model='Static -2000;DLL1000;target4000;55%best-day consistency;90calendar days. Frozen incumbent research scenario,not assertion of verified contract terms.',
      validation_accessed=False,test_accessed=False,paper_results_accessed=False)
    (RUN/'training_data_identity.json').write_text(json.dumps(provenance,indent=2,default=str)+'\n')
    print(json.dumps({k:v for k,v in provenance.items() if k!='data_loads'}),flush=True)


if __name__=='__main__':main()

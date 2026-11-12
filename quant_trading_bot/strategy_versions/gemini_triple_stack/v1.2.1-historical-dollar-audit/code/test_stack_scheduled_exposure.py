"""Synthetic source-parquet integration checks of the scheduled-open repair."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import pandas as pd
import pytest
import stack_continuous_exposure_fix_train as repair


def prepare(tmp_path,monkeypatch,active_gap=False,exit_error=False):
    original=tmp_path/'original';original.mkdir();run=tmp_path/'repaired';run.mkdir()
    monkeypatch.setattr(repair,'ORIGINAL',original);monkeypatch.setattr(repair,'RUN',run)
    tin=pd.Timestamp('2020-07-01T14:00Z');tout=pd.Timestamp('2020-07-01T20:00Z')
    clock=pd.date_range(tin,tout+pd.Timedelta(hours=1),freq='min')
    # Unrelated postexit16:15-16:30ET interval must not block a16:00open exit.
    keep=~((clock>tout+pd.Timedelta(minutes=14))&(clock<tout+pd.Timedelta(minutes=30)))
    if active_gap:keep&=~((clock>tin+pd.Timedelta(hours=1))&(clock<tin+pd.Timedelta(hours=1,minutes=20)))
    clock=clock[keep]
    bars=pd.DataFrame(dict(timestamp_utc=clock,open=np.where(clock==tout,105.,100.),high=106.,low=98.,close=100.,volume=10.,contract='MNQU0'))
    market=tmp_path/'train.parquet';bars.to_parquet(market,index=False)
    empty=tmp_path/'empty_train.parquet';bars.iloc[:0].to_parquet(empty,index=False)
    row=dict(id=0,sleeve='AG_TRD60_D_1c',prio=1,inst='MNQ',side=1,entry=100.5,exit=104.0 if exit_error else 104.5,
        tin=tin.tz_convert('America/New_York'),tout=tout.tz_convert('America/New_York'),
        available_exit=(tout+pd.Timedelta(hours=1)).tz_convert('America/New_York'),
        multiplier=2.,entry_risk=50.,n_contracts=1.,per=7.,path_valid=False,adverse=-100.,favorable=100.,
        first_ts=tin,last_ts=tout,bars=0,unique_bars=0,contracts=1,low=98.,high=106.,entry_open=100.,maximum_gap_seconds=960.,bad_ohlc=0.)
    table=original/'training_trade_bounds.parquet';pd.DataFrame([row]).to_parquet(table,index=False)
    p=dict(data_integrity_repair=dict(original_bound_table_sha256=repair.old.sha(table),
        source_engine_sha256=repair.old.sha(repair.ROOT/'scripts/mass_execution.py'),
        source_sleeve_wrapper_sha256=repair.old.sha(repair.ROOT/'src/quant_futures/ensemble_paper.py')),
        training_sources={s:dict(path=str(market if s=='MNQ' else empty),sha256=repair.old.sha(market if s=='MNQ' else empty),role='train') for s in ('MES','ES','MNQ','NQ')})
    return repair.corrected_prepare(p)


def test_postexit_gap_is_not_held_exposure(tmp_path,monkeypatch):
    df=prepare(tmp_path,monkeypatch)
    assert df.path_valid.iloc[0] and df.maximum_gap_seconds.iloc[0]==60
    assert df.available_exit.iloc[0]>df.tout.iloc[0] # routing still waits


def test_missing_quotes_during_actual_hold_remain_rejected(tmp_path,monkeypatch):
    df=prepare(tmp_path,monkeypatch,active_gap=True)
    assert not df.path_valid.iloc[0] and df.maximum_gap_seconds.iloc[0]>300


def test_exit_fill_must_match_actual_exit_open(tmp_path,monkeypatch):
    df=prepare(tmp_path,monkeypatch,exit_error=True)
    assert not df.path_valid.iloc[0]

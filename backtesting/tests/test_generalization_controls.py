from pathlib import Path
import json
import io
import zipfile
from types import SimpleNamespace
import importlib
import hashlib

import pandas as pd
import pytest

from backtesting.generalization_policy import initialize,policy,frozen_profile,assert_search_allowed,assert_historical_period,assert_promotion_allowed
from backtesting.generalization_diagnostics import purged_mask,robust_choice,multiplicity_check
from backtesting.forward_validation import evaluate
from backtesting.external_validation import parse_btc,validate_btc,BTC,recorded_result
from backtesting.eth_research.perpetual_data import COLUMNS
from test_dvs import candles
from test_v15 import write_selection


@pytest.fixture
def locked(tmp_path,monkeypatch):
    import backtesting.save_v15 as exporter
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    experiment=tmp_path/'experiment';write_selection(experiment);exporter.save(experiment)
    repo=Path(__file__).resolve().parents[1]
    for name in ['alternative_strategies.py','engine.py','regime_filters.py','indicators.py','config.py']:
        (tmp_path/name).write_bytes((repo/name).read_bytes())
    initialize('2026-11-03 17:13:48+00:00',tmp_path,version='v1.5')
    return tmp_path


def test_lock_blocks_profit_search_promotions_and_future_training(locked):
    with pytest.raises(ValueError,match='optimization is disabled'):assert_search_allowed(locked)
    with pytest.raises(ValueError,match='unseen forward evidence'):assert_promotion_allowed(locked,{},locked)
    assert_historical_period('2026-11-04',locked)
    with pytest.raises(ValueError,match='locked future holdout'):assert_historical_period('2026-11-04 00:05:00+00:00',locked)
    assert not policy(locked)['ready_for_funded_trading']


@pytest.mark.parametrize('name',['campaign_research','optimize','alternative_research','channel_period_research',
    'exit_research','filter_research','management_research','numbered_research','net_profit_research','trend_research','entry_neighborhood'])
def test_all_optimization_entrypoints_stop_before_reading_args_or_writing(locked,monkeypatch,name):
    module=importlib.import_module('backtesting.'+name)
    monkeypatch.setattr(module,'ROOT',locked)
    with pytest.raises(ValueError,match='optimization is disabled'):module.run(SimpleNamespace())


def test_changed_model_or_execution_invalidates_lock(locked):
    frozen_profile(locked)
    (locked/'engine.py').write_text('changed execution model')
    with pytest.raises(ValueError,match='implementation changed'):frozen_profile(locked)


def test_forward_evaluation_cannot_read_data_before_fixed_date(locked):
    result=evaluate(locked/'does_not_exist.parquet',locked,now='2027-01-01')
    assert result['status']=='awaiting_future_window' and not result['passed']
    assert not (locked/'artifacts/generalization/forward/forward_certificate.json').exists()


def test_ml_training_rejects_locked_future_rows_before_fitting(locked,monkeypatch):
    pytest.importorskip('sklearn')
    pytest.importorskip('xgboost')
    pytest.importorskip('torch')
    import backtesting.eth_research.train as trainer
    monkeypatch.setattr(trainer,'ROOT',locked)
    path=locked/'future_training.csv'
    pd.DataFrame({'timestamp':['2026-11-04 00:00:00+00:00']}).to_csv(path,index=False)
    with pytest.raises(ValueError,match='locked future holdout'):
        trainer.train(SimpleNamespace(bars=path))


def test_filtered_replay_cannot_reveal_future_test_data(locked,monkeypatch):
    import backtesting.filtered_replay as module
    monkeypatch.setattr(module,'ROOT',locked)
    raw=candles(10)
    raw['timestamp']=pd.date_range('2026-11-04',periods=10,freq='5min',tz='UTC')
    destination=locked/'must_not_write'
    with pytest.raises(ValueError,match='locked future holdout'):
        module.replay(raw,{}, {},destination)
    assert not destination.exists()


def test_completed_forward_test_is_consumed_and_cannot_be_overwritten(locked):
    p,rule,_,_=frozen_profile(locked)
    start=pd.Timestamp(p['future_start_utc']);end=pd.Timestamp(p['future_end_exclusive_utc'])
    warmup=pd.Timedelta(hours=rule.slow*5)
    n=int((end-(start-warmup))/pd.Timedelta(minutes=5))
    bars=candles(n)
    bars['timestamp']=pd.date_range(start-warmup,periods=n,freq='5min')
    bars['exchange_close_time']=bars.timestamp+pd.Timedelta(minutes=5)-pd.Timedelta(milliseconds=1)
    path=locked/'future.parquet';bars.to_parquet(path,index=False)
    result=evaluate(path,locked,now=end)
    assert result['prospective_validation_complete'] and not result['ready_for_funded_trading']
    bars.loc[0,'volume']+=1
    bars.to_parquet(path,index=False)
    with pytest.raises(ValueError,match='manifest differs'):evaluate(path,locked,now=end)


def test_forward_test_rejects_missing_candles(locked):
    raw=candles(20)
    raw['timestamp']=pd.date_range('2026-11-03',periods=20,freq='5min',tz='UTC')
    raw['exchange_close_time']=raw.timestamp+pd.Timedelta(minutes=5)-pd.Timedelta(milliseconds=1)
    raw=raw.drop(index=5)
    path=locked/'gapped.parquet';raw.to_parquet(path,index=False)
    with pytest.raises(ValueError,match='data has gaps'):evaluate(path,locked,now='2027-05-03')


def test_purging_uses_outcome_availability_and_gap_not_only_decision_time():
    decisions=pd.Series(pd.to_datetime(['2026-01-01','2026-01-01','2026-01-07'],utc=True))
    ends=pd.Series(pd.to_datetime(['2026-01-02','2026-01-10','2026-01-08'],utc=True))
    assert purged_mask(decisions,ends,'2026-01-15',gap_days=7).tolist()==[True,False,False]


def test_inner_selection_ignores_outer_profit_and_has_no_trade_fallback():
    good=[dict(closed_net=1500,entries=10,margin_calls=0,drawdown=.01)]*3
    rows=[dict(version='simple',complexity_order=0,inner=good,outer_profit=-100000),dict(version='later',complexity_order=1,inner=good,outer_profit=100000)]
    assert robust_choice(rows)=='simple'
    assert robust_choice([dict(version='bad',complexity_order=0,inner=[dict(closed_net=-500,entries=10,margin_calls=0,drawdown=.01)]*3)]) is None


def test_multiplicity_diagnostic_does_not_claim_complete_history():
    result=multiplicity_check([0.]*30,trials=848,draws=100)
    assert result['bonferroni_adjusted_p']==1
    assert not result['complete_search_history_available'] and not result['forward_validation']


def test_btc_parser_preserves_instrument_and_header_and_rejects_eth():
    t=int(pd.Timestamp('2024-01-01',tz='UTC').timestamp()*1000)
    rows=[[t+i*300000,100,101,99,100,10,t+(i+1)*300000-1,1000,5,4,400,0] for i in range(3)]
    payload=io.BytesIO()
    with zipfile.ZipFile(payload,'w') as archive:
        archive.writestr('BTCUSDT.csv',','.join(COLUMNS)+'\n'+'\n'.join(','.join(map(str,r)) for r in rows))
    frame=parse_btc(payload.getvalue())
    assert frame.ticker.eq(BTC).all() and len(frame)==3
    wrong=frame.copy();wrong['ticker']='BINANCE:ETHUSDT.P'
    with pytest.raises(ValueError,match='Only BINANCE:BTC'):validate_btc(wrong)


def test_consumed_transfer_audit_rejects_changed_source_dataset(tmp_path):
    data=tmp_path/'data/generalization/btc';data.mkdir(parents=True)
    parquet=data/'candles.parquet';parquet.write_bytes(b'frozen source')
    out=tmp_path/'artifacts/generalization/btc';out.mkdir(parents=True)
    result={'provenance':{'dataset_sha256':hashlib.sha256(parquet.read_bytes()).hexdigest(),'archives':[]}}
    (out/'results.json').write_text(json.dumps(result))
    assert recorded_result('btc',tmp_path)==result
    parquet.write_bytes(b'new price history')
    with pytest.raises(ValueError,match='consumed audit cannot be overwritten'):recorded_result('btc',tmp_path)

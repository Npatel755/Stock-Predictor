import hashlib
import json

import pandas as pd
import pytest

from backtesting.coinbase_validation import parse_day,validate_coinbase,fetch_day,PRODUCTS
from backtesting.coinbase_verification import exact_frame


def source_rows():
    t=int(pd.Timestamp('2023-01-01',tz='UTC').timestamp())
    return [[t,90,110,100,105,12],[t+300,95,112,105,106,8]],t


def test_coinbase_schema_maps_low_high_open_close_and_volume_without_binance_labels():
    rows,t=source_rows()
    frame,quality=parse_day(json.dumps(list(reversed(rows))).encode(),'ETH-USD','2023-01-01','2023-01-02')
    assert frame.timestamp.iloc[0]==pd.Timestamp(t,unit='s',tz='UTC')
    assert frame.iloc[0][['low','high','open','close','volume']].tolist()==[90,110,100,105,12]
    assert frame.ticker.eq(PRODUCTS['ETH-USD']).all() and quality['rows']==2
    assert 'exchange_close_time' not in frame


def test_coinbase_inclusive_endpoint_and_preceding_start_are_excluded_and_reported():
    rows,t=source_rows();rows+=[[t-300,90,110,100,105,12],[t+86400,90,110,100,105,12]]
    frame,q=parse_day(json.dumps(rows).encode(),'BTC-USD','2023-01-01','2023-01-02')
    assert len(frame)==2 and q['excluded_outside_requested_day']==2 and q['raw_rows']==4
    assert frame.ticker.eq('COINBASE:BTC-USD.SPOT').all()


def test_real_missing_interval_is_reported_and_is_never_forward_filled():
    rows,t=source_rows();rows[1][0]=t+600
    frame,_=parse_day(json.dumps(rows).encode(),'ETH-USD','2023-01-01','2023-01-02')
    _,q=validate_coinbase(frame,'ETH-USD')
    assert q['missing_bars']==1 and len(frame)==2
    wrong=frame.copy();wrong['ticker']='BINANCE:ETHUSDT.P'
    with pytest.raises(ValueError,match='Only COINBASE'):validate_coinbase(wrong,'ETH-USD')


@pytest.mark.parametrize('rows',[
    {'message':'rate limit'},[[1,2,3]],[[1672531200,90,110,100,105,None]],
    [[1672531200.5,90,110,100,105,12]],[[1672531200,120,110,100,105,12]],
    [[1672531201,90,110,100,105,12]],[[1672531200,90,110,100,105,12]]*2,
])
def test_malformed_or_duplicate_source_data_is_rejected(rows):
    with pytest.raises((ValueError,TypeError)):
        parse_day(json.dumps(rows).encode(),'ETH-USD','2023-01-01','2023-01-02')


def test_empty_exchange_response_is_missing_data_not_an_invented_candle():
    frame,q=parse_day(b'[]','ETH-USD','2023-01-01','2023-01-02')
    assert frame.empty and q['rows']==0


def test_pinned_response_cache_does_not_silently_accept_a_local_price_revision(tmp_path):
    day=pd.Timestamp('2023-01-01',tz='UTC');payload=json.dumps(source_rows()[0]).encode()
    raw=tmp_path/'ETH-USD_20230101.json';side=tmp_path/'ETH-USD_20230101.source.json'
    raw.write_bytes(payload)
    side.write_text(json.dumps(dict(url='https://api.exchange.coinbase.com/products/ETH-USD/candles',
        params=dict(start=day.isoformat(),end=(day+pd.Timedelta(days=1)).isoformat(),granularity=300),sha256=hashlib.sha256(payload).hexdigest())))
    class NoNetwork:
        def wait(self):raise AssertionError('Pinned cache must not request new data')
    frame,source=fetch_day('ETH-USD',day,tmp_path,NoNetwork())
    assert len(frame)==2 and source['sha256']==hashlib.sha256(payload).hexdigest()
    raw.write_bytes(b'[]')
    with pytest.raises(ValueError,match='Pinned Coinbase response changed'):
        fetch_day('ETH-USD',day,tmp_path,NoNetwork())


def test_unsupported_products_and_partial_days_cannot_share_daily_cache_keys(tmp_path):
    with pytest.raises(ValueError,match='Unsupported'):
        fetch_day('BTC-USDT',pd.Timestamp('2023-01-01',tz='UTC'),tmp_path,None)
    with pytest.raises(ValueError,match='complete UTC days'):
        fetch_day('ETH-USD',pd.Timestamp('2023-01-01 12:00',tz='UTC'),tmp_path,None)


def test_rate_limit_retry_then_response_pinning_uses_public_endpoint_only(tmp_path,monkeypatch):
    import backtesting.coinbase_validation as module
    payload=json.dumps(source_rows()[0]).encode();calls=[];sleeps=[]
    class Response:
        def __init__(self,status):
            self.status_code=status;self.headers={'Retry-After':'1'};self.content=payload
    def get(url,**kwargs):
        calls.append((url,kwargs));return Response(429 if len(calls)==1 else 200)
    class Limiter:
        def wait(self):pass
    monkeypatch.setattr(module.requests,'get',get)
    monkeypatch.setattr(module.time,'sleep',sleeps.append)
    frame,provenance=fetch_day('ETH-USD',pd.Timestamp('2023-01-01',tz='UTC'),tmp_path,Limiter())
    assert len(frame)==2 and sleeps==[1]
    assert all(url=='https://api.exchange.coinbase.com/products/ETH-USD/candles' for url,_ in calls)
    assert all(not kw['allow_redirects'] and 'auth' not in kw for _,kw in calls)
    assert provenance['sha256']==hashlib.sha256(payload).hexdigest()
    assert (tmp_path/'ETH-USD_20230101.json').read_bytes()==payload


def test_http_rejection_is_not_pinned_as_a_successful_price_response(tmp_path,monkeypatch):
    import backtesting.coinbase_validation as module
    class Rejected:status_code=403
    class Limiter:
        def wait(self):pass
    monkeypatch.setattr(module.requests,'get',lambda *a,**k:Rejected())
    with pytest.raises(ValueError,match='HTTP 403'):
        fetch_day('BTC-USD',pd.Timestamp('2023-01-01',tz='UTC'),tmp_path,Limiter())
    assert not list(tmp_path.glob('*.json'))


def test_verification_normalizes_only_timestamp_storage_units_and_keeps_prices_exact():
    left=pd.DataFrame(dict(timestamp=pd.to_datetime(['2023-01-01'],utc=True).as_unit('s'),close=[100.]))
    right=left.copy();right['timestamp']=right.timestamp.dt.as_unit('ms')
    exact_frame(left,right)
    right.loc[0,'close']+=1e-12
    with pytest.raises(AssertionError):exact_frame(left,right)
    right=left.copy();right['timestamp']+=pd.Timedelta(milliseconds=1)
    with pytest.raises(AssertionError):exact_frame(left,right)

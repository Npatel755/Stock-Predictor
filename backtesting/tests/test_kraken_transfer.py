import io
import json
import zipfile

import pandas as pd
import pytest

from backtesting.remote_zip import RangeZip
from backtesting.kraken_validation import parse_csv,validate_kraken,TICKER


class Response:
    def __init__(self,body,start,end,total,etag='"original"',status=206):
        self.status_code=status
        self.headers={'Content-Range':f'bytes {start}-{end}/{total}','ETag':etag}
        self.raw=io.BytesIO(body)

    def __enter__(self):return self
    def __exit__(self,*args):return False


class Session:
    def __init__(self,payloads):
        self.payloads=payloads;self.requests=[];self.status=206;self.etag='"original"';self.extra=b''

    def get(self,url,headers,**kwargs):
        self.requests.append((url,headers))
        start,end=map(int,headers['Range'].removeprefix('bytes=').split('-'))
        data=self.payloads[url]
        return Response(data[start:end+1]+self.extra,start,end,len(data),self.etag,self.status)


def parts(payloads):
    return [dict(url=url,size=len(data),etag='"original"') for url,data in payloads.items()]


def test_random_access_zip_reads_across_part_boundaries_and_verifies_member_crc(tmp_path):
    output=io.BytesIO()
    content=b'fixed historical ETH/USD member\n'*100
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr('ETHUSD_5.csv',content)
    raw=output.getvalue();split=len(raw)//2
    payloads={'part0':raw[:split],'part1':raw[split:]};session=Session(payloads)
    with RangeZip(parts(payloads),tmp_path,session=session) as stream:
        with zipfile.ZipFile(stream) as archive:assert archive.read('ETHUSD_5.csv')==content
        assert stream.transferred<4096
    assert session.requests and all(h['If-Match']=='"original"' for _,h in session.requests)


def test_range_cache_is_identity_bound_and_detects_modified_local_bytes(tmp_path):
    payloads={'part':b'0123456789'};session=Session(payloads)
    stream=RangeZip(parts(payloads),tmp_path,session=session)
    assert stream.read(5)==b'01234'
    stream.seek(0)
    assert stream.read(5)==b'01234' and len(session.requests)==1
    next(tmp_path.glob('*.bin')).write_bytes(b'wrong')
    stream.seek(0)
    with pytest.raises(ValueError,match='Cached archive range changed'):stream.read(5)


def test_a_corrupt_selected_zip_member_fails_crc_validation(tmp_path):
    output=io.BytesIO();content=b'original ETH/USD candle payload'
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as archive:archive.writestr('ETHUSD_5.csv',content)
    raw=output.getvalue();offset=raw.index(content)
    corrupted=raw[:offset]+b'X'+raw[offset+1:]
    payloads={'part':corrupted}
    with RangeZip(parts(payloads),tmp_path,session=Session(payloads)) as stream:
        with zipfile.ZipFile(stream) as archive:
            with pytest.raises(zipfile.BadZipFile,match='CRC'):archive.read('ETHUSD_5.csv')


@pytest.mark.parametrize('mode',['full_response','changed_etag','extra_body','short_body','wrong_boundaries','encoded'])
def test_unsafe_or_inconsistent_http_range_responses_are_rejected(tmp_path,mode):
    payloads={'part':b'0123456789'};session=Session(payloads)
    if mode=='full_response':session.status=200
    if mode=='changed_etag':session.etag='"new"'
    if mode=='extra_body':session.extra=b'x'
    get=session.get
    if mode in {'short_body','wrong_boundaries','encoded'}:
        def response(*args,**kwargs):
            r=get(*args,**kwargs)
            if mode=='short_body':r.raw=io.BytesIO(b'0')
            if mode=='wrong_boundaries':r.headers['Content-Range']='bytes 1-5/10'
            if mode=='encoded':r.headers['Content-Encoding']='gzip'
            return r
        session.get=response
    stream=RangeZip(parts(payloads),tmp_path,session=session)
    with pytest.raises(ValueError):stream.read(5)
    assert not list(tmp_path.glob('*.bin'))


def test_transfer_and_single_read_limits_prevent_unbounded_archive_downloads(tmp_path):
    payloads={'part':b'0123456789'};session=Session(payloads)
    stream=RangeZip(parts(payloads),tmp_path,session=session,max_bytes=4,max_read=8)
    with pytest.raises(ValueError,match='transfer budget'):stream.read(5)
    with pytest.raises(ValueError,match='bounded request'):stream.read(9)
    assert not session.requests


def test_kraken_parser_preserves_real_gaps_and_reports_off_grid_without_shifting():
    start=int(pd.Timestamp('2020-01-01',tz='UTC').timestamp())
    rows=[[start+i*300,100,101,99,100,10,5] for i in [0,1,3]]
    rows.append([start+600+1,100,101,99,100,10,5])
    payload=('\n'.join(','.join(map(str,r)) for r in rows)).encode()
    frame,quality=parse_csv(payload,'2020-01-01','2020-01-02')
    assert frame.ticker.eq(TICKER).all() and len(frame)==3
    assert quality['excluded_off_grid_rows']==1 and quality['missing_bars']==1
    assert frame.timestamp.tolist()==list(pd.to_datetime([start,start+300,start+900],unit='s',utc=True))
    assert 'exchange_close_time' not in frame
    wrong=frame.copy();wrong['ticker']='BINANCE:ETHUSDT.P'
    with pytest.raises(ValueError,match='Only KRAKEN'):validate_kraken(wrong)


def test_kraken_parser_rejects_duplicate_and_noninteger_source_rows():
    start=int(pd.Timestamp('2020-01-01',tz='UTC').timestamp())
    row=f'{start},100,101,99,100,10,5'
    with pytest.raises(ValueError,match='Duplicate'):parse_csv((row+'\n'+row).encode())
    with pytest.raises(ValueError,match='Noninteger'):parse_csv(f'{start},100,101,99,100,10,5.5'.encode())

"""Bounded, identity-checked HTTP range reads across a concatenated ZIP."""
from __future__ import annotations

import hashlib
import io
import json
from bisect import bisect_right
from pathlib import Path

import requests


class RangeZip(io.RawIOBase):
    def __init__(self,parts,cache: Path,session=None,max_bytes=128*1024*1024,max_read=32*1024*1024):
        super().__init__()
        self.parts=parts;self.cache=cache;self.cache.mkdir(parents=True,exist_ok=True)
        self.session=session or requests.Session();self.owns_session=session is None
        self.starts=[0]
        for part in parts:
            if not isinstance(part['size'],int) or part['size']<=0 or not part.get('etag'):
                raise ValueError('Range archive needs positive part sizes and pinned ETags')
            self.starts.append(self.starts[-1]+part['size'])
        self.position=0;self.transferred=0;self.max_bytes=max_bytes;self.max_read=max_read;self.ledger=[]

    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position

    def seek(self,offset,whence=0):
        target=offset if whence==0 else self.position+offset if whence==1 else self.starts[-1]+offset if whence==2 else -1
        if target<0:raise ValueError('Invalid range archive seek')
        self.position=target
        return target

    def read(self,size=-1):
        if size is None or size<0:size=self.starts[-1]-self.position
        size=min(size,max(0,self.starts[-1]-self.position))
        if size>self.max_read:raise ValueError('Archive read exceeds bounded request size')
        chunks=[]
        while size:
            index=bisect_right(self.starts,self.position)-1
            local=self.position-self.starts[index]
            count=min(size,self.parts[index]['size']-local)
            chunks.append(self._part(index,local,count))
            self.position+=count;size-=count
        return b''.join(chunks)

    def _part(self,index,start,count):
        part=self.parts[index];end=start+count-1
        identity=dict(url=part['url'],etag=part['etag'],size=part['size'],start=start,end=end)
        key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        raw=self.cache/f'{key}.bin';sidecar=self.cache/f'{key}.json'
        if raw.exists() and sidecar.exists():
            saved=json.loads(sidecar.read_text(encoding='utf-8'));payload=raw.read_bytes()
            if (saved['identity']!=identity or len(payload)!=count
                    or hashlib.sha256(payload).hexdigest()!=saved['sha256']):
                raise ValueError('Cached archive range changed')
        else:
            if self.transferred+count>self.max_bytes:raise ValueError('Archive transfer budget exceeded')
            headers={'Range':f'bytes={start}-{end}','If-Match':part['etag'],'Accept-Encoding':'identity'}
            with self.session.get(part['url'],headers=headers,timeout=30,stream=True) as response:
                if response.status_code!=206:raise ValueError(f'Archive server did not honor a bounded range: HTTP {response.status_code}')
                if response.headers.get('Content-Range')!=f"bytes {start}-{end}/{part['size']}":
                    raise ValueError('Archive range response boundaries differ')
                if response.headers.get('ETag')!=part['etag']:raise ValueError('Remote archive identity changed')
                if response.headers.get('Content-Encoding','identity') not in {'identity',''}:
                    raise ValueError('Encoded range response is not a ZIP byte range')
                payload=response.raw.read(count+1)
            if len(payload)!=count:raise ValueError('Archive range body has unexpected length')
            self.transferred+=count
            raw.write_bytes(payload)
            sidecar.write_text(json.dumps(dict(identity=identity,sha256=hashlib.sha256(payload).hexdigest()),indent=2),encoding='utf-8')
        self.ledger.append(dict(**identity,sha256=hashlib.sha256(payload).hexdigest(),cache_file=raw.name))
        return payload

    def close(self):
        if self.owns_session:self.session.close()
        super().close()

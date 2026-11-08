"""Publish automatically after the frozen validation batch seals; no price execution."""
import json
from pathlib import Path
import time
from quant_futures.config import file_hash
from quant_futures.research import json_write
import validation_selection_200k as batch


def main():
    publisher=Path(__file__).with_name('publish_validation_selection_200k.py')
    registration=batch.RUN/'automatic_publication.json'
    expected=file_hash(publisher)
    if registration.exists():
        saved=batch.read(registration)
        if saved['publisher_sha256']!=expected:raise ValueError('Registered publisher changed')
    else:json_write(registration,dict(publisher_sha256=expected,created_at=batch.now(),phase='wait_for_sealed_validation_then_report',test_accessed=False))
    print(json.dumps(dict(automatic_report_registered=True)),flush=True)
    while not (batch.RUN/'validation_complete.json').exists():
        time.sleep(15)
    if file_hash(publisher)!=expected:raise ValueError('Registered publisher changed while waiting')
    from publish_validation_selection_200k import main as publish
    publish()


if __name__=='__main__':main()

"""Keep exact historical input bytes when live archive caches are extended."""
import hashlib
from pathlib import Path


def retain(path,root):
    payload=path.read_bytes();digest=hashlib.sha256(payload).hexdigest()
    destination=root/'artifacts/generalization/frozen_inputs'/digest/path.name
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest()!=digest:raise ValueError('Frozen input snapshot was modified')
    else:destination.write_bytes(payload)
    quality=path.with_suffix('.quality.json')
    if quality.exists() and not destination.with_suffix('.quality.json').exists():
        destination.with_suffix('.quality.json').write_bytes(quality.read_bytes())
    return destination,digest


def recorded_path(root,name,expected):
    current=root/name
    if current.exists() and hashlib.sha256(current.read_bytes()).hexdigest()==expected:return current
    archived=root/'artifacts/generalization/frozen_inputs'/expected/Path(name).name
    if archived.exists() and hashlib.sha256(archived.read_bytes()).hexdigest()==expected:return archived
    raise ValueError(f'Frozen data_hashes input changed without an exact retained snapshot: {name}')

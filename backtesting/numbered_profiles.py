"""Hash-verified numbered ETH profiles, including explicit v1.5 filters."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .alternative_strategies import SignalRule
from .config import StrategyConfig
from .paths import ROOT
from .regime_filters import RegimeFilter


def load_profile(root: Path = ROOT, version='v1.3'):
    if not re.fullmatch(r'v1\.(?:[3-9]|[1-9][0-9]+)', version):
        raise ValueError('Unsupported independent strategy version')
    suffix = version.replace('.', '_')
    payload = json.loads((root/f'configs/eth_strategy_{suffix}.json').read_text(encoding='utf-8'))
    metadata = json.loads((root/f'configs/eth_strategy_{suffix}.metadata.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    pine = root/f'reference/ETH_Strategy_{suffix}.pine'
    if (digest != metadata['configuration_sha256']
            or hashlib.sha256(pine.read_bytes()).hexdigest() != metadata['pine_sha256']
            or metadata['strategy_name'] != f'ETH {version}'):
        raise ValueError(f'{version} configuration or Pine does not match its saved metadata')
    filters = payload.get('filters')
    if filters is not None:
        RegimeFilter(**filters)
        if metadata.get('entry_filters') != filters:
            raise ValueError('Profile filter metadata differs from its backtested entry filters')
    elif metadata.get('entry_filters'):
        raise ValueError('Filter metadata has no corresponding saved profile')
    return SignalRule(**payload['rule']), StrategyConfig(**payload['execution']), metadata, pine

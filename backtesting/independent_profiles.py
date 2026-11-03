"""Versioned independent profiles, isolated from older cached loaders."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .alternative_strategies import SignalRule
from .config import StrategyConfig
from .paths import ROOT


def load_profile(root: Path = ROOT, version='v1.3'):
    if version not in {'v1.3', 'v1.4'}:
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
    return SignalRule(**payload['rule']), StrategyConfig(**payload['execution']), metadata, pine

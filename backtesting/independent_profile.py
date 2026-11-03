"""Load an independent profile only when config and Pine hashes agree."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .alternative_strategies import SignalRule
from .config import StrategyConfig
from .paths import ROOT


def load_profile(root: Path = ROOT):
    payload = json.loads((root/'configs/eth_strategy_v1_3.json').read_text(encoding='utf-8'))
    metadata = json.loads((root/'configs/eth_strategy_v1_3.metadata.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    pine = root/'reference/ETH_Strategy_v1_3.pine'
    if digest != metadata['configuration_sha256'] or hashlib.sha256(pine.read_bytes()).hexdigest() != metadata['pine_sha256']:
        raise ValueError('v1.3 configuration or Pine does not match its saved metadata')
    return SignalRule(**payload['rule']), StrategyConfig(**payload['execution']), metadata, pine

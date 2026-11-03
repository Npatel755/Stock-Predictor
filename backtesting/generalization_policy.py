"""Freeze strategy identity and keep inspected history out of forward validation."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pandas as pd

from .exit_research import freeze
from .numbered_profiles import load_profile
from .paths import ROOT


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def policy(root=ROOT):
    path=root/'configs/generalization_policy.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def initialize(now,root=ROOT,version='v1.11'):
    now=pd.Timestamp(now)
    now=now.tz_localize('UTC') if now.tzinfo is None else now.tz_convert('UTC')
    rule,cfg,meta,pine=load_profile(root,version)
    payload=dict(rule=asdict(rule),execution=asdict(cfg),filters=meta['entry_filters'])
    start=now.floor('D')+pd.Timedelta(days=1)
    settings=dict(protocol_version=1,created_at_utc=str(now),frozen_version=version,
                  frozen_configuration_sha256=digest(payload),frozen_pine_sha256=hashlib.sha256(pine.read_bytes()).hexdigest(),
                  frozen_payload=payload,known_inspected_history_through=str(now),
                  historical_search_slots_at_freeze=848,whole_history_profit_search_enabled=False,
                  new_version_promotion_requires_unseen_evidence=True,
                  future_start_utc=str(start),future_end_exclusive_utc=str(start+pd.Timedelta(days=180)),
                  minimum_closed_trades=30,maximum_intrabar_drawdown=.05,
                  required_cost_scenarios_bps=[2.,4.,8.],
                  final_evaluation_only=True,parameters_may_change_during_forward_window=False,
                  prospective_validation_complete=False,ready_for_funded_trading=False,
                  algorithms={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                              ['alternative_strategies.py','engine.py','regime_filters.py','indicators.py','config.py']},
                  new_data_policy='Freeze rules before fetching a new dataset. Test once as a diagnostic. After inspection it becomes development data; never tune on it while calling it a holdout.',
                  uncertainty='No finite backtest guarantees future performance. Historical walk-forward and multiplicity checks remain retrospective because the candidate pool was already inspected.')
    path=root/'configs/generalization_policy.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    freeze(path,settings)
    return settings


def frozen_profile(root=ROOT):
    p=policy(root)
    if p is None: raise ValueError('Initialize the generalization protocol first')
    rule,cfg,meta,pine=load_profile(root,p['frozen_version'])
    payload=dict(rule=asdict(rule),execution=asdict(cfg),filters=meta['entry_filters'])
    if digest(payload)!=p['frozen_configuration_sha256'] or hashlib.sha256(pine.read_bytes()).hexdigest()!=p['frozen_pine_sha256']:
        raise ValueError('Frozen strategy changed after the validation lock')
    for name,value in p['algorithms'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=value:
            raise ValueError(f'Frozen execution/feature implementation changed: {name}')
    return p,rule,cfg,meta


def assert_search_allowed(root=ROOT):
    p=policy(root)
    if p and not p['whole_history_profit_search_enabled']:
        raise ValueError('Whole-history profit optimization is disabled by the generalization policy. Use fixed-rule diagnostics or the locked forward evaluation.')


def forward_status(root=ROOT):
    p=policy(root)
    if not p:return 'not_initialized'
    path=root/'artifacts/generalization/forward/forward_certificate.json'
    if not path.exists():
        return 'awaiting_future_window' if pd.Timestamp.now(tz='UTC')<pd.Timestamp(p['future_end_exclusive_utc']) else 'awaiting_complete_data'
    if pd.Timestamp.now(tz='UTC')<pd.Timestamp(p['future_end_exclusive_utc']):return 'premature_certificate_rejected'
    c=json.loads(path.read_text(encoding='utf-8'))
    if c.get('protocol_sha256')!=digest(p) or c.get('configuration_sha256')!=p['frozen_configuration_sha256']:
        return 'invalidated_certificate'
    return 'passed_frozen_forward_test' if c.get('passed') else 'forward_test_failed_or_insufficient'


def assert_historical_period(end_exclusive,root=ROOT):
    p=policy(root)
    end=pd.Timestamp(end_exclusive)
    end=end.tz_localize('UTC') if end.tzinfo is None else end.tz_convert('UTC')
    if p and end>pd.Timestamp(p['future_start_utc']):
        raise ValueError('This period enters the locked future holdout. It cannot be used for training, tuning or ordinary replay.')


def assert_promotion_allowed(directory,payload,root=ROOT):
    p=policy(root)
    if not p: return
    certificate=directory/'forward_certificate.json'
    if not certificate.exists():
        raise ValueError('Historical P&L cannot promote a version. Matching unseen forward evidence is required by the generalization policy.')
    c=json.loads(certificate.read_text(encoding='utf-8'))
    if (c.get('protocol_sha256')!=digest(p) or c.get('configuration_sha256')!=digest(payload)
            or digest(payload)!=p['frozen_configuration_sha256']
            or not c.get('passed') or c.get('evaluation_type')!='locked_forward'
            or c.get('period')!=[p['future_start_utc'],p['future_end_exclusive_utc']]
            or pd.Timestamp.now(tz='UTC')<pd.Timestamp(p['future_end_exclusive_utc'])):
        raise ValueError('The forward certificate is incomplete or does not match the locked strategy/protocol')
    frozen_profile(root)

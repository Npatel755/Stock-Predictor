"""Policy, qualification, robustness scoring, and cross-contract transfer for 500k search.

Informed by:
- overfitting-defense: Protect statistical evidence from adaptive reuse and multiple testing.
- cross-contract-transfer: Research signals on NQ/ES while mapping to MNQ/MES with correct economics.
- market-regime-analysis: Multi-year calendar fold consistency (2020-2023).
- strategy-discovery: Balanced coverage across all 10 strategy families.
"""
import csv
import json
from pathlib import Path
import mass_research as engine
from mass_configurations import semantic_key
from quant_futures.config import file_hash

BENCHMARK_ID = 'mass_4a0b95329be1d0438243'
PRIOR = (
    'mass_training_v2',
    'mass_training_continuation_v1',
    'training_search_50k_v2',
    'training_search_100k_v1',
    'training_search_200k_v1'
)


def robustness_metric(net_pnl, profit_factor, intrabar_dd):
    if net_pnl <= 0 or profit_factor <= 1.0:
        return 0.0
    return float((net_pnl * (profit_factor - 1.0)) / max(float(intrabar_dd), 500.0))


def aggregate(configuration, folds, signal):
    row = engine.aggregate(configuration, folds, signal)
    pf = float(row.get('profit_factor', 0.0) or 0.0)
    net = float(row.get('net_pnl', 0.0) or 0.0)
    worst_ib_dd = max(float(m['intrabar_drawdown']) for m in folds)
    worst_close_dd = max(float(m['max_drawdown']) for m in folds)
    worst_cash_dd = max(float(m['realized_drawdown']) for m in folds)
    
    # Anti-overfitting qualification gates:
    # 1. No permanent locks or funded floor breaches in any training year
    no_breaches = all(not m['killed'] and not m['funded_failed'] for m in folds)
    # 2. Strict drawdown limit (<$2000 in every fold: cash, closing, and intrabar)
    dd_pass = (worst_ib_dd < 2000.0 and worst_close_dd < 2000.0 and worst_cash_dd < 2000.0)
    # 3. Overall positive net profit across training history
    positive_net = net > 0.0
    # 4. Consistency: at least 3 out of 4 calendar folds positive (avoids single-regime curve fitting)
    pos_folds = sum(m['net_pnl'] > 0 for m in folds)
    fold_consistency = pos_folds >= 3
    # 5. Quality filter: Profit Factor >= 1.30
    quality_pf = pf >= 1.30
    # 6. Trade count: between 80 and 800 trades total across training folds
    total_trades = sum(m['trades'] for m in folds)
    trade_count_pass = (80 <= total_trades <= 800)
    
    row['qualified'] = bool(no_breaches and dd_pass and positive_net and fold_consistency and quality_pf and trade_count_pass)
    row['evaluation_phase_qualified'] = bool(row['qualified'] and all(m.get('consistency_50_pass', False) for m in folds))
    row['robustness_score'] = robustness_metric(net, pf, worst_ib_dd)
    return row


def prior_training(root, names=PRIOR):
    preserved = {}; benchmark = None
    for name in names:
        folder = Path(root)/'runs'/name
        for filename in ('protocol.json', 'ranked.csv', 'configurations.jsonl', 'results.json'):
            target = folder/filename
            if target.exists():
                preserved[str(target)] = file_hash(target)
        ranked_path = folder/'ranked.csv'
        if ranked_path.exists() and benchmark is None:
            with ranked_path.open(encoding='utf-8', newline='') as stream:
                for row in csv.DictReader(stream):
                    if row['config_id'] == BENCHMARK_ID:
                        benchmark = dict(
                            config_id=row['config_id'],
                            parameters=json.loads(row['parameters']),
                            net_pnl=float(row['net_pnl']),
                            max_drawdown=float(row['max_drawdown']),
                            realized_drawdown=float(row['realized_drawdown']),
                            intrabar_drawdown=float(row['intrabar_drawdown']),
                            fold_metrics=json.loads(row['fold_metrics']),
                            profit_factor=float(row.get('profit_factor', 1.5))
                        )
    if benchmark is None:
        bench_path = Path(root)/'runs/top_test_reused_validation_mass_4a0b95329be1d0438243/frozen_candidate.json'
        if bench_path.exists():
            fc = json.loads(bench_path.read_text(encoding='utf-8'))['candidate']
            stc = fc['source_training_candidate']
            benchmark = dict(
                config_id=BENCHMARK_ID,
                parameters=fc['parameters'],
                net_pnl=float(stc['training_net']),
                max_drawdown=float(stc['training_closing_dd']),
                realized_drawdown=float(stc['training_cash_dd']),
                intrabar_drawdown=float(stc['training_intrabar_dd']),
                fold_metrics=[],
                profit_factor=1.5
            )
    return names, benchmark, preserved

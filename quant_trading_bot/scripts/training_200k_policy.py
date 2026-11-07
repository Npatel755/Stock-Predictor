"""Policy, qualification, and robustness scoring for 200,000-strategy training search.

Informed by overfitting-defense, market-regime-analysis, and strategy-discovery skills.
Prioritizes high profit factor, asymmetric risk/reward, clean turnover, and low drawdown
to prevent curve-fitting and maximize out-of-sample generalization.
"""
import csv
import json
from pathlib import Path
import mass_research as engine
from mass_configurations import semantic_key
from quant_futures.config import file_hash

# The user's highlighted benchmark strategy that validated and tested successfully:
BENCHMARK_ID = 'mass_4a0b95329be1d0438243'
PRIOR = ('mass_training_v2', 'mass_training_continuation_v1', 'training_search_50k_v2', 'training_search_100k_v1')


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
    
    # Anti-overfitting research qualification:
    # 1. No permanent locks or funded-account floor breaches in any year
    no_breaches = all(not m['killed'] and not m['funded_failed'] for m in folds)
    # 2. Strict drawdown limit (<$2000 in every fold, cash, closing, and intrabar)
    dd_pass = (worst_ib_dd < 2000.0 and worst_close_dd < 2000.0 and worst_cash_dd < 2000.0)
    # 3. Overall profitability across the 4 training years
    positive_net = net > 0.0
    # 4. Consistency: at least 3 out of 4 calendar folds positive (avoids over-tuning to single regimes)
    pos_folds = sum(m['net_pnl'] > 0 for m in folds)
    fold_consistency = pos_folds >= 3
    # 5. Quality: Profit factor >= 1.30 (filters out low-margin churn that fails out-of-sample)
    quality_pf = pf >= 1.30
    # 6. Trade count: between 80 and 800 trades total (statistically meaningful without scalping churn)
    total_trades = sum(m['trades'] for m in folds)
    trade_count_pass = (80 <= total_trades <= 800)
    
    row['qualified'] = bool(no_breaches and dd_pass and positive_net and fold_consistency and quality_pf and trade_count_pass)
    row['evaluation_phase_qualified'] = bool(row['qualified'] and all(m.get('consistency_50_pass', False) for m in folds))
    row['robustness_score'] = robustness_metric(net, pf, worst_ib_dd)
    return row


def prior_training(root, names=PRIOR):
    excluded = set(); preserved = {}; benchmark = None
    for name in names:
        folder = Path(root)/'runs'/name
        for filename in ('protocol.json', 'ranked.csv', 'configurations.jsonl', 'results.json'):
            target = folder/filename
            if target.exists():
                preserved[str(target)] = file_hash(target)
        for line in (folder/'configurations.jsonl').read_text(encoding='utf-8').splitlines():
            excluded.add(semantic_key(json.loads(line)))
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
    if len(excluded) != 170000:
        raise ValueError(f'Expected 170,000 prior configurations across batches, got {len(excluded)}')
    if benchmark is None:
        # Fallback to load directly from previous run if not in ranked.csv
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
    return excluded, benchmark, preserved

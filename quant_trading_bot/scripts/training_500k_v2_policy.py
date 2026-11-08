"""Policy and ranking rules for 500,000 Training Search v2.

Sets mass_e57ba183f302b3ba886b as the new baseline ($4,935.50 Net P&L).
Maximizes Net P&L subject to the strict constraint that all drawdowns stay under $2,000.
Strictly TRAIN data only (2020-2023). Validation evaluation performed post-selection without tuning.
"""
from pathlib import Path
from quant_futures.config import file_hash

BENCHMARK_ID = 'mass_e57ba183f302b3ba886b'
BENCHMARK_PARAMS = {
    'config_id': 'mass_e57ba183f302b3ba886b',
    'experiment_order': 401804,
    'family': 'momentum',
    'hold_bars': 12,
    'instrument': 'MNQ',
    'lookback': 16,
    'max_contracts': 1,
    'session_end': 945,
    'session_start': 585,
    'stop_atr': 1.0,
    'target_r': 4.0,
    'threshold': 1.5,
    'trailing_atr': 2.0
}
BENCHMARK_METRICS = {
    'config_id': 'mass_e57ba183f302b3ba886b',
    'net_pnl': 4935.50,
    'realized_drawdown': 408.00,
    'max_drawdown': 500.50,
    'intrabar_drawdown': 533.25,
    'profit_factor': 1.83,
    'trades': 202
}

PRIOR = [
    'collaborative_200k_v1',
    'mass_training_continuation_v1',
    'mass_training_v1',
    'mass_training_v2',
    'training_search_100k_v1',
    'training_search_200k_v1',
    'training_search_500k_v1',
    'training_search_50k_v1',
    'training_search_50k_v2'
]


def aggregate(c, fold_metrics, signal):
    net_pnl = sum(m['net_pnl'] for m in fold_metrics)
    max_dd = max(m['max_drawdown'] for m in fold_metrics)
    realized_dd = max(m['realized_drawdown'] for m in fold_metrics)
    intrabar_dd = max(m['intrabar_drawdown'] for m in fold_metrics)
    trades = sum(m['trades'] for m in fold_metrics)
    gross_pnl = sum(m['gross_pnl'] for m in fold_metrics)
    fees = sum(m['fees'] for m in fold_metrics)
    pos_pnl = sum(m['positive_trade_pnl'] for m in fold_metrics)
    neg_pnl = sum(m['negative_trade_pnl'] for m in fold_metrics)
    locks = sum(m['lock'] for m in fold_metrics)
    funded_fails = sum(1 for m in fold_metrics if m['funded_failed'])
    positive_folds = sum(1 for m in fold_metrics if m['net_pnl'] > 0)
    
    pf = (pos_pnl / abs(neg_pnl)) if neg_pnl < 0 else (99.0 if pos_pnl > 0 else 0.0)

    # Qualification criteria: Net PnL positive, all DDs < $2,000, zero locks, min 50 trades, >=3/4 positive folds
    qualified = bool(
        intrabar_dd < 2000 and max_dd < 2000 and realized_dd < 2000 and
        locks == 0 and funded_fails == 0 and
        trades >= 50 and positive_folds >= 3 and
        net_pnl > 0
    )
    
    better_than_baseline = bool(qualified and net_pnl > BENCHMARK_METRICS['net_pnl'])

    return dict(
        config_id=c['config_id'],
        instrument=c['instrument'],
        family=c['family'],
        qualified=qualified,
        better_than_baseline=better_than_baseline,
        net_pnl=net_pnl,
        max_drawdown=max_dd,
        realized_drawdown=realized_dd,
        intrabar_drawdown=intrabar_dd,
        profit_factor=pf,
        trades=trades,
        positive_folds=positive_folds,
        total_folds=len(fold_metrics),
        locks=locks,
        funded_breaches=funded_fails,
        parameters=c,
        fold_metrics=fold_metrics
    )


def prior_training(root, prior_names):
    benchmark = dict(parameters=BENCHMARK_PARAMS, **BENCHMARK_METRICS)
    preserved = {}
    for name in prior_names:
        for f in ('protocol.json', 'ranked.csv', 'results.json', 'configurations.jsonl'):
            p = root/'runs'/name/f
            if p.exists():
                preserved[str(p)] = file_hash(p)
    return prior_names, benchmark, preserved

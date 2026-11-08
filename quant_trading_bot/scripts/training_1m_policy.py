"""Research policy and qualification gates for 1,000,000 Training Search."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def aggregate(c, fold_metrics, signal):
    """Aggregate fold metrics and apply strict evaluation research gates."""
    trades = sum(m.get('trades', 0) for m in fold_metrics)
    net_pnl = sum(m.get('net_pnl', 0.0) for m in fold_metrics)
    realized_dd = max(m.get('realized_drawdown', 0.0) for m in fold_metrics) if fold_metrics else 0.0
    closing_dd = max(m.get('max_drawdown', 0.0) for m in fold_metrics) if fold_metrics else 0.0
    intrabar_dd = max(m.get('intrabar_drawdown', 0.0) for m in fold_metrics) if fold_metrics else 0.0
    locks = sum(m.get('lock', 0) for m in fold_metrics)

    wins = sum(m.get('net_pnl', 0.0) for m in fold_metrics if m.get('net_pnl', 0.0) > 0)
    loss = abs(sum(m.get('net_pnl', 0.0) for m in fold_metrics if m.get('net_pnl', 0.0) < 0))
    pf = (wins / loss) if loss > 0 else (99.0 if wins > 0 else 0.0)

    pos_folds = sum(1 for m in fold_metrics if m.get('net_pnl', 0.0) > 0)
    max_fold_dd = max(m.get('intrabar_drawdown', 0.0) for m in fold_metrics) if fold_metrics else 0.0

    # Gates for qualification:
    # 1. Net profit > 0
    # 2. Minimum 40 trades on train
    # 3. At least 3 of 4 folds positive
    # 4. Intrabar drawdown strictly < $2,000 across all folds
    # 5. Zero account locks (no daily loss or hard DD breach)
    qualified = (
        net_pnl > 0 and
        trades >= 40 and
        pos_folds >= 3 and
        intrabar_dd < 2000.0 and
        max_fold_dd < 2000.0 and
        locks == 0
    )

    return {
        'config_id': c['config_id'],
        'experiment_order': c.get('experiment_order', 0),
        'instrument': c['instrument'],
        'family': c['family'],
        'net_pnl': net_pnl,
        'trades': trades,
        'profit_factor': pf,
        'realized_drawdown': realized_dd,
        'max_drawdown': closing_dd,
        'intrabar_drawdown': intrabar_dd,
        'positive_folds': pos_folds,
        'locks': locks,
        'qualified': bool(qualified),
        'parameters': c
    }

"""Research policy and high-velocity qualification gates for 2,000,000 Training Search."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

SPECS = {
    "MNQ": {"tick": 0.25, "multiplier": 2.0},
    "MES": {"tick": 0.25, "multiplier": 5.0},
    "NQ": {"tick": 0.25, "multiplier": 20.0},
    "ES": {"tick": 0.25, "multiplier": 50.0},
}


def execution_cfg_2m(c, factor=1):
    symbol = c["instrument"]
    spec = SPECS[symbol]
    qty = int(c.get("max_contracts", 1))
    return dict(
        initial_balance=50000.0,
        tick=spec["tick"],
        multiplier=spec["multiplier"],
        commission_per_side=1.75 if symbol in ("ES", "NQ") else 0.50,
        exchange_per_side=0.0,
        regulatory_per_side=0.0,
        spread_ticks=1,
        slippage_ticks=1,
        impact_ticks=0.25 * (qty - 1),
        factor=factor,
        maxqty=qty,
        risk_per_trade=150.0 * qty,
        max_open_risk=150.0 * qty,
        daily_loss=400.0 * qty,
        hard_drawdown=2000.0,
        stop_atr=float(c["stop_atr"]),
        target_ratio=float(c["target_r"]),
        hold_bars=int(c["hold_bars"]),
        entry_start=int(c["session_start"]) - 15,
        entry_end=int(c["session_end"]) - 30,
        flat_minute=min(int(c["session_end"]), 955),
        max_gap_minutes=20,
        participation=0.01,
        trailing_atr=float(c["trailing_atr"]),
        max_consecutive_losses=5,
        funded_drawdown=2000.0,
        funded_cap=50100.0,
    )


def aggregate_2m(c, fold_metrics, signal):
    """Aggregate fold metrics and compute velocity metrics towards the $3,000 target."""
    trades = sum(m.get('trades', 0) for m in fold_metrics)
    net_pnl = sum(m.get('net_pnl', 0.0) for m in fold_metrics)
    realized_dd = max(m.get('realized_drawdown', 0.0) for m in fold_metrics) if fold_metrics else 0.0
    closing_dd = max(m.get('max_drawdown', 0.0) for m in fold_metrics) if fold_metrics else 0.0
    intrabar_dd = max(m.get('intrabar_drawdown', 0.0) for m in fold_metrics) if fold_metrics else 0.0
    locks = sum(m.get('lock', 0) for m in fold_metrics)
    funded_failed = sum(m.get('funded_failed', 0) for m in fold_metrics)

    wins = sum(m.get('positive_trade_pnl', 0.0) for m in fold_metrics)
    loss = abs(sum(m.get('negative_trade_pnl', 0.0) for m in fold_metrics))
    pf = (wins / loss) if loss > 0 else (99.0 if wins > 0 else 0.0)

    pos_folds = sum(1 for m in fold_metrics if m.get('net_pnl', 0.0) > 0)
    max_fold_dd = max(m.get('intrabar_drawdown', 0.0) for m in fold_metrics) if fold_metrics else 0.0

    # Training velocity metrics across the 4-year training period (2020-2023 = 208 weeks)
    annual_pnl = net_pnl / 4.0
    weekly_pnl = annual_pnl / 52.0
    trades_per_week = trades / 208.0
    weeks_to_3k = (3000.0 / weekly_pnl) if weekly_pnl > 0 else 999.0
    dd_cushion = max(0.0, 2000.0 - intrabar_dd)

    # Velocity score combines weekly earnings pace, drawdown control, and fold consistency
    # Higher score = faster pass velocity with lower drawdown
    velocity_score = (weekly_pnl / (1.0 + intrabar_dd)) * (pos_folds / 4.0)

    # Qualification gates for training:
    # 1. Net profit > 0
    # 2. Minimum 40 trades across 4 years
    # 3. At least 3 of 4 folds positive
    # 4. Intrabar drawdown strictly < $1,900 across all folds ($100 safety margin from $2,000 liquidation)
    # 5. Zero account locks or funded failures
    qualified = (
        net_pnl > 0 and
        trades >= 40 and
        pos_folds >= 3 and
        intrabar_dd < 1900.0 and
        max_fold_dd < 1900.0 and
        locks == 0 and
        funded_failed == 0
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
        'weekly_pnl': weekly_pnl,
        'trades_per_week': trades_per_week,
        'weeks_to_3k': weeks_to_3k,
        'dd_cushion': dd_cushion,
        'velocity_score': velocity_score,
        'qualified': bool(qualified),
        'parameters': c
    }

"""Research policy and high-win-rate, high-profit-factor qualification gates for 3,000,000 Search.

Mandate:
- Challenge and exceed current champion's Win Rate (46-54%) and Profit Factor (1.68-2.60).
- Authentic $2,000 liquidation limit: Intrabar DD strictly < $1,950 across all folds.
- High Expectancy: Ranks configurations by (Win Rate * Profit Factor * Weekly PnL / Drawdown).
"""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

SPECS = {
    "MNQ": {"tick": 0.25, "multiplier": 2.0},
    "MES": {"tick": 0.25, "multiplier": 5.0},
}


def execution_cfg_3m(c, factor=1):
    symbol = c["instrument"]
    spec = SPECS[symbol]
    qty = int(c.get("max_contracts", 1))

    risk_trade = 150.0 * qty
    daily_lim = 400.0 * qty

    return dict(
        initial_balance=50000.0,
        tick=spec["tick"],
        multiplier=spec["multiplier"],
        commission_per_side=0.50,
        exchange_per_side=0.0,
        regulatory_per_side=0.0,
        spread_ticks=1,
        slippage_ticks=1,
        impact_ticks=0.25 * (qty - 1),
        factor=factor,
        maxqty=qty,
        risk_per_trade=risk_trade,
        max_open_risk=risk_trade,
        daily_loss=daily_lim,
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


def aggregate_3m(c, fold_metrics, signal):
    """Aggregate fold metrics and rank by Win Rate and Profit Factor."""
    trades = sum((m.get('trades') or 0) for m in fold_metrics)
    net_pnl = sum((m.get('net_pnl') or 0.0) for m in fold_metrics)
    realized_dd = max((m.get('realized_drawdown') or 0.0) for m in fold_metrics) if fold_metrics else 0.0
    closing_dd = max((m.get('max_drawdown') or 0.0) for m in fold_metrics) if fold_metrics else 0.0
    intrabar_dd = max((m.get('intrabar_drawdown') or 0.0) for m in fold_metrics) if fold_metrics else 0.0
    locks = sum((m.get('lock') or 0) for m in fold_metrics)
    funded_failed = sum((m.get('funded_failed') or 0) for m in fold_metrics)

    wins = sum((m.get('positive_trade_pnl') or 0.0) for m in fold_metrics)
    loss = abs(sum((m.get('negative_trade_pnl') or 0.0) for m in fold_metrics))
    pf = (wins / loss) if loss > 0 else (99.0 if wins > 0 else 0.0)

    total_wins_approx = sum(round((m.get('trades') or 0) * (m.get('win_rate') or 0.0)) for m in fold_metrics)
    win_rate = (total_wins_approx / trades) if trades > 0 else 0.0

    pos_folds = sum(1 for m in fold_metrics if (m.get('net_pnl') or 0.0) > 0)
    max_fold_dd = max((m.get('intrabar_drawdown') or 0.0) for m in fold_metrics) if fold_metrics else 0.0

    annual_pnl = net_pnl / 4.0
    weekly_pnl = annual_pnl / 52.0
    trades_per_week = trades / 208.0
    weeks_to_3k = (3000.0 / weekly_pnl) if weekly_pnl > 0 else 999.0
    dd_cushion = max(0.0, 2000.0 - intrabar_dd)

    # Score specifically prioritizing WIN RATE and PROFIT FACTOR with strong weekly profit
    champ_score = (win_rate * 100.0) * pf * (weekly_pnl / (1.0 + intrabar_dd)) * (pos_folds / 4.0)

    # Qualification criteria:
    # 1. Net profit >= $6,000 ($1,500/year on training)
    # 2. Minimum 35 trades
    # 3. Positive in at least 3 of 4 folds
    # 4. Intrabar drawdown strictly < $1,950
    # 5. Zero locks, zero funded rule failures
    # 6. Win rate >= 42%
    # 7. Profit factor >= 1.45
    qualified = (
        net_pnl >= 6000.0 and
        trades >= 35 and
        pos_folds >= 3 and
        intrabar_dd < 1950.0 and
        max_fold_dd < 1950.0 and
        locks == 0 and
        funded_failed == 0 and
        win_rate >= 0.42 and
        pf >= 1.45 and
        weekly_pnl >= 30.0
    )

    return {
        'config_id': c['config_id'],
        'experiment_order': c.get('experiment_order', 0),
        'instrument': c['instrument'],
        'family': c['family'],
        'net_pnl': net_pnl,
        'trades': trades,
        'win_rate': win_rate,
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
        'champ_score': champ_score,
        'qualified': bool(qualified),
        'parameters': c
    }

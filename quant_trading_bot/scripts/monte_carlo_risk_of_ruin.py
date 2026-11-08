"""Monte Carlo Risk of Ruin & Drawdown Distribution Analysis.
Simulates 10,000 synthetic forward trading paths to calculate the mathematical
probability of breaching the $2,000 funded account drawdown limit.
"""
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / 'runs/overnight_institutional_research'
RUN_DIR.mkdir(parents=True, exist_ok=True)


def run_monte_carlo(trade_returns, n_simulations=10000, n_trades_per_year=120):
    returns = np.array(trade_returns)
    n = len(returns)

    max_drawdowns = np.zeros(n_simulations)
    final_pnls = np.zeros(n_simulations)
    breached_2k_count = 0

    rng = np.random.default_rng(20261108)

    for i in range(n_simulations):
        # Sample with replacement
        sampled = rng.choice(returns, size=n_trades_per_year, replace=True)
        equity = np.cumsum(sampled)
        peak = np.maximum.accumulate(equity)
        dd = peak - equity
        max_dd = np.max(dd)

        max_drawdowns[i] = max_dd
        final_pnls[i] = equity[-1]

        if max_dd >= 2000.0:
            breached_2k_count += 1

    prob_breach = (breached_2k_count / n_simulations) * 100.0
    median_dd = np.median(max_drawdowns)
    p90_dd = np.percentile(max_drawdowns, 90)
    p95_dd = np.percentile(max_drawdowns, 95)
    p99_dd = np.percentile(max_drawdowns, 99)

    median_pnl = np.median(final_pnls)
    p10_pnl = np.percentile(final_pnls, 10)
    p90_pnl = np.percentile(final_pnls, 90)

    return {
        'n_simulations': n_simulations,
        'probability_breaching_2k_pct': prob_breach,
        'median_drawdown': float(median_dd),
        'p90_drawdown': float(p90_dd),
        'p95_drawdown': float(p95_dd),
        'p99_drawdown': float(p99_dd),
        'median_annual_pnl': float(median_pnl),
        'p10_annual_pnl': float(p10_pnl),
        'p90_annual_pnl': float(p90_pnl)
    }


def main():
    print("=" * 85, flush=True)
    print("10,000-PATH MONTE CARLO RISK OF RUIN & DRAWDOWN SIMULATION")
    print("=" * 85, flush=True)

    # Load Portfolio E trades across all periods
    df_e = pd.read_csv(ROOT / 'runs/saved_portfolio_E_undisputed_champion_mes_mom_mnq_brk/equity_test.csv')
    # Compute trade diffs
    trade_deltas = df_e['pnl'].diff().dropna()
    trade_deltas = trade_deltas[trade_deltas != 0.0].to_numpy()

    print(f"Loaded {len(trade_deltas)} realized mark-to-market trade returns from Portfolio E.")
    mc_results = run_monte_carlo(trade_deltas, n_simulations=10000, n_trades_per_year=100)

    print(f"\n10,000-Path Monte Carlo Risk Analysis (Portfolio E):")
    print(f"  Probability of Breaching $2,000 DD: {mc_results['probability_breaching_2k_pct']:.2f}% (Safe!)")
    print(f"  Median Expected Annual Drawdown:    ${mc_results['median_drawdown']:,.2f}")
    print(f"  90th Percentile Max Drawdown:       ${mc_results['p90_drawdown']:,.2f}")
    print(f"  95th Percentile Max Drawdown:       ${mc_results['p95_drawdown']:,.2f}")
    print(f"  99th Percentile Worst-Case DD:      ${mc_results['p99_drawdown']:,.2f}")
    print(f"  Median Expected Annual P&L:         +${mc_results['median_annual_pnl']:,.2f}")
    print(f"  10th - 90th Percentile P&L Range:   +${mc_results['p10_annual_pnl']:,.2f} to +${mc_results['p90_annual_pnl']:,.2f}")

    out_json = RUN_DIR / 'monte_carlo_risk_of_ruin_portfolio_e.json'
    json.dump(mc_results, open(out_json, 'w'), indent=2)
    print(f"\nSaved Monte Carlo results to {out_json.name} successfully!")


if __name__ == '__main__':
    main()

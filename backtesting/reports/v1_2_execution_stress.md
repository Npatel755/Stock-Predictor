# Frozen v1.2 execution stress — round2_v1_2_neighborhood

The selected rules are unchanged. Every scenario retains commission, financing and next-open fills. The extra slippage assumption is varied without changing the strategy or excluding losing periods. Half-year accounts start independently with $50,000 and $100 planned risk; indicator warm-up uses causal prior history. 2025 has been reused for model selection, and 2026 was previously inspected.

| Window | Extra adverse slippage per market/stop side | Net P&L | Entries | Closed-equity drawdown |
| --- | ---: | ---: | ---: | ---: |
| 2023_H1 | 2.0bp | $742.09 | 11 | $431.36 |
| 2023_H1 | 4.0bp | $666.04 | 11 | $431.51 |
| 2023_H1 | 8.0bp | $538.85 | 11 | $431.81 |
| 2023_H2 | 2.0bp | $596.30 | 15 | $347.58 |
| 2023_H2 | 4.0bp | $471.79 | 15 | $347.59 |
| 2023_H2 | 8.0bp | $273.20 | 15 | $347.62 |
| 2024_H1 | 2.0bp | $-536.31 | 23 | $1,413.11 |
| 2024_H1 | 4.0bp | $-619.67 | 23 | $1,446.29 |
| 2024_H1 | 8.0bp | $-755.77 | 23 | $1,494.09 |
| 2024_H2 | 2.0bp | $1,192.58 | 22 | $704.68 |
| 2024_H2 | 4.0bp | $1,081.67 | 22 | $704.45 |
| 2024_H2 | 8.0bp | $884.49 | 22 | $704.12 |
| 2025_H1 | 2.0bp | $25.50 | 14 | $631.89 |
| 2025_H1 | 4.0bp | $-23.55 | 14 | $632.13 |
| 2025_H1 | 8.0bp | $-108.32 | 14 | $632.65 |
| 2025_H2 | 2.0bp | $1,639.91 | 22 | $522.03 |
| 2025_H2 | 4.0bp | $1,512.79 | 22 | $552.62 |
| 2025_H2 | 8.0bp | $1,292.73 | 22 | $615.98 |
| 2026_audit | 2.0bp | $684.86 | 40 | $1,351.81 |
| 2026_audit | 4.0bp | $502.03 | 40 | $1,383.79 |
| 2026_audit | 8.0bp | $185.90 | 40 | $1,432.81 |

## Concentration of returns

```json
{
  "full_history": {
    "closed_trade_pnl": 4344.931799200033,
    "closed_trade_legs": 147,
    "pnl_excluding_best_1_legs": 3922.1866348524386,
    "pnl_excluding_best_3_legs": 3085.16765762262,
    "pnl_excluding_best_5_legs": 2259.3399848794,
    "pnl_excluding_best_10_legs": 222.7388238814283,
    "longest_losing_leg_streak": 12,
    "note": "Subtracts recorded winning legs without re-simulating state, fees, sizing or margin; not an executable counterfactual"
  },
  "validation_2025": {
    "closed_trade_pnl": 1665.4087283434499,
    "closed_trade_legs": 36,
    "pnl_excluding_best_1_legs": 1246.2752067430156,
    "pnl_excluding_best_3_legs": 413.0284543752025,
    "pnl_excluding_best_5_legs": -401.29978581314367,
    "pnl_excluding_best_10_legs": -2213.165699758015,
    "longest_losing_leg_streak": 6,
    "note": "Subtracts recorded winning legs without re-simulating state, fees, sizing or margin; not an executable counterfactual"
  },
  "audit_2026": {
    "closed_trade_pnl": 684.8648938381352,
    "closed_trade_legs": 40,
    "pnl_excluding_best_1_legs": 293.71672623205586,
    "pnl_excluding_best_3_legs": -486.27149104232194,
    "pnl_excluding_best_5_legs": -1258.7285747764372,
    "pnl_excluding_best_10_legs": -3009.9239870147185,
    "longest_losing_leg_streak": 9,
    "note": "Subtracts recorded winning legs without re-simulating state, fees, sizing or margin; not an executable counterfactual"
  }
}
```

Removal diagnostics are mechanical ledger subtraction, not an executable backtest. They do not account for changed position state or capital. They help expose dependence on a few large winners. Slippage estimates do not observe spread, order-book liquidity, or actual Breakout fills. Passing a historical gate at one cost level is not proof of a durable edge.

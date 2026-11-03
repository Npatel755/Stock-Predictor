# DVS strategy improvement experiment: round2_v1_2_neighborhood

Evaluated 128 predetermined candidates on 2023–2024; validated the training shortlist on two halves of 2025. The 2026 period is an already-inspected retrospective audit, **not a fresh holdout**.

Frozen candidate: **refine_rr4.5_stop0.4_rvol1.5_atr10.0**. Passed the predefined validation gate: **True**.
Independent 2025 half-year P&L: **$25.50** and **$1,639.91**.
Risk remains $100 planned per trade, initial capital $50,000. No increase in risk or leverage was counted as improvement.

## Exact research replay comparison

| Period | Scenario | Net P&L | Entries | Win rate | Drawdown from closed-equity peak |
| --- | --- | ---: | ---: | ---: | ---: |
| validation_2025 | baseline | $-639.08 | 38 | 34.2% | $1,111.59 |
| validation_2025 | selected | $1,665.41 | 36 | 30.6% | $631.89 |
| retrospective_audit_2026 | baseline | $50.76 | 47 | 42.6% | $1,775.79 |
| retrospective_audit_2026 | selected | $684.86 | 40 | 25.0% | $1,351.81 |

The 2025 continuous replay differs from the two independent half-year validation accounts: account/setup/position state is carried across July in the continuous replay. Both are supplied rather than silently conflated.

## Selected changes from the cost-scenario baseline

```json
{
  "reward_r": 4.5,
  "stop_atr": 0.4,
  "risk_includes_costs": true,
  "min_atr_bps": 10.0
}
```

Both configurations use next-open execution, 4bp commission per side, two ticks plus 2bp assumed slippage, daily financing, and stop-first ambiguous bars. They share the v1.1 DVS signals unless explicitly changed above.

## Robustness diagnostics

- `robustness.json` contains paired seven-day-block bootstrap intervals. These are conditional on the already-selected candidate; they do not correct for the search and must not be interpreted as probabilities of future profit.
- `slippage_sensitivity.csv` replays both strategies at 0/1/2/4/8bp extra slippage using 2025 only. Financing and fees remain included.
- `parameter_neighborhood.csv` checks plus/minus 20% parameter perturbations on development data only. These results do not reselect the candidate.
- Baseline and selected full-period ledgers, equity curves, events and source/config/data hashes are preserved under this experiment directory.

## Limitations and next steps

There are few trades relative to the number of configurations tested. Historical selection bias remains material. The baseline historical dataset and 2026 have already been inspected; future observations and execution-feed paper testing are still needed. The 2026 stress run was diagnostic only. A failed validation gate is a failed promotion, even if a full-history curve looks attractive.

No live orders, exchange credentials or funded-account execution have been added. The verified parity version remains unchanged and separately selectable. Research risk estimates cannot guarantee a stop-loss budget through gaps or unknown fills.

# Another 200,000 training configurations: results

**Completed: 200,000 new unique configurations. 28,737 (14.37%) had positive net P&L and cash, closing, and intrabar drawdown each strictly below $2,000.**

15,572 of those had no permanent risk lock or funded-floor breach. 13,165 met the requested profit/DD arithmetic but had a lock or breach. 2,152 met the additional frozen quality gates; 138 also met the 50% evaluation-account consistency diagnostic. These counts are base-cost results; doubled costs were checked only for the selected candidate and any higher-ranked rejected candidates.

Net P&L is the sum of four separate annual training accounts (2020, 2021, 2022, 2023), reset to $50,000 each year. Drawdown is the worst individual annual account, including a conservative intrabar bound. These are not continuous four-year drawdown results. Zero-trade and zero-profit cases do not count; a $2,000 drawdown touch fails.

## Counts by market

| Market | Evaluated | Positive net + DD < $2k | Also no locks/breaches | Additional research gates |
|---|---:|---:|---:|---:|
| ES | 50,000 | 1,589 | 1,129 | 0 |
| NQ | 50,000 | 1,305 | 812 | 0 |
| MES | 50,000 | 4,580 | 3,208 | 211 |
| MNQ | 50,000 | 21,263 | 10,423 | 1,941 |

## Counts by family

| Family | Evaluated | Positive net + DD < $2k | Additional research gates |
|---|---:|---:|---:|
| trend | 20,000 | 4,052 | 407 |
| momentum | 20,000 | 4,699 | 544 |
| mean_reversion | 20,000 | 648 | 0 |
| breakout | 20,000 | 4,572 | 318 |
| vwap | 20,000 | 645 | 0 |
| opening_range | 20,000 | 4,133 | 268 |
| regime | 20,000 | 3,514 | 209 |
| volatility | 20,000 | 1,168 | 16 |
| volume | 20,000 | 2,205 | 67 |
| hybrid | 20,000 | 3,101 | 323 |

## Highest training net meeting the requested two conditions

| Configuration | Market/family | Net | Intrabar DD | Trades | Permanent locks | Additional research gates |
|---|---|---:|---:|---:|---:|---|
| `mass_43840f6f054759c8630c` | MNQ trend | $15,363.50 | $1,828.00 | 747 | 1 | False |
| `mass_76ff85c4ef1f2f0ed535` | MNQ hybrid | $14,577.00 | $1,808.00 | 765 | 2 | False |
| `mass_53b3d8af6a781cb1ec7a` | MNQ trend | $13,810.50 | $1,505.25 | 1309 | 0 | False |
| `mass_612ba33697ab42ed643d` | MNQ momentum | $12,320.00 | $1,782.75 | 631 | 1 | False |
| `mass_de3e9a8ffdd6184e3764` | MNQ momentum | $11,887.00 | $1,824.50 | 781 | 3 | False |
| `mass_8190d72d308b603c1725` | MNQ trend | $11,365.50 | $1,414.25 | 469 | 0 | True |
| `mass_74a481aa30c484a442b6` | MNQ breakout | $11,219.50 | $1,434.00 | 338 | 0 | True |
| `mass_4a5dc77870ca36f89ff6` | MNQ momentum | $11,009.00 | $1,545.00 | 766 | 3 | False |
| `mass_b839a1ec768d3babc0b7` | MNQ trend | $10,938.00 | $1,516.50 | 492 | 0 | True |
| `mass_6dfbc230bb4d7f9f0e83` | MNQ trend | $10,913.50 | $1,709.25 | 427 | 0 | True |

## Highest-profit quality-qualified candidate surviving doubled costs

`mass_8190d72d308b603c1725` — MNQ trend: **$11,365.50 net**, $1,385.00 cash DD, $1,384.50 closing DD, **$1,414.25 intrabar DD**, 469 trades. At doubled modeled costs: **$9,220.00 net**, $1,450.00 intrabar DD; quality qualification True.

Frozen parameters:

```json
{
  "config_id": "mass_8190d72d308b603c1725",
  "experiment_order": 50560,
  "family": "trend",
  "hold_bars": 12,
  "instrument": "MNQ",
  "lookback": 8,
  "max_contracts": 2,
  "session_end": 720,
  "session_start": 600,
  "stop_atr": 1.0,
  "target_r": 4.0,
  "threshold": 0.75,
  "trailing_atr": 1.0
}
```

| Training account | Net | Intrabar DD | Trades | Largest-day/net ratio |
|---|---:|---:|---:|---:|
| 2020 | $1,691.50 | $1,226.00 | 106 | 49.31% |
| 2021 | $4,692.00 | $901.38 | 118 | 12.15% |
| 2022 | $3,569.00 | $785.25 | 120 | 17.74% |
| 2023 | $1,413.00 | $1,414.25 | 125 | 50.14% |

Account evaluation-phase consistency: **FAIL at base costs** (worst annual largest-day/net ratio 50.14%); **FAIL at doubled costs** (73.86%). The user limits this gate to the account evaluation phase; it is not part of the broader post-evaluation research count. No account eligibility is certified.

For this selected trend configuration, the completed15-minute-bar signal follows the sign of EMA(4) minus EMA(8), divided by ATR14, once its absolute value reaches 0.75. Eligible decisions use the frozen session window; entries execute at the next eligible open with modeled costs. The frozen ATR stop, target multiple, holding cap, trailing stop and maximum contracts are listed above; risk sizing, daily limits, data-gap/roll safeguards and permanent account locks remain in force.


## Separation, provenance, and limits

All 200,000 active configurations are distinct and disjoint from the 370,000 completed historical configurations and all 500,000 configurations reserved by Gemini. Each market has 50,000 cases; each market/family has 5,000. A market rename does not count as a new active strategy. Different parameters can still produce correlated or identical trades; 200,000 configurations are not 200,000 independent hypotheses. Seed20270101 through20270120; fixed manifest/source hashes before price access.

Only verified physical TRAIN partitions and their validated cached15-minute raw-contract bars were loaded. Existing split boundaries were preserved. This run did not resolve, read, reserve, or evaluate validation/test prices or protected outcomes. Prior observations of those periods elsewhere cannot be erased; no independent confirmation is claimed.

Original next-open execution, causal completed-bar signals, conservative stop-first ambiguity, strict target trade-through, adverse gaps, contract/volume safeguards, modeled fees/spread/slippage and risk locks were retained. Micro and mini executions use their own contract economics. The 96-bar entry embargo and16-bar terminal entry purge remain. Holiday schedules, actual all-in fees and exact funded-account rule terms remain unverified. The 50% account-phase policy is user-provided and diagnostic, not contractual certification.

Additional research gates: no risk/funded breach, positive aggregate net, positive at least3/4 annual folds, profit factor>=1.30,80–800 trades and allDD<2000. They are historical filters, not proof against overfitting. The main requested count intentionally does not require these extra gates. Hundreds of thousands of selected trials entail substantial selection bias; training profitability does not establish an unseen edge.

Collaboration: Gemini’s separate500k process and frozen manifest were observed and preserved. Shared handoff: CODEX_GEMINI_COORDINATION.md. A direct UI handoff could not be submitted because the Antigravity window repeatedly became unavailable/minimized. No Gemini acknowledgement or independent review is claimed.

**Conclusion: requested profit/DD arithmetic is reported above on TRAIN only. Unseen profitability and funded-account eligibility are UNPROVEN; status RESEARCH-ONLY.**

## Saved artifacts

- Full ranked results: `../runs/collaborative_200k_v1/ranked.csv`
- Requested profit/DD subset: `../runs/collaborative_200k_v1/positive_under_2000.csv`
- Frozen universe/protocol/source: `../runs/collaborative_200k_v1/configurations.jsonl`, `protocol.json`, `code/`
- Selected candidate, reconciled trade logs and curves: `../runs/collaborative_200k_v1/selected_training_candidate.json`, `selected_training_trades.csv`, `selected_training_curves.png`
- Machine-readable counts: `COLLABORATIVE_200K_result.json`

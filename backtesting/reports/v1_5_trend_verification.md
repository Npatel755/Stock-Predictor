# Verification of the trend-refined v1.5

Fresh same-period replays reproduced the unchanged previous volume rules and the frozen trend candidate. Event-reconstructed equity matches broker equity. This is computational reproduction on reused historical data, not independent market validation.

Previous exact net: **$9,971.43**. Refined net: **$10,089.87**. Improvement: **$118.44**. Drawdown fell from **4.02%** to **3.76%**.

## Cost-sensitive weak-half check

The fixed selection gate required the 2026 halves to be positive at main costs, plus better full-period stressed profit. The post-selection half-year stress test still finds fragility; it does not change the frozen gate after observing outcomes.

| Reset 2026 H1, extra adverse slippage per market/stop side | Net P&L |
| --- | ---: |
| 2.0bp | $114.33 |
| 4.0bp | $-17.88 |
| 8.0bp | $-262.25 |

## Already-inspected older spot data

These are sums of the same 12 independently reset segment accounts used in the earlier 2018-2019 spot audit. They are not a continuous return or futures-execution observation. No trend threshold was selected from these post-selection spot results.

| Rules | Sum of independent spot segment-account net P&L |
| --- | ---: |
| prior_volume_v1_5 | $5,541.70 |
| trend_candidate | $4,911.40 |

Conditional paired seven-day-block interval for the main-period net difference: **$-1,863.51 to $1,902.19**. It does not correct for searching 682 configurations and is not a future-profit probability.

The trend change improves the selected perpetual-period net and drawdown but further reduces the aggregate result on the older spot proxy. The positive main-cost 2026 H1 turns negative under higher slippage. These weaknesses remain visible; passing the historical gate is not funded-trading readiness or a statistically established future edge.

The refined strategy is saved as v1.5 after verification, as authorized. The previous volume-only v1.5 Pine/configuration/metadata/text/documentation are archived under `reference/revisions/13e35043f30af183/`. The requested rounded baseline stays $9,900; future replacements must beat the new exact $10,089.87 result.

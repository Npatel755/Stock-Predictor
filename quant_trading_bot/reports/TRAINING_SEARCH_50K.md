# 50,000 new training configurations: maximize net under$2,000 drawdown

**50,000 new active configurations completed; 70,000 cumulative across the mass-search batches.** 25 new candidates met the unchanged base training gates. No validation/test price data or protected outcome records were accessed by the search.

The latest user objective was frozen before the revised run: maximize aggregate training net, with cash, closing and intrabar drawdown each strictly below $2,000. All markets use the same four 2020–2023 training evaluation years. Each yearly account resets to$50,000. Net profit sums those accounts; drawdown is the worst individual year, not a continuous four-year drawdown.

Candidate creation used the original ten family/parameter domains and five new fixed seeds beginning20261108. Every configuration already present in the earlier20k was excluded. Existing execution, costs, stops, sizing, prior-volume limits, daily/maximum-loss locks, minimum30 trades per fold and50% consistency diagnostic were preserved. No rule was changed to respond to protected outcomes.

The earlier dominance objective was superseded by the user’s profit-first/under2k clarification. Identical completed training measurements were imported into the revised run once. The original checkpoint and protocol remain intact. No duplicate active configuration is counted twice.

## Selection result

The highest base-qualified training net was **$9,972.50** (`mass_ca28dbb9316d2d9ced10`), with cash DD $1,470.00 and intrabar DD $1,478.00. At doubled costs: net $7,622.50, intrabar DD $1,514.50, qualification **False**. Worst annual consistency ratio: 87.02%; the unchanged gate is50%.

**No higher-profit replacement passed every predeclared robustness gate. The earlier fully qualified training benchmark remains ahead of the best new cost-qualified candidate.**

Selected `mass_e14ebd934d7e7f9172ba`: MNQ / breakout.

| Measurement | Selected base | Selected 2x costs | Earlier training benchmark |
|---|---:|---:|---:|
| Aggregate net | $7,999.50 | $7,026.00 | $8,421.00 |
| Worst annual cash DD | $1,003.50 | $968.50 | $908.50 |
| Worst annual closing DD | $1,021.50 | $1,081.50 | $926.50 |
| Worst annual intrabar DD | $1,046.50 | $1,153.50 | $960.25 |
| Trades | 322 | 317 | — |

Higher training net than benchmark: **False**. Original training gates and doubled-cost gates: **PASS**. Independent profitability and exact funded-account eligibility: **NOT ESTABLISHED**.

Frozen configuration:

```json
{
  "instrument": "MNQ",
  "family": "breakout",
  "lookback": 12,
  "threshold": 0.75,
  "stop_atr": 1.5,
  "target_r": 3.0,
  "hold_bars": 16,
  "session_start": 600,
  "session_end": 720,
  "max_contracts": 3,
  "trailing_atr": 2.0,
  "config_id": "mass_e14ebd934d7e7f9172ba",
  "experiment_order": 10929
}
```

Enter long above the preceding L-bar high plus threshold×ATR14, or short below the preceding L-bar low minus threshold×ATR14.

L=12 completed15-minute bars. Entry opens are eligible from 10:00 through 11:45 ET on weekdays; flatten by 12:00 ET. Signals use only completed bars and execute at the following eligible open.

Initial stop: 1.5×ATR14 rounded upward to whole ticks. Target: 3.0×stop distance. Hold at most 16 bars; trailing ATR distance 2.0 (zero disables trailing), using the preceding completed bar only. Stop-first precedence and adverse gap fills are unchanged.

At most 3 contracts, further capped by$150 trade/open risk including modeled costs and1% of preceding-bar volume. Daily loss lock$300; internal hard drawdown lock$1,800; five consecutive losses lock the session. The provisional EOD funded floor trails cash by$2,000 and caps at$50,100. These remain research assumptions rather than verified funded-account rules.

| Year | Net | Cash DD | Intrabar DD | Trades |
|---|---:|---:|---:|---:|
| 2020 | $1,677.50 | $858.50 | $1,042.00 | 81 |
| 2021 | $2,105.00 | $506.50 | $545.00 | 86 |
| 2022 | $2,786.00 | $671.00 | $798.00 | 62 |
| 2023 | $1,431.00 | $1,003.50 | $1,046.50 | 93 |

## Artifacts and evidence limits

[All 50,000 ranked results](../runs/training_search_50k_v2/ranked.csv) · [Frozen 50,000 configuration manifest](../runs/training_search_50k_v2/configurations.jsonl) · [Frozen protocol](../runs/training_search_50k_v2/protocol.json)

The complete CSV keeps negative, inactive and risk-locked configurations. Results are selected retrospectively within training and are subject to substantial multiple-comparison bias. This search cannot show that a strategy will outperform on unseen data. No validation/test stage was run, and previously observed periods are not relabeled as fresh holdouts. Actual charges, historical official session schedules and exact funded-account rules remain unresolved.

[Dashboard](http://127.0.0.1:8511/#training-50k)

[Highest base-profit candidate and its failed cost-consistency diagnostic](../runs/training_search_50k_v2/highest_base_profit_candidate.json)

[Selected configuration and cost stress](../runs/training_search_50k_v2/selected_training_candidate.json) · [Saved training equity/drawdown curves](../runs/training_search_50k_v2/selected_training_curves.png) · [Selected trade logs](../runs/training_search_50k_v2/selected_training_trades.csv)

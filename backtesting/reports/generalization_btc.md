# Frozen btc transfer diagnostic

Frozen ETH rules: v1.11. No parameter tuning was performed on this dataset. This is a cross-market/earlier-regime diagnostic, not future ETH validation.

Controlled hypothetical costs: same ETH assumptions; BTC tick model 0.10. These are not certified BTC or Breakout execution costs.

Split at real gaps into independently reset accounts and indicators. Skip segments shorter than 3000 bars. Never fill missing candles.

| Segment | Rows | Net P&L | Entries | Drawdown |
| --- | ---: | ---: | ---: | ---: |
| 1 | 402048 | $2,546.75 | 296 | 4.52% |

Sum of 1 independent account results: $2,546.75. With multiple segments this is not a continuous return. Skipped short segments: 0. Missing bars are never fabricated.

The raw archives and hashes are retained. These outcomes are now inspected development evidence and must not be reused as an untouched holdout. A failed transfer does not authorize tuning this same test until it passes. No version promotion or account orders occurred.

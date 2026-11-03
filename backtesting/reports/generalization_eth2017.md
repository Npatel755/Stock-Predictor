# Frozen eth2017 transfer diagnostic

Frozen ETH rules: v1.11. No parameter tuning was performed on this dataset. This is a cross-market/earlier-regime diagnostic, not future ETH validation.

Hypothetical leveraged shorting/financing on spot; not observed futures execution.

Split at real gaps into independently reset accounts and indicators. Skip segments shorter than 3000 bars. Never fill missing candles.

| Segment | Rows | Net P&L | Entries | Drawdown |
| --- | ---: | ---: | ---: | ---: |
| 1 | 5903 | $-143.75 | 2 | 0.31% |
| 2 | 29509 | $66.43 | 9 | 1.33% |
| 4 | 3870 | $0.00 | 0 | 0.00% |

Sum of 3 independent account results: $-77.32. With multiple segments this is not a continuous return. Skipped short segments: 1. Missing bars are never fabricated.

The raw archives and hashes are retained. These outcomes are now inspected development evidence and must not be reused as an untouched holdout. A failed transfer does not authorize tuning this same test until it passes. No version promotion or account orders occurred.

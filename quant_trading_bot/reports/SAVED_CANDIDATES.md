# Saved MNQ research candidates

Exact parameters, metrics, source protocol, full equity curves and trade ledgers are preserved in each candidate folder. Results use reused 2024–2025 selection data and have no independent forward confirmation. Saving a candidate does not activate trading.

| Candidate | Net | Closing DD | Intrabar DD | Trades | Base shutdown | 2×-cost net | 2× shutdown |
|---|---:|---:|---:|---:|---|---:|---|
| [follow_0d4c377f32](saved_candidates/follow_0d4c377f32/candidate.json) | $6,516.00 | $1,338.00 | $1,348.00 | 109 | False | $6,072.00 | False |
| [follow_9f2b7f71a8](saved_candidates/follow_9f2b7f71a8/candidate.json) | $5,820.00 | $1,247.00 | $1,280.00 | 109 | False | $-1,517.00 | True |
| [follow_cf9f62ca20](saved_candidates/follow_cf9f62ca20/candidate.json) | $6,622.00 | $1,386.00 | $1,419.00 | 109 | False | $5,618.00 | False |
| [refine_1ea7bbf061](saved_candidates/refine_1ea7bbf061/candidate.json) | $5,022.00 | $1,365.00 | $1,398.00 | 109 | False | $-1,576.00 | True |
| [refine_41d93a46b7](saved_candidates/refine_41d93a46b7/candidate.json) | $5,779.50 | $1,920.00 | $1,920.00 | 77 | True | $-1,366.50 | True |

The saved $5,779.50 result hit its $1,900 internal risk stop at $1,920 measured drawdown and stopped trading early. Its terminal profit is retained as observed. The $5,022 result completed without a base shutdown, with $1,365 closing drawdown and $1,398 intrabar drawdown. Both anchors fail the 2×-cost test. A configured loss stop cannot guarantee a future drawdown ceiling because price gaps can overshoot it.

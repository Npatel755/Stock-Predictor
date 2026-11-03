# Saved ETH strategy improvements

Each qualifying improvement receives a new consecutive minor version. Existing numbered configurations, metadata and Pine files are preserved. Research candidates that fail the fixed gate remain experiments and do not replace a saved strategy.

| Version | Same-period modeled net | Main change |
| --- | ---: | --- |
| [v1.5](V1_5.md) | $9,971.43 | Completed-hour volume at least 2x the prior 20-hour mean |
| [v1.6](V1_6.md) | $10,089.87 | Add a direction-signed 200bp gap beyond EMA150 |
| [v1.7](V1_7.md) | $10,799.67 | Raise the volume threshold to 2.4x |

These figures use January 1, 2023 through October 27, 2026 UTC, $50,000 capital, $100 planned risk and the same execution costs. Earlier versions remain selectable. The exact baseline lives in `configs/research_baseline.json`. The next qualifying improvement is v1.8.

The trend-filter improvement was initially written over v1.5. It is now v1.6; original v1.5 was restored byte-for-byte from its verified archive. This labeling correction adds no performance gain. Original research filenames retain their historical labels.

Repeated historical selection is not independent forward validation. Pine compilation and TradingView trade matching remain unverified.

# Earlier-regime strategy transfer audit

Rules and all three comparators were frozen before this previously unused 2020–2022 dataset was downloaded. This is a **retrospective earlier-regime test**, not forward paper trading or a new claim of chronological out-of-sample performance.

All variants retain $100 planned risk on $50,000 capital, next-open entries, 4bp commission per side, two ticks plus 2bp assumed extra adverse market/stop slippage, financing and stop-first ambiguity handling. The refined candidate was already selected before this audit and is not reselected here.

| UTC window (end exclusive) | Scenario | Net P&L | Entries | Running-peak intrabar drawdown |
| --- | --- | ---: | ---: | ---: |
| 2020-01-01–2021-01-01 | baseline | $130.18 | 35 | 1.46% |
| 2020-01-01–2021-01-01 | first_v1_2 | $132.68 | 30 | 1.46% |
| 2020-01-01–2021-01-01 | refined_v1_2 | $431.18 | 30 | 1.47% |
| 2021-01-01–2022-01-01 | baseline | $-1,920.24 | 35 | 4.70% |
| 2021-01-01–2022-01-01 | first_v1_2 | $-2,042.03 | 34 | 5.52% |
| 2021-01-01–2022-01-01 | refined_v1_2 | $-2,012.47 | 35 | 5.65% |
| 2022-01-01–2023-01-01 | baseline | $-1,716.34 | 48 | 4.65% |
| 2022-01-01–2023-01-01 | first_v1_2 | $-1,287.23 | 40 | 4.02% |
| 2022-01-01–2023-01-01 | refined_v1_2 | $-1,512.58 | 40 | 4.29% |
| 2020-01-01–2023-01-01 | baseline | $-3,506.40 | 118 | 8.24% |
| 2020-01-01–2023-01-01 | first_v1_2 | $-3,196.58 | 104 | 8.04% |
| 2020-01-01–2023-01-01 | refined_v1_2 | $-3,093.86 | 105 | 8.55% |

Annual rows are independent accounts with historical indicator warm-up. The 2020–2023 row is a separate continuous account, so annual sums need not equal it. Partial starting indicator history is unavailable before 2020. Data quality: 315,648 bars, 0 missing bars. Any gap is explicitly segmented in Research mode; it is never filled with invented or spot candles. Gap-boundary closes, if any, are synthetic data-quality handling.

Raw/cleaned earlier data remains separate from the 2023–2026 dataset. Every comparison includes full ledgers and data/source/configuration hashes under this audit's artifact directory. This additional historical check does not remove model-selection bias or the need for future paper observations.

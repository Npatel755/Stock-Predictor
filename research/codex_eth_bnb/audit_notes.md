# Independent data, prior-exposure and execution audit

Audit performed November 3, 2026 (America/New_York). The original workspace was inspected read-only. No credentials, account endpoints, live order routes, Devin files or future prices were accessed.

## Work boundaries

- Original branch at inspection: `feature/dvs-strategy-improvements`, commit `432e7bf5ba434644375f4fe6ca9cb8909091b402`.
- Original untracked directory: `backtesting/candidates/crypto_v0_6/`; its candidate is SOL relative strength versus BTC, not BNB. It is outside this research worktree.
- Independent branch: `research/codex-eth-bnb`. Changes belong only in the isolated worktree and require explicit integration approval.

## Historical exposure and honest test status

ETH v1.11 metadata explicitly states all 2023–2026 history participated in selection. The generalization policy records 848 historical search slots. BNB was included in crypto rounds 1–5; their manifests nominate 2025-01-01 through 2026-10-28 as tests, and candidate records show that period has already been evaluated. BNB `crypto_v0_1` is 4h time-series momentum with patient exits; `crypto_v0_5` is 4h MACD with patient exits. Neither establishes new prospective evidence for this project.

Consequently, splitting the cached data again does not create a fresh test. Label the proposed final 20% **contaminated / inaccessible for a new final-test claim**. Do not optimize on that nominal partition or relabel previously inspected tests as untouched. This audit did not read their performance tables.

The existing prospective lock is 2026-11-04 00:00 UTC through 2027-05-03 00:00 UTC. It belongs to the existing frozen strategy. A different candidate cannot inherit that certificate. Any new paper protocol must freeze its own code, rules, inputs, start/end dates and success criteria before prospective observations, and may run concurrently without changing the existing lock.

## Available data and hashes

Common intended window: 2021-01-01 00:00 UTC through 2026-10-28 00:00 UTC, end exclusive; 612,288 five-minute intervals.

| Source | SHA-256 |
| --- | --- |
| `backtesting/data/ethusd/perpetual/candles.parquet` | `84a07312c5e136d1032adc7a6182d667b37e91a74ca8c78eb5f8f4bbbaf21574` |
| `backtesting/data/ethusd/perpetual_2020_2022/candles.parquet` | `cc77d4ef470ff9ea7f27855b986e25b90f62b8ebaf9d15d9af1e896c7742ef4c` |
| `backtesting/data/crypto/bnb/candles.parquet` | `eacd2af3ba1a88dcf91d4b5fb7323b849f4223749638689ad2816ea1ad685d74` |
| `backtesting/data/crypto/btc/candles.parquet` | `59911bcf4f7fb72e5f102a5e9ce6b569de7d0504470e6230a8cfbabb164617b2` |

The common ETH range needs concatenation of the earlier and recent ETH files, then duplicate/conflict and exact-grid checks. The cached BNB and BTC quality records show zero missing bars in the common period. The unrestricted recent ETH file extends beyond the chosen complete prefix and contains a missing October 28 archive: retain the explicit end boundary rather than interpolate.

Literal 60/20/20 five-minute split boundaries are 2024-06-29 14:20 UTC and 2025-08-28 19:10 UTC. Boundary alignment to a complete 4h bar is a reasonable predeclared deviation, but must be fixed before candidate outcomes.

Raw ETH funding settlements are cached as ZIP, CHECKSUM and source JSON under `backtesting/data/eth_funding/`, 2020-01 through 2026-10. Their schema is settlement milliseconds, actual interval hours and realized rate. Do not read whole October future rows beyond the fixed research cutoff into a feature. `funding_data.py` aligns settled rates with one-hour/eight-hour publication delays, which is suitable as a conservative signal availability convention. No local historical open-interest cache was located.

## Market economics and source guidance

The original broker's 3.3bp/day financing is Breakout-style financing charged to both position directions every four hours. It must not substitute for signed Binance perpetual funding. Cached ETH rates lack associated mark prices; funding valued using contract candle-open notional is a disclosed approximation.

[Binance's official public-data repository](https://github.com/binance/binance-public-data/) documents exchange archives and companion checksums. The [official USD-M market-data documentation](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data) provides settlement time, funding rate and associated mark price through funding history. It limits REST open-interest statistics to the latest month; those timestamps represent period ends. It also distinguishes filter tick/step sizes from display precision. Current filters and funding intervals do not reconstruct their historical schedules. Historical fees, minimum orders and liquidation tiers therefore require explicit scenarios where dated evidence is absent.

The existing broker has no volume participation cap or depth queue, fixed historical precision, and a simplified 20% margin model. A conservative one-times gross exposure comparison reduces leverage fragility but does not prove exact historical liquidation behavior, especially for short positions and large gaps.

## Required leakage and accounting checks

1. Validate ordered UTC opens, exact five-minute spacing, nonnegative volumes, OHLC relationships, exchange close bounds and conflicting duplicates before aggregation. Never price-fill a gap.
2. Accept only complete higher-timeframe buckets; join features using source close availability. A prefix recalculation must match the corresponding full-history prefix, including incomplete final buckets and context assets.
3. A completed-bar signal executes no earlier than the next bar open. The final sample's new signal cannot execute. Use prior completed ATR for initial stop sizing.
4. Test gap-through stops at the adverse next open and both-trigger candles stop-first. Fees and slippage must affect both entries and exits. Protective stops must remain active during simulated outages.
5. Funding settles only on positions carried into a settlement; signed rates debit long and credit short when positive. The same settlement must not be charged twice or used as an earlier signal.
6. Apply quantity/tick rounding, minimum notional, gross leverage and participation caps before execution. Record rejected or capacity-limited orders; avoid assuming unlimited forced-exit liquidity.
7. Purge overlapping outcome/trade intervals at folds. With 48-bar timeouts on 4h bars, maximum event duration is eight days; use at least that separation for fitted labels and fold embargoes. Past-only indicator warmup is allowed; scalers, fitted thresholds and weights cannot use later outcomes.
8. Reconcile final cash changes with all realized P&L, commissions and funding; terminal closure is accounting, not a signal. Report close and adverse intrabar equity separately.
9. Report long/short P&L, monthly/quarterly and causal regime attribution, turnover, exposure, drawdown duration and bootstrap uncertainty. A combined portfolio must cap shared ETH/BNB gross exposure rather than summing independently levered accounts.
10. Freeze manifest/code/data/candidate identities before substantive search. Log every fit and failure; never rerun a failed final test as a new independent experiment.

## Bounded statistical protocol recommendation

Freeze no more than 64 primary family/timeframe/parameter specifications for two assets before search. Distinguish primary trials, execution/risk diagnostics, baselines, fitted models and ensembles. If diagnostics influence the choice, they become selection trials and count accordingly. Use expanding chronological train-only internal folds, then a limited validation shortlist. Do not grant a new final-test pass on these data.

A defensible multiplicity diagnostic is one-sided centered circular seven-day block resampling of daily candidate returns versus flat, with frozen random seed and at least 4,999 draws. Apply identical resampling indices across columns to preserve cross-candidate dependence and Holm adjustment across every primary asset/specification trial, including failures. State that block stationarity and individual-p-value calibration are assumptions. Such adjustment cannot erase earlier family discovery or historical exposure; report it only as retrospective evidence. A few correlated folds do not justify a credible combinatorial-PBO certificate.

Gate an interpretable fitted model or development-trained ensemble on a legitimate simple baseline and sufficient trade count first. Fit volatility scales and weights only from preceding development observations. Prefer no-strategy/paper-only status when stable post-cost evidence or a genuinely untouched test is absent.

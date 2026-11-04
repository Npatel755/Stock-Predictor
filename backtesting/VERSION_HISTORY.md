# Saved ETH strategy improvements

These are preserved historical development versions. After the generalization concern, v1.11 was frozen and whole-history profit optimization was disabled. A rising historical score does not establish future usability. New promotion requires separately locked unseen evidence; see [the generalization protocol](GENERALIZATION.md).

| Version | Same-period modeled net | Main change |
| --- | ---: | --- |
| [v1.5](V1_5.md) | $9,971.43 | Completed-hour volume at least 2x the prior 20-hour mean |
| [v1.6](V1_6.md) | $10,089.87 | Add a direction-signed 200bp gap beyond EMA150 |
| [v1.7](V1_7.md) | $10,799.67 | Raise the volume threshold to 2.4x |
| [v1.8](V1_8.md) | $11,541.24 | Use a 72-hour channel and EMA250 |
| [v1.9](V1_9.md) | $12,113.22 | Raise the initial target from 4.5R to 5R |
| [v1.10](V1_10.md) | $12,690.41 | Raise the volume minimum from 2.4x to 2.8x |
| [v1.11](V1_11.md) | $12,814.03 | 5.5R target; now frozen and experimental |

These figures use January 1, 2023 through October 27, 2026 UTC, $50,000 capital, $100 planned risk and the same execution costs. All these observations were reused during selection. Earlier versions remain selectable. The score in `configs/research_baseline.json` is descriptive; future validation remains pending.

Fresh reproduction certificates establish computational repeatability, not generalization. The earlier v1.8 search retained a rejected 36-configuration exit grid and tested a separate 12-configuration period grid. All five period candidates that passed the initial screen passed the complete historical gate; the highest-net pass was saved before the new policy.

The v1.9 search compared two frozen campaigns totaling 60 slots: exit geometry and volume/trend filters. One candidate passed each campaign, and the highest-net pass was saved after reproduction. The older spot proxy earns slightly less than v1.8, and both 2026 reset halves also earn less; these weaknesses remain visible in the version report.

The v1.10 search tested 24 volume/trend filters with v1.9's 5R target. Two candidates passed the complete gate; the higher-net 2.8x volume rule was saved. The weak 2026 first half and older spot proxy improve, but the 2025 halves and 2026 second half earn less than v1.9.

The trend-filter improvement was initially written over v1.5. It is now v1.6; original v1.5 was restored byte-for-byte from its verified archive. This labeling correction adds no performance gain. Original research filenames retain their historical labels.

Repeated historical selection is not independent forward validation. Pine compilation and TradingView trade matching remain unverified.

## crypto_v0_1 (candidate, 2026-11-03)

Separate instrument line, not an ETH version. Pre-registered 8-coin lab (`backtesting/crypto_research/`): 25 fixed candidates per coin (6 signal families x 1h/4h x two exit geometries, plus ETH v1.11's rules transplanted), train 2021-23 as annual folds, validation 2024, one held-out look at 2025-2026-10-28 for the single selected pair. Drawdown is penalized in the score and capped at 5% in every gate. Selected: BNB, time_series_momentum, 4h, 3 ATR stop / 5R / 4 ATR trail. Held-out: +$972 (2025) and +$300 (2026) at 8bp, drawdown under 1.7%. Registered as `candidates/crypto_v0_1` (unpromoted). ETH v1.11 unchanged. Absent whole UTC days in Binance monthly archives (LTC/SOL/XRP, Feb/Apr 2022) are repaired from daily archives, never synthesized.

## crypto_round2_bnb (no new version, 2026-11-03)

Pre-registered BNB-only neighbourhood search around crypto_v0_1 (`backtesting/crypto_research/round2.py`): 240 momentum rules (lookback 10-40 x trend EMA 100/200/none x volume gate x 4h/8h x four exit sets), same training score and gates as round 1, ranked by the median score over each rule and its one-step grid neighbours (plateau gate) so an isolated spike cannot win. Top plateau rule `tsm_l15_t100_von_4h_wide` (all three training years positive, 6/7 neighbours passing) lost $914 in 2024 validation and was rejected; no `crypto_v0_2` proposed, the held-out window was not opened. crypto_v0_1 itself ranks 11 of 240 on plateau score with only 4/8 neighbours passing, and only 55/240 grid points have a positive training score, so the BNB momentum edge is narrow; the candidate stays unpromoted. ETH v1.11 and crypto_v0_1 unchanged.

## crypto_round3_families -> crypto_v0_4 (SOL), crypto_v0_5 (BNB) (shelved candidates, 2026-11-04)

Pre-registered sideways search (`backtesting/crypto_research/round3.py`): eight signal families not used in rounds 1-2 (Donchian 20/55, Keltner breakout, volatility contraction, z-score reversion, MACD, efficiency ratio, RSI-50) x 4h/1D x two exit sets = 32 candidates per coin on all eight coins; round-1 score, gates and chronology. 26/256 passed training; the best training candidate per coin was validated on 2024 and three passed (BNB macd_4h_patient +$341, SOL keltner_4h_patient +$53, BTC donchian55_4h_patient +$7). Those three plus the round-1 BTC squeeze_breakout_4h_balanced carry-over (validated in round 1, never tested) each received one held-out look at 2025-2026-10-28. Both BTC pairs lost and were rejected; SOL keltner (+$865 / +$640, drawdown <= 1.7%) and BNB macd (+$629 / +$155, drawdown <= 1.8%) passed and were registered as `candidates/crypto_v0_4` and `crypto_v0_5`. Versions are assigned in the fixed pre-registered order, so v0_2/v0_3 belong to the two rejected BTC pairs and were never created. Both are unpromoted and not paper traded: the user asked to keep searching and add only one or two strategies to the paper server after a final ranking. ETH v1.11 and crypto_v0_1 unchanged.

## crypto_round4_youtube (no new version, 2026-11-04)

Pre-registered test of strategies presented on YouTube (`backtesting/crypto_research/round4.py`), each encoded literally from the video's stated rules with assumptions recorded in the manifest: DEMA200 + Supertrend(12, 3), 5-EMA breakout, Bollinger(30, 2) + RSI(13) reversion, CCI(14)/CCI(28) +-100, and Quantified Strategies' daily MACD-histogram, 25-day close breakout and turn-of-month (13 variants per coin, 104 in total; seven further videos were excluded as discretionary or proprietary). Signal-based exits run through a round-local copy of the cost_reserve simulator with an `exit_signal` column, because the hash-locked simulators are not edited. Every training-eligible candidate (8/104) was validated on 2024; four passed (SOL yt_cci14_1D, SOL yt_cci28_1D, BNB yt_cci14_1D, LTC yt_turn_of_month_1D) and each received one held-out look at 2025-2026-10-28. All four lost in 2025 (-$73 to -$324 at $100 risk, 8bp) and were rejected; no version registered. The popular 1h/4h indicator rules lost in every training year at realistic costs. ETH v1.11, crypto_v0_1, v0_4 and v0_5 unchanged.

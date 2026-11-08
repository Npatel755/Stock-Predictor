# mass_v2 exhaustive search protocol (registered 2026-11-08, before any run)

Request (Nick): test as many rules as needed to find one with a real edge; no tuning on validation or test; evaluate
validation once to infer performance.

## Why a new version
Searches to date (370k + 500k + 200k + 5M-universe "m5") scored every rule on the same four years 2020-2023 and
selected the maximum of ~1M+ trials; on the 10 unseen years 2010-2019 the picks earn ~0 after costs
(reports/UNSEEN_YEARS_2010_2019.md). mass_v2 changes the evidence, not just the count:
- training = ES/NQ 2010-2023 (14 full years, strict 15-min bars from the physical TRAIN partition only), traded as
  MES/MNQ economics (tick 0.25, $5/$2 per point, $0.50/side, 1-tick spread, 1-tick slip) with annual $50k accounts and
  the engine's funded rules ($150 risk, $300 daily loss, $1.8k hard DD, flat before close);
- the gate is per-year consistency across 14 years, not total P&L;
- the whole grid is enumerated, not sampled, so the trial count is known exactly for deflation;
- sizing is fixed at 1 contract in the search (sizing is a later, separate decision).

## Universe (exhaustive)
instrument {ES->MES rules, NQ->MNQ rules} x family (10, mass_features.signal_for unchanged) x lookback (8 values;
opening_range uses the 15-min multiples) x threshold (5 per family) x session (5 windows) x stop_atr {1,1.5,2,3} x
target_r {1,1.5,2,3,4} x hold_bars {2,4,8,12,16} x trailing_atr {0,1,2}, max_contracts = 1.
= 2 x 10 x 8 x 5 x 5 x 4 x 5 x 5 x 3 = 1,200,000 configurations, 4,000 distinct signal masks.
Engine: runs/training_search_500k_v1/code (mass_execution.execute, mass_features), unchanged.

## Training gate (all required; evaluated at today's costs)
G1 total net > 0 over 2010-2023 and >= 10 of 14 years net positive;
G2 worst annual intrabar drawdown < $1,000 (1 contract);
G3 >= 140 trades (>= 10/yr average) and no single year > 40% of total net (top_year_share);
G4 placebo: per-trade net exceeds the 95th percentile of 20 within-year signal-time permutations of the same config
   (same exits, same number of signals, random bar placement inside the eligible session) - survivors only;
G5 deflated Sharpe (Bailey & Lopez de Prado) on annual net series with N = 1,200,000 trials, skew/kurtosis of annual
   returns, must be > 0.95 (reported; configs failing G5 are "research-only", not candidates).
Secondary (reported, not gating): restated-friction variant (cost factor = median close of year / median close 2020).

## Behavioural dedup
Survivors with identical trade-entry fingerprints (same signal mask, exits differing only in unused params) collapse
to one; among near-duplicates (>= 90% shared entry bars) keep the one with the smallest worst-year DD.

## Validation (once)
At most 20 frozen survivors (ranked by worst-year net, then DSR) are run once on MES/MNQ 2024-2025 strict bars, 1
contract, same costs. "Holds" = validation net > 0, 2024 and 2025 each >= -$300, no $2k breach, val per-trade net
>= 50% of training per-trade net. No re-ranking or parameter change after this run. 2026 is never loaded.

## Outputs
runs/mass_v2/ (gitignored, checkpointed sqlite) ; reports/MASS_V2_TRAINING.md/.json, reports/MASS_V2_VALIDATION.md ;
research/strategy_memory/events.jsonl entry. Paper promotion is a separate decision; nothing is auto-deployed.

Throughput measured on the VM: load 14y strict 0.7 s, features 2.5 s per lookback, execute 14y 0.14 s per config ->
~7 configs/s/core, 8 cores ~ 180k configs/hour -> full universe ~7 h.

## Amendment A1 (2026-11-08, registered after the strict-bar training run, BEFORE any validation run)
Finding during training QA: the strict 15-minute bar rule (all 15 source minutes present) drops ~40% of NQ bars before
2018 (overnight minutes missing in the Databento export) and creates 1,700-2,100 feature-segment breaks per year vs
~500 under the lenient rule. Rolling features with lookback >= 48 are therefore NaN for most of 2010-2017 on NQ, and
several strict-run G1-G3 passers (MNQ momentum lb64) have 0-5 trades per year before 2018 - their "10 of 14 positive
years" is not evidence over 14 years. Fix applied uniformly to every configuration, gate unchanged:
- The full grid is re-run under the lenient bar rule (>= 1 source minute, the same rule used as a sensitivity variant
  in reports/UNSEEN_YEARS_2010_2019.md). Results in runs/mass_v2/results_lenient.sqlite.
- Freeze rule becomes: a configuration is frozen for validation only if it passes G1-G4 under BOTH bar rules
  (robustness to bar construction), dedup by fingerprint, cap 20, ranking unchanged.
- Additional reported statistic: trades per year; configurations with fewer than 5 trades in 4 or more years are
  labelled "sparse" in the report (not a gate, since it was not pre-registered).
2024-2025 and 2026 data have not been loaded at the time of this amendment.

## Amendment A2 (2026-11-08, registered after the first validation look, before any A2 run)
Engine artifact found while re-scoring fees: a position held into a CME early close (13:00 ET sessions) crosses the
>20-minute gap to the 18:00 reopen and the engine locks the sleeve permanently ("market_data_gap"). In the A1 runs this
silently killed any configuration that was in a trade at 12:45 ET on an early-close day for the rest of that annual
account, biasing the grid against all-day sessions. Fix (src/quant_futures/session_calendar.py, applied uniformly in the
data layer, engine code unchanged): bars from the early session's last regular bar onward are presented to the engine
as >= 16:00 ET, so it exits at that bar's open and takes no new entries. Both bar-rule runs are repeated with the fix
(results_a2 / results_lenient_a2); gates, placebo, DSR, freeze rule (pass under both) and cap are unchanged.
Validation exposure: the A2 frozen list will be the SECOND look at 2024-2025 (first: A1 list, 1 of 12 held). The A1
look did not influence any A2 choice; A2 only corrects a mechanical defect. 2026 is still never loaded.

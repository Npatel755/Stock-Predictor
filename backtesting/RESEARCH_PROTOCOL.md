# DVS strategy improvement research

This program tests modifications to the supplied DVS v1.1 setup/retest strategy while retaining the original parity mode. The original market, indicator availability, pivot confirmation, and no-lookahead rules are unchanged. Experimental changes require Research mode and are rejected in parity mode.

Every candidate keeps $50,000 capital, $100 planned risk, a $300 personal daily entry gate, and 5x maximum notional leverage. Increasing size is not counted as a strategy improvement. The cost scenario uses next-open entries, 4bp commission per side, two instrument ticks plus 2bp assumed adverse slippage on market/stop orders, 3.3bp/day financing at four-hour snapshots, and stop-first treatment if both bracket levels are touched. This remains a proxy execution scenario, not observed Breakout fills.

## Fixed chronological protocol

The candidate universe, parameter bounds, seed, selection formula, data hash and implementation hashes are written to `manifest.json` **before** results are calculated. The manifest must match exactly when resuming. The search uses:

1. **2023–2024:** screen a predetermined universe, starting with single-variable ablations, then fixed-seed hypothesis families. Rank by net return in $100 risk units minus half the largest closed-equity drawdown in those units. Candidates with fewer than 25 entries or margin calls are ineligible.
2. **2025 H1 and H2:** evaluate the fixed training shortlist. Rank by combined net risk units minus 1.5 times the magnitude of a negative worst half and half the worst half's drawdown. Require at least six entries per half and 25 combined. The promotion gate additionally requires both halves to be profitable and aggregate validation P&L above the unchanged baseline.
3. **2026 through October 27:** freeze the candidate and its rules first, then run a retrospective audit and a stress test doubling assumed extra slippage from 2bp to 4bp. The audit cannot change the selection.

All of this historical dataset has previously been used or inspected in this project, including 2026. The audit is **not an untouched holdout**. Extensive candidate searches create selection bias even with chronological validation. A candidate needs future paper observations and actual feed/fill reconciliation before any claim about funded trading performance. Losing or inconclusive experiments remain in the record.

Indicators are calculated from the chronological development history. Each evaluation window starts with a new account and no setup/position, while using only already-available indicator history. At a boundary an open position remains marked, with open-position details in metrics. Fold P&L is a diagnostic sum of independent accounts, not a claim that a deployable continuous account achieved that total. Full-period replays are separately exported.

## Hypotheses under test

- Reward/risk, volume thresholds, setup timeout, retest tolerance and stop buffer.
- Stop-distance floors in basis points or ATR multiples. These widen the stop and recalculate both size and target.
- Sizing based on stop distance **plus estimated round-trip entry/exit costs**, preventing fees from consuming risk on tight stops. The estimate assumes the signal price and omits unknowable future financing; realized gap/fill losses can still exceed planned risk.
- A minimum target-to-estimated-cost ratio, rejecting trades whose prospective reward barely covers friction.
- ATR and four-hour trend-distance filters, broad fixed UTC sessions, weekday restrictions and long/short ablations.
- Cooldown after exits, maximum holding duration, close-triggered breakeven and ATR trailing stops. Stops update only after the current completed candle has been processed; new stops are effective on the next bar and cannot retroactively consume its past high/low. Unrealistically marketable stop updates are skipped.

`capture_details=False` is a low-memory screening option on the **same event-driven engine**. It suppresses per-bar chart/signal tables but retains exact trade/event ledgers and metric calculations. Regression tests compare it against full-detail execution; no alternate vectorized fill simulator is used.

## Run and monitor

From the repository root using the current CPU environment:

```powershell
.ethvenv/Scripts/python.exe -m backtesting.optimize --candidates 256 --finalists 32 --output backtesting/artifacts/optimization/round1_verified
```

Rerunning the exact command resumes completed checkpoints if the code/data/protocol hashes match. Changes require a new output directory. `training.jsonl` and `validation.jsonl` append one completed candidate at a time. `selection.json` freezes the final validation choice before audit evaluation. `summary.json`, `leaderboard.csv`, `audit.json`, and full-detail selected/baseline replays provide the result trail. The dashboard's **Strategy research** tab displays saved progress and completed experiments. Progress is a checkpoint count, not a declaration that an OS process remains live.

The initial `round1` directory was stopped after a few training candidates to correct cooldown handling for a next-open entry that exits on the same candle and to prevent a breakeven stop beyond the current market. It is not an eligible completed experiment. `round1_verified` uses the corrected implementation and a new frozen manifest.

Future rounds may investigate neighborhoods or alternative mechanisms using development periods, but the number of rounds must be disclosed. Do not keep retuning on the 2026 audit and presenting the resulting winner as independent validation. Keep the parity baseline and source artifacts reproducible.

## Post-selection diagnostics and Pine export

After the search has saved `summary.json`, run:

```powershell
.ethvenv/Scripts/python.exe -m backtesting.analyze_experiment backtesting/artifacts/optimization/round1_verified
.ethvenv/Scripts/python.exe -m backtesting.export_candidate backtesting/artifacts/optimization/round1_verified
```

The analysis verifies the frozen source and data hashes, replays a continuous 2025 validation account, repeats the previously inspected 2026 audit, and saves paired weekly-block uncertainty estimates. Slippage sensitivity uses 2025 only; parameter-neighborhood diagnostics use development history only. Neither changes the frozen selection. The intervals are conditional on the selected candidate and do **not** account for searching many candidates.

The optional Pine derivative exports experimental signal and risk rules with candidate defaults and an embedded configuration hash, retaining the supplied source license. It is **not a parity-verified execution equivalent**: Pine's fixed tick slippage does not reproduce Python's extra basis-point market/stop slippage, daily financing, or pessimistic stop-first treatment of a candle touching both bracket levels. Those differences are stated in the generated file. Pine compilation and chart/export reconciliation still need to be performed in TradingView; Python's exporter tests are not a Pine compiler.

The user requested the new derivative be named **DVS ETH v1.2**. The exporter saves it as `reference/DVS_ETH_v1_2.pine`, with the corresponding Python research configuration at `configs/dvs_eth_v1_2.json` and validation/source metadata at `configs/dvs_eth_v1_2.metadata.json`. The config's `strategy_version: v1.1` identifies the underlying supplied Pine state machine; the added experimental rules and the profile name identify the v1.2 derivative. It is not a rename or modification of the original v1.1 file.

The first 256-candidate search found no shortlisted candidate that passed both half-year profit gates. Its frozen winner improved aggregate net P&L, but failed the gate with a small H1 loss. It is saved as experimental v1.2, not promoted as validated.

The follow-up `python -m backtesting.refine` preregisters 128 configurations around the saved v1.2, retaining its cost-aware sizing and original DVS state machine while varying reward/risk, stop buffer, breakout RVOL and minimum ATR. It snapshots the parent configuration and records the new source/protocol hashes before evaluation. It uses 2023–2024 screening and **reuses 2025 selection data**, so this is additional model selection, not independent validation. Both validation halves being profitable is an eligibility condition before ranking in this round. The already-inspected 2026 audit cannot choose parameters. It does not automatically overwrite v1.2.

## Follow-up evidence and earlier-regime transfer

The refinement finished with reward/risk 4.5, stop buffer 0.4 ATR, cost-aware risk and minimum ATR 10bp. Its 2025 halves made +$25.50 and +$1,639.91. Current v1.2 uses these frozen rules; earlier Pine/config/metadata are content-addressed revisions. This historical gate pass is not prospective validation.

`python -m backtesting.transfer_audit` froze the three comparators before downloading previously unused 2020–2022 perpetual data into a separate directory. Refined v1.2 lost $3,093.86 over that period, with 8.55% running-peak drawdown. The failed regime transfer is preserved without tuning to it.

`python -m backtesting.execution_audit backtesting/artifacts/optimization/round2_v1_2_neighborhood` measures half-year slippage sensitivity and concentration without selecting new rules. H1 2025 turns negative at 4bp extra slippage, and a few large winners drive much of the 2026 result.

The separate `python -m backtesting.adaptive_audit` diagnostic compares fixed variants with cash. Quarterly allocation uses only the preceding 12 months of shadow marks/exits, requiring 20 closed legs and profit in both halves. It liquidates at scheduled quarter ends with costs, carries cash across windows and resets setup state. This is a causal historical allocation replay, **not independent walk-forward validation**, since the candidates themselves were selected using later data. It never overwrites v1.2 or submits orders. The verified run is stored in `adaptive_trailing_audit_verified`; the first diagnostic was rerun after correcting reporting of scheduled liquidation costs, without changing allocation rules.

## v1.3 exit-management experiment

The next exported strategy version is **v1.3**, as requested. v1.2 files and downloads stay intact. `python -m backtesting.exit_research` freezes 24 configurations before evaluating them: the saved v1.2, original research baseline, and a small set of closer targets, completed-close breakeven/trailing rules and maximum holding times. It uses the same event-driven engine and risk/cost assumptions.

2020–2024 annual accounts form the training shortlist; this explicitly converts the previously failed 2020–2022 transfer data into development data. Six changed finalists are selected before evaluating the reused 2025 halves. Eligibility requires four profitable training years, training sum and worst year at least as good as v1.2, both validation halves positive, validation sum above v1.2, sufficient observations, no margin calls and positive continuous 2025 at 4bp extra slippage. If no candidate passes, the best changed candidate may be saved as unpromoted research with a failed gate. It cannot be called an improvement simply because it wins this search. The inspected 2026 audit and recent October diagnostic run only after selection; they cannot select parameters. A continuous 2020–2026 replay is separate from independently reset folds. No future-validation claim is made.

Independent non-DVS ETH strategy families are also authorized for further research and must use the same cost/risk and chronological standards. Their results must be distinguished from the DVS exit experiment and counted as additional model selection.

`python -m backtesting.alternative_research --output backtesting/artifacts/optimization/round3_independent_families_verified` screens 12 fixed hourly configurations across EMA crossover, Donchian-style channel breakouts and Bollinger reversion, with five-minute execution. Hourly signals are generated only on the hour's final completed five-minute candle and fill at the next open. It uses 2020–2024 annual training, a four-candidate shortlist, reused 2025 selection, the same historical gates, and a frozen 2026 retrospective audit. All are cost-aware with unchanged dollar risk; they share the existing Broker but not DVS signal logic. An initial implementation trial suppressed trades because of hourly ATR index alignment; that run is explicitly invalid, and corrected regressions require finite ATR on signals, actual trades and known expected family signals. Only the new-manifest verified run is eligible.

The 24-rule DVS exit experiment failed its gate: a small gain in the recent October window came with worse broad-history results. The 12-rule independent comparison also failed its gate: its selected 55-hour channel/3-ATR trailing rule was substantially stronger over continuous 2020–2026, but below the saved v1.2's 2025 validation sum and negative in the inspected 2026 audit. Neither failed gate is erased by subsequent research.

`python -m backtesting.channel_refine` preregisters a 24-slot follow-up across 40/55/80-hour channel lengths and bounded stop/reward/trailing geometry. This is further reuse of the family-selection data, not fresh validation. Its unchanged historical gate selected the 80-hour channel, 200-hour EMA, 2 ATR stop, 3R target and 3 ATR trail. Five training years and both validation halves were profitable, and 2025 remained positive at 4bp extra slippage. The candidate was frozen before its retrospective 2026 replay, which lost $1,077.22. It is saved as independent experimental **ETH v1.3**, with no edits to v1.2. Across the searches there are 444 slots including repeated configurations; post-selection diagnostics do not change the choice. See `V1_3.md` and the retained robustness failures. Historical gate passage is not funded-trading readiness.

## Explicit historical-profit objective after v1.3

The user subsequently required a strategy that exceeds the highest saved net P&L on the same period. `python -m backtesting.net_profit_research` freezes 64 bounded channel configurations and ranks their complete 2023-01-01 through 2026-10-27 replays by net profit at unchanged $100 risk, $50,000 capital and execution costs. This deliberately changes the selection target: **2026 now participates in selection and cannot be called an independent audit for this round**. The prior frozen experiments and their failures remain intact.

The top eight eligible-screen candidates get additional checks: at least 100 entries, no margin calls, at most 5% running-peak intrabar drawdown, both reused 2025 halves positive, earlier 2020–2022 aggregate positive, and full-period net P&L at 4bp extra slippage still above the original saved-profit benchmark. Among candidates passing these historical checks, the highest full-period net profit wins; lower ID breaks ties. The full candidate universe, ranking/gate rules, account and source/data hashes are frozen before results. Original v1.2 and v1.3 are recomputed on identical dates, so a different start date, larger account, greater risk or omitted cost cannot count as clearing the benchmark. This search is historical optimization, not future performance evidence. Exporting a winner requires explicitly retaining that distinction.

The first 64-rule pass found $5,009.28 at 2.78% drawdown but failed the higher-cost gate ($3,848.16 at 4bp extra slippage). Its report and ledgers are retained. `python -m backtesting.profit_refine` then froze another 64 configurations in bounded neighborhoods around observed channel64/EMA200 and channel96/EMA100 geometries. Its additional adaptive-selection protocol and generator source hash are stored with its manifest. This follow-up reuses the same historical observations, so it supplies no independent validation. Across searches there are now **572 configuration slots including repeats**, plus post-selection diagnostics.

The highest-profit qualifying follow-up candidate was channel96/EMA150, 1.5 ATR initial stop, 4.5R target and 3 ATR trail. It made $6,034.44 on the same continuous 2023–2026 period, versus saved v1.2's $4,344.93 and the previous v1.3's $4,075.01. Its modeled intrabar drawdown increased to 4.92% from v1.2's 2.99%. Full-period 4bp-extra-slippage net was $4,721.92; both 2025 halves and earlier-regime aggregate were positive. Its separately reset 2026 selection-period check still lost $284.04. The lower-drawdown channel64/EMA200 alternative made $5,863.93 at 2.83% drawdown and passed the same gate, but the user's stated priority was the highest net profit. Both candidates and the tradeoff remain in the record. The user named the higher-profit derivative **v1.4**. Its separate Pine/configuration/metadata/downloads are saved under v1_4 names; the previous v1.3 files are restored byte-for-byte and remain separately selectable. The interim higher-profit v1.3 export is archived as revision history.

## Entry-quality research after the saved v1.4

`python -m backtesting.filter_research` freezes 48 neutral, single-filter and fixed-seed combined entry configurations around the unchanged v1.4 geometry. Filters use completed-hour ATR, direction-signed close-to-EMA gap, direction-signed six-hour EMA slope, volume relative to the preceding 20 hours, long/short ablations and UTC weekend restrictions. They modify the existing signal column and then run the unchanged event-driven simulator; rejected signals can alter later position availability, so this is not deletion of losing ledger rows.

All 2023–2026 observations are reused selection data. The top six screen candidates are checked against a new fixed gate: main net above v1.4, at least 100 entries, drawdown no worse than v1.4, positive 2025 halves with at least six entries each, positive independently reset 2026 and 2020–2022 aggregate, and 4bp-extra-slippage net above v1.4 at the same 4bp costs. Margin calls are disqualifying. A neutral-filter replay must exactly reproduce the unfiltered metrics/trades/events, and future-data mutation/prefix checks cover the extra features. The existing generic Pine exporter rejects filtered candidates rather than silently dropping their filters. Saved v1.4 config/Pine/metadata hashes are protected and never overwritten by this experiment. A failed gate stays in the report; passing it still supplies no independent future validation.

The completed 48-filter screen found $7,793.34 at 4.78% drawdown with minimum hourly RVOL 1.5. Higher-cost net was $6,497.82, but the independently reset 2026 check still lost $218.57, so it failed the complete gate. That failure remains in `reports/v1_4_entry_filters.md`.

`python -m backtesting.volume_refine` freezes an 18-configuration follow-up: the saved v1.4 geometry and the previously observed lower-drawdown channel64/EMA200/1.75ATR/3.5R/trail3 geometry; each has a neutral control plus minimum hourly RVOL 1.2/1.5/2/2.5 with/without UTC weekends. The same gate remains, including positive independently reset 2026 and higher-cost improvement. Both geometries and the volume hypothesis were selected using inspected outcomes, so this is additional adaptive historical selection. The top six drawdown/exposure-eligible variants are checked, then the highest-net complete-gate pass is selected. Existing saved versions are protected by file hashes and are not overwritten. After this screen the cumulative search count is 638 configuration slots including repeats, plus diagnostics. Any new filtered Pine export must explicitly implement the filters; the generic exporter continues to reject them.

The selected volume candidate retained the v1.4 geometry and added minimum completed-hour RVOL 2.0, with weekends allowed. Main net was $9,971.43 at 4.02% drawdown, versus protected v1.4's $6,034.44 at 4.92%; at 4bp extra slippage it made $8,735.76, and at 8bp $6,468.48. Both 2025 halves, reset 2026 aggregate and earlier-regime aggregate were positive. A post-selection split still found a losing 2026 H1 (-$240.43 at main costs); this is retained alongside the positive full-year aggregate. Fresh replay and event-reconstructed equity reproduce the result; a conditional paired uncertainty estimate ignores the search bias. A separate, unnumbered experimental Pine/text export and filtered dashboard replay preserve all numbered versions. The narrow filter-aware exporter implements RVOL against the prior 20 completed hours and the UTC-weekend condition, rejects unsupported active filters and requires the historical gate. Compilation, actual feed/fill reconciliation and future observations remain unverified. See `VOLUME_RESEARCH.md` for results and failed diagnostics.

## v1.5 baseline and additional-data audit

The user set **$6,000 net profit** as the baseline on the unchanged original 2023-2026 perpetual dates at $100 planned risk and named the volume-filter version **v1.5**. The exact comparison assumptions are saved in `configs/research_baseline.json`; v1.4's actual reference result remains $6,034.44. `python -m backtesting.save_v15` exports the fixed RVOL2.0 candidate, including its filters and baseline, to separate v1_5 Pine/configuration/metadata/downloads. Main net $9,971.43 is $3,971.43 above the requested baseline; new data cannot be appended to inflate that figure.

Additional-data plans froze v1.4/v1.5 before requests. Native 2019 archives and two missing recent days were unavailable; REST returned HTTP 451 and the older Massive crypto query HTTP 403. No restriction was bypassed. The available recent archive rows were already present and are not counted as new evidence. `python -m backtesting.v15_proxy_audit --output backtesting/artifacts/optimization/v1_5_spot_proxy_verified` instead added 208,855 official checksum-verified ETHUSDT spot bars from 2018-2019. Spot provenance is retained through an explicit optional validator in the unchanged broker algorithm. Default native behavior matches the preserved pre-extension simulator source exactly in regression tests; older strict source manifests remain unchanged, with the earlier source archived for reproduction.

The source included 241 off-grid records, excluded/reported without timestamp shifting. The 1,385 missing intervals are split into independent segment accounts with fresh warm-up; four short segments are skipped. Frozen v1.5's sum of 12 independent segment-account P&Ls was +$5,541.70 versus +$6,833.37 for v1.4, with lower worst segment drawdown. This is a weaker comparative result on genuinely additional cross-market data, not a continuous account return or native-perpetual execution claim. The rules were not changed to erase it. Earlier spot data does not provide future validation or undo the extensive selection on 2023-2026. Full evidence is in `V1_5.md` and the retained audit reports. Earlier numbered profiles remain unchanged; no live orders occur.

# Point-in-time price/news alignment reference

## Separate descriptive events from actionable strategy features

1. **Event table**: an immutable event with `event_id`, `source_id`, `event_kind`, `symbols`, `source_url`, `scheduled_time_utc`, `first_publication_time_utc`, `vendor_available_time_utc`, `local_ingest_time_utc`, `version`, `revision_of`, `timestamp_precision`, `initial_actual`, `consensus_asof_utc`, `pre_release_consensus`, `license_status`. All timestamps timezone-aware. Null/unknown is preferable to fabricated precision.
2. **Price table**: instrument, contract_id, exchange timestamp, receive timestamp when available, bid, ask, bid_size, ask_size, trade_price, trade_volume, bar_start_utc, bar_end_utc, `is_roll_adjusted` and source metadata. Use an **unadjusted, tradeable contract** for fills. Preserve raw inputs.
3. **Descriptive event study**: `event_id`, horizons, outcome return/volume/volatility/spread, baseline/control, completeness. Pre/post windows can include outcomes as labels, but the table is **never available as predictor input**.
4. **Actionable point-in-time features**: for each decision/price-bar time `t`, compute a news feature only using `event.available_to_strategy_at <= t` where available_to_strategy_at = max(first-publication, vendor delivery, system ingest when known) + realistic parsing and compute latency. `scheduled_time` may be known before release, but the surprise and article text may not. Do not use missing unknown latency as zero.
5. **Execution**: signal at or after t may execute only at an executable later opportunity consistent with quote stream, connection delay, and queue/fill logic. For minute bars containing a release, prefer next-bar entry with stress tests; don't pretend bar-close price was available inside the same minute.
6. **Futures mapping**: do not execute synthetic continuous NQ/ES series; map to a contract month and realistic MNQ/MES quote and commission schedule, roll dates, DST and CME sessions.
7. **Equity-to-index mapping**: company earnings/filing articles are not automatically index news. Use historical membership and exposure (and lagged weights if available) and report uncertain attribution.
8. **Controls**: matched time-of-day/no-news periods, price-only strategies, calendar-only blackout features, shuffled labels on training, and event-cluster uncertainty estimates. Avoid mixing overlapping event windows or counting one publication many times.
9. **Revisions and provenance**: first-vintage actual vs forecast from before the announcement, confirmed source timestamp, version/hash, historical vendor access rights. Never use retrospectively revised data or backfilled sentiment without time-appropriate model version.
10. **Acceptance**: incremental OOS net performance after commission/slippage, robust execution delay, no holdout contamination, enough independent events, bounded funded-account risk and reproducibility. Else `NO VERIFIED NEWS EDGE`.

## Minimal timing leakage tests

- Article first published **after** a price bar cannot affect that bar's feature.
- A scheduled CPI time is known beforehand, CPI **actual/surprise** is not.
- If a vendor posts at 08:30:04, a signal cannot trade at 08:30:00.
- A corrected 2024 data print released in 2025 cannot replace the initial figure in a 2024 training example.
- A later article about a preceding price rally cannot be used as a cause or pre-rally signal.
- Duplicate wire stories don't artificially multiply sentiment.
- A news item with only a date, no time, is not a valid intraday event timestamp.
- A U.S. DST transition does not shift an Eastern 8:30 a.m. release to the wrong UTC time.
- A release inside a minute bar cannot use that minute's pre-release quote as a post-release fill.

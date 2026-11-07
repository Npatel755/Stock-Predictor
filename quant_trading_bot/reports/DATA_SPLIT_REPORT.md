# Chronological data split

The active user-provided Databento data is physically separated into training, validation and test Parquet files for each instrument. No random shuffle was used.

- Training: available history before January 1, 2024 UTC.
- Validation: January 1, 2024 through December 31, 2025 UTC.
- Test: January 1, 2026 through the archive end, November 5, 2026 UTC.

| Instrument | Training bars | Validation bars | Test bars | Total selected bars |
|---|---:|---:|---:|---:|
| MES | 1,637,070 | 707,415 | 301,755 | 2,646,240 |
| MNQ | 1,638,673 | 707,652 | 301,755 | 2,648,080 |
| ES | 4,732,083 | 707,375 | 301,748 | 5,741,206 |
| NQ | 4,558,150 | 707,567 | 301,743 | 5,567,460 |

MES/MNQ training begins May 5, 2019 UTC. ES/NQ training begins June 6, 2010 UTC and remains distinct mini-futures reference history. All four validation sets begin January 1, 2024 at 23:00 UTC and test sets begin January 1, 2026 at 23:00 UTC; closures and absent bars are not filled.

The default fixed protocol fits estimators, preprocessing and calibration only on eligible training rows. Training labels reaching the validation boundary are purged. Candidate selection uses validation. Features can carry causal earlier-period history, but the development loader never reads test prices. An optional explicitly configured walk-forward protocol may fit completed earlier validation observations for subsequent validation blocks.

Ordinary research loading rejects a direct test partition. Final evaluation verifies the frozen artifact and source, then consumes a global single-use test reservation before loading test prices. The real-market test remains unevaluated; fixture tests exercise this guard without consuming it.

Every selected row is assigned exactly once. Date ranges are disjoint; per-file SHA-256 hashes, UTC coverage and protocol IDs are recorded in `data/catalog.json` and adjacent partition manifests. The original ZIP and imported raw contract partitions are preserved. Superseded unsplit derived files were retired after the new partitions and catalog were committed.

Split protocol ID: `4865072f60c7a5f588f5cf1086076ea5148e720f317a1ceb5c582f06891fdd33`.

Verification: python -m pytest -q -p no:cacheprovider; passed: `True`. See `test_receipt.json` for the matching source hash.

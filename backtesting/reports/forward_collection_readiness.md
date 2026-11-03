# Locked forward-test data readiness

Coverage-only collection. No strategy signals, trades, returns or version selection were run. The frozen v1.11 rules and prospective window are unchanged.

Observed collection: **2026-11-03 18:45:07.198004+00:00**. Source coverage ends at **2026-11-03 00:00:00+00:00 exclusive**; only fully completed UTC days are requested.

- Pinned, checksum-verified daily archives: 51.
- Retained five-minute source rows: 14,424.
- Forward-test rows collected: 0.
- Missing required completed intervals: 288.
- Data state: `collecting_or_incomplete`.

Warm-up begins 2026-09-12 22:00:00+00:00. The locked forward period is 2026-11-04 00:00:00+00:00 to 2027-05-03 00:00:00+00:00 exclusive. Final evaluation cannot occur before 2027-05-03 00:00:00+00:00.

| Missing start | Missing end exclusive | Bars |
| --- | --- | ---: |
| 2026-10-28 00:00:00+00:00 | 2026-10-29 00:00:00+00:00 | 288 |

October 28 remains unavailable from the official daily archive source; November 2 is now available. Missing bars are not fabricated or replaced with another venue. The unresolved warm-up gap means this dataset cannot currently satisfy the final evaluator, even though prospective observations have not begun. The test window is not moved to avoid this issue.

Sources are pinned on first successful capture. Replacing either the ZIP or its checksum is rejected after capture. New days extend content-addressed snapshots; earlier snapshots and provenance remain intact. Concurrent collectors are excluded by an OS writer lock. No background schedule is installed.

Refresh the dashboard and use Generalization ? Collect completed ETH days without evaluating returns. The final evaluator uses the retained snapshot path and remains disabled until the fixed date. Collection is data management, not a strategy-validation pass.

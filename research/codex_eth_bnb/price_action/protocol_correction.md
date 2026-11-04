# Opening-range fade state correction

The initial implementation in commit41189bd could re-arm an expired opening-range fade while price remained outside the SAME fixed session boundary. That violated the intended requirement for a fresh crossing. A review found it after18ETH15m variants had completed three TRAIN folds each(54replays), before any shortlist or validation was evaluated.

Correction: a new excursion can arm only when the prior close was not already beyond the buffered boundary. Continuing outside closes cannot reset the four-bar fade clock. A deterministic regression test keeps price outside for six bars and then returns inside; no fade may be emitted. No threshold, family, exit, cost or selection objective changed in response to profits.

The original source is retained in git, initial manifest in manifest_initial_superseded.json, and initial54registry rows in superseded_registry.csv. Existing outputs remain untouched. All initial18variants are conservatively counted again in the cumulative Holm family(208prior+72current+18superseded=298). The append-only registry keeps both implementations, with code hashes distinguishing them. Summary scoreboards use corrected-code runs only; calendar/cost/weekly exports explicitly label superseded records. No old implementation accessed validation or final performance.

The initial frozen plan remains unchanged as a historical record; this dated engineering addendum supersedes only its state-machine implementation and multiplicity count. The new freeze includes both plan and correction hashes. All85tests must pass before the corrected run begins. These are still retrospective development diagnostics on inspected data, not a fresh holdout.

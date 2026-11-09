# Paper runner incident 2026-11-09 — forced exits at the newest bar (fixed 0a5cf6f)

Symptom: at the 17:18Z run, ag_quad, ag_quad_v2, ensemble_beta, portfolio_e and portfolio_e_scaled each showed one MES long opened 16:00Z (11:00 ET) and
closed 16:30–16:45Z with reason `session_exit`, −$62 to −$125 each. In the backtests positions exit only on stop / target / hold bars / 15:55 flatten.

Cause 1: `session_calendar.early_close_minute_offset` treats any trade date whose last regular bar is before 15:00 ET as an early-close day and relabels
that bar as the 15:55 flatten bar (a heuristic for unknown half-days in history). Live, the day in progress always ends "early", so its newest bar got
minute 960 (seen: 16:30Z bar → minute 960) → `no_entry` → forced `session_exit`. Fix: `ensemble_paper.live_early_close` keeps plain ET minutes for the
last trade date when it is not a calendar early close and the data ends before 16:00 ET; identical to `apply_early_close` for completed days (tested).

Cause 2: the engine closes any position still open on the final bar (`terminal_close`, reason 7) and the runner ledgered that as a closed trade, so an open
position looked flat and each later run produced a divergence + a new artefact trade. Fix: `run_sleeve` now converts a `terminal_close` trade back into the
open position (marked at the last close, exit costs included) and removes its cash hit from the curve.

Cleanup: the artefact `session_exit`/`terminal_close` trade records dated 2026-11-09 and their divergence records were removed from the five ledgers
(backups: /opt/futures-paper/runs/_backup_20261109_sessionexit/). After the fix the 17:34Z run shows 0 trades and the five positions open
(ag_quad/v2: 1 MES −36 marked; beta/e_scaled: 1 MES +19; portfolio_e: 2 MES +38). Overnight ledgers were never affected (own code path).

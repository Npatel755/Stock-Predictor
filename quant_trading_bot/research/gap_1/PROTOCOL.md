# gap_1: overnight gap and Globex-range mechanics at the RTH open (registered 2026-11-08, before any run)

Mechanism: overnight (Globex) price discovery is thin; the 09:30 ET open re-prices against the prior RTH close. Two opposite
hypotheses with literature support: (A) gap fill — large gaps partly revert during the first hours; (B) gap-and-go — gaps that
the first 15 minutes confirm continue. (C) Globex-range break — the overnight high/low acts as a level; the first break in RTH continues.
Not covered by mass_v2 (ORB used only the RTH range) or mass_1m.

Data: 15-min bars incl. Globex from the Databento 1-min splits. TRAIN = ES/NQ 2010-2018 + MES/MNQ 2019-2023 at micro economics;
VALIDATION = MES/MNQ 2024-2025, looked at once for the frozen passers; 2026 never loaded.
Trade date = ET date of (timestamp + 6h) so the 18:00 ET Globex open belongs to the next trade date. Features use only bars
before the decision bar closes: prior RTH close (last bar < 16:00 ET of the prior trade date), Globex high/low (bars from the
Globex open to 09:30), dATR = mean of the prior 14 sessions' RTH high-low range, bar ATR(14) on 15-min bars.
Engine: fixed research engine (mass_execution), $0.61/side, MNQ spread 1.75 ticks (MES 1.0), 1 tick slippage, 1 contract,
$150 risk, $400 daily loss, $2k funded lock, flat 15:55 ET, early-close fix.

Grid (fixed; 1 contract; decision on the 15-min bar closing at 09:45 for A/B, filled at the 09:45 open):
- A gap fade: gap = (09:30 open - prior RTH close)/dATR; |gap| >= th in {0.5, 1.0, 1.5}; trade against the gap only if the
  09:30-09:45 bar has not already closed beyond the prior close; stop in {1.0, 1.5} bar-ATR; target in {1, 2} R; hold in {4, 8} bars -> 24
- B gap-and-go: |gap| >= th in {0.5, 1.0, 1.5}; direction = gap sign; confirm in {none, first 15-min bar closes in gap direction};
  stop 1.5 ATR; target in {2, 3} R; hold in {4, 8, 12} bars -> 36
- C Globex-range break: first 15-min close beyond Globex high (+ th in {0, 0.25} ATR) within window in {09:45-10:30, 09:45-11:30};
  stop 1.5 ATR; target in {2, 3} R; hold in {8, 12} bars -> 16
Both instruments -> 152 configs. Family-level results reported for all configs.

Gate (as mass_v2): total train net > 0; >= 10 of 14 years positive; no year > 40% of total profit; worst annual intrabar DD < $2,000;
>= 150 trades; beats 95% of 50 placebo runs (same entry count, entries moved to random eligible sessions, direction shuffled).
Passers are frozen as a list before the single validation look. Holm correction across the 152 trials on the per-year sign test.
Outputs: reports/GAP_1_TRAINING.{json,md}, reports/GAP_1_VALIDATION.md if any passer; events.jsonl line.

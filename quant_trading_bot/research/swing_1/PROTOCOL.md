# swing_1 — multi-day mean-reversion holds on MNQ/MES (pre-registered 2026-11-09)

## Motivation
Every round so far held for one night or one RTH session. The best-documented index effect that is *not* intraday is short-term
(2–5 day) mean reversion after consecutive down closes (Connors RSI(2)/"3 lower closes", SPY 1993–2020s), which the project has never tested;
the memo flagged "new mechanism, not more of the same bars". Multi-day holds also amortise micro costs (≈$3 round trip vs $150–400 daily ranges).
Known risk: no intraday stop, several nights of exposure — the funded floor is checked on marked (session-low) equity, not closed P&L.

## Data and separation
MNQ/MES 1-min, train 2010-01-01 … 2023-12-31 only (ES/NQ continuous scaled to micro economics). 2024–26 not loaded.
Daily frame from the 1-min bars per ET trade date: RTH close (15:59 bar close), 18:05 reopen open (entry), full-session low.

## Rules (long only; short mirrors are negative controls)
Signal on RTH close of day D, filled at the 18:05 reopen open of the following Globex session (+1 tick slip, half spread, $0.61/side).
Exit at the RTH close of the first day meeting the exit rule (MOC approximated at the 15:59 close, same costs).
Entry signals: S1 two lower closes; S2 three lower closes; S3 RSI(2) < 10; S4 close at a 5-day closing low.
Exits: X1 close > previous close (or 5 days); X2 fixed 3 days; X3 fixed 5 days.
Trend filter: none / close > 200-day SMA of closes.  Grid: 2 instruments × 4 × 3 × 2 = 48 long configs + 48 short mirrors. 1 contract, no pyramiding.

## Controls
200 random entry-day sets per config (same count per year, same exit rule), training only.

## Gate (all required; a passer is still only a paper challenger)
net > 0; ≥ 100 trades; positive years ≥ 11/14; max-year share ≤ 40%; marked (session-low) trailing DD < $2,000; 2010–19 net > 0;
beats ≥ 190/200 placebos; the family must be coherent (≥ 2/3 of same-signal configs net-positive) — one cell alone is not a result.
Deployment at Devin's discretion (Nick 2026-11-09), beside existing ledgers, never replacing them. No 2024–26 scoring.

# portfolio_4 — ag_all_weather_v2_1c + overnight_dip_v2 as one 1-contract account (pre-registered 2026-11-09)

## Question
portfolio_1/3 showed the overnight reopen-dip leg and an intraday leg (Arch C v2, Quad v2) are complementary but their March-2020 co-losses push the
combined closed drawdown over the $2,000 floor ($2,315 / $2,396). All-Weather v2 1c has the smallest own drawdown of the intraday candidates
($1,256 on 2010–23, sizing_1). Does it combine with overnight_dip_v2 inside a $2,000 floor, and what cushion is needed if not?

## Data and separation
Training 2010-01-01 … 2023-12-31 only (both legs are already frozen on paper; no parameter is chosen here). 2024–26 not loaded.

## Method (identical to portfolio_3)
Daily closed P&L of each leg (overnight night P&L booked on the exit day), summed; per-year table; monthly correlation; closed DD of each leg and of
the sum; worst day; count of intraday fills placed while the overnight position is still open (must be 0 for a 1-contract account);
block-bootstrap (L = 10 days, 3,000 paths, one trading year) breach probability at $2,000 and $3,000 floors, total and ex-2020–22.

## Decision rule
The book may run as one $2,000-floor account only if combined closed DD < $2,000 and 1-year P(DD ≥ $2,000) ≤ 10 %. Otherwise report the cushion
at which the $3,000-floor breach probability is at or below the single-leg $2,000 level, as the staging rule. No deployment either way
(both legs already run on paper); report only.

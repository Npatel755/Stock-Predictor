# book_1 — intraday-trailing-floor check of the portfolio_4 pair (pre-registered 2026-11-09)

## Question
portfolio_3/4 used *closed* daily P&L. LucidFlex / Topstep-style floors trail on intraday mark-to-market (or end-of-day for some firms), so an
overnight hold with no stop can breach intraday even if it closes inside the floor. Does the pair overnight_dip_v2 + ag_all_weather_v2_1c stay
inside a $2,000 intraday-trailing floor on 2010–23?

## Data and separation
Training 2010–23 only, MNQ 1-min. Both legs frozen; nothing chosen. 2024–26 not loaded.

## Method
- Overnight leg: for each held night, path of unrealized P&L at every 1-min low from the 18:05 fill to the 09:45 exit (worst mark = min low − entry).
- Intraday leg: per trade, worst mark bounded by the stop (stop_risk from the engine) — conservative: assume the stop level is touched.
- Equity path = closed equity + running unrealized; high-water mark on the same path; breach if HWM − equity ≥ floor, floors $2,000 / $2,500 / $3,000.
- Report: number of breaches of each floor, worst intraday trailing DD, date; compare with the closed-DD figure (1,633); daily-loss distribution
  (worst MTM day) against a $1,000 daily-loss limit (count of days exceeding).

## Decision
Report only (no parameter and no deployment). If the intraday-trailing DD ≥ $2,000, the staging rule (one leg until ≈$3k cushion) applies to this
pair too and PORTFOLIO_4 is annotated accordingly.

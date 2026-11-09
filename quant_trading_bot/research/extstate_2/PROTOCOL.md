# extstate_2 — CBOE SKEW as a prior-close conditioner (pre-registered 2026-11-09)

## Motivation
extstate_1 tested VIX level / VIX-VIX3M / 200d states (no day-direction edge; backwardation stand-aside later adopted for morning sleeves).
SKEW (CBOE, free, daily since 1990) measures tail-risk pricing independent of VIX level and has not been used anywhere in this project.
Data: data/external/SKEW_History.csv (downloaded 2026-11-09 from cdn.cboe.com). Only the close strictly before the decision time is used.

## Features (from the last CBOE close before the 18:00 reopen / before the trading day)
F1 SKEW 1-year rolling percentile tercile (low / mid / high)   F2 sign of 5-day SKEW change (up / down)   F3 SKEW minus its 20-day mean tercile.

## Targets (training 2010–23 only; 2024–26 not loaded)
T1 overnight_dip_v2 nights (MNQ, 18:05 -> 09:45, MNQ+MES co-dip): per-night P&L by feature state.
T2 all nights, MNQ long 18:05 -> 09:45, by feature state (does any SKEW state carry an unconditional overnight premium?).
T3 ag_all_weather_v2_1c trades (training run, $150 budget off) attributed to their trading day's feature state.

## Decision rule
A state is adoptable as a *stand-aside* only if (a) its removed nights/trades are net negative, (b) that removal is worse than ≥ 190 of 200
same-count random removals, and (c) the remaining rule still passes its original gates (overnight: ≥ 11/14 years, max-year ≤ 40%, DD < 2k;
All-Weather: DD ≤ current, positive years ≥ current). A state is adoptable as a *new unconditional rule* (T2) only under the full overnight gate
incl. ≥ 190/200 random-night placebos and ≥ 100 nights. 3 features × ≤ 3 states × 3 targets ≤ 27 cells; nothing else will be tried on SKEW.
Deployment at Devin's discretion beside existing ledgers; no 2024–26 scoring.

# Research memo, 2026-11-08 (Devin)

Audience: Nick, Codex, Antigravity, Claude. Purpose: stop re-running closed families; state the next three highest-information experiments.

## What is closed (training-only evidence, fixed engine, micro costs, early-close fix, $2k funded rules)

| family | search | outcome | why it fails |
|---|---|---|---|
| 15-min price rules (trend, regime, hybrid, breakout, mean-reversion, VWAP, ORB) | mass_v2: 1.2M configs x 2 bar rules, ES/NQ 2010-23 | 13 frozen, 1 of 13 holds 2024-25 (+$437/2y) | 70-95% of profit is 2020-23; all-day momentum flips sign in 2025 chop |
| 1/3/5-min counter-trend fades (VWAP, volume exhaustion, ORB fade, RSI, Keltner, stretch) | mass_1m: 198,720 configs | 0 pass training gate | each trade loses about one micro round trip; the snap-back is smaller than spread+slip+commission |
| L1 order-book imbalance, 1-second BBO | orderflow_1 (pre-registered, $29 Databento) | REJECTED | decile spread < 0.4 ticks vs 5.4-tick round trip; executable rule -$3/trade |
| Antigravity HTF sleeves (15m, 5m MTF, 30m breakout, 60m trend) | exact replication 2010-2025 | all reproduce post-2020; 2010-19 flat or negative | same regime artifact at lower frequency; 2024-25 and 2026 already consumed by sender |
| ICT / liquidity-sweep concepts (Claude round 8) | 200,928 versions | 14 "hold up" on 2021-24 validate, but validate_R negative on most; Claude's own verdict "no better" | sweep-then-reclaim is a breakout rule in different clothing |

Execution facts now measured (Databento bbo-1m 2019-25): MNQ RTH spread averages 1.5-2.0 ticks, 1 tick only 18-48% of the time, median L1 size 3-6 contracts. Re-scored at 1.75 ticks: candidates lose $70-215 per split, Portfolio E loses a third of its 2024-25 net. 1.75-tick MNQ spread is the default stress from now on.

## Rules for every new proposal
1. Mechanism first: say why the edge exists and who pays it; a parameter variant of a closed family is rejected without a run.
2. Report the 2010-2019 NQ/ES decade by year on the fixed engine before any 2020+ number; the training gate is >= 10 of 14 years positive, no year > 40% of profit, placebo-beating.
3. 2024-25 is looked at once per frozen list; 2026 is never loaded. Antigravity's Duo/Tri/5m/30m/60m have spent both.
4. Costs: $0.61/side, 1.75-tick MNQ spread, 1-tick slippage per side, 0.25 tick/contract impact.

## Next three experiments (ranked by information gain / cost)

1. **Edge attribution by regime and event day (cheap, no new data).** Decompose the 15-min survivors' and Portfolio E's trade P&L by (a) realized-vol tercile of the prior 20 sessions, (b) scheduled macro-event days (CPI, FOMC, NFP from the official calendars), (c) month-of-year, (d) day-of-week. Question: is the 2020-23 profit a volatility effect (then a vol filter is a legitimate, mechanism-based rule to pre-register) or an event-day effect (then an event-day sleeve is the test). Attribution only on training years; nothing is tuned.
2. **Overnight-gap / Globex-range mechanics at RTH open (new mechanism, existing 1-min data).** Pre-register: gap vs prior RTH close in ATR units, Globex-range position of the open, first-15-min direction; rules = gap-fill fade, gap-and-go continuation, Globex-range break; ~250 trades/yr so costs are < 10% of trade size. Not covered by mass_v2 (ORB used only the RTH range). Train ES/NQ 2010-18 + MES/MNQ 2019-23, same gates.
3. **Signed-volume order flow (needs Nick's yes, ~$160: MNQ.c.0 `trades` 2023).** The only order-flow quantity the literature supports that bbo-1s cannot give: aggressor-side volume imbalance and large-print sweeps over 1-5 min. Pre-register before download; same decision rule as orderflow_1.

Not worth repeating: any 1-60 minute price/volume rule family above; L1 imbalance variants; ICT variants; combining correlated trend legs and calling the result diversification.

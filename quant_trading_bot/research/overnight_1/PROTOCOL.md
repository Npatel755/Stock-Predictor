# overnight_1 — Globex overnight hold (pre-registered 2026-11-09, before any overnight P&L is computed)

Rule basis (Nick's screenshot of Topstep/Lucid rules): positions may be held past midnight but must be flat before the daily cutoff (Topstep 16:10 ET,
Lucid 16:45 ET). So the capturable overnight window is Globex reopen 18:00 ET -> next day's 09:30 ET RTH open (not 16:00 -> 18:00).
Hypothesis: the equity premium accrues overnight (Lou, Polk, Skouras 2019; Cliff Asness "overnight returns"); intraday-only rules here repeatedly found
"the premium is earned overnight". Prior: moderate for the raw long; the question is whether it clears one round trip per night after costs.
Data: existing ES/NQ (2010-18) and MES/MNQ (2019-23) 1-min bars (Globex sessions included). Costs: 1.75-tick MNQ / 1-tick MES spread, 1 tick slippage/side,
$0.61/side (Topstep micro). Entry: 18:05 ET bar open (first completed bar after reopen); exit: 09:30 ET open (variant 09:35 close); 1 contract; no stop
(variant: stop at 2x the prior 20-night std of the overnight move), funded lock $2k intrabar / $400 daily tracked.
Variants (14, all reported): V1 long every night MNQ; V2 long every night MES; V3 long Sunday-night only; V4 long Mon-Thu nights only; V5 long only
after a down RTH day; V6 long only after an up RTH day; V7 long only when prior-close VIX/VIX3M in contango; V8 backwardation; V9 long only when the
18:00 reopen gap vs 16:00 close is negative (dip at reopen); V10 skip nights before scheduled FOMC/CPI/NFP mornings (calendar from scripts/news_calendar);
V11 stop variant of V1; V12 V1 exit 09:35 close; V13 short every night (control); V14 long MNQ nights where ES fell > 1% intraday (stress).
Placebo: for day-filtered variants (V3-V10, V14) 200 random same-size night sets; for V1/V2 the control is the short (V13) and the zero-cost gross.
Gates: net > 0, >= 10/14 years positive, largest year <= 40%, >= 95% placebo (filtered variants), >= 100 nights, and no funded breach year.
Training 2010-2023; validation 2024-2025 one shot for passers; 2026 never loaded. No paper promotion without Nick's yes. No spend.

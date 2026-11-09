# dplus_3 - opening-leg checks on ag_arch_d_plus_v2 (pre-registered 2026-11-09, training 2010-23 only)

D+ v2 (Crabel 15m + MNQ 60m trend + MES 30m trend, strict 1c router, $150 budget) is now the planned opening leg (research/DEPLOYMENT_PLAN.md),
so its assumptions get the checks the book legs already had. Nothing is changed unless the adoption rule below is met; 2024-26 never read.

A. Macro-event-day stand-aside (same family news_round1 tested on the Codex sleeves - slight help, not enough years; never tested on the AG
   sleeves). Cells (declared): skip trades entered on FOMC statement days; on CPI / Employment-Situation (08:30 ET) release days; on either.
   Calendar: research/news/official_calendar_2010_2026.csv (families FOMC, CPI, EMPLOYMENT; dates known in advance). Post-hoc removal of
   the routed trade list (router re-fill ignored; stated approximation). Adoption rule: the removed set is net negative AND >= 190 of 200
   random same-count day removals leave a higher net AND >= 11/14 positive years remain. Otherwise recorded as a state.
B. Execution stress (report only): slippage 2 ticks/side; spread 2 ticks; both. Report net, $/trade, marked DD retention vs base.
   Promotion veto if net retention under "both" < 50 % (the leg would be too execution-sensitive to anchor the plan).
C. Engine risk-gate sensitivity (report only, no change): daily_loss {200, 400 = base, off}; hard_drawdown {1000, 2000 = base, off}.
   Reported as marked DD and net per cell; it documents how much of the $882 marked DD is the gates' doing.
Deliverable: reports/DPLUS_3_TRAINING.md/json.

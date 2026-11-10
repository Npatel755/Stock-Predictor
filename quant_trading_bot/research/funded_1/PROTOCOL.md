# funded_1 - prop-firm rule model from Nick's notes (pre-registered 2026-11-09, training 2010-23 only; policy study, no strategy change)

Rules modeled (from Nick's Topstep / Tradeify notes of 2026-11-09 - to be verified against the firms' current policies before acting):
  Floor variants on a $50k account: STATIC $2k (fixed floor), TRAIL_EOD $2k (trails end-of-day closed balance, stops trailing once it reaches the
  start balance), TRAIL_MARK $2k (staging_1's intraday-marked variant, harshest). Daily loss limit $1,000 on closed daily P&L (DLL; Topstep Daily Payouts+,
  Tradeify Select Daily) or none (Tradeify Select Flex).
  Evaluation: pass when closed profit >= target ($3,000 trailing / $4,000 static) AND best day <= 55 % of total profit; fail on floor or DLL breach.
  Funded payout eligibility: winning days = closed day >= +$150 (5 needed per payout); consistency path = best day <= 40 % of net.
Configurations (frozen legs, same trade lists as staging_2): L1 overnight v2, L2 All-Weather 1c, L3 D+ v2, L3G gap-sized D+, Book A (L1+L2), Book A SKEW-sized.
Sizes: evaluation 1-4 contracts via linear scaling of each trade's net and mark (declared approximation: ignores the engine's budget / hard-DD gates
at size, so k >= 2 is optimistic on trade admission; dplus_5 showed Crabel is exactly linear). Funded phase at 1c and (for L3G / SKEW book) their own sizing.
Metrics, 157 monthly starts x 12 months: evaluation P(pass), median trading days to pass, P(fail), P(neither in 12m); expected resets per pass;
funded P(breach) per floor variant, P(DLL hit), winning ($150+) days per year, best-day / annual-net consistency ratio, median 12m net.
No gates - the output is the decision table for which firm / variant / evaluation size fits each configuration. Nothing deployed.

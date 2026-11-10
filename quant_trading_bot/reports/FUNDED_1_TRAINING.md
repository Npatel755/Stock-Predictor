# funded_1 - prop-firm rule model from Nick's notes (training 2010-23 only; protocol research/funded_1/PROTOCOL.md; policy study, nothing deployed)

Rules per Nick's 2026-11-09 Topstep / Tradeify notes (verify against current policy before acting): $50k account, $2k max loss (STATIC fixed floor, or end-of-day
TRAILING that stops at the start balance), $1,000 daily loss limit where the account has one, evaluation target $3k (trailing) / $4k (static) with best day <= 55 %
of profit, payouts after 5 winning days >= $150 or via a 40 % best-day consistency path. Position cap (5 minis / 50 micros) never binds at the sizes modeled.
157 monthly starts, 12 months each; frozen legs from staging_2; sizes by linear scaling of each trade (declared approximation: optimistic on trade admission at
>= 2c because the engine's $150-per-contract budget admits extra high-ATR trades at larger budgets - see the engine check below).

## Evaluation: P(pass within 12 months) / P(fail) / median trading days to pass
| configuration | Topstep trailing ($3k) 1c | 2c | 3c | 4c | Topstep static ($4k) 1c | 2c | 3c | 4c | Tradeify Select 1c | 2c | 3c |
|---|---|---|---|---|---|---|---|---|---|---|---|
| overnight v2 | 7/0 %/25d | 18/15 %/12d | 24/15 %/10d | 26/24 %/7d | 3/0 %/28d | 10/17 % | 22/15 % | 24/24 % | 7/0 % | 22/9 % | 23/15 % |
| All-Weather 1c | 17/0 %/49d | 28/4 %/31d | 20/28 % | 26/45 % | 15/0 %/61d | 21/3 % | 22/14 % | 22/29 % | 17/0 % | 25/3 % | 20/27 % |
| D+ v2 | 17/0 %/52d | 34/0 %/35d | 35/8 %/26d | 39/12 %/22d | 13/0 %/63d | 29/0 %/44d | 34/0 %/30d | 33/11 % | 17/0 % | 32/0 % | 35/8 % |
| **gap-sized D+** | 23/0 %/44d | 40/1 %/31d | **43/4 %/26d** | 38/21 % | 15/0 %/45d | 33/0 %/37d | **38/4 %/30d** | 31/16 % | 23/0 % | 39/1 % | 44/3 % |
| Book A | 28/4 %/53d | 36/13 % | 41/22 % | 42/29 % | 18/0 %/61d | 29/12 % | 33/19 % | 34/31 % | 28/4 % | 38/12 % | 42/22 % |
| Book A SKEW | 35/8 %/37d | 40/23 % | 38/40 % | 29/60 % | 34/5 %/43d | 33/20 % | 35/38 % | 29/54 % | 35/8 % | 41/22 % | 43/28 % |

Reading: the target is 2-3 years of 1c earnings, so at 1c nothing passes within a year more than ~35 % of the time (but nothing fails either). The best
pass-per-fail trade is gap-sized D+ at 3 micros (trailing 43 % / 4 %; static 38 % / 4 %); at 4c fails rise faster than passes everywhere, and the overnight /
SKEW books fail often at size because their worst nights hit the $2k floor or the $1k daily loss. Plan for 1-3 evaluation attempts at 3c (a reset is $109-149).

## Funded phase (1c unless stated): P(floor breach) / P($1k daily-loss hit) / $150+ winning days per year / best-day share of annual net / median 12m net
| configuration | static + DLL | EOD-trailing + DLL | EOD-trailing, no DLL | intraday-marked (staging_1) | win days / yr | best-day share | median 12m net | worst day |
|---|---|---|---|---|---|---|---|---|
| overnight v2 | 0 / 0 % | 0 / 0 % | 0 % | 0 % | 1 | 0.30 | +$432 | -$666 |
| All-Weather 1c | 0 / 0 % | 0 / 0 % | 0 % | 0 % | 3 | 0.35 | +$425 | -$603 |
| D+ v2 | 0 / 0 % | 0 / 0 % | 0 % | 0 % | 2 | 0.31 | +$526 | -$330 |
| D+ v2, 2c | 0 / 0 % | 0 / 0 % | 0 % | 0 % | 8 | 0.31 | +$1,052 | -$659 |
| gap-sized D+ | 0 / 0 % | 0 / 0 % | 0 % | 0 % | 3 | 0.31 | +$783 | -$402 |
| gap-sized D+, 2c | 0 / 0 % | 0.6 / 0 % | 0.6 % | 0.6 % | 11 | 0.31 | +$1,566 | -$803 |
| Book A | 0 / 0 % | 4.5 / 0 % | 4.5 % | 4.5 % | 4-5 | 0.20 | +$1,003-1,071 | -$666 |
| Book A, 2c | 5.1 / 13.4 % | 12.1 / 10.2 % | 14.6 % | 15.3 % | 9 | 0.20 | +$1,691-1,867 | -$1,331 |
| Book A SKEW | 3.8 / 7.6 % | 7.0 / 7.6 % | 7.6 % | 7.6 % | 7 | 0.23 | +$1,149-1,387 | -$1,007 |

Reading: a STATIC floor removes Book A's 4.5 % breach entirely (banked profit protects from day one; no lock wait), and the D+ legs are clean under every
variant even at 2c. The $1,000 daily-loss limit only bites the 2c overnight / SKEW books (8-23 % of years) - those belong on a no-DLL account (Tradeify
Select Flex) or stay at 1c. Payouts: at 1c a 5-winning-day payout takes a year or more; D+ at 2c produces 8-11 qualifying days a year. The 40 % consistency path
is satisfied by every configuration (best day 20-35 % of annual net).

## Engine check of the 3c evaluation size
ENGINE_CHECK

Decision (policy, for Nick): Topstep $50k Static; evaluation with gap-sized D+ at 3 micros; funded phase per research/DEPLOYMENT_PLAN.md with the static floor
noted (Stage 1 can start as soon as $500 is banked, no lock needed). Not evidence for 2024-26 (sealed). Script: scripts/funded_1_pilot.py; data: reports/FUNDED_1_TRAINING.json.

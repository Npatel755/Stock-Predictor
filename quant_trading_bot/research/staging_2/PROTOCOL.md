# staging_2 - gap-sized D+ as the opening leg of the funded ladder (pre-registered 2026-11-09, training 2010-23 only; derived from dplus_5)

Same provisional floor model and ladder as staging_1 (trailing $2k floor, lock at +$2.1k to +$100; single leg -> Book A at $500 cushion -> SKEW-sized
book at $1.5k -> + D+ at $3k). New legs: L3G = D+ v2 with 2 contracts on gap-continuation Crabel drives (dplus_5), else 1.
Policies: S_3 (static D+ v2 1c), S_3G (static gap-sized D+), P_L3 (staged from D+ v2, the documented plan), P_L3G (staged from gap-sized D+; stage 3 adds L3G).
Scoring: 157 monthly 12-month starts, variants A (intraday marks) / B (closed equity); 2,000 one-year block-bootstrap paths.
Adoption rule (P_L3G replaces P_L3 as the plan's Stage 0 only if ALL): survival A >= P_L3's; bootstrap breach A <= 1 %; median 12m net >= 1.2 x P_L3's;
p10 12m net >= P_L3's. Otherwise plan unchanged, result recorded. Rule semantics still need prop-firm confirmation (unchanged caveat).

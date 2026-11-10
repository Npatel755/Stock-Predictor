# dplus_5 - gap-alignment state as a sizing input for ag_arch_d_plus_v2 (pre-registered 2026-11-09, training 2010-23 only; derived from dplus_4)

S1: Crabel 15m trades whose drive agrees with the opening gap (dplus_4 definition) take 2 contracts; all other D+ v2 trades 1 contract.
C1 (mirror control): 2 contracts on gap-fade Crabel trades instead. Reference: D+ v2 1c (+$17,576, marked DD $882) and v2_2c ($300 budget: +$27,327, $1,453).
Method: post-hoc doubling of net and stop_risk on the routed D+ v2 trade list (exact under the engine's per-contract linearity for a fixed
qty; the $300 budget admits the same trade set; daily-loss/hard-DD gates never bound at 1c in dplus_3 - re-checked on the marked path here).
Gates (all required for a Future-strategies ledger): S1 net/marked-DD > both references; S1 marked DD < $1,453 and 0 touches of $2k;
S1 beats C1 on net and on marked DD; S1 1-year block-bootstrap breach of a $2k floor (20-day blocks, 2,000 paths) <= 1 %; >= 11/14 years.
Derived on the same split -> one-split evidence; forward paper decides.

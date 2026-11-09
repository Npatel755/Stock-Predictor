# dplus_4 - audit of Antigravity's Crabel gap-alignment / ag_arch_d_plus_v3 (fixed engine, training 2010-23 only; protocol research/dplus_4/PROTOCOL.md)

Gap = 09:30 ET 15m bar open minus the previous trading day's last RTH close (Antigravity committed no script and no definition). Gate applied post-hoc to the routed D+ v2 trade list.

| set | trades | net | $/trade | years>0 | marked DD |
|---|---|---|---|---|---|
| Crabel 15m, all (routed, under D+ v2) | 493 | +$8,105 | 16.44 | 11/14 | $520 |
| gap-continuation drives (kept) | 261 | +$5,566 | 21.32 | 13/14 | $705 |
| gap-fade drives (removed) | 232 | +$2,540 | 10.95 | 7/14 | $684 |
| D+ v2 (base) | 1,398 | +$17,576 | 12.57 | 12/14 | $882 |
| D+ v3 = gated Crabel + 60m trend + MES 30m | 1,166 | +$15,037 | 12.90 | 12/14 | $879 |
| mirror control (fades only + other sleeves) | 1,137 | +$12,011 | 10.56 | 9/14 | $1,043 |

Placebo: 190 of 200 random same-count Crabel-trade removals leave a lower net (exactly at the bar).

Gates: g1 removed set net <= 0 or per-trade < 1/3 of kept: **FAIL** (+$2,540, $10.95 vs $7.11); g2 placebo >= 190: pass (190); g3 kept years >= 11: pass (13);
g4 v3 marked DD < $882 and net >= 85 %: pass ($879, 85.6 %); g5 mirror clearly worse: pass. **4 of 5 - no ledger.**

Reading: the gap-alignment state is real in direction (continuation drives earn twice the fade drives per trade, and the fades are the years-inconsistent half), but the
fades are still net positive at $11/trade after costs, so removing them is a net-for-nothing trade: D+ v3's marked drawdown is $879 vs $882 - the claimed $431 does not
reproduce, nor do 14/14 years (+$8,498 on 336): on the fixed engine it is 13/14 on 261 trades for +$5,566. Same verdict as the SKEW and bond states: a recorded state,
usable later as a sizing input once a cushion exists, not a filter. Nothing deployed; D+ v2 unchanged. Not evidence for 2024-26 (sealed).
Script: scripts/dplus_4_pilot.py; data: reports/DPLUS_4_TRAINING.json.

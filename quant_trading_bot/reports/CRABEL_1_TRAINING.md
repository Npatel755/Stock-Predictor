# crabel_1 — Crabel open-drive on MES and the backwardation attribution (training 2010–2023; 2024–26 sealed)

Protocol: research/crabel_1/PROTOCOL.md. Script: scripts/crabel_1_pilot.py. Raw: reports/CRABEL_1_TRAINING.json. Engine default costs.

## Q1 — Crabel open-drive on MES (ES 2010–18, MES 2019–23): REJECTED
−$1,973 on 457 trades, 1 of 14 years positive, beats 12 of 20 same-count random-day placebos (placebo mean −$1,959 — i.e. indistinguishable from random).
The open-drive pattern that earns +$6.5k on NQ does nothing on the S&P contract. A mechanism confined to one index contract is weaker evidence than one that
transfers; this lowers the prior on the Crabel leg of Architecture C (it stays on paper as deployed).

## Q2 — per-sleeve P&L on days after a VIX > VIX3M close (backwardation) vs other days
| sleeve | all | other days $/trade (n) | backwardation days $/trade (n) |
|---|---:|---:|---:|
| Arch C Crabel 10:00 | 6,468 | +12.1 (596) | **−18.3 (42)** |
| Arch C / Quad 30m morning trend lb16 | 7,372 | +9.1 (934) | **−17.9 (65)** |
| Arch C / Quad 60m trend lb12 | 5,973 | +7.2 (847) | −1.5 (52) |
| All-Weather 30m breakout lb8 | 7,096 | +11.4 (704) | **−22.6 (41)** |
| Quad 30m afternoon trend lb8 | 4,233 | +3.2 (843) | **+28.2 (56)** |

Reconciliation: extstate_1's "trend/breakout sleeves earned on backwardation days" holds for the afternoon trend sleeve only; every morning sleeve loses on
those days. The `ag_arch_c_v2` filter (stand aside after a backwardation close) is therefore well-founded, and the same filter would likely help
`ag_all_weather` (breakout −$925 on 41 such days) — an idea for a future pre-registered round, not applied here. Nothing deployed; 2024–26 untouched.

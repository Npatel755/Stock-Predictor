# archc_4 — NQ-only drive: trade only when MES does NOT confirm (training 2010–23 only; derived from archc_3)

Protocol research/archc_4/PROTOCOL.md; script scripts/archc_4_pilot.py; raw reports/ARCHC_4_TRAINING.json. Fixed engine; 2024–26 not loaded.
Declared derivation: this is the flip of the archc_3 gate, formed after seeing archc_3 on the same split — hence the stricter gates and the coherence requirement.

| cell | net | trades | $/trade | closed DD | +years | max-yr | 2010–19 | beats random same-count subsets |
|---|---|---|---|---|---|---|---|---|
| Arch C baseline | +16,070 | 1,980 | 8.12 | 1,596 | 11 | 42 % | +5,050 | – |
| R1 Arch C, all sleeves, MES must NOT agree | +12,240 | 1,058 | 11.57 | 1,515 | 10 | 32 % | +3,474 | 193/200 |
| R2 Arch C, trend sleeves only | +14,086 | 1,282 | 10.99 | **957** | 10 | 31 % | +3,263 | **199/200** |
| All-Weather 1c baseline | +16,520 | 1,590 | 10.39 | 1,256 | 8 | 43 % | +2,874 | – |
| R3 All-Weather, MES must NOT agree | +9,984 | 896 | 11.14 | 1,085 | 9 | 25 % | +2,307 | 120/200 |

## Verdict: 0 of 3 pass — recorded, not deployed
- R2 is the best risk-adjusted Arch C variant seen (net/DD 14.7 vs 10.1; DD −40 % for −12 % net; 199/200), but it misses the positive-years gate by one
  (10 vs 11) and, decisively, the mechanism does not transfer: on the All-Weather MNQ sleeves the same gate is indistinguishable from random (120/200).
  A derived hypothesis that only works on the family it was derived from is the textbook false positive; it stays a note.
- What is robust across both rounds: *requiring* ES confirmation is harmful for NQ intraday sleeves (archc_3); *forbidding* it helps only Arch C.
- Would re-open only with independent evidence (e.g. the same gate on NQ/ES full-size data from a different vendor or a different era) — not by re-testing on 2010–23.

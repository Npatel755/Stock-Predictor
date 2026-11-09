# overnight_4 — stress diagnostics of overnight_dip_v2 (training 2010–2023 only; no parameter changed)

Protocol: research/overnight_4/PROTOCOL.md. Script: scripts/overnight_4_pilot.py. Raw: reports/OVERNIGHT_4_STRESS.json.
Rule under test (frozen, on paper): long 1 MNQ 18:05 → 09:45 ET when both MNQ and MES 18:00 reopen gaps ≤ −0.5 × sd of their previous 20 gaps.
Training: +$11,797 / 490 nights / 12 of 14 years / closed DD $1,646 / 2010–19 +$4,969.

| check | result |
|---|---|
| Plateau (k 0.25–1.0 × sd, window 10–40 nights, 30 cells) | all 30 cells net > 0 (+$7.4k … +$11.8k); the rule is the best cell. Neighbours k 0.375–0.625 × w 15–30: all positive, 11–13 positive years, DD $1,579–2,075; **k 0.375 / w 15 has DD $2,075 → protocol's "fragile" flag fires**. k ≤ 0.25 cells have DD $2.9–3.6k (too many weak nights). |
| Intrabar drawdown (marked at the overnight low) | max $1,751 (2020), $1,738 (2022), $1,081 (2021); every year before 2020 ≤ $571 |
| Block-bootstrap Monte Carlo, 5,000 paths | 1 yr (35 nights): P(closed DD ≥ $2k) 0.3 %, P(intrabar DD ≥ $2k) 0.7 %, annual net p5/p50/p95 −$542 / +$573 / +$2,935. 2 yr: 2.0 % / 3.0 %, +$1,439 median. Excluding 2020–22: 0 % breach, median +$381 per year |
| Tail | worst nights −$666 (2020-03-15), −$505, −$461; 5 nights ≤ −$400, 2 ≤ −$500; intrabar worst −$617. **Top 5 % of nights (24) = 101 % of net** — the edge is a tail of large reversal nights, the other 466 nights net to zero |
| Calendar | Sunday nights 137 of 490, +$3,335; weekdays +$8,462 (Tue +$3,837, Thu +$3,058, Mon +$680, Wed +$887); one night lacked a 09:45 bar |
| Slippage 2 / 3 ticks per side | +$11,307 / +$10,817, 12 positive years both |

## Reading
- Robustness is good in the one way that matters for the funded floor: no plateau cell is negative, and the 1-year breach probability is under 1 % even with 2020–22 included. The protocol flag is technical (one neighbour at DD $2,075) and reported as such.
- The honest caveat is the tail concentration: expect long flat stretches (median ≈ +$400–600 per year outside stress regimes) punctuated by a few $200–700 nights; a year without a volatility episode will look like noise. The paper comparison v2 vs v1 therefore needs many months, not weeks.
- No change to the rule; v2 stays on paper as deployed; 2024–26 remain sealed.

# overnight_2 — reopen-dip overnight hold follow-up (2026-11-09)

Protocol research/overnight_2/PROTOCOL.md (pre-registered). Long 1 contract at the 18:05 ET bar open on nights whose 18:00 reopen is below the prior
RTH 16:00 close (Sunday: vs Friday close — fixed before validation, after the first run dropped Sunday nights), exit next 09:30 open; Topstep micro costs.
32 variants (16 per product), 200 same-size random-night placebos each, gates incl. nightly-equity max DD < $2,000. Script scripts/overnight_2_pilot.py;
all numbers in reports/OVERNIGHT_2_TRAINING.json.

## Training 2010–2023 (MNQ; MES is weaker throughout)
| variant | net | nights | $/night | +years | 2010–19 | largest-year share | max DD | placebo beats |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D0 gap < 0 | +5,072 | 1,481 | 3.4 | 10/14 | +2,089 | 66% | 3,852 | 188/200 |
| D1 gap ≤ −0.05% | +5,493 | 1,130 | 4.9 | 12/14 | +2,221 | 59% | 3,456 | 191 |
| D2 gap ≤ −0.10% | +6,220 | 837 | 7.4 | 11/14 | +2,099 | 51% | 2,477 | 196 |
| D3 gap ≤ −0.20% | +7,766 | 538 | 14.4 | 11/14 | +1,482 | 43% | 1,394 | 199 |
| D4 gap ≤ −0.5σ | +7,228 | 446 | 16.2 | 11/14 | +1,870 | 40.2% | 1,303 | 199 |
| **D5 gap ≤ −1.0σ** | +3,386 | 258 | 13.1 | 10/14 | +1,029 | 39% | 1,186 | 193 → **passes** |
| X1 dip & backwardation | +2,802 | 96 | 29.2 | 10/12 | +611 | 41% | 865 | 196 (too few nights) |
| S2 dip, exit 09:35 | +8,529 | 1,481 | 5.8 | 11/14 | +3,123 | 43% | 2,769 | 195 |
Other filters (contango, VIX level, stop, prior-day direction, weekday, Sunday-only) add nothing or hurt; Sunday nights alone lose.

## One-shot validation 2024–2025 of the single frozen passer (MNQ D5)
2024 −$1,031, 2025 +$1,751 → +$720 on 34 nights, 1 of 2 years positive, max DD $3,402 (nightly equity) → **NOT validated** under the frozen rule.

## Verdict
The dip-night overnight premium is real and consistent in direction: deeper reopen dips earn more per night (3 → 16 $/night from D0 to D4), 10–12 of 14
training years are positive, and every threshold beats 94–99.5% of random same-size night sets. It is still not a fundable edge: 2020–22 supplies 40–66% of
the profit, 2010–19 is ≈ $100–220 per year at 1 contract, the 2023 year is negative in every variant, and the one variant that cleared the gates failed the
2024–25 check (2024 negative; drawdown over the $2k lock). The 2024–25 split is now spent for this family — no further overnight variants may be validated
on it. Multiplicity: 52 overnight variants total; 1 passer is consistent with chance at the 95% placebo gate. Lead status: strongest after-cost family found,
not an edge; forward paper evidence (an overnight paper sleeve, 16:05 safety flatten) is the only remaining clean test if Nick wants it.

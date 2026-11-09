# swing_1 — multi-day mean-reversion holds on MNQ/MES (training 2010–23 only)

Protocol: research/swing_1/PROTOCOL.md (pre-registered). Script: scripts/swing_1_pilot.py. Raw: reports/SWING_1_TRAINING.json.
Data: MNQ/MES 1-min train split only; 2024–26 not loaded. 1 contract, entry at the 18:05 reopen after the signal close, exit MOC;
micro costs ($0.61/side, 1.75/1.0-tick spread, 1 tick slip). Marked DD uses each held session's low. 200 same-count-per-year random-entry placebos.

## Result: 0 of 48 long configs pass; the family is closed
The mechanism is real in sign but one micro contract held for days is far too large for a $2,000 floor.

| config (long) | net | trades | $/trade | +years | 2010–19 | marked DD | placebos beaten |
|---|---|---|---|---|---|---|---|
| MNQ 5-day closing low, exit on first up close | +16,546 | 414 | 40 | 10/14 | +2,981 | **4,231** | 195/200 |
| MNQ 5-day closing low, fixed 3 days | +19,149 | 363 | 53 | 12/14 | +3,313 | **5,362** | 194/200 |
| MES 5-day closing low, fixed 3 days | +13,143 | 352 | 37 | 9/14 | +261 | **3,290** | 198/200 |
| MES RSI(2) < 10, exit on first up close | +6,075 | 183 | 33 | 10/14 | −156 | **3,206** | 192/200 |
| MNQ 3 lower closes, exit on first up close | +10,121 | 175 | 58 | 10/14 | +2,289 | **3,094** | 193/200 |

- Every one of the 48 long cells has marked DD ≥ $2,457 (median ≈ $4,200); the smallest-DD cells are the weakest ones. All 48 short mirrors lose.
- Dip selection adds to drift: the 5-day-low cells beat 194–198 of 200 random same-count entry sets on both contracts, coherent across exits (5 of 6
  unfiltered cells > 190 or close). RSI(2) and 2/3-lower-closes are weaker and inconsistent across exits.
- The 200-day-SMA filter *hurts* everywhere (removes the 2020/2022 bear-market bounces, which supply most of the profit) — the effect is a
  stress-regime bounce, like the overnight reopen-dip, not an uptrend pullback.
- 2010–19 is small or negative on MES in most cells; the profit is 2020–23-heavy (max-year share 26–47% in the best cells).

## Why it fails the floor (structural, not tunable)
A 3-day MNQ hold has a typical adverse excursion of 1–2% of a $55k notional = $550–1,100 per trade at 2020+ price levels; three in a row
is the floor. MES at $34k notional only scales that by 0.6. No smaller index future exists, and adding a stop to a mean-reversion hold
would be post-hoc here (not pre-registered) and historically converts the bounce into a stop-out stream. Not deployed; nothing re-scored on 2024–26.

## Do not repeat
Multi-day close-to-close mean reversion at 1 micro contract under a $2k floor (either contract, with or without trend filter).
A pre-registered follow-up would only be worthwhile with a mechanism that bounds the excursion (e.g. the 1-night version already on paper
is the bounded form of this effect).

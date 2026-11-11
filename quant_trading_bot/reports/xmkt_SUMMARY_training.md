# xmkt: rates (ZN) and micro FX (M6E / M6A / M6B) as new evaluation sleeves (fork A, 2026-11-11, TRAINING 2010-23 only)

Verdict: REJECTED. 40 pre-declared cells, 0 screen passers, so no pass-rate runs. No cell has gross edge large enough to cover realistic costs.
Each stream's correlation with the eval_8 book is about 0 (rho -0.02 to +0.07), so these would diversify the book if they had edge, but none does.

## Topstep tradability (help.topstep.com "When and What Products Can I Trade?", read 2026-11-11)
- ZN (10-Year Note) and M6E are permitted for the Combine. M6A and M6B appear on the Launchpad allowed list. No micro ZN is listed.
- Fees page: ZN $2.62, M6E $1.00.
- All positions must be flat by 3:10 PM CT (16:10 ET). Trading resumes at 5:00 PM CT (18:00 ET). Every trade here exits by 16:00 ET.

## ZN: 10 cells (`scripts/xmkt_zn_train.py`, `reports/xmkt_zn_training.json`)
- Data: hourly ZN.c.0 (Databento, on hand).
- Costs: 1.5 ticks per side plus $2.62 commission per side, $52 round trip per contract.

| Cells | Gross per trade | Net per trade at the cheapest realistic cost ($21 round trip: 1 tick + commission) | Profit factor | Years positive |
|---|---|---|---|---|
| Noise band, ORB | about +$7 | about -$14 | 0.44-0.55 | 0/7 in each half |
| Daily trend (TSMOM) | -$6 to +$5 | | 0.65-0.73 | 0/7 in each half |
| Intraday momentum | +$2 to +$3 | | 0.22-0.25 | 0/7 in each half |

- Placebo: the noise-band and ORB cells beat 189-195/200 random-side controls, so they have the right direction but the gross edge is too small.

## FX: 30 cells (`scripts/xmkt_fx_train.py`, `reports/xmkt_fx_training.json`)
- Cells (10 per pair): London breakout of the Asia range, NY opening-range breakout, noise band from 03:00 or 08:00, and daily trend.
- Data: free HistData 1-minute bid bars, 2010-2023 (`scripts/xmkt_fetch_histdata.py` -> `data/external/xmkt_histdata/`).
- Clock check (`scripts/xmkt_fx_clock_check.py`, `reports/xmkt_fx_clock_check.json`):
  - The first-Friday 08:30 ET spike and the 17:00 Sunday open confirm New York time with daylight saving.
  - Fall-gap weeks from 2019 are an hour off.
  - Rule applied: drop all spring-gap and fall-gap weeks, plus 5 noisy AUD/GBP year-regimes.
- Results:
  - Gross per trade is -1.28 to +0.66 pips. Costs are 5.6 / 6.0 / 7.2 pips round trip at the directive's micro costs, or about 2.4-2.8 pips at full-size costs (still all negative).
  - Placebo: 12-163/200, which is chance level.
  - Profit factor 0.32-0.83; at most 1 of 7 years positive in any half.
  - Daily Sharpe -0.09 to -0.32; lift at the best weight -0.007 to -0.04 in both halves.

## Lessons
- Within Topstep hours (flat by 16:10 ET, so no overnight carry), intraday breakout, noise-band and trend rules have about zero gross edge on EUR/AUD/GBP 2010-23, and less than half a tick on ZN.
- Rates and FX on Topstep's permitted list do not supply the uncorrelated edge the evaluation needs. Do not re-run these families.
- HistData FX shares the gold clock defect: fall-gap weeks from 2019 are an hour off.

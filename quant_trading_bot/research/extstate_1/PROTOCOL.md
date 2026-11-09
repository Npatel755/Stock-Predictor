# extstate_1: daily external state (implied vol, term structure, long-term trend) as point-in-time day filters / day-direction signals (pre-registered 2026-11-09)

Data. Free CBOE daily history: VIX and VIX3M closes (data/external/*_History.csv; FRED VIXCLS as fallback). ES/NQ daily closes
derived from the 1-min training data. Everything is used as of the PRIOR day's close (state known before 09:30 ET). Training
2010-2023 only; validation 2024-25 once for a frozen passer; 2026 never loaded. Costs and products as anomaly_1.

States (each a boolean per day, from prior close): contango = VIX3M/VIX - 1 > 0; backwardation = < 0; vix_hi / vix_lo = VIX in
top / bottom tercile of its trailing-252-day distribution; above200 / below200 = ES close vs 200-day mean; vix_up5 / vix_dn5 =
5-day VIX change sign. 8 states.

Test 1 - day direction (MNQ, MES): enter 09:45 open, exit 15:54 close, long on {contango, above200, vix_lo, vix_dn5} days,
short on {backwardation, below200, vix_hi, vix_up5} days, plus the two combos (contango & above200 long; backwardation &
below200 short). 10 variants x 2 products = 20. Placebo: random direction on the same days (20 draws).
Test 2 - state filter on the fixed 15m MNQ momentum rule of anomaly_1 C (lb24, 09:45-15:30, 2.0 ATR, 3R, hold 24, flat 15:55):
trade only on days in state S, for each of the 8 states. Placebo: random day masks with the same number of days per year (20).

Gates as anomaly_1 (net > 0, >= 10 of 14 years positive, max year <= 40%, >= 95% of placebos beaten, >= 100 trades). PASS ->
freeze and validate once; else REJECTED. Nothing promoted to paper from this round.

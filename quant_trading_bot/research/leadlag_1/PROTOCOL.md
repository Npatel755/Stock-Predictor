# leadlag_1: cross-contract lead-lag between ES and NQ at 1 minute (pre-registered 2026-11-09, before any result is seen)

Hypothesis. Index futures are arbitraged within seconds, so any 1-minute lead-lag should be ~zero. The testable residual is the
idiosyncratic component: when one contract moves far more than its beta-implied share of the other's move in the last 1-5 min,
does the laggard catch up (continuation of the leader's move) or does the leader revert? Either direction would be the first
non-trend, non-order-flow mechanism on data already on disk; if neither beats micro costs the cross-asset road is closed too.

Data. Databento 1-min ES and NQ continuous, train split only (2010-01 .. 2023-12, RTH 09:30-16:00 ET), joined on bar close
timestamp (both closes known at the same instant; signal at close t, fill at next bar open t+1 min, no lookahead). MES/MNQ
2019-23 are not used separately (the minis define the signal; costs are micro). Validation 2024-25 is run once only if a
frozen config passes training; 2026 never loaded.

Features (past-only, at close t): r_ES(k), r_NQ(k) = k-min log returns, k in {1, 3, 5}; beta = rolling 20-session OLS of
1-min NQ on ES returns (lagged one session); resid(k) = r_NQ(k) - beta * r_ES(k), in units of the trailing 20-session
std of resid(k) at that k ("z"). Volatility normalisation uses only past sessions.

Test 1 (predictive). Decile of z(k) -> NQ forward return over 1/5/15 min, and ES forward return over the same, day-block t.
Gate: |t| > 4 and top-minus-bottom decile spread in MNQ ticks > 6.2 ticks (round trip: 1.75-tick spread + 2 ticks slip +
$1.22 / $0.50 = 2.44 ticks). Also report resid sign: negative slope = laggard catches up / leader reverts ("convergence"),
positive = divergence continues.

Test 2 (executable, MNQ 1 contract, marketable fills). Entry when |z(k)| >= q, q in {2, 2.5, 3}, k in {1, 3, 5}, two modes
(convergence: trade NQ against resid sign; divergence: with it), hold {5, 15, 30} min, stop 1.5 x trailing ATR(14, 1-min),
entries 09:45-15:30, flat 15:45. 54 configs. Costs: $0.61/side, 1.75-tick spread (half-spread paid each side), 1 tick slip
per side, MNQ $0.50/tick. Gate (same as mass_v2): net > 0 in >= 10 of 14 years, no year > 40% of net, beats >= 95% of 20
same-count random-time placebos, >= 300 trades. Decision: PASS -> freeze, run 2024-25 once; else REJECTED. No paper
promotion from this round regardless.

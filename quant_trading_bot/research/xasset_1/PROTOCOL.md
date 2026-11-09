# xasset_1 — cross-asset intraday information for MNQ/MES (pre-registered 2026-11-08, before any cross-asset file is opened)

Data (approved by Nick, new Databento account, cap $125, quoted $45.94): GLBX.MDP3 ohlcv-1m, continuous front month, Jun 2010 – Dec 2025:
ZN.c.0 (10-yr Treasury), 6E.c.0 (euro FX), CL.c.0 (crude). Stored under data/market/crossasset/*.parquet (gitignored). Joined to the existing
ES/NQ (2010-18) and MES/MNQ (2019-23) 1-min bars on UTC minute; features use completed minutes only and are lagged one bar before use.
Training 2010-2023; validation 2024-2025 only for frozen passers; 2026 never loaded. Costs: 1.75-tick MNQ / 1-tick MES spread, 1 tick
slippage, $0.61/side, flat 15:55 ET. Gates (all rounds): net > 0, ≥ 10/14 positive years, no year > 40% of net, ≥ 95% placebo dominance,
≥ 100 trades. No paper promotion without Nick's yes.

Hypotheses (institutional risk-on/off flow; prior low-moderate: cross-contract NQ/ES lead-lag was 0.3-0.8 ticks at 1 min, but rates/FX/oil
are different information rather than the same index):

T1 — predictive test, no rule search: at horizons 1 / 5 / 15 / 30 min, regress forward MNQ (NQ) RTH return on the lagged 5-, 15- and 30-min
returns of ZN, 6E, CL (each separately and jointly), by year. Report t-stats, decile spreads in ticks, and the share of years with the same
sign. Decision rule: a channel qualifies for T2 only if |t| > 4 on 2010-23 pooled, the top-vs-bottom decile spread exceeds the MNQ round-trip
cost (≈ 5.4 ticks) at some horizon ≤ 30 min, and ≥ 10/14 years share the sign. Otherwise T2 for that channel is not run.

T2 — executable rules (only for qualifying channels): signal = sign of the lagged cross-asset return when |z| ≥ k (k ∈ 1.0, 1.5, 2.0; z over the
prior 20 sessions' same-window returns), direction = continuation of the implied risk-on/off move (ZN up / 6E down / CL down → risk-off → short
MNQ, and vice versa), hold H ∈ {15, 30, 60} min or stop 2 ATR14(1m)·√H, entry 09:45-15:00 ET, 1 contract. 9 configs per channel.
Placebo: 20 random signal sets per config with the same count per session and random direction.

T3 — risk-off day-state filters on the fixed 15m MNQ momentum rule (anomaly_1 rule): state = prior 60 min (08:30-09:30 ET) ZN / 6E / CL move in
z-units ≥ 1 (risk-off / risk-on); filter the rule to those days, 2 directions × 3 channels = 6 variants; placebo 20 random same-size day sets.

Everything here is decided before the data is downloaded. The prediction, written now: T1 will show statistically significant but sub-cost
lead-lag (as for NQ→ES); T3 is the most plausible to pass. Report: reports/XASSET_1_TRAINING.md. Spend recorded in the report.

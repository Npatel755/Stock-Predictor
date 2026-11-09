# leadlag_1 result: ES/NQ 1-min residual lead-lag, training 2010-2023 (pre-registered research/leadlag_1/PROTOCOL.md)

**Verdict: REJECTED.** 0 of 54 executable configs pass; every config is negative. Validation 2024-25 not run; 2026 never loaded. Data: 1,305,618 aligned RTH minutes over 3,397 sessions (ES/NQ to 2018, MES/MNQ 2019-23).

## Test 1: predictive (decile of residual z(k) = NQ k-min return minus beta x ES return, in trailing-20-session SDs)

| z window | target | horizon | top-minus-bottom (ticks) | day-block t | monotone rho |
|---|---|---:|---:|---:|---:|
| z1 | NQ | 1 min | +0.252 | +2.71 | +0.38 |
| z1 | NQ | 5 min | +0.384 | +2.09 | +0.35 |
| z1 | NQ | 15 min | +1.042 | +3.41 | +0.55 |
| z1 | ES | 1 min | +0.594 | +24.81 | +1.00 |
| z1 | ES | 5 min | +0.647 | +13.90 | +0.96 |
| z1 | ES | 15 min | +0.781 | +10.23 | +0.96 |
| z3 | NQ | 1 min | +0.042 | +0.44 | -0.33 |
| z3 | NQ | 5 min | +0.533 | +1.93 | +0.18 |
| z3 | NQ | 15 min | +1.513 | +3.16 | +0.66 |
| z3 | ES | 1 min | +0.352 | +14.64 | +1.00 |
| z3 | ES | 5 min | +0.481 | +7.00 | +0.94 |
| z3 | ES | 15 min | +0.712 | +5.83 | +0.98 |
| z5 | NQ | 1 min | +0.168 | +1.83 | +0.14 |
| z5 | NQ | 5 min | +0.739 | +2.35 | +0.31 |
| z5 | NQ | 15 min | +1.633 | +2.61 | +0.66 |
| z5 | ES | 1 min | +0.298 | +12.89 | +0.99 |
| z5 | ES | 5 min | +0.474 | +5.87 | +0.95 |
| z5 | ES | 15 min | +0.733 | +4.58 | +0.92 |

Gate: |t| > 4 **and** decile spread > 6.2 MNQ ticks (round trip). Findings:
- NQ -> ES lead is real and perfectly monotone (z1 -> ES next minute: t = +24.8, rho 1.00): when NQ moves more than its beta-implied share, ES follows. But the size is 0.3-0.8 ES ticks across the extreme deciles - about one eighth of a micro round trip. Statistically undeniable, economically zero for a retail-latency marketable trader; this is the well-known NQ-leads-ES effect, arbitraged down to sub-cost size.
- NQ itself does not revert or continue after an idiosyncratic move beyond 0.2-1.6 ticks (t 0.4-3.4), i.e. no usable MNQ leg in either direction.

## Test 2: executable (MNQ 1c, 54 configs: |z(k)| >= q, convergence vs divergence, hold 5/15/30 min, stop 1.5 ATR, 20 placebos each)

- All 54 negative; best div z5 q3.0 hold 30: -9,496 over 5,232 trades (0 of 14 years positive; placebo mean -51,650).
- Convergence (fade the NQ overshoot) loses more than divergence; both lose roughly one round trip per trade. Every config beats its same-count random placebos (100%), so the residual carries a little information - as with L1 imbalance and signed volume, less than spread + slippage + commission.

## Consequence
Cross-contract lead-lag on 1-min bars is closed. An MES leg driven by NQ (the only significant direction) would need the extreme-decile spread (0.8 ES ticks at 15 min) to exceed ~4.4 MES ticks of cost; it does not, so no MES grid is warranted and none was run. With this, every mechanism testable on data on disk (price rules 1-60 min, fades, gaps/Globex, news conditioning, vol regimes, L1 imbalance, signed volume, lead-lag) has been tested under the fixed costs and rejected or found era-dependent. Remaining evidence source: the five forward paper ledgers.

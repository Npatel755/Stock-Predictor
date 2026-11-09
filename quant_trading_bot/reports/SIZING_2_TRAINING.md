# sizing_2 — $250 stop-risk budget, training 2010–23 (2026-11-09)

Protocol: research/sizing_2/PROTOCOL.md (pre-registered after sizing_1; one comparison per candidate, no further budget values). Script: scripts/sizing_1_pilot.py
with `SIZING_BUDGET=250`. Data: train split only; 2024–26 not loaded. Second sizing comparison on this split for these candidates (multiplicity noted).

| candidate | V0 $150 (deployed) | V2 $250 | V1 ∞ (sizing_1) | V2 added vs V0 | gate |
|---|---|---|---|---|---|
| ag_quad_v2 | +17,707 / 2,274 tr / DD $2,048 / 11 +yrs / 2.4 % | +23,390 / 2,422 / **$2,061** / 12 / 4.6 % | +23,319 / 2,440 / $2,061 / 12 / 4.8 % | 167 tr, +6,501 ($38.9/tr), P1 p50 +1,660 | FAIL (DD > $2,000; breach odds +2.2 pts) |
| ag_arch_c_v2 | +17,868 / 1,856 / $1,596 / 12 / 0.3 % | +21,107 / 1,951 / **$1,911** / **11** / 1.7 % | +20,028 / 1,957 / $1,911 / 11 / 1.8 % | 99 tr, +3,362 ($34.0/tr), P1 p50 +687 | FAIL (DD +$315 > +$100; positive years 11 < 12; breach odds +1.4 pts) |
| ag_all_weather_v2 | +14,073 / 1,551 / $1,455 / 8 / 0.1 % | identical to V1 (no trade has stop risk > $250) | +16,520 / 1,590 / $1,256 / 8 / 0.2 % | — | report only (V1 is already on paper as `_1c`) |

## Reading
- Capping at $250 removes the few >$250 trades (Quad 18, Arch C 6) and they were net negative, so V2 nets slightly more than V1 for Quad/Arch C — but the
  **drawdown is the same as V1 to the dollar** ($2,061 / $1,911): the extra drawdown comes from the $150–250 band itself, in the 2020 and 2022 stretches
  where those bigger stops hit in a row. The band's trades are good on average and bad in clusters, which is exactly what the $2k floor cannot absorb.
- Both fail their pre-registered gates for the same reasons as V1. The $150 budget therefore stands for `ag_quad_v2` and `ag_arch_c_v2` (and the
  unfiltered originals); the sizing question is closed — no other budget value will be tried.
- Practical meaning for the paper ledgers: when the 15-min NQ ATR is above ≈55–60 pts (1.25–1.5 ATR stops > $150) they are *meant* to sit out; only
  `ag_all_weather_v2_1c` trades through, and its own history has no trade above $250 risk, so at today's ≈$425+ stops it is in unexplored territory —
  that is the point of running it on paper beside its capped twin.
- No 2024–26 data touched. Nothing deployed from this round.

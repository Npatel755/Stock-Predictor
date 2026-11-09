# orderflow_1: top-of-book imbalance pilot on MNQ (pre-registered 2026-11-08, before any data was opened)

## Why
mass_v2 (1.2M 15-min price rules) and mass_1m (198,720 1-5 min OHLCV/volume fades) found no counter-trend leg that survives
micro costs. The remaining mechanism with literature support is top-of-book (L1) imbalance: when displayed bid size greatly
exceeds ask size the next price change is more likely up (and vice versa), over horizons of seconds to a few minutes.
This pilot asks one question: **does L1 imbalance on MNQ predict the next 1-5 minutes by more than the cost of a marketable
micro round trip?** Budget approved by Nick: ~$29 (MNQ.c.0 bbo-1s 2023, bbo-1m 2019-05-06..2025-12-31). No other purchase.

## Data (Databento GLBX.MDP3, continuous front month `MNQ.c.0`)
- `bbo-1s` 2023: per-second snapshot of best bid/ask price+size and the last trade (price, size, side) in that second.
- `bbo-1m` 2019-2025: same at 1-minute cadence (fills the empty bid/ask columns of the existing 1-min parquet).
- Classification per orderflow-microstructure skill: **proxy-only** for signed volume (only the last trade of each second
  is observed), **supported** for L1 depth imbalance and spread. Queue position / MBO analytics: not testable.
- Integrity checks before use: record counts per session, clock monotonicity, spread distribution (MNQ should be 1 tick
  almost always in RTH), roll dates of `.c.0`, DST alignment with the existing 1-min bars.

## Features (past-only; value at second t is usable at t+1 s at the earliest)
- `imb = (bid_sz - ask_sz) / (bid_sz + ask_sz)` in [-1, 1]; also 5 s / 30 s / 60 s rolling means.
- `micro = (bid_px*ask_sz + ask_px*bid_sz)/(bid_sz+ask_sz) - mid` in ticks (microprice offset).
- `lt_side_60s` = net count of last-trade sides over the trailing 60 s (proxy signed flow, labelled as such).
- `spread_ticks`, time of day, 30-min ATR from the existing 1-min bars (for normalising forward returns).

## Tests (in-sample on 2023 only; this is a screening pilot, not a 14-year gate)
1. **Predictive regression / binned means**: forward mid-change over 10 s, 60 s, 300 s vs imbalance decile, RTH only,
   with Newey-West (dependence-aware) errors. Baseline: same for a time-of-day-only model and a 1-min momentum model.
   Report in ticks and relative to the one-way taker cost (half-spread 0.5 tick + commission $0.61 = ~1.7 ticks round trip
   incl. 1 tick slippage, as in the main engine).
2. **Executable rule (the only rule family, fixed in advance)**: enter marketable when 30 s mean |imb| >= q (q in
   {0.3, 0.5, 0.7}) in the imbalance direction, hold h in {60 s, 180 s, 300 s} or exit on a 2-tick/4-tick adverse move;
   RTH 09:45-15:45 ET; flat by 15:55; one position at a time; 1 contract; engine costs ($0.61/side, 1 tick spread, 1 tick slip).
   That is 3 x 3 x 2 = 18 configurations; report all of them (no cherry-pick), plus 20 placebo runs per config (same entry
   times shuffled within the day).
3. **Counter-trend variant**: same rule entered against the imbalance (tests whether displayed size is spoofed/absorbed).

## Decision rule (fixed now)
- SUPPORTED if (1) shows a monotone imbalance-return relation whose top-vs-bottom-decile spread at 60 s or 300 s exceeds
  the round-trip cost with |t| > 4 (Newey-West), AND at least one of the 18 executable configs is net-positive after costs
  in >= 9 of 12 months of 2023 and beats its placebo distribution (p < 0.05). Then and only then ask Nick to fund 2019-25
  MNQ + MES bbo-1s (~$260) for the full per-year gate and a one-shot 2024-25 validation.
- PROXY-ONLY / not actionable if (1) is significant but no executable config clears costs: write up, no further spend.
- REJECTED if neither holds. Either way the result is appended to research/strategy_memory/lessons.md.
- 2024-2026 data of any schema is not used in this pilot. No live trading.

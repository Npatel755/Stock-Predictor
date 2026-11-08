# mass_1m: 1-minute counter-trend search (pre-registered 2026-11-08, before any run)

## Why
mass_v2 (1.2M 15-min price rules x 2 bar rules, early-close fix applied) found no counter-trend family that passes
training gates (mean_reversion / vwap / opening_range: 0 of ~360k) and no durable standalone edge (1/13 holds).
Intraday mean reversion (VWAP snap-backs, liquidity exhaustion, failed opening-range breaks) resolves in 1-5 minutes and
is blurred at 15-min resolution. Goal: a counter-trend sleeve that is uncorrelated with the morning trend runner.

## Data
- Training (14 calendar years): ES/NQ 1-min 2010-01..2018-12 relabelled to MES/MNQ economics (as in mass_v2) and real
  MES/MNQ 1-min 2019-05..2023-12. Resolutions 1, 3 and 5 min built from the 1-min bars (time_bucket, lenient).
- Validation: MES/MNQ 2024-2025, loaded only after the frozen list exists; run once. 2026 never loaded.
- Early-close handling: session_calendar.apply_early_close on every run.

## Execution (unchanged from mass_v2)
execution_cfg_5m_v2 economics, 1 contract: $0.50/side commission (LucidFlex $0.61 reported as sensitivity on
survivors), 1-tick spread, 1-tick slippage, $150 risk/contract, $400 daily loss, $2,000 hard drawdown, flat 15:55 ET,
signal on bar close -> fill next bar open.

## Signal families (all fade the preceding move; long and short symmetric)
1. vwap_snapback: RTH-anchored VWAP; stretch = (close - vwap)/ATR; |stretch| >= th and the bar closes back toward VWAP.
2. volume_exhaustion: bar volume >= th x rolling median volume(lookback) and the bar extends the lookback move by
   >= 1 ATR and closes in the extreme quarter of its range -> fade.
3. orb_fade: break of the opening range (first `lookback` minutes, 15/30/60) by >= th x 0.5 ATR followed by a close back
   inside the range -> enter toward the range midpoint.
4. rsi_extreme: RSI(lookback) <= 50 - 10*th (long) / >= 50 + 10*th (short).
5. keltner_fade: close outside EMA(lookback) +/- th x ATR on the previous bar and back inside on this bar.
6. stretch_fade: lookback-bar return >= th x ATR and this bar closes against the move.
Grid: lookback {10, 20, 30, 60} bars (orb: 15/30/60 minutes), th {1.0, 1.5, 2.0, 3.0}, resolution {1, 3, 5} min,
session (fill-time ET minutes) {(585,690), (600,720), (720,870), (840,945), (585,945)},
exits: stop ATR {1, 2, 3}, target R {0.5, 1, 2}, max hold {15, 30, 60, 120} minutes, trail ATR {0, 2}.
Total: (5 families x 4 lookbacks + ORB x 3 ranges) = 23 signal units x 4 thresholds x 5 sessions x 3 resolutions x 72 exits x 2 instruments = 198,720 configurations.

## Gates (identical to mass_v2)
G1 net > 0 after costs over the 14 training years; G2 >= 10 of 14 years positive and worst annual DD < $1,000;
G3 >= 140 trades and no year > 40% of total profit; G4 beats the 95th percentile of 20 within-year placebo
permutations on $/trade; G5 deflated Sharpe (N = 198,720) reported, not required. Dedupe by trade-entry fingerprint;
freeze at most 20; validate once on MES/MNQ 2024-2025; "holds" = net > 0 in both years and DD < $2,000.
Survivors are additionally scored for correlation with the mass_v2 trend holder (v2_7f233cc729959bec) and with the
paper sleeves (daily P&L correlation on training years) — the pairing requirement.

## Implementation notes (registered before the first run)
- ATR used for stops/targets/stretch units is a 30-minute ATR (30/res bars) at every resolution, so a "1 ATR stop" means the
  same thing on 1-, 3- and 5-minute bars; signal lookbacks are in bars as listed. Family names carry the resolution
  suffix (`_r1`, `_r3`, `_r5`) in the results database. Results: runs/mass_1m/results_1m.sqlite; reports *_1M.md.

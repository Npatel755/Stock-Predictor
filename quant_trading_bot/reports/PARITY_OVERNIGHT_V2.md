# Parity audit — paper runner `run_overnight` (overnight_dip_v2) vs research engine, train 2022–23 (2026-11-09)

Script: scripts/parity_overnight_v2.py. The live paper code (src/quant_futures/ensemble_paper.py, spec `overnight_dip_v2`: exit 09:45, MES co-dip
required) was replayed over MNQ + MES 1-min **training** bars from 2021-10-01 (warm-up) with start 2022-01-01, and its trade list compared with the
research `nights()` / `pnl()` path used in overnight_3 and later rounds. 2024–26 not loaded.

| | runner | research |
|---|---|---|
| nights traded 2022–23 | 74 | 74 (same 74 dates; none only on one side) |
| net | +4,177.15 | +4,176.97 |
| largest per-night difference | 0.01 | |

Code-level differences reviewed and found immaterial: the runner's 20-gap σ window includes nights that have no 09:45 exit bar (research drops
them), the reopen/entry/exit bars are "first bar in the 5-minute window" vs the exact-minute bar, and the runner flattens at 16:05 if no RTH open
follows within three sessions (research drops such nights). Gap reference (last 15:55–16:00 close, Friday's for Sunday nights), σ (ddof = 1, prior 20
nights only), threshold, entry/exit prices, spread + slippage + commission all agree. Forward paper results for this ledger are therefore
attributable to the backtested rule, not to implementation drift. The seed gaps used before 20 live nights exist come from owned Dec-2025 data
(warm-up only; no parameter depends on them).

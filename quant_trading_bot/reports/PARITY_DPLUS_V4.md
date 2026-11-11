# D+ v4 runner build and parity (Claude, 2026-11-09; training 2010-23 only)

Nick's decision (2026-11-09): build Devin's dplus_7e "v4" cell into the paper runner. The winning-day metric is the target, so the $1.50 miss on
the median winning *trade* gate is accepted.

## What v4 is
- D+ v2 sleeves (Crabel 15m open drive, MNQ 60m trend, MES 30m trend) at 3 micros, **4 micros on Crabel drives that agree with the opening gap**.
- Engine gates per sleeve: hard-drawdown lock $6,000, daily stop $600 (as v3). **Per-sleeve funded floor off** (see finding 1).
- **Account-level daily stop**: no new entry on any sleeve once the day's realised P&L is <= -$600. Open trades run to their exits.
- **Post-hoc 1-position routing** (`router="posthoc_1c"`), identical to the research `route()` (see finding 2).
- Ledger: `ag_arch_d_plus_v2_gapsize_4c_v4` (Future strategies). Paper only; no routing to a broker.

## Runner changes (src/quant_futures/ensemble_paper.py; existing candidates unaffected - every change is opt-in per candidate)
| change | purpose |
|---|---|
| `addon_scale` on addons (`scale_run`) | 1/3 of the 3-micro Crabel trade = +1 micro, so the book trades 4 on continuation drives |
| `account_daily_stop` on books (`account_daily_stop_filter`) | account-level -$600 daily stop; entries with the same timestamp are one decision |
| `router="posthoc_1c"` (`_route_posthoc`) | research-identical routing: sleeves run on their own signals, a trade is skipped if its decision falls inside an accepted trade's [entry, exit) |
| `funded_drawdown` sleeve override in `run_sleeve` | lets v4 turn off the policy's per-sleeve $2,000 trailing floor |

## Parity (scripts/parity_dplus_v4.py -> PARITY_DPLUS_V4.json)
| | research (dplus_7e) | runner |
|---|---|---|
| entries (base + addon twins summed) | 1,289 | 1,289 (0 missing either side) |
| net 2010-23 | +$59,257.67 | +$59,257.67 (max per-entry difference $0.003) |
| median winning day | $154.88 | $154.88 |
| $150+ days per year | 19.3 | 19.3 |
| worst day / days <= -$1,000 | -$950.50 / 0 | -$950.50 / 0 |
Research-only metrics (dplus_7e): median winning trade $148.50, 0.6 % static-floor breach and 0 % $1k-DLL hits over 157 monthly 12-month starts.

Live-path check (scripts/check_dplus_v4_live_path.py -> CHECK_DPLUS_V4_LIVE_PATH.json): bars truncated 15 minutes into a 2023-10-05 continuation
trade -> position reported open (short 3 + 1 micros, addon unrealised exactly 1/3 of the base), 1,689 earlier closed trades identical to the full run.

## Findings on the way (for Devin / Nick)
1. **[FIXED 2026-11-09, VERIFY_DPLUS_ROUTER_FIX.md] Per-sleeve funded floor locks sleeves at size.** The policy gives every sleeve its own $2,000 trailing floor. Under the strict router at
   3 micros, the Crabel sleeve hit it in Aug 2015 and never traded again (2010-23 Crabel net -$1,990 vs +$23,908 researched). The real account
   has one floor on combined P&L. The deployed 3c / 3c v3 ledgers still carry the per-sleeve floor: a $2,000 losing streak in one sleeve would
   permanently stop that sleeve in the paper ledger.
2. **[FIXED 2026-11-09, VERIFY_DPLUS_ROUTER_FIX.md] The strict_1c router is not the researched routing.** It masks a blocked signal bar and re-runs, so sleeves re-enter later and their
   engine state changes. The deployed `ag_arch_d_plus_v2` replays 2010-23 at **1,287 trades / +$15,074** through the runner vs
   **1,398 / +$17,576** in its provenance (research route). The same applies to every strict_1c D+ ledger. Not changed here (live ledgers);
   a `posthoc_1c` version of each would match its research numbers.
3. **The live VIX stand-aside only knows the last year** (yfinance 1y). Correct for live trading, but any 2010-23 replay through the runner
   silently runs with the filter off unless the historical series is supplied (the parity script does this).
4. Research quirk carried over on purpose: a trade decided before an accepted trade's *entry* is accepted, so two positions can briefly overlap.

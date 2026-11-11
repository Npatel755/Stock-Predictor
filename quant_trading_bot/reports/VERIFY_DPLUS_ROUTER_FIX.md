# D+ ledgers: router and per-sleeve floor fix (Claude, 2026-11-09; Nick's decision; training 2010-23 only)

## Problem (found while building v4, reports/PARITY_DPLUS_V4.md)
1. The deployed D+ ledgers used `router="strict_1c"`, which masks a blocked signal bar and re-runs the sleeve, so sleeves re-enter later and
   their engine state changes. The research measured a different rule (`route()`: sleeves run on their own signals, a trade is skipped if
   its decision falls inside an accepted trade's [entry, exit)). The paper ledgers were therefore trading a different strategy.
2. Every D+ sleeve carried the policy's per-sleeve $2,000 trailing funded floor. The account rule is one static $2,000 floor on combined
   P&L. Under the strict router (VIX filter off) the 3c Crabel sleeve tripped its own floor in 2015 and never traded again.

## Fix (src/quant_futures/ensemble_paper.py)
- `router="posthoc_1c"` for ag_arch_d_plus, ag_arch_d_plus_v2, ag_arch_d_plus_v2_2c and the hidden bases ag_arch_d_plus_v2_3c / _3c_v3
  (addons and books follow their bases).
- `_dplus_sl` sets `funded_drawdown=1e9` on every D+ sleeve (no per-sleeve floor). The engine's per-sleeve hard-drawdown lock is unchanged
  (it is part of the researched 2c / 3c numbers).
- New `account_static_floor=2000.0` on the visible D+ ledgers: the run record's `funded_failed` is set when combined intrabar equity touches
  -$2,000 from the start balance (new run-record field `worst_from_start`).
- Versions bumped: 1.0.0 -> 1.1.0 (D+ original, v2, v2_2c, gap addon, gapsize, 3c, 3c addon, gapsize_3c); 3.0.0 -> 3.1.0 (3c_v3 family).

## Replay 2010-23 through the runner (scripts/verify_dplus_router_fix.py -> VERIFY_DPLUS_ROUTER_FIX.json; historical VIX injected)
| ledger | research | before (strict, floor on) | after (posthoc, floor off) |
|---|---|---|---|
| ag_arch_d_plus | +20,723 / 1,968 | +13,066 / 1,447 | **+20,723.25 / 1,968** |
| ag_arch_d_plus_v2 | +17,576 / 1,398 | +15,074 / 1,287 | **+17,576.00 / 1,398** |
| ag_arch_d_plus_v2_2c | +27,327 / 1,281 | +28,082 / 1,334 | **+27,327.25 / 1,281** |
| ag_arch_d_plus_v2_gapsize | +23,142 | +18,631 | **+23,141.50** |
| ag_arch_d_plus_v2_gapsize_3c | +49,999 (1,228 base) | +43,171 (1,159) | **+49,999.50 (1,228)** |
| ag_arch_d_plus_v2_gapsize_3c_v3 | +70,734 (1,456 base) | +52,449 (1,335) | **+70,733.75 (1,456)** |
Per-sleeve floor on vs off under posthoc routing: identical for every ledger (it never trips on the research path), so removing it changes
no historical number. Spot check of the edited source (not the test patch): v2 +17,576.00 / 1,398, gapsize_3c_v3 +70,733.75. Tests: 12/12 pass.

## Deployment note
The paper runner runs on another host. When it picks up this code, the D+ ledgers record the new version; any trade already ledgered since
the 2026-11-09 paper start that the research routing would not have taken is written as a `divergence` record - that is the intended audit
trail of the switch, not a data error.

## Deployed (2026-11-10, Nick's approval)
Droplet 143.198.126.83 (`/opt/futures-paper`, systemd `futures-paper.timer`, paper only). The live engine was commit c03eaa3
(sha256 f8670d4a...); replaced by this working copy (8a9a0a66...) = c03eaa3 + the v4 / router / floor changes only.
- Dry run first on an isolated /tmp copy (notifications off): 24 existing ledgers identical to the live run, v4 added, 0 divergences.
- Backups: `src/quant_futures/ensemble_paper.py.bak_c03eaa3` and `/opt/futures-paper/runs_backup_20261110` (11 MB).
- First live run: success, 25 ledgers, 0 divergences, 0 errors; D+ ledgers on 1.1.0 / 3.1.0, v4 ledger 4.0.0 (1 trade, +$113.25).
- Rollback: `mv ensemble_paper.py.bak_c03eaa3 ensemble_paper.py` in `/opt/futures-paper/app/src/quant_futures/`.
- Note: the droplet app is copied files, not a git checkout; the paper start there is 2026-11-06.

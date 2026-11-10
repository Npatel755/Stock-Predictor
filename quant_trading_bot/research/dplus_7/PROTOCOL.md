# dplus_7 - size-scaled engine gates for a 4-micro gap-sized D+ (pre-registered 2026-11-09, training 2010-23 only; derived from payout_1)

Problem (payout_1): the engine's per-sleeve hard_drawdown lock is a fixed $2,000, so at 4 micros it trips constantly and the D+ trade set collapses.
Change under test (new engine policy version, not a strategy rule change): hard_drawdown = $2,000 x contracts; the sleeve's daily-loss gate is set
BELOW the account's $1,000 daily loss limit so the strategy stops itself first. Cells at k = 4 (budget $600): daily_loss in {1,600 (engine default), 800, 600, 400};
reference k = 3 with hard_drawdown 6,000 / daily 1,200 (lock removal alone). Gap sizing (Crabel continuation x2) applied on top, as deployed.
Metrics: median winning trade / day, share >= $150, $150+ days per year, net, $/trade, years > 0, closed DD, worst day; static $2k floor breach and
$1k-DLL hit rate over 157 monthly 12-month starts; median 12m net.
Gate for a Future-strategies ledger (`ag_arch_d_plus_v2_gapsize_4c`, separate name): median winning trade >= $150 AND median winning day >= $150 AND
static breach <= 2 % AND DLL hit <= 2 % AND net per trade >= the 3c ledger's $40.72 AND years > 0 >= 11/14. The daily-loss cell is chosen by the gate,
not by net (declared order: prefer the largest daily_loss that passes).

Addendum (declared after seeing the first two cells, before any k = 3 daily-loss cell was run): the k = 3 lock-removal reference already clears the
$150 mark (median win $165) but fails on DLL hits (10.8 %, worst day -$1,331); k = 4 keeps losing trades to the engine's 1 % volume-participation
fill model, not only to the lock. Derived cells, same gate, same declared preference order: k = 3, hard_drawdown 6,000, daily_loss in {800, 600, 400}.

Addendum 2 (declared after the DLL composition check, before running): the 5 days <= -$1,000 in 14 years are (a) four 3c trend stops on one day
(2022-12-13) - which the $600 daily stop does cut - and (b) four days where a 6-micro Crabel continuation trade lost $730-770 (a stop gapped through).
Derived cells (dplus_7c), same gate: k = 3, lock $6,000, daily_loss $600, and the Crabel doubling applied only when the 3c trade's stop risk is
<= {$300, $250} (so the doubled trade risks <= $600 / $500); trades above the cap stay at 3 micros. Reference: no cap (= the daily-$600 cell).

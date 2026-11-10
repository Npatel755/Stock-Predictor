# dplus_7 - size-scaled engine gates for a $150-per-trade gap-sized D+ (training 2010-23 only; protocol research/dplus_7/PROTOCOL.md)

Goal: lift the median winning trade over $150 (payout_1 left it at $141 at 3 micros) by scaling the engine's fixed $2,000 per-sleeve hard-drawdown lock
with size, and protect the account's $1,000 daily loss limit with the strategy's own daily stop. All cells gap-sized (Crabel continuation x2), engine-exact,
static $2k floor + $1k DLL over 157 monthly 12-month starts.

| cell | trades | net 2010-23 | $/trade | years>0 | closed DD | median win trade / day | winners >= $150 | $150+ days/yr | worst day | static breach | DLL hit | median 12m net | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3c, lock $2k (payout_1, deployed) | 1,228 | +$49,999 | 40.72 | 12 | $2,735 | $141 / $147 | 47 % | 16.7 | -$885 | 0.6 % | 0 % | +$1,914 | - |
| 3c, lock $6k, daily $1,200 (default) | 1,457 | +$70,643 | 48.49 | 12 | $3,107 | **$165 / $168** | 53 % | 20.7 | -$1,331 | 0.6 % | **10.8 %** | +$1,835 | fail (DLL) |
| 3c, lock $6k, daily $800 | 1,457 | +$70,643 | 48.49 | 12 | $3,107 | $165 / $168 | 53 % | 20.7 | -$1,331 | 0.6 % | 10.8 % | +$1,835 | fail |
| 3c, lock $6k, daily $600 | 1,456 | +$70,734 | 48.58 | 12 | $3,107 | $165 / $168 | 53 % | 20.7 | -$1,205 | 0.6 % | 10.8 % | fail |
| 3c, lock $6k, daily $400 | 1,453 | +$66,523 | 45.78 | 12 | $4,367 | $164 / $166 | 53 % | 20.4 | -$1,280 | 0.6 % | 10.8 % | fail |
| 4c, lock $8k, daily $1,600 / $800 / $600 | 795 | +$46,859 | 58.94 | 12 | $6,313 | $192 / $208 | 57 % | 14.0 | -$1,184 | 1.3 % | 22.3 % | +$595 | fail |
| 4c, lock $8k, daily $400 | 795 | +$41,786 | 52.56 | 12 | $9,385 | $192 / $208 | 57 % | 13.9 | -$1,184 | 2.5 % | 14.0 % | +$834 | fail |

Findings.
1. Removing the fixed lock works as intended: at 3 micros the median winning trade goes to **$165** (53 % of winners, 55 % of winning days clear $150,
   20.7 qualifying days a year), net +$70.6k on 2010-23, static-floor breach unchanged at 0.6 %.
2. The strategy-level daily stop is inert: $800 and $600 give identical results to the default, because the losing days are made by one or two trades
   whose stops are already in the market - a daily-loss gate only blocks *new* entries. The $1k-DLL hit rate (10.8 % of 12-month starts) comes from
   single-trade stop risk at size (see the composition below), not from a run of trades.
3. 4 micros is not viable regardless of the lock: the engine's 1 % prior-volume participation model rejects most fills (795 trades), DLL hits 14-22 %.

## Where the $1k days come from (3 micros, lock $6k)
Only 5 days in 14 years close at or below -$1,000 (14 at or below -$800). One (2022-12-13, -$1,331) is four 3c trend stops in a row - the $600 daily
stop cuts it to -$1,205. The other four each contain a 6-micro Crabel continuation trade losing $730-770, i.e. $120-130 per contract against a $40-90 stop
risk: the stop was gapped through. Capping the doubling by stop risk ($300 / $250 / $200 at 3c) therefore changes nothing (dplus_7c, reports/DPLUS_7C_TRAINING.json):
those trades had small stop risks and large realised losses. The 10.8 % figure is the share of 12-month windows containing one of these 5 days.

## Verdict
- Gate (median trade >= $150, static breach <= 2 %, DLL hits <= 2 %, $/trade >= 40.72, >= 11 years): **fails on the DLL term only** - every other term passes
  with room (median win $165, breach 0.6 %, $48.58 per trade, 12/14 years).
- The DLL term is account-specific. On an account without a daily loss limit (Tradeify Select Flex per Nick's notes) the configuration passes everything measured.
- Deployed as **`ag_arch_d_plus_v2_gapsize_3c_v3`** (engine v3 gates: lock $2,000 x contracts, daily stop $600) in the Future-strategies section, labelled for
  no-DLL accounts; the DLL-safe `ag_arch_d_plus_v2_gapsize_3c` (median win $141, 0 % DLL) stays as the Topstep-compatible version. Runner change: sleeve-level
  `hard_drawdown` / `daily_loss` overrides are now honoured (src/quant_futures/ensemble_paper.py, run_sleeve).
Not evidence for 2024-26 (sealed). Scripts: scripts/dplus_7_pilot.py, dplus_7b_pilot.py, dplus_7c_pilot.py; data: reports/DPLUS_7_TRAINING.json, DPLUS_7B_TRAINING.json, DPLUS_7C_TRAINING.json.


## dplus_7d / 7e - continuation size and an account-level daily stop (3 micros base, engine v3 gates)
| continuation size | account daily stop | trades | net | $/trade | median win trade / day | winners >= $150 | $150+ days/yr | worst day | days <= -$1k | static breach | DLL hit | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 micros | none | 1,456 | +$70,734 | 48.58 | $165 / $168 | 53 % | 20.7 | -$1,205 | 5 | 0.6 % | 10.8 % | fail (DLL) |
| 5 micros | none | 1,456 | +$65,355 | 44.89 | $162 / $164 | 52 % | 20.1 | -$1,101 | 3 | 0.6 % | 8.3 % | fail (DLL) |
| 5 micros | $600 | 1,450 | +$64,887 | 44.75 | $160.5 / $164 | 52 % | 20.1 | -$1,078 | 3 | 0.6 % | 8.9 % | fail (DLL) |
| 5 micros | $400 | 1,443 | +$65,499 | 45.39 | $159.75 / $163.5 | 51 % | 20.0 | -$1,014 | 2 | 0.6 % | 8.9 % | fail (DLL) |
| 4 micros | none | 1,456 | +$59,975 | 41.19 | $151.75 / $155 | 50 % | 19.3 | -$1,101 | 1 | 0.6 % | 7.6 % | fail (DLL) |
| **4 micros** | **$600** | 1,451 | +$59,258 | 40.84 | **$148.50 / $155** | 50 % | 19.3 | **-$951** | **0** | 0.6 % | **0 %** | **fail by $1.50 (median trade)** |
| 4 micros | $500 / $400 | 1,449 / 1,445 | +$58,248 / +$59,596 | 40.2 / 41.2 | $147.75 / $154.5 | 50 % | 19.2 | -$951 / -$885 | 0 | 0.6 % | 0 % | fail (median trade) |

Account-level daily stop = no new entry on any sleeve once the day's realised P&L <= -X (post-hoc removal of later entries; router re-fill ignored). The engine's own
daily stop is per sleeve, which is why it never prevented the four-stop day. With 5 micros the gap-through Crabel day plus already-open trend losses still reach -$1k;
with 4 micros and a $600 account stop no day in 14 years reaches -$1,000, DLL hits are 0 % and the static breach is unchanged (0.6 %) - but the median winning trade is
$148.50, $1.50 under the pre-registered gate (the median winning DAY, which the payout rule counts, is $155). Not deployed by rule; offered to Nick as a decision:
if the winning-day metric is the target, the account-level daily stop becomes a runner feature and this ships as the Topstep-compatible v4.
Data: reports/DPLUS_7D_TRAINING.json, DPLUS_7E_TRAINING.json (4-micro cells), DPLUS_7E5_TRAINING.json / DPLUS_7E5B_TRAINING.json (5-micro cells).

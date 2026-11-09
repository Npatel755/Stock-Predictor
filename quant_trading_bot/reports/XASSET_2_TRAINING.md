# xasset_2 — ZN / CL / 6E day and reopen states as conditioners for overnight_dip_v2 (training 2010–23 only)

Protocol research/xasset_2/PROTOCOL.md; script scripts/xasset_2_pilot.py; raw reports/XASSET_2_TRAINING.json. 490 v2 nights, MNQ 18:05→09:45. 2024–26 not loaded.
Coverage = share of dip nights with the asset feature available (ZN/6E 16:00 and 18:00–18:04 bars are missing on many days in the 1-min files).

| state (known at 18:05) | nights | $/night | removed net | random removals worse | remaining: net / years / DD | coverage |
|---|---|---|---|---|---|---|
| ZN day > 0 (bonds up) | 170 | **36.3** | +6,170 | 177/200 | 5,627 / 11 / 2,163 | 62 % |
| ZN day < 0 (bonds down) | 128 | **2.0** | +261 | **7/200** | **11,536 / 12 / 1,265** | 62 % |
| ZN reopen > 0 | 147 | 38.7 | +5,694 | 186/200 | 6,103 / 11 / 2,424 | 63 % |
| ZN reopen < 0 | 103 | 30.7 | +3,165 | 142/200 | 8,633 / 12 / 1,133 | 63 % |
| CL day > 0 | 155 | 37.5 | +5,806 | 179/200 | 5,992 / 11 / 1,535 | 64 % |
| CL day < 0 | 160 | 13.9 | +2,215 | 29/200 | 9,582 / 12 / 1,812 | 64 % |
| CL reopen > / < 0 | 190 / 239 | 25.9 / 19.1 | – | 120 / 59 | – | 91 % |
| 6E day > / < 0, reopen > / < 0 | 111–136 | 22.7–26.5 | – | 86–119 | – | 49–63 % |

## Verdict: 0 of 12 adoptable — recorded, not deployed
- Mechanism confirmed in direction: equity dips with a bond rally (growth scare / flight to quality) recover strongly overnight ($36/night); dips with a bond
  sell-off (rates-driven, 2022-style) barely recover ($2/night). Oil and the euro carry no information; reopen moves add nothing beyond the day move.
- Not adoptable under the pre-registered rule because the bonds-down nights are still net positive (+$261); the rule exists to stop us deleting
  harmless nights on the strength of one split. Standing aside would keep 98 % of the net at −23 % DD — attractive, but it is a training-only observation.
- Data caveat: ZN features exist on only 62 % of dip nights (missing 16:00 / 18:00 bars in the continuous file); a cleaner feature (e.g. 15:00 ET cash close) is needed before this becomes a rule.
- Status: same class as SKEW (extstate_2) — a state that ranks nights, usable later as a sizing/staging condition; a pre-registered "bond-confirmed" variant would need the coverage fix first.

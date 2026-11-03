# ETH v1.5 additional native-perpetual data

Rules are frozen before new archive requests. 2019 is earlier-regime retrospective evidence; new late-2026 data is a short chronological extension, not enough for reliable inference. Newly fetched rows already in the old dataset do not count as new information. Missing candles are never fabricated. No parameter selection, account execution or saved-profile overwrite.

Rules and comparators were frozen before archive requests. The baseline remains $6,000 on the original comparison dates; new dates cannot be added to inflate that benchmark.

| Requested archive | Frequency | Available | Rows |
| --- | --- | --- | ---: |
| 2019-11 | monthly | False | 0 |
| 2019-12 | monthly | False | 0 |
| 2026-10-28 | daily | False | 0 |
| 2026-10-29 | daily | True | 288 |
| 2026-10-30 | daily | True | 288 |
| 2026-10-31 | daily | True | 288 |
| 2026-11-01 | daily | True | 288 |
| 2026-11-02 | daily | False | 0 |

## early

Status: **unavailable**.
No requested archives available; no synthetic backfill

## recent

Status: **rejected_for_replay**.
Coverage: 2026-10-29 00:00:00+00:00 to 2026-11-02 00:00:00+00:00 exclusive; 1,152 rows, 0 timestamps absent from the previous main dataset.
Requires complete candles and enough hourly warm-up. Coverage/availability preserved without invented data.
Unavailable periods: `[{"start": "2026-10-28 00:00:00+00:00", "end_exclusive": "2026-10-29 00:00:00+00:00", "missing_bars": 288}, {"start": "2026-11-02 00:00:00+00:00", "end_exclusive": "2026-11-03 00:00:00+00:00", "missing_bars": 288}]`.

There is no guarantee that native history extends before the exchange listed the contract. Additional spot or other-venue ETH data must be labeled separately and must not masquerade as Binance perpetual or Breakout execution. Extra historical data does not erase the selection bias from tuning the existing years. The old datasets and all saved numbered versions remain unchanged.

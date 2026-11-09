# Edge attribution by realized-vol tercile (training years 2010-2023 only; descriptive, nothing tuned)

Sleeves: Portfolio E's MES_MOM / MNQ_BRK_E, the mass_v2 survivor MNQ_TRD8, Antigravity's MNQ_Trend / MNQ_MornBrk / MES_Mom. ES/NQ 2010-18 at micro economics + MES/MNQ 2019-23, annual $50k accounts, $0.61/side, MNQ spread 1.75 ticks. Vol = annualized std of the prior 20 RTH close-to-close returns, known at the open; terciles fixed on all 2010-23 sessions.

## Sessions per decade and tercile
- MES: cut points [0.101, 0.156]; 2010-19|high: 49, 2010-19|low: 72, 2010-19|mid: 50, 2020-23|high: 61, 2020-23|low: 43, 2020-23|mid: 153
- MNQ: cut points [0.128, 0.19]; 2010-19|high: 60, 2010-19|low: 63, 2010-19|mid: 48, 2020-23|high: 88, 2020-23|low: 9, 2020-23|mid: 160

## Net $ (trades, $/trade) by decade x vol tercile

| sleeve | total | 2010-19 low | 2010-19 mid | 2010-19 high | 2020-23 low | 2020-23 mid | 2020-23 high |
|---|---:|---:|---:|---:|---:|---:|---:|
| MES_MOM_3c | 7,110 (406, +18) | -842 (102, -8) | -60 (86, -1) | -250 (56, -4) | 1,004 (25, +40) | 771 (63, +12) | 6,488 (74, +88) |
| MNQ_BRK_E_2c | 9,075 (616, +15) | 175 (204, +1) | -548 (167, -3) | -1,523 (77, -20) | 451 (28, +16) | 4,930 (47, +105) | 5,741 (88, +65) |
| MNQ_TRD8_1c | 4,084 (514, +8) | 31 (192, +0) | 467 (130, +4) | 2 (61, +0) | 820 (23, +36) | 1,189 (51, +23) | 1,589 (55, +29) |
| AG_MNQ_Trend_1c | 6,957 (576, +12) | 580 (234, +2) | -26 (137, -0) | 236 (57, +4) | 367 (30, +12) | 2,515 (49, +51) | 3,335 (66, +50) |
| AG_MNQ_MornBrk_1c | 4,317 (536, +8) | -37 (184, -0) | -329 (148, -2) | -809 (63, -13) | -11 (26, -0) | 2,430 (40, +61) | 3,127 (71, +44) |
| AG_MES_Mom_1c | 2,304 (232, +10) | -76 (76, -1) | 30 (30, +1) | 141 (26, +5) | 530 (26, +20) | 328 (29, +11) | 1,383 (44, +31) |

## Exit reason and side

| sleeve | stop | target | hold timeout | session end | long | short | top-5 sessions / gross wins | top-5% trades / net |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MES_MOM_3c | -15,538 (171, -91) | 10,614 (28, +379) | - | 12,035 (207, +58) | 683 (283, +2) | 6,427 (123, +52) | 0.163 | 1.54 |
| MNQ_BRK_E_2c | -18,655 (254, -73) | 17,333 (84, +206) | - | 10,397 (278, +37) | 4,978 (253, +20) | 4,097 (363, +11) | 0.097 | 1.4 |
| MNQ_TRD8_1c | -6,607 (142, -46) | 6,431 (63, +102) | - | 4,260 (309, +14) | 2,161 (253, +8) | 1,923 (261, +7) | 0.121 | 1.19 |
| AG_MNQ_Trend_1c | -8,857 (218, -41) | 9,608 (91, +106) | 6,020 (244, +25) | 186 (23, +8) | 3,602 (239, +15) | 3,355 (337, +10) | 0.107 | 0.92 |
| AG_MNQ_MornBrk_1c | -8,418 (231, -36) | 7,930 (75, +106) | - | 4,804 (230, +21) | 2,479 (225, +11) | 1,838 (311, +6) | 0.119 | 1.35 |
| AG_MES_Mom_1c | -4,494 (114, -39) | 4,463 (52, +86) | 1,471 (32, +46) | 865 (34, +25) | 1,216 (122, +10) | 1,088 (110, +10) | 0.217 | 0.92 |

## Reading

- High-vol sessions were NOT profitable before 2020 (MNQ_BRK_E -1,523, MornBrk -809, MES_MOM -250 in the 2010-19 high tercile) while every tercile of 2020-23 is positive. The 2020-23 profit is an era effect (intraday trend persistence), not a realized-vol effect; a vol filter is not a legitimate rescue and will not be pursued.
- Verdict: **EDGE CONCENTRATED** by era for all six sleeves. Hypothesis for later, not evidence: post-2020 index intraday autocorrelation (0DTE/gamma, retail flow) is the mechanism; it can leave as it came.

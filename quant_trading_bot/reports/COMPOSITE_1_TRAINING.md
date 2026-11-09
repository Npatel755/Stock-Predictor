# composite_1 — composite selected-day 10:00 MNQ entries, training 2010–2023 (2026-11-09)

Protocol research/composite_1/PROTOCOL.md (pre-registered; fixed exits stop 1.5 ATR / 4R / hold 20 / flat 15:55; micro costs). Signals: S1 NQ/ES opening
divergence |z| ≥ 1.25, S2 Crabel open-drive, S3 VIX/VIX3M velocity crush. Script scripts/composite_1_pilot.py. Placebo: 20 random day sets with the same
long/short counts per year. Gates: net > 0, ≥ 10/14 years, largest year ≤ 40%, ≥ 95% placebo, ≥ 100 trades, ≥ $8/trade. Validation 2024–25 untouched.

| variant | 14-yr net | trades | $/trade | +years | 2010–19 | largest year | placebo mean | beats |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A_any_two_sided | +7,430 | 1104 | +6.73 | 9/14 | +640 | 46% | -4,092 | 20/20 |
| B_any_long_only | +6,523 | 767 | +8.50 | 11/14 | +1,212 | 43% | -2,788 | 20/20 |
| C_two_agree_two_sided | +2,242 | 240 | +9.34 | 10/14 | +430 | 78% | -821 | 20/20 |
| D_two_agree_long_only | +2,278 | 238 | +9.57 | 10/14 | +466 | 76% | -544 | 20/20 |
| E_s1_and_s2_agree | +1,613 | 135 | +11.95 | 10/14 | +222 | 54% | +43 | 19/20 |
| F_exactly_one | +5,755 | 876 | +6.57 | 10/14 | +210 | 46% | -2,909 | 20/20 |

## Verdict
**0 of 6 pass.** Every variant beats its same-exposure random-day placebo (19–20/20) and four of six reach 10–11 positive years, so the day selection is
real and additive — but no variant clears two gates at once: the union variants (A, B, F) make $6.6–8.5/trade with 2021 at 43–46% of the net, and the
intersection variants (C, D, E) reach $9–12/trade only on 135–240 trades with a single year (2021) carrying 54–78%. 2010–19 is +$0.2k–1.2k over ten years
in every case. Combining three weak day filters raised the hit rate, not the size of the move: the per-trade edge stays ≈ 1–2 round trips and lives in
2020–21. Validation stays sealed; nothing is promoted. This closes the day-selection lead on the data owned.

# Antigravity Crabel open-drive and VIX velocity-crush — fixed-engine replication (2026-11-09)

Specs as sent 2026-11-08 (both best-of-324 grids on 2010–23, so training is in-sample). 15m MNQ bars, NQ 2010–18 + MNQ 2019–23, 1.75-tick spread,
1 tick slippage, $0.61/side, signal on the 09:45 bar → fill at the 10:00 open, flat 15:55. Placebo: 20 random day sets with the same number of long and
short signals per year, same entry time and exits. Script: scripts/replicate_antigravity_crabel_vix.py.

| rule | 14-yr net (trades) | sender claim | 2010–19 | +years/14 | largest year share | placebo mean | beats |
|---|---:|---|---:|---:|---:|---:|---:|
| Crabel open-drive (tails 0.20/0.85, range ≥ 1 ATR, stop 1.5, 4R, hold 20) | +3,676 (311) | +6,713 / 517 trades / 10 of 14 / pre-2020 +571 / DD 1,148 | +801 | 9 | 2021 = 61% | -872 | 20/20 |
| VIX/VIX3M velocity crush (Δratio ≤ −0.015, morning ≥ +0.1%, stop 1.5, 5R, hold 24) | +4,925 (400) | +4,180 / 409 trades / 10 of 14 / pre-2020 +1,176 / DD 2,196 | +1,158 | 9 | 2021 = 46% | -1,553 | 20/20 |

Crabel by year: 2010: -76, 2011: -146, 2012: +142, 2013: -47, 2014: +40, 2015: +130, 2016: -126, 2017: +152, 2018: +426, 2019: +305, 2020: +740, 2021: +2,250, 2022: -293, 2023: +178
VIX crush by year: 2010: +86, 2011: +149, 2012: +102, 2013: -46, 2014: -74, 2015: -70, 2016: -192, 2017: +86, 2018: +412, 2019: +705, 2020: +904, 2021: +2,266, 2022: -292, 2023: +888

Verdict: **neither passes** (9/14 years each; 2021 alone is 46–61% of the net, over the 40% cap; best-of-324 uncorrected). Both do beat same-exposure
random-day placebos 20/20, so — like the NQ-leader signal — they select days with genuine long drift at 10:00, worth ≈ $9–12/trade in-sample and
≈ $4–5/trade before 2020. Three independent day-selection signals (NQ/ES opening divergence, Crabel open-drive, VIX crush) now show the same profile:
real, small, 2020–21-heavy. A pre-registered composite "selected-day 10:00 long" study is the one lead this leaves; it must be frozen before 2024–25 is touched.

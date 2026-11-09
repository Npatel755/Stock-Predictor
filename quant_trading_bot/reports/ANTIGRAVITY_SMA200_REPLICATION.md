# Antigravity "Daily 200 SMA Gated Trend" — fixed-engine replication (2026-11-08)

Rule: MNQ 30m EWMA trend (EMA8−EMA16)/ATR14, |trend| ≥ 0.75, stop 1.5 ATR, 4R target, hold 8 bars, decisions on 30m closes 10:00–12:00 ET,
flat 15:55; gate = prior session RTH close vs its 200-session SMA (above → long only, below → short only). NQ 2010–18 + MNQ 2019–23,
1 micro contract, 1.75-tick spread + 1 tick slippage + $0.61/side. Script: scripts/replicate_antigravity_sma200.py. Gate chosen by the
sender after seeing 2010–2026, so every year is in-sample for the gate; 2024–25 not run (already consulted by the sender).

| year | ungated net | gated net (trades) |
|---|---:|---:|
| 2010 | -125 | +0 (0) |
| 2011 | -56 | -172 (25) |
| 2012 | +212 | +174 (30) |
| 2013 | -418 | -216 (58) |
| 2014 | +226 | +180 (51) |
| 2015 | +718 | +320 (44) |
| 2016 | +188 | +4 (42) |
| 2017 | +88 | +224 (53) |
| 2018 | +644 | +432 (47) |
| 2019 | +406 | -21 (28) |
| 2020 | +1,088 | +432 (51) |
| 2021 | +3,146 | +2,676 (38) |
| 2022 | +1,286 | +501 (28) |
| 2023 | -120 | +1,018 (51) |

Ungated: 2010–19 +1,882, 14-year +7,282, 10/14 positive years. Gated: 2010–19 +927, 14-year +5,554, 10/14 positive.

Placebo (20 random long-only/short-only day gates with the same long share per year): 14-year mean +6,349, 2010–19 mean
+1,240; the real 200-SMA gate beats 1/20 on the 14-year total and 3/20 on 2010–19.

Verdict: **REJECTED as a filter.** The 200-day gate removes about half the trades and lowers profit relative to both the ungated rule and
random gates of equal exposure — it carries no information beyond "trade less". The sender's +$2,522 for 2010–19 is the 4-sleeve portfolio,
not this sleeve; here the ungated morning lb16 trend sleeve alone is +$1,882 for 2010–19 (8 of 10 years) and the gate cuts that to +$927.
The ungated sleeve is the most consistent single trend rule seen so far (10/14 years) but 74% of its 14-year net is 2020–23 and its 2010–19
profit is ~$190/yr at 1 contract — well below any funded-account target. It is already the morning sleeve of the ag_quad paper ledger.

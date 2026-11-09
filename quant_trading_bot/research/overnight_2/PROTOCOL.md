# overnight_2 — reopen-dip overnight hold follow-up (pre-registered 2026-11-09, before any run; 2024-25 untouched by overnight_1/2 so far)

Parent result (overnight_1 V9): long MNQ 18:05 -> next 09:30 ET on nights where the 18:00 reopen is below the 16:00 RTH close: +$5,724 / 1,136 nights /
10 of 14 years / 193 of 200 placebos; failed only the 40% single-year cap (54%). V8 (VIX backwardation nights) +$3,659 / 195 nights.
Economic story: a down reopen after the cash close is liquidity-driven selling into a thin book (ETF hedging, Asia open positioning) that mean-reverts into
the US open where the overnight premium also accrues; the premium is concentrated in those nights (Lou-Polk-Skouras; the "night-dip" literature).
Fixed: entry 18:05 ET bar open, exit next RTH 09:30 open, 1 contract, costs as overnight_1 (Topstep: $0.61/side micro), flat-before-cutoff satisfied.
Variants (16 per product, 32 total, all reported; no further search afterwards):
 D0 gap < 0 (= V9 baseline)   D1 gap <= -0.05%   D2 gap <= -0.10%   D3 gap <= -0.20%   D4 gap <= -0.5 x std20(gap)   D5 gap <= -1.0 x std20(gap)
 X1 D0 & VIX/VIX3M > 1 (backwardation)   X2 D0 & ratio <= 1 (contango)   X3 D0 & VIX > 20   X4 D0 & VIX <= 20
 S1 D0 with stop at 2 x std20(overnight move) below entry (checked on 1-min lows)   S2 D0 exit at 09:35 close   S3 D0 & RTH day was down   S4 D0 & RTH day was up
 Q1 D0 Mon-Thu nights only   Q2 D0 Sunday nights only
Placebo: 200 random same-size night sets per year (same per-year counts), same P&L mechanics. Gates: net > 0, >= 10/14 years, largest year <= 40% of net,
>= 95% placebo (>= 190/200), >= 100 nights, and funded accounting: worst single night loss (counts toward the $400 daily loss limit... reported, not gated) and
max drawdown of the nightly net equity curve < $2,000 (gated).
Freeze rule: all variants that pass on 2010-23 are frozen as a list; validation 2024-2025 is run ONCE on that list (same mechanics), reported per variant;
2026 never loaded. A variant is "validated" if 2024-25 net > 0 and both years positive. Multiplicity: 32 variants in this round (plus 20 in overnight_1);
with placebo gates at 95% the expected false passers are ~1.6 — a single passer is NOT conclusive and will be stated as such.
No paper promotion without Nick's yes (the paper runner would need a new overnight candidate type with a 16:05 ET safety flatten).

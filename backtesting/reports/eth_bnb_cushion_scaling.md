# Cushion-scaled risk, ETH v1.11 $100 + BNB crypto_v0_1 $200 base, Breakout 50k static floor, 2024-01-01 .. 2026-10-28

Risk per trade = base x multiplier(cushion), cushion = closed P&L above the starting balance; multiplier re-evaluated only while that sleeve is flat. Reporting only; see module docstring.

| Rule | Net from Jan-2024 | Median 12-month net (all starts) | Worst loss from any start | Starts breached / reached $5k (of n) | Median months to $5k |
|---|---|---|---|---|---|
| fixed (no scaling) | $16,794 | $6,626 | $1,771 | 0 / 22 (of 29) | 6.1 |
| +50% per $1,500 cushion, cap 2x | $30,904 | $10,229 | $1,771 | 0 / 22 (of 29) | 4.6 |
| +50% per $1,500 cushion, cap 3x | $43,263 | $12,151 | $1,771 | 0 / 22 (of 29) | 4.5 |
| +25% per $1,000 cushion, cap 3x | $42,356 | $11,782 | $1,771 | 0 / 22 (of 29) | 4.7 |
| +100% per $3,000 cushion, cap 3x | $41,701 | $9,792 | $1,771 | 0 / 22 (of 29) | 5.3 |

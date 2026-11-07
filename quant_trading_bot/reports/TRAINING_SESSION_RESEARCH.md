# Training-only session strategy research

No candidate passed every declared base/2× training check. No candidate was promoted.

This batch never opened validation or test prices. It compared 24 prespecified settings across three chronological blocks inside the NQ training split. The highest-ranked four base cases were frozen before doubled-cost training replays. No validation/test result was used by this selection code.

24 fixed cases: three session-rule families, both/long-only directions, half/full opening-range stop, 2R/3R target, one NQ contract. Completed five-minute candles. One entry attempt per session, noon flattening. No protective-stop retuning.

Evaluate each case continuously within 2010–2015, 2016–2019, 2020–2023 NQ training blocks. Risk/capital reset at block boundaries only. Rank by qualification, no risk shutdown, number of profitable blocks, worst block net/worst drawdown, total net, id. Freeze top four base-ranked cases before 2x training cost stress. Select one qualified base/stress survivor, otherwise no promoted candidate. Minimum 60 trades per block, positive each block, no shutdown, close/intrabar DD <20000 actual NQ dollars. No validation or test replay in this script.

All P&L below uses actual NQ mini-contract economics. The $20,000 rejection ceiling corresponds to explicitly scaled training risk budgets; it is not a measured $2,000 MNQ result. Each block resets capital and risk separately, so totals across blocks are attribution sums, not a continuous 2010–2023 account curve.

## All base training cases

| Candidate | Rule | Long only | Stop fraction | Target | 2010–2015 net | 2016–2019 net | 2020–2023 net | Profitable blocks | Risk shutdowns |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| session5_545d17d6de | opening_breakout_5m | True | 1.0 | 3 | $251.50 | $2,848.00 | $3,479.50 | 3 | 1 |
| session5_d34febd0d2 | opening_breakout_5m | True | 1.0 | 2 | $251.50 | $2,743.00 | $3,524.50 | 3 | 1 |
| session5_d95e333244 | opening_momentum_5m | True | 0.5 | 3 | $-1,694.50 | $3,832.00 | $16,902.00 | 2 | 1 |
| session5_cf52b43df2 | opening_breakout_5m | True | 0.5 | 2 | $-2,024.50 | $184.00 | $702.50 | 2 | 2 |
| session5_6127fd4f88 | opening_breakout_5m | True | 0.5 | 3 | $-2,514.50 | $4,399.00 | $15,620.50 | 2 | 1 |
| session5_3179c74df3 | opening_momentum_5m | True | 0.5 | 2 | $-2,634.50 | $232.00 | $26,342.00 | 2 | 1 |
| session5_41304d2e47 | opening_momentum_5m | False | 0.5 | 3 | $-7,707.50 | $1,994.50 | $27,466.00 | 2 | 1 |
| session5_ed3cb67c2b | opening_momentum_5m | False | 0.5 | 2 | $-9,562.50 | $969.50 | $34,981.00 | 2 | 1 |
| session5_1f48c5724d | opening_momentum_5m | True | 1.0 | 3 | $-4,049.50 | $11,197.50 | $-2,765.00 | 1 | 1 |
| session5_f0b5b232ca | opening_momentum_5m | True | 1.0 | 2 | $-4,049.50 | $11,617.50 | $-3,415.00 | 1 | 1 |
| session5_c8c800e38d | opening_breakout_5m | False | 1.0 | 2 | $-1,969.00 | $-6,462.50 | $7,509.50 | 1 | 2 |
| session5_326e02413f | opening_breakout_5m | False | 0.5 | 3 | $-2,849.00 | $-10,348.50 | $39,298.50 | 1 | 1 |
| session5_c04da3d6f6 | opening_breakout_5m | False | 0.5 | 2 | $-8,064.50 | $-11,573.50 | $23,118.50 | 1 | 1 |
| session5_7dea359380 | failed_breakout_5m | True | 1.0 | 3 | $-1,308.50 | $-16,843.00 | $1,577.00 | 1 | 1 |
| session5_2b5d70f68d | failed_breakout_5m | True | 1.0 | 2 | $-1,388.50 | $-17,133.00 | $2,262.00 | 1 | 1 |
| session5_f6b4b97842 | failed_breakout_5m | False | 1.0 | 3 | $-2,411.50 | $-901.00 | $-10,417.50 | 0 | 2 |
| session5_96bbd81250 | failed_breakout_5m | False | 1.0 | 2 | $-2,041.50 | $-501.00 | $-11,487.50 | 0 | 2 |
| session5_6f9a435796 | failed_breakout_5m | True | 0.5 | 3 | $-833.50 | $-12,272.00 | $-15,045.50 | 0 | 2 |
| session5_c84b11d35c | failed_breakout_5m | True | 0.5 | 2 | $-1,168.50 | $-9,227.00 | $-15,533.50 | 0 | 2 |
| session5_8777d94e62 | failed_breakout_5m | False | 0.5 | 3 | $-366.50 | $-16,506.00 | $-6,980.50 | 0 | 3 |
| session5_8740280fd1 | failed_breakout_5m | False | 0.5 | 2 | $-1,186.50 | $-17,388.00 | $-8,072.00 | 0 | 3 |
| session5_ea7b9c4c64 | opening_breakout_5m | False | 1.0 | 3 | $-1,999.00 | $-5,432.50 | $-18,011.50 | 0 | 3 |
| session5_e23faa3cbb | opening_momentum_5m | False | 1.0 | 3 | $-3,663.50 | $-7,731.50 | $-18,098.00 | 0 | 3 |
| session5_72ca1eb3c0 | opening_momentum_5m | False | 1.0 | 2 | $-3,813.50 | $-7,696.50 | $-18,288.00 | 0 | 3 |

## Shortlisted doubled-cost training results

| Candidate | Block | Base net | Base close DD | 2× net | 2× close DD | 2× intrabar DD | 2× risk shutdown | Qualified across blocks |
|---|---|---:|---:|---:|---:|---:|---|---|
| session5_545d17d6de | 2010_2015 | $251.50 | $898.00 | $-487.00 | $1,123.00 | $1,138.00 | True | False |
| session5_545d17d6de | 2016_2019 | $2,848.00 | $7,949.50 | $-2,629.00 | $12,022.00 | $12,057.00 | False | False |
| session5_545d17d6de | 2020_2023 | $3,479.50 | $12,562.50 | $-167.00 | $13,470.00 | $13,755.00 | False | False |
| session5_d34febd0d2 | 2010_2015 | $251.50 | $898.00 | $-487.00 | $1,123.00 | $1,138.00 | True | False |
| session5_d34febd0d2 | 2016_2019 | $2,743.00 | $7,991.00 | $-2,634.00 | $12,052.00 | $12,087.00 | False | False |
| session5_d34febd0d2 | 2020_2023 | $3,524.50 | $12,992.50 | $-102.00 | $13,890.00 | $14,175.00 | False | False |
| session5_d95e333244 | 2010_2015 | $-1,694.50 | $3,714.75 | $-3,634.00 | $4,729.50 | $4,729.50 | True | False |
| session5_d95e333244 | 2016_2019 | $3,832.00 | $10,491.50 | $-1,756.00 | $12,212.00 | $12,597.00 | False | False |
| session5_d95e333244 | 2020_2023 | $16,902.00 | $18,098.50 | $8,387.00 | $19,025.50 | $19,025.50 | True | False |
| session5_cf52b43df2 | 2010_2015 | $-2,024.50 | $4,286.50 | $-5,129.00 | $5,748.50 | $5,793.50 | True | False |
| session5_cf52b43df2 | 2016_2019 | $184.00 | $11,396.00 | $-6,092.00 | $15,852.00 | $15,887.00 | False | False |
| session5_cf52b43df2 | 2020_2023 | $702.50 | $19,035.00 | $-1,693.00 | $19,093.00 | $19,093.00 | True | False |

## Interpretation

This is in-training research and repeated hypothesis search; internal blocks are not untouched external confirmation. NQ has real mini economics and 10x micro risk budgets, not synthetic early MNQ P&L. The researcher retains prior validation/test knowledge; outcomes cannot remove that contamination. Configured risk stops may be exceeded by gaps.

Historical training qualification is not deployment eligibility. This batch does not authorize another validation/test search. A training failure remains a failure; it is not repaired by choosing a candidate on the later splits.

Run artifacts: `C:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot\runs\training_sessions_20261107T023706Z`. [Machine-readable research](training_session_research.json) · [Dashboard](http://127.0.0.1:8511)

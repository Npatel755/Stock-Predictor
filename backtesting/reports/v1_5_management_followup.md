# Exit-management follow-up after ETH v1.5

All 2023-2026 observations including 2026 participate in reused-data selection. No fresh validation or future-performance claim. Risk, account size, fees, slippage, financing, entry logic and RVOL2 filter are fixed; only trailing distance and maximum holding duration vary.

Screened 20 fixed exit configurations. Selected diagnostic: **trail3.0_hold288**. Full historical improvement gate: **False**.

| Same original 2023-01-01 to 2026-10-28 exclusive period | Net P&L | Entries | Intrabar drawdown |
| --- | ---: | ---: | ---: |
| Saved v1.5 | $9,971.43 | 397 | 4.02% |
| Changed exit candidate | $7,434.94 | 414 | 3.93% |
| Saved v1.5 at 4bp | $8,735.76 | 397 | 4.11% |
| Candidate at 4bp | $6,189.61 | 414 | 4.11% |
| Candidate at 8bp | $3,906.30 | 414 | 4.59% |

Rule: `{"family": "channel_breakout", "lookback": 96, "max_holding_bars": 288, "reward_r": 4.5, "slow": 150, "stop_atr": 1.5, "trail_atr": 3.0}`.

| Reused-data check, independently reset account | Net P&L | Entries |
| --- | ---: | ---: |
| 2025_h1 | $1,581.16 | 54 |
| 2025_h2 | $1,536.40 | 53 |
| 2026_h1 | $-741.67 | 60 |
| 2026_h2 | $472.84 | 31 |
| earlier_2020_2022 | $4,465.89 | 335 |

Completed-close management updates cannot retroactively consume the same candle. Maximum-duration exits use market slippage and fees; longer or shorter holding periods can alter financing and later entry availability. The existing broker simulator is unchanged. Independent half-year/earlier accounts are not a continuous account sum.

The saved v1.5 Pine/profile/metadata/downloads remain unchanged. This is reused historical research, including the inspected weak 2026 half. There is no new forward evidence and no live trading. Failed historical gates remain failures even if a headline total improves.

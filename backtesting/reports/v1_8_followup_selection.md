# ETH v1.8 follow-up: joint selection decision

The decision rule was frozen before outcomes from the filter campaign: finish both fixed grids against the same exact v1.8 reference, then choose the highest-net complete-gate pass. No untested combination of the two changes is selected. Earlier versions remain unchanged.

| Fixed campaign | Slots including control | Best complete-gate net | Selected settings |
| --- | ---: | ---: | --- |
| round14_v1_8_exits | 36 | $12,113.22 | stop_atr=1.5_reward_r=5.0_trail_atr=3.0 |
| round15_v1_8_filters | 24 | $11,749.94 | min_rvol=2.8_min_trend_gap_bps=200.0 |

Winner for fresh reproduction and separate v1.9 save: **round14_v1_8_exits**, modeled net **$12,113.22**. Exact parent reference: $11,541.24. All dates, account size, risk and execution costs are identical.

There are 60 slots in these two campaigns and 808 cumulative slots including repeated controls and earlier searches. All original observations remain reused selection history. No fresh forward-validation claim is made.

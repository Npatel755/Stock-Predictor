# Spread sensitivity: MNQ spread 1 tick (engine default) vs 1.75 ticks (measured 2019-25 RTH mean), $0.61/side

Closed-equity DD is the combined candidate curve (sleeves summed), annual $50k accounts, 2026 never loaded.

| candidate | split | net @1t | net @1.75t | delta | worst DD @1t | worst DD @1.75t | trades |
|---|---|---:|---:|---:|---:|---:|---:|
| ensemble_beta | train | 13,210 | 13,025 | -186 | 1,046 | 1,046 | 491 |
| ensemble_beta | validation | 692 | 616 | -76 | 1,793 | 1,753 | 186 |
| ensemble_epsilon | train | 15,058 | 15,330 | 272 | 1,859 | 1,859 | 1356 |
| ensemble_epsilon | validation | 2,430 | 2,572 | 142 | 2,626 | 2,716 | 543 |
| mass_v2_survivor | train | 3,598 | 3,598 | 0 | 494 | 494 | 129 |
| mass_v2_survivor | validation | 135 | 66 | -68 | 1,165 | 1,165 | 42 |
| portfolio_e | train | 19,668 | 19,454 | -214 | 1,363 | 1,375 | 324 |
| portfolio_e | validation | 2,996 | 1,991 | -1,006 | 2,042 | 2,062 | 154 |
| portfolio_e_scaled | train | 16,855 | 16,642 | -214 | 1,135 | 1,143 | 324 |
| portfolio_e_scaled | validation | 2,743 | 1,737 | -1,006 | 1,546 | 1,555 | 172 |

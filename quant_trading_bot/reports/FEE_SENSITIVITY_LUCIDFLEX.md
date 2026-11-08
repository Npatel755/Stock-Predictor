# Fee sensitivity: engine default $0.50/side vs LucidFlex micro all-in $0.61/side

Closed-equity DD is the combined candidate curve (sleeves summed), annual $50k accounts, 2026 never loaded.

| candidate | split | net @0.50 | net @0.61 | delta | worst DD @0.50 | worst DD @0.61 | trades |
|---|---|---:|---:|---:|---:|---:|---:|
| ensemble_beta | train | 13,498 | 13,210 | -288 | 1,040 | 1,046 | 493 |
| ensemble_beta | validation | -332 | -226 | 106 | 1,688 | 1,698 | 147 |
| ensemble_epsilon | train | 15,636 | 15,058 | -578 | 1,844 | 1,859 | 1359 |
| ensemble_epsilon | validation | 3,263 | 2,838 | -425 | 2,451 | 2,373 | 499 |
| mass_v2_survivor | train | 3,626 | 3,598 | -28 | 492 | 494 | 129 |
| mass_v2_survivor | validation | 437 | 135 | -302 | 1,160 | 1,165 | 43 |
| portfolio_e | train | 19,839 | 19,668 | -171 | 1,354 | 1,363 | 324 |
| portfolio_e | validation | 1,291 | 1,225 | -66 | 2,025 | 2,042 | 147 |

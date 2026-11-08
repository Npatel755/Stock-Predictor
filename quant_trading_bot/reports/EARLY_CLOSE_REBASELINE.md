# Re-baseline after the early-close fix (continuous 2024-2025 validation account, MES/MNQ strict bars)

Recorded (locked) numbers vs fixed, at $0.50/side and at the LucidFlex $0.61/side. Combined DD = summed sleeve curves (closed) / summed worst marks (intrabar).

| candidate | fee | val net | closed DD | intrabar DD | trades | sleeves (net/trades/lock) |
|---|---|---:|---:|---:|---:|---|
| portfolio_e | 0.50 | +3,600 | 1,710 | 1,744 | 151 | MES_MOM_3c +1121/54t/maximum_drawdown; MNQ_BRK_E_2c +2480/97t/- |
| portfolio_e | 0.61 | +3,532 | 1,717 | 1,751 | 151 | MES_MOM_3c +1086/54t/maximum_drawdown; MNQ_BRK_E_2c +2446/97t/- |
| portfolio_e | recorded | +3,142 / DD 1,744 (MES leg locked 2024-11-29) | | | | |
| ensemble_epsilon | 0.50 | +2,866 | 2,824 | 2,857 | 547 | MES_MOM_1c +114/72t/-; MNQ_VOL_1c +1212/372t/-; MNQ_E57_1c +1540/103t/- |
| ensemble_epsilon | 0.61 | +2,430 | 3,015 | 3,046 | 543 | MES_MOM_1c +98/72t/-; MNQ_VOL_1c +813/368t/-; MNQ_E57_1c +1519/103t/- |
| ensemble_epsilon | recorded | +4,053 / DD 1,725 (MES leg locked 2024-11-29, E57 locked 2024-12-24) | | | | |
| ensemble_beta | 0.50 | +558 | 1,996 | 2,171 | 187 | MES_MOM_2c +329/75t/-; MNQ_BRK_E_1c +128/56t/-; MNQ_HYB_C_1c +101/56t/- |
| ensemble_beta | 0.61 | +692 | 1,998 | 2,166 | 186 | MES_MOM_2c +297/75t/-; MNQ_BRK_E_1c +265/55t/-; MNQ_HYB_C_1c +130/56t/- |
| ensemble_beta | recorded | +787 / DD 1,344 (MES leg locked 2024-11-29, HYB locked 2025-07-03) | | | | |
| mass_v2_survivor | 0.50 | +437 | 1,160 | 1,207 | 43 | MNQ_TRD8_1c +437/43t/- |
| mass_v2_survivor | 0.61 | +135 | 1,165 | 1,211 | 42 | MNQ_TRD8_1c +135/42t/- |
| mass_v2_survivor | recorded | +437 / DD 1,208 (no lock) | | | | |

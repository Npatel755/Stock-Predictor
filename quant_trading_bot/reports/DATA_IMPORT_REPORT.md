# Databento data replacement

Active source: **GLBX-20261106-FX6FM5XWUX**. Original ZIP preserved at `C:\Users\Nick\Downloads\GLBX-20261106-FX6FM5XWUX.zip`.

All three archive members match their supplied SHA-256 hashes. The official Databento SDK decoded the DBN stream directly from ZIP without duplicating the large compressed payload.

The source contains **24,004,467 records**: **22,409,292 outright bars** and **1,595,175 non-outright/spread records**. Spreads remain in the original ZIP; they are counted and never mislabeled as outright futures.

| Instrument | Raw outright bars | Selected front-contract bars | First raw observation (UTC) | Last raw observation (UTC) |
|---|---:|---:|---|---|
| MES | 3,736,607 | 2,646,240 | 2019-05-05 22:00:00+00:00 | 2026-11-05 23:59:00+00:00 |
| MNQ | 3,975,164 | 2,648,080 | 2019-05-05 22:03:00+00:00 | 2026-11-05 23:59:00+00:00 |
| ES | 7,869,484 | 5,741,206 | 2010-06-06 22:00:00+00:00 | 2026-11-05 23:59:00+00:00 |
| NQ | 6,828,037 | 5,567,460 | 2010-06-06 22:00:00+00:00 | 2026-11-05 23:59:00+00:00 |

The imported outright bars had zero invalid/nonpositive prices, invalid OHLC relationships, invalid volumes, off-tick values, duplicate keys, timestamp-alignment failures or prelaunch micro observations in the implemented checks. This does not establish complete exchange-calendar coverage. Missing/no-trade intervals are not forward-filled.

The raw partitions preserve every imported outright contract and its instrument ID. Selected series use only the preceding completed session's volume, roll forward by expiry, and flag contract changes. The 2010 ES/NQ data remains mini-futures reference history; no MES/MNQ observations were fabricated before May 2019. Bid/ask and book fields remain null because the export is OHLCV only.

Cleanup removed **2,598 generated files** from this futures project's old synthetic/sample datasets, their runs and disposable test fixtures. Separate ETH/BNB research and the supplied source ZIP were preserved. The detailed allowlist is in `reports/data_replacement_history.json`.

The disposable `.clean-check` verification environment remains because automatic approval review blocked its removal. It is not an active price dataset.

Data import did not fit a model, consume a market holdout or activate trading. User-confirmed account settings are 50% consistency and DLL off; other contractual details still require verification.

## Access

```powershell
.\.venv\Scripts\python.exe -m quant_futures datasets
```

Use `MES`, `MNQ`, `ES`, or `NQ` as dataset arguments to resolve development descriptors containing training and validation only. Physical test files are reserved. See [DATA_SPLIT_REPORT.md](DATA_SPLIT_REPORT.md) for the chronological protocol and exact counts. Full contract/year partitions, symbology, condition metadata, selection schedule and checksums are retained beside the imported data. Dataset use and redistribution remain governed by the user's Databento entitlement.

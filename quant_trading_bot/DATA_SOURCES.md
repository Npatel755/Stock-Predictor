# Historical data report and acquisition options

## Active user-provided export

The current source is `C:/Users/Nick/Downloads/GLBX-20261106-FX6FM5XWUX.zip`, a Databento `GLBX.MDP3` one-minute DBN export of the ES, NQ, MNQ and MES parent symbols. The compressed member, metadata and condition file match their supplied SHA-256 hashes. It contains 24,004,467 records: 22,409,292 outright bars and 1,595,175 spread records. Outrights are mapped by embedded, date-aware symbology and stored at raw prices; spreads remain available in the untouched source ZIP and are explicitly counted.

MES starts 2019-05-05 22:00 UTC; MNQ starts 2019-05-05 22:03 UTC. ES and NQ begin 2010-06-06 22:00 UTC. All extend through 2026-11-05 23:59 UTC. The selected research series use prior-session volume and contain 2,646,240 MES, 2,648,080 MNQ, 5,741,206 ES and 5,567,460 NQ bars. No micro history was created from the minis. All previously downloaded samples and synthetic project datasets were removed at the user's request; the historical source comparison below is retained as an audit record.

Detailed source hashes, contract identities, condition metadata, raw partitions, selection schedule and import findings are under `data/market/GLBX-20261106-FX6FM5XWUX-v3/`. User entitlement governs storage and redistribution. This local import made no paid API request. See `reports/DATA_IMPORT_REPORT.md` for the replacement record. The initial-audit paragraphs below describe the state **before** this new export was supplied.

Accessed 2026-11-06. No paid data, accounts, API downloads or subscriptions were purchased. The repository's existing ETH/BNB/BTC data is neither MES/MNQ history nor a validated proxy. Its license was not established during this audit, so it was not reused for futures performance.

| Provider | History and resolution | Prices and books | Access and limits | Cost and licensing status |
|---|---|---|---|---|
| Databento GLBX.MDP3 | CME history in trades, OHLCV 1s/1m/1h/1d and market-data schemas; actual MES/MNQ date range must be queried | Raw contracts, unadjusted continuous mappings; MBP-1/10 and MBO schemas | Historical/live APIs; exact requested range priced by metadata | Usage-dependent historical estimate unavailable without key; displayed Standard plan $199/month is not a total acquisition quote. Exchange entitlement and use rights still required |
| FirstRate Data | MES/MNQ product pages report continuous coverage from 2019-05-05; individual contracts start at Z19; 1m/5m/30m/1h/daily | Raw/absolute/ratio continuous variants and individual contracts; these OHLCV pages do not establish historical quotes/depth | CSV ZIP exports; samples limited; product-specific futures API capability not established | Purchase price not exposed in retrieved page; updates advertised $99.95/year after included month. Private-use license, research/model outputs allowed, raw redistribution restricted |
| Interactive Brokers | Historical bars and ticks within API coverage; expired futures older than two years unavailable | Explicit futures and historical continuous instruments; continuous cannot execute orders | Permissions/subscriptions required; small-bar pacing, tick history and request limits apply | Account/data entitlement costs not quoted; not acquired. Continuous symbols cannot be used for live orders or streaming |
| CME DataMine / authorized distributors | Exchange historical products; request instrument/schema-specific coverage | Depends on selected product | Catalog/authorized vendor access and licensing | Quote required; no claim of free institutional futures history |

Primary sources: [Databento pricing](https://databento.com/pricing/), [schemas and APIs](https://databento.com/futures), [free cost metadata](https://databento.com/docs/api-historical/metadata/metadata-get-cost?lang=python), [continuous symbology](https://databento.com/docs/examples/symbology/continuous), [FirstRate MES](https://firstratedata.com/i/futures/MES), [MNQ](https://firstratedata.com/i/futures/MNQ), [license](https://firstratedata.com/about/license), [IBKR limitations](https://www.interactivebrokers.com/docs/tws-api/doc/md/market-data-limitations), [IBKR futures](https://www.interactivebrokers.com/docs/tws-api/contracts/futures), [CME DataMine](https://www.cmegroup.com/market-data/datamine-historical-data.html).

## Acquired public samples

`scripts/audit_free_samples.py` downloads the public evaluation samples without authentication or spending, retains private local ZIPs, and writes `reports/provider_sample_audit.json`. On this audit MES contained **16,235** one-minute rows and MNQ **16,236**, approximately 2026-10-21 through 2026-11-05. Exact UTC bounds, hashes, duplicates, OHLC violations and gap counts are in the report. The provider readme states bar-open timestamps, US Eastern timezone, and omitted zero-volume intervals.

Neither sample includes an explicit underlying contract identifier or a definitive adjustment basis. They were therefore **not imported as raw tradable contracts or used to claim market P&L**. The samples are short and unsuitable for multi-year robustness or account-failure estimation even if their price basis is later confirmed. Raw samples remain in the ignored data directory under the provider's private-use license; published analysis must attribute FirstRate Data.

The generated fixtures are separately marked `synthetic: true` with their random seed. Their OHLC, volume and sessions are artificial functional inputs, not reconstructed observations. Optional bid/ask and book fields remain null. No continuous series has been relabeled as an individual tradable micro contract.

## Calendar and roll provenance

Use the [CME holiday/trading calendar](https://www.cmegroup.com/trading-hours.html) and [equity roll dates](https://www.cmegroup.com/trading/equity-index/rolldates.html). A settlement-time document is not a trading-hours schedule. The supplied code contains verified 2026 expirations, including June 18, and customary roll Mondays; later years require official overrides. Research features can use causal forward additive adjustments, while the engine only books raw contract P&L and rejects an unresolved roll with an open position.

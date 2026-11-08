# LucidFlex automation: rules check and bridge design (2026-11-08)

Status: design only. No bridge code exists, no order is routed anywhere, and nothing may be connected
to a Lucid account without the account owner's explicit written go after the paper period.

## What Lucid permits (checked 2026-11-08)

Source: Lucid Trading Help Center, "Other Trading Activities" (updated 2026-08-26) and the General FAQ.

- "Automated trading systems and trade copiers are permitted"; "traders are fully responsible for any
  software errors, malfunctions, or unintended outcomes".
- Flat by 4:45 PM ET Mon-Fri; trading resumes 6:00 PM ET Sun-Thu; no overnight holds on Pro/Flex/Direct.
- No hedging, including opposite positions across accounts or correlated instruments (long MES in one
  account and short MNQ in another counts).
- No micro-scalping (>50% of profit from trades held <= 5 s) and no HFT.
- News trading allowed on Flex/Pro/Direct (hard breach only on LucidDaily).
- Platforms: NinjaTrader, Tradovate and Rithmic-based platforms (data provider dependent).

Fit of the paper candidates: every sleeve flattens at the first 15-minute bar opening 15:55 ET or later,
holds 15 minutes to several hours, and never carries overnight. Running two candidates that can be long
MES and short MNQ at the same time in two Lucid accounts would breach the hedging rule, so one candidate
per household, or one combined account, is the safe shape.

## Route options

| Route | How | Fidelity to the research engine | Effort / risk |
|---|---|---|---|
| A. Server engine -> Tradovate API | the droplet job that already produces the paper ledger submits the same orders to a Tradovate demo account first, then (on go) the Lucid Tradovate account | exact signals (same code); fills become real broker fills | needs Tradovate API access (paid API add-on or Lucid-provided), OAuth token refresh, order/position reconciliation, kill switch |
| B. TradingView alert -> webhook -> bridge | `pine/mass_sleeve_15m_v1_0_1.pine` alert JSON -> `paper_webhook.py`-style receiver -> Tradovate/NinjaTrader order; same pattern as the crypto paper set | Pine overlay differs slightly from the engine (EMA seeding, touch fills, integer slippage); alert latency 1-10 s | no broker API coding if a third-party bridge (TradersPost, PickMyTrade, TradingView-Tradovate connector) is used; third-party cost and reliability |
| C. NinjaTrader strategy | port the sleeves to NinjaScript on the Lucid NinjaTrader connection | another re-implementation to reconcile | highest porting effort; runs on Nick's PC, so uptime depends on it |

Recommendation: A for the authoritative path (one implementation, already running on the droplet, 15-minute
cadence means a one-minute polling job is fast enough), with B kept only as a visual overlay. Decide after
the paper period; a Tradovate *demo* account can be wired first to measure real fill slippage against the
engine's 1.5-2 tick assumption without touching Lucid.

## Minimum controls before any live connection

1. Paper period: at least 8 weeks or 60 closed trades on the server ledger, no divergence records, and
   forward P&L inside the training-era distribution (no intrabar DD above the worst training year).
2. Risk governor outside the strategy code: per-account hard stop at Lucid's trailing drawdown minus a
   buffer, daily loss cap, max contracts, forced flat at 15:55 ET and 16:40 ET, and a dead-man switch
   that flattens if the job misses two 15-minute cycles.
3. Reconciliation: broker positions and fills reconciled against the engine ledger every cycle; any
   mismatch flattens and halts.
4. Data: the live signal must come from the broker/exchange feed (Tradovate market data), not the Yahoo
   proxy; the proxy stays as a cross-check.
5. Explicit, written go from the account owner naming the account, candidate, version hash and risk
   limits; a log entry records it.

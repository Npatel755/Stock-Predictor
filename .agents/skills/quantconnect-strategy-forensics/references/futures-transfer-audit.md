# NQ / ES → MNQ / MES Translation Audit

The user's target can include research signals generated from NQ/ES history and execution on MNQ/MES. These are closely related contracts but **not interchangeable fills**.

## Contract research checklist
1. Verify current CME tick size, contract multiplier, settlement/exchange hours, holiday schedule, margin, and broker-specific commission for each instrument; maintain dated sources. Do not hardcode fees in skill as universal truths.
2. Distinguish normalized analytical continuous series from raw exchange contract prices and tradable LEAN mapped symbols. Never send orders at back-adjusted signal prices.
3. Explicitly select contract mapping and normalization modes and document their impact on signals and returns; roll open positions across expirations with spread, volume/impact and commissions.
4. Keep timestamps consistent (exchange timezone, US Eastern, UTC, daylight saving, session boundaries); audit whether an opening-range calculation inadvertently uses bars from another session.
5. If NQ/ES creates signals but MNQ/MES is traded, align actual timestamps and use micro bid-ask / spread / slip estimates from the micro contract where available. An E-mini price or volume series is not automatically an accurate micro fill proxy.
6. Simulate simultaneous NQ/MNQ or ES/MES market data latency and missed signals if cross-contract execution is part of the thesis. Do not assume zero latency.
7. Compute P&L in ticks × per-contract tick value × position size less all round-trip costs; use realistic position sizing in the funded account, margin and contract caps.
8. Model risk-relevant path features (realized drawdown, trailing intraday high watermark if required, daily limits, lockout) rather than only end-of-day equity.
9. Test stop/target ordering with finer data when available; otherwise conservative fill assumptions.
10. Run trials under at least two fee/slippage regimes and mark inaccessible market-depth and true queue-fills as execution uncertainty.

## Anti-overfitting rules
- Any interval already shown in a source article is not untouched independent validation.
- All new rule variations and instrument-specific filters are developed on training data only.
- Use distinct risk/conformance metrics for different funded-account products; verify the current LucidFlex rules directly instead of assuming a fixed policy.
- Reject a transfer that only works with impossible fills or micro-specific fees omitted.

## Independence check
A strong original LEAN reproduction demonstrates code fidelity, not necessarily a live edge in MNQ/MES. Demand genuinely unused samples or prospective paper-trading evidence for transfer confidence.

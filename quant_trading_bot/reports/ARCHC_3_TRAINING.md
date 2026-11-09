# archc_3 — "breadth" (MES confirmation) gate on Architecture C (training 2010–23 only)

Protocol research/archc_3/PROTOCOL.md; script scripts/archc_3_pilot.py; raw reports/ARCHC_3_TRAINING.json. Fixed engine, $150 budget, strict 1c router. 2024–26 not loaded.
Context: Antigravity's "Architecture C++ (Breadth Router)" table (Nick's screenshot 2026-11-09; no script pushed) — +16,351 / 1,463 trades / DD 1,025 vs Enhanced C +16,048 / 1,543 / DD 1,025.

| variant | net | trades | $/trade | closed DD | +years | max-yr | 2010–19 | removed trades (net) | random removals worse |
|---|---|---|---|---|---|---|---|---|---|
| baseline ag_arch_c | +16,070 | 1,980 | 8.12 | 1,596 | 11 | 42 % | +5,050 | – | – |
| B1 MES must agree (all sleeves) | +6,695 | 1,208 | 5.54 | 2,642 | 9 | 62 % | +2,369 | 934 (+11,153) | 193/200 |
| B2 MES must agree (trend sleeves only) | +10,464 | 1,474 | 7.10 | 1,673 | 7 | 57 % | +2,889 | 612 (+7,379) | 176/200 |
| B3 MES must not be opposite | +16,050 | 1,980 | 8.11 | 1,596 | 11 | 42 % | +5,030 | 2 (+86) | – |

## Verdict: 0 of 3 — cross-index confirmation destroys the edge; nothing deployed
- The trades that MES confirmation removes are far *better* than average (+$11.9/trade vs $8.1): Architecture C earns on days when NQ drives while ES does not
  follow. That matches crabel_1 (the Crabel open-drive does not transfer to MES): the pattern is an NQ-relative-strength effect, and a "breadth" requirement
  removes exactly those days. MES is almost never opposite at the decision bar (B3 changes 2 trades), so a "veto on disagreement" is a no-op.
- Their C++ cannot be assessed without the spec. Their DD (1,025) is below any Arch C variant on the fixed engine (1,589–1,596 for C / Enhanced C), so their
  engine still differs; if their "breadth router" is MES confirmation, it fails here. Awaiting their push.

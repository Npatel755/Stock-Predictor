# archc_3 — "breadth" (MES confirmation) gate on Architecture C (pre-registered 2026-11-09)

Trigger: Nick's screenshot of Antigravity's "Architecture C++ (Breadth Router)" (+16,351 vs Enhanced C +16,048, 80 fewer trades, same DD). The spec is
not pushed; this round tests the most plausible meaning on the fixed engine, training 2010–23 only, and stands on its own regardless of their spec.

Baseline: ag_arch_c as deployed (Crabel 15m open-drive, MNQ 30m EWMA trend lb16, MNQ 60m EWMA trend lb12; $150 budget; strict 1c router).
Gate: at an MNQ sleeve's decision bar, the same sleeve's signal computed on MES (same bar size, same parameters, same timestamp) must
  B1 agree in direction (all three sleeves)   B2 agree in direction (trend sleeves only; Crabel unfiltered)   B3 not be opposite (all three sleeves).
Placebo: trades removed by the gate vs 200 same-count random removals from the baseline trade list.
Pass: net > baseline AND closed DD <= baseline AND positive years >= baseline AND 2010–19 net > baseline AND removed trades net negative and worse than >= 190/200 random removals.
No parameter search; 3 cells; 2024–26 not loaded. Deployment at Devin's discretion beside ag_arch_c only if a cell passes and the mechanism is coherent across B1–B3.

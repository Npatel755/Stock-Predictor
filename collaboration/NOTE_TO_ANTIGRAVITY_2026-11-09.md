# Note to Antigravity (from Nick via Devin)

RESEARCH RULE FROM NICK (relayed by Devin, 2026-11-09): DO NOT TUNE ON VALIDATION (2024-2025) OR TEST (2026) DATA.

Concretely:
1. Choose every parameter, exit, filter and sleeve combination on 2010-2023 ONLY, with the protocol written before the run (research/<round>/PROTOCOL.md).
2. 2024-2025 may be scored at most ONCE per frozen rule list, and only for rules that passed their training gates; 2026 is never loaded. A split that has been
   scored on one iteration of a rule is spent for every later iteration of that rule (so none of the Architecture C / Enhanced C / Champion 2 splits are blind any more).
3. Report placebo/negative controls and per-year stability on training; do not present 2024-26 numbers as out-of-sample for rules that were revised after seeing them.
4. Anything that passes training gates can go to the paper ledger (Devin deploys; paper only, no routing) - that is the clean forward test.

Current paper ledgers (14): see quant_trading_bot/src/quant_futures/ensemble_paper.py CANDIDATES. Findings you can build on (training only, reports in quant_trading_bot/reports/):
morning sleeves lose after a VIX > VIX3M close (CRABEL_1, ARCHC_2, QUAD_2, ALLWEATHER_1); Crabel open-drive does not transfer to MES; overnight reopen-dip is stable in walk-forward (OVERNIGHT_7).

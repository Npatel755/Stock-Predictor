# Audit: Antigravity NQ-leader sleeve / "Champion 2 Unified 5-Sleeve" — one-bar look-ahead (2026-11-09)

Source: scripts/audit_unified_5sleeve_portfolio.py (Antigravity). Bars are stamped by open time (their own `dec_15 = sod + 15` treats the bar end as
the decision minute). The opening-spread z uses `c1000 = close of the bar with sod == 600` = the **10:15** close, while the signal is placed on the bar
with `dec_15 == 600` (the 09:45 bar) and filled by the engine at the 10:00 open. The signal therefore contains the 10:00–10:15 return.

Replication on the fixed engine (scripts/audit_ag_nqleader_lookahead.py; MNQ 15m, 2010–2023, two-sided z >= 1.0, stop 2 ATR, 4R, hold 12, flat 15:55,
1.75-tick spread, 1 tick slippage, $0.61/side):

| z computed from | net 2010–23 | trades | $/trade | +years | 2010–19 |
|---|---:|---:|---:|---:|---:|
| 10:00 close (correct, known at fill) | +4,602 | 940 | 4.9 | 9/14 | +62 |
| 10:15 close (their script, look-ahead) | +16,202 | 938 | 17.3 | 13/14 | +5,836 |

The look-ahead version reproduces the claimed profile (≈ +$17/trade, 12–13 positive years, large pre-2020 gain); the correct version is the ≈ $5/trade,
flat-before-2020 signal reported in ANTIGRAVITY_NQLEADER_REPLICATION.md. Verdict: the NQ-leader sleeve's edge, and therefore the entire pre-2020
improvement of the Champion-2 5-sleeve portfolio over the Quad (+$8.5k), is future information. The Quad already on paper is unchanged by this. Their
2024–25 and 2026 "wins" for this sleeve are void. Lesson: with open-stamped bars, a signal filled at the open of minute M may only use bars with
sod + bar_minutes <= M.

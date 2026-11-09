# Antigravity "Grand Champion Architecture D" — fixed-engine replication (2026-11-09, training 2010–23 only)

Spec (from scripts/audit_champion1_all_splits.py + audit_champion1_enhanced_afternoon.py, pulled 2026-11-09 04:57): Champion 1 "Dual Morning" = at the 10:00 ET
close, Crabel open-drive (09:30 open / 10:00 close in opposite 20 % tails of the 09:30–10:00 range) and NQ-leader (z of MNQ−MES 09:30→10:00 return ≥ +1.25 / ≤ −1.25,
std of prior 20 sessions); agree or single signal → trade that direction, conflict → flat; long and short; stop 2 ATR14(15m), 4R, hold 12 bars, flat 15:55;
plus an afternoon MNQ 30m EWMA trend sleeve (lb 8, |trend| ≥ 0.5, decisions 13:30–15:15 ET, stop 1.5 ATR, 4R, hold 8) only while the morning is flat.
$150 stop-risk budget, strict 1c router. Script: scripts/replicate_antigravity_arch_d.py; raw: reports/ANTIGRAVITY_ARCH_D_REPLICATION.json. 2024–26 not loaded.

| component (2010–23) | net | trades | $/trade | closed DD | +years | max-yr | 2010–19 net (trades) |
|---|---|---|---|---|---|---|---|
| Crabel only | +6,468 | 638 | 10.14 | 973 | 8 | 45 % | +847 (483) |
| NQ-leader only | +3,664 | 648 | 5.65 | 988 | 8 | 42 % | −223 (492) |
| Champion 1 (dual morning) | +7,011 | 1,012 | 6.93 | 979 | 7 | 27 % | +356 (766) |
| afternoon 30m trend only | +2,736 | 899 | 3.04 | 1,069 | 7 | 44 % | +513 (735) |
| **Architecture D** (morning + afternoon, 1c router) | **+9,746** | 1,911 | 5.10 | 1,775 | **7** | 28 % | **+868 (1,501)** |

Sender's claims (their engine): training +19,301 (4,384 pre-2020 + 14,917 post-2020), continuous DD 1,312, 13/17 years, "76.9 % OOS outperformance", 2026 +1,880.

## Verdict: FAIL — not a paper ledger
- 7 of 14 training years positive; 2010–2016 every year negative; 2010–19 earns $0.58 per trade on 1,501 trades (one tick of extra slippage = −$1/trade).
  Everything is 2018 and 2020–23. Gate requires ≥ 11/14 years and a meaningful pre-2020 edge.
- Training total does not reproduce (+9.7k vs +19.3k; trade counts comparable), consistent with every earlier Antigravity replication (their engine fills/accounting are more generous).
- Both morning components were replicated and rejected before (reports/ANTIGRAVITY_CRABEL_VIX_REPLICATION.md, ANTIGRAVITY_NQLEADER_REPLICATION.md): real day-selection,
  tiny and 2020–21-heavy. Combining two weak 10:00 signals plus a $3/trade afternoon sleeve does not create a fundable edge.
- Contamination: their "Diagnostic and Enhancement Protocol" (scripts/diagnose_champion1_2026.py) added the afternoon sleeve to answer "why did Champion 1 only take 5 trades
  in 2026?" — the 2026 test split drove the design, so the 2024–26 columns are not out-of-sample for D; the validation split was also scored for Champion 1 and 2 before.

# composite_1 — composite selected-day 10:00 entry (pre-registered 2026-11-09, before any run)

Motivation: three independent day-selection signals each beat same-count random-day placebos 20/20 on 2010-23 but fail the gates alone
(NQ/ES opening divergence, Crabel open-drive, VIX/VIX3M velocity crush; reports/ANTIGRAVITY_NQLEADER_REPLICATION.md, ANTIGRAVITY_CRABEL_VIX_REPLICATION.md).
Question: does combining them raise the per-trade edge above one round trip while keeping 10/14 years?

Signals (exactly as already replicated, computed on the 09:30 and 09:45 15m bars, decision at the 09:45 bar close, fill at the 10:00 open):
 S1 divergence: z = (NQ 09:30-10:00 return - ES return) / std over prior 20 sessions; |z| >= 1.25, direction = sign(z).
 S2 Crabel: open tail <= 0.20, close tail >= 0.85 (bull) / <= 0.15 (bear), range >= 1.0 ATR14; direction bull +1 / bear -1.
 S3 VIX crush: prior-day VIX/VIX3M ratio change <= -0.015 and 09:30-10:00 return >= +0.1%; direction +1 (long only).
Fixed exits for every variant (no grid): stop 1.5 ATR14, target 4R, hold 20 bars, flat 15:55 ET, 1 MNQ, micro costs (1.75-tick spread, 1 tick slippage, $0.61/side).
Variants (6): A any-signal two-sided (direction = sign of the sum, skip if 0); B any-signal long-only; C >= 2 agreeing signals two-sided; D >= 2 agreeing long-only;
E S1 & S2 both firing and agreeing; F day count-weighted: trade only when exactly one signal fires (tests whether overlap or union carries the edge).
Placebo: 20 random day sets per variant with the same number of long and short days per year, same entry/exits. Gates: net > 0, >= 10/14 years, no year
> 40% of net, >= 95% placebo dominance, >= 100 trades, and net per trade >= $8 (about 1.5 round trips) on 2010-23. Passers (if any) frozen, then one-shot
validation 2024-25; 2026 never loaded. Multiplicity: 6 variants, all reported. No paper promotion without Nick's yes.

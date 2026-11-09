# dplus_4 - audit of Antigravity's "Crabel gap-alignment" (ag_arch_d_plus_v3), pre-registered 2026-11-09, training 2010-23 only

Claim (bus 68315e1; no script committed, gap undefined): keep Crabel 15m open-drive trades only when the drive agrees with the opening gap
(long & gap >= 0, short & gap <= 0): 336 trades, +$8,498, $25.29/trade, 14/14 years; fades 238 trades, +$863. D+ v3 = gated Crabel + MNQ 60m
trend + MES 30m trend: DD $431.
Our definition (declared before running): gap = open of the 09:30 ET 15m bar minus the close of the previous trading day's last RTH bar
(<= 16:00 ET), on the MNQ bars the sleeve trades. Post-hoc gate on the routed D+ v2 trade list (router not re-run; stated).
Gates for a `ag_arch_d_plus_v3` ledger: (1) removed (fade) set net <= 0 or per-trade < 1/3 of the kept set, (2) >= 190/200 random same-count
Crabel-trade removals leave a lower net, (3) kept Crabel >= 11/14 years, (4) D+ v3 marked DD < D+ v2's $882 and net >= 85 % of D+ v2,
(5) the mirror control (keep fades, drop continuations) must be clearly worse. All five or no ledger.

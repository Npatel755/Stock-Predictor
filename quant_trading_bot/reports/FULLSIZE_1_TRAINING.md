# fullsize_1 — re-score at full-size NQ economics (2026-11-09)

Protocol research/fullsize_1/PROTOCOL.md. NQ: tick $5, 1-tick spread, 1 tick slippage/side, $2.50/side (Topstep's actual $1.89 would change results by
< $1.25/trade), funded lock $2,000 intrabar / $400 daily applied per contract, 2010–2023 by year. Script scripts/fullsize_1_pilot.py; JSON alongside.

| rule @ 1 NQ | net | trades | $/trade | +years | worst-year DD | lock breaches |
|---|---:|---:|---:|---:|---:|---:|
| F2 NQ/ES opening divergence, two-sided | −465 | 32 | −14.5 | 5 | 538 | 0 |
| F3 composite B (any signal, long) | −1,315 | 150 | −8.8 | 4 | 2,010 | 1 |
| F3 composite D (two agree, long) | −425 | 49 | −8.7 | 3 | 788 | 0 |
| F4a fixed 15m momentum lb24 | −9,035 | 242 | −37.3 | 2 | 2,023 | hits the $2k lock in nearly every year |
| F4b AG morning EWMA trend lb16 (30m) | −185 | 62 | −3.0 | 4 | 1,158 | 0 |

Verdict: **REJECTED — nothing crosses from sub-cost to profitable at full size.** The 1.4–2 ticks saved per round trip do not matter because at 1 NQ the
funded constraints bind first: the 15m momentum rule loses ≈ $1.8k and stops at the $2k lock almost every year (the engine's $400 daily-loss and risk
caps also throttle entries, which is why trade counts are far below the MNQ runs), and every day-selection rule is negative over 2010–19. Trade counts after
2019 were not confirmed in this run (totals equal the pre-2020 sums) — flagged for a re-check, but it cannot change the pre-2020 verdict. Conclusion for the
project: full-size contracts do not unlock the sub-cost signals; they only make the drawdown lock the limiting factor. Overnight holding (overnight_1) is
the remaining structural change worth testing.

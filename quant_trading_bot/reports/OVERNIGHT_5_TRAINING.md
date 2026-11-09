# overnight_5 — scheduled-release calendar gate on overnight_dip_v2 (training 2010–2023; 2024–26 sealed) — REJECTED, 0 of 5

Protocol: research/overnight_5/PROTOCOL.md. Script: scripts/overnight_5_pilot.py. Raw: reports/OVERNIGHT_5_TRAINING.json. Champion: +$11,797 / 490 nights / $24.1 per night / 12 of 14 years / DD $1,646.

| variant | net | nights | $/night | +yrs | DD | removed nights | verdict |
|---|---:|---:|---:|---:|---:|---|---|
| R1 skip tier-1 08:30 release mornings (CPI, NFP, PPI, retail, GDP) | 10,839 | 446 | 24.3 | 12 | 1,398 | 44 nights, +$959, t 1.0 | release nights are not a drag → no gate |
| R2 release mornings only | 959 | 44 | 21.8 | 8 | 602 | – | same per-night as the rest |
| F1 skip pre-FOMC nights | 9,147 | 473 | 19.3 | 11 | 2,358 | **17 nights, +$2,650, $156/night, t 2.5** | removing them hurts badly |
| F2 pre-FOMC nights only | 2,650 | 17 | 155.9 | 7 | 16 | – | small, consistent with the pre-FOMC drift literature |
| R3 skip both | 8,188 | 429 | 19.1 | 12 | 1,756 | 61 nights, +$3,609 | worse |

Attribution: on release mornings the 08:30 → 09:45 leg averages +30 ticks vs +7 on other mornings — the dip-night reversal is, if anything, helped by the
08:30 print, so there is no reason to avoid them. Pre-FOMC dip nights (17 in 14 years) earned $156/night with a $16 max drawdown — too few to gate on,
but an unconditional pre-FOMC overnight hold (Lucca–Moench drift) is a separate, pre-registrable hypothesis (overnight_6).
No change to v2; nothing deployed.

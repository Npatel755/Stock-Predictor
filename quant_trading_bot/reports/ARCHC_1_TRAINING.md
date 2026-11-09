# archc_1 — improvement round for Architecture C (training 2010–2023 only; 2024–26 sealed) — REJECTED, 0 of 18

Protocol: research/archc_1/PROTOCOL.md (pre-registered). Script: scripts/archc_1_pilot.py. Raw: reports/ARCHC_1_TRAINING.json.
Champion re-scored inside the run with the stated commission ($0.61/side; the engine moved only −$272 vs the default run, so the spread override
appears not to be honoured — comparisons below are like-for-like in any case): **+$15,798 / 1,976 trades / $7.99 per trade / 10 of 14 years / largest
year 42.5 % / closed DD $1,604 / 2010–19 +$4,727.**

| variant | net | trades | $/trade | +yrs | 2010–19 | max yr | DD | verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| A1 drop Crabel | 11,915 | 1,666 | 7.2 | 11 | 4,490 | 40 % | 2,480 | worse, DD over floor |
| A2 drop 30m trend | 12,873 | 1,357 | 9.5 | 10 | 3,432 | 37 % | **974** | less net, much lower DD |
| A3 drop 60m trend | 10,606 | 1,397 | 7.6 | 11 | 2,088 | 47 % | 1,182 | worse |
| A4 trend-first priority | 15,798 | 1,976 | 8.0 | 10 | 4,727 | 42 % | 1,604 | identical (decision times rarely tie) |
| B1 Crabel tails 0.15 | 13,002 | 1,854 | 7.0 | 10 | 4,886 | 44 % | 2,402 | worse |
| B2 Crabel tails 0.25 | 13,217 | 2,185 | 6.1 | 8 | 3,518 | 52 % | 2,744 | worse |
| B3 range ≥ 1 ATR filter | 15,798 | 1,976 | 8.0 | 10 | 4,727 | 42 % | 1,604 | identical (every open-drive day already qualifies) |
| B4 Crabel long-only | 13,690 | 1,841 | 7.4 | 9 | 4,955 | 46 % | 2,309 | worse |
| B5 Crabel stop 1.5 / hold 20 | 14,889 | 2,063 | 7.2 | 9 | 3,529 | 51 % | 2,194 | worse |
| C1 hold × 1.5 | 15,836 | 1,976 | 8.0 | 8 | 4,499 | 45 % | 2,010 | flat net, worse everything else |
| C2 target 3R | 14,355 | 1,995 | 7.2 | 10 | 4,705 | 47 % | 1,604 | worse |
| C3 trailing 2 ATR | 14,146 | 2,001 | 7.1 | 10 | 3,665 | 49 % | 1,825 | worse |
| D1 only VIX ≥ 15 | 11,679 | 879 | 13.3 | 11 | 2,548 | 31 % | 2,007 | beats 2 of 20 same-count random-day sets |
| D2 only VIX/VIX3M ≥ 0.9 | 5,029 | 620 | 8.1 | 9 | 2,690 | 46 % | 2,256 | 4 of 20 |
| D3 only high realized vol | 7,553 | 886 | 8.5 | 11 | 4,142 | 30 % | 1,698 | **0 of 20** |
| E1 2 contracts when VIX ≥ 25 | 16,924 | 1,976 | 8.6 | 10 | 3,807 | 45 % | 2,210 | DD over floor |

## Reading
- Architecture C sits at a local optimum of its own grid — every single change makes it worse or leaves it unchanged, which is what a best-of-grid
  rule looks like in-sample. No challenger; nothing goes to paper beyond `ag_arch_c` v1.0.0.
- The one informative result is negative: **volatility gating hurts**. Restricting to high-VIX / high-realized-vol days does *worse* than the same number
  of random days (0–4 of 20 placebos), so the sleeves earn their money on ordinary days and lose on stress days — the opposite of the overnight dip rule.
  That also means 2021's 42 % share is not a "stress regime" artefact but a trend-persistence one.
- Removing the 30m trend sleeve (A2) is the only variant that improves the funded profile (DD $974, $9.5/trade) at the cost of −$2.9k net; it fails the
  pre-registered net gate and is recorded, not adopted.
- Paper caveat (all candidates): the engine's $150-per-trade risk budget blocks any 1-contract entry while the 15m ATR is ≈110–130 NQ points (a 2-ATR stop ≈ $440),
  which is the case now; paper evidence accrues only when volatility normalises.

# sizing_1 — $150 stop-risk budget (as deployed) vs always-one-contract, training 2010–23 (2026-11-09)

Protocol: research/sizing_1/PROTOCOL.md (pre-registered). Script: scripts/sizing_1_pilot.py. Data: MNQ/MES train split only; 2024–26 not loaded.
Question: the paper ledgers have taken no intraday trade since 2026-11-06 because the engine refuses any 1-contract entry whose stop risk exceeds
$150 (15-min NQ ATR ≈ 110–130 pts → 1.25–2 ATR stops ≈ $300–520). Were the trades this rule blocked historically good or bad?
V0 = engine as deployed; V1 = same sleeves, same filters, `risk_per_trade = max_open_risk = ∞`, max 1 contract, every other gate unchanged.

| candidate | V0 net / trades / DD / +yrs / P(DD≥2k,1y) | V1 net / trades / DD / +yrs / P(DD≥2k,1y) | added trades (n, net, $/tr) | random same-count trade sets p50 | gate |
|---|---|---|---|---|---|
| ag_quad_v2 | +17,707 / 2,274 / $2,048 / 11 / 2.4 % | +23,319 / 2,440 / **$2,061** / 12 / 4.8 % | 185, +6,430, $34.8 | +1,983 | FAIL (DD > $2,000; 2022 = 48 % of net) |
| ag_arch_c_v2 | +17,868 / 1,856 / $1,596 / 12 / 0.2 % | +20,028 / 1,957 / $1,911 / **11** / 1.8 % | 105, +2,284, $21.8 | +991 | FAIL (positive years 11 < 12; DD +$315) |
| ag_all_weather_v2 | +14,073 / 1,551 / $1,455 / 8 / 0.2 % | **+16,520 / 1,590 / $1,256 / 8 / 0.2 %** | 39, +2,447, $62.7 | +120 | **PASS** (all five conditions) |

(ag_arch_c_v2 V0 is +17,868 here vs +17,291 in ARCHC_2_TRAINING.md: this pilot routes with the paper runner's sleeve order/decision-time rule; same
sleeves, same filter. The gap is router tie-breaking, not a parameter change.)

Stop-risk buckets of V1 trades (1-contract stop risk at the decision bar, approx.): Quad <150: 2,256 tr $7.5/tr · 150–250: 166 tr $39.5 · 250–400: 14 tr −$26.5 · >400: 4 tr;
Arch C <150: 1,853 tr $9.6 · 150–250: 98 tr $34.8 · 250–400: 6 tr −$180; All-Weather <150: 1,551 tr $9.1 (38 % win) · 150–250: 39 tr $62.7 (51 % win) · none above $250.

## What this says
- The budget was blocking *better-than-average* trades in every candidate: the added $150–250-risk trades earn 4–7× the per-trade average and beat
  random same-count sets of the candidate's own trades by a wide margin (Quad +6,430 vs p50 +1,983; Arch C +2,284 vs +991; All-Weather +2,447 vs +120).
  Mechanism: a bigger ATR is a bigger trend day for these trend/breakout sleeves — the stop scales with ATR but so does the move.
- The cost is concentration: the extra profit sits almost entirely in 2020 and 2022 (Quad 2022 +11,283 vs +5,285; All-Weather 2022 +7,021 vs +4,867),
  i.e. the same high-volatility years that already carry these strategies; 2023 gets slightly worse in all three. The Quad's drawdown crosses the floor
  ($2,061) and Arch C's rises $315 with one fewer positive year — both rejected by the pre-registered gates. Only All-Weather improves on every axis
  (net +17 %, DD −14 %, breach odds unchanged).
- Trades with stop risk above $250 are few (0–18 per candidate in 14 years) and negative where they exist; the data do not support the stop sizes the
  current regime would require (≈$425–520 at today's ATR). So even V1 says nothing about trading *today's* volatility — it says the budget should not
  cut off the $150–250 band.

## Decision
- Deployed **`ag_all_weather_v2_1c`** (15th paper ledger, version 2.1.0) beside `ag_all_weather_v2`: same two filtered sleeves, risk budget removed, all
  other gates (daily loss, hard drawdown, funded lock, flatten 15:55) unchanged. Paper only, simulated fills, no routing. Runner change: `run_sleeve`
  honours a per-sleeve `risk_per_trade`/`max_open_risk` override (src/quant_futures/ensemble_paper.py).
- Quad and Arch C one-contract variants: rejected and **not** deployed; the $150 budget stands for them and for every other ledger.
- The zero-trade state of the intraday ledgers is therefore still the rule working as intended at today's ATR; it is not a missed edge. An intermediate
  budget (e.g. $250) was *not* tested — it would be a new parameter picked after seeing these results, so it would need its own pre-registered round
  (and the one-year bootstrap says the 150–250 band adds little drawdown, so that round has a plausible prior).
- No 2024–26 data were touched.

# quad_2 — backwardation stand-aside for the Quad's morning sleeves (training 2010–2023; 2024–26 sealed) — PASS

Protocol: research/quad_2/PROTOCOL.md. Script: scripts/quad_2_pilot.py. Raw: reports/QUAD_2_TRAINING.json. Engine default costs; trade-level 1-contract router.

| | net | trades | $/trade | +yrs | 2010–19 | max yr | closed DD | by sleeve (morn30 / 60m / pm30 / MES) | removed days | removed net | random 5th pct |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| champion (ag_quad) | 16,811 | 2,355 | 7.14 | 11 | 4,651 | 31 % | 2,048 | 5,200 / 6,456 / 2,377 / 2,779 | – | – | – |
| V1 morning sleeves stand aside after VIX > VIX3M close | **17,707** | 2,274 | 7.79 | 11 | 5,277 | 30 % | 2,048 | 6,333 / 6,226 / 2,283 / 2,866 | 35 | **−1,374** | −336 |

All gates pass (net ↑, DD ≤, years =, removed days genuinely bad). Deployed as `ag_quad_v2` beside `ag_quad` (afternoon and MES sleeves unfiltered). The Quad's
training DD of $2,048 is itself at the funded floor — both versions carry that caveat. Nothing scored on 2024–26.

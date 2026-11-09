# archc_4 — NQ-only drive: trade the intraday sleeves only when MES does NOT confirm (pre-registered 2026-11-09, derived from archc_3)

Derivation (declared): archc_3 showed the Architecture C trades removed by an MES-confirmation gate earn $11.9/trade vs $5.5 for the confirmed ones.
This round tests the flipped hypothesis as a mechanism — NQ relative-strength drive while ES lags — on training 2010–23 only. Because it is derived from
a result on the same split, it must pass stricter gates and show coherence across sleeve families before anything is deployed.

Cells: R1 Arch C, all sleeves: take an MNQ decision bar only if the MES signal (same sleeve, same bar) is NOT the same direction.
       R2 Arch C, trend sleeves only (Crabel unfiltered).  R3 ag_all_weather_v2_1c sleeves (30m breakout lb8, 60m trend) with the R1 gate (coherence).
Placebo: kept trades vs 200 random same-count subsets of the baseline trade list (R3: of the All-Weather baseline).
Pass (each): net/trade > baseline, closed DD <= baseline, positive years >= baseline, max-year share <= 40%, 2010–19 net > 0.5 x baseline, kept set beats >= 190/200 subsets.
Deploy only if R1 or R2 passes AND R3 shows the same sign (per-trade up); otherwise record. 2024–26 not loaded; no parameter search (gate is binary).

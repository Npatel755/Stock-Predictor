# overnight_5 — scheduled-release calendar gate for overnight_dip_v2 (pre-registered 2026-11-09; training 2010-2023 only; 2024-26 sealed)

Champion: overnight_dip_v2 (MNQ 18:05 -> 09:45 when MNQ and MES reopen gaps <= -0.5 sd20). Calendar: research/news/official_calendar_2010_2026.csv (scheduled
dates known in advance -> point-in-time safe). "Release night" = the exit morning (09:45) has a tier-1 08:30 ET release: CPI, EMPLOYMENT (NFP), PPI, RETAIL_SALES, GDP.
"Pre-FOMC night" = the exit day is an FOMC decision day. Variants (all reported):
 R1 skip release nights   R2 release nights only   F1 skip pre-FOMC nights   F2 pre-FOMC nights only   R3 skip release nights AND pre-FOMC nights
Attribution (informational): mean/t of the nightly net on release nights vs other nights; the 08:30 -> 09:45 leg separately on release nights.
Gates for a skip-variant to replace the champion: net > champion, >= 12 positive years, DD <= champion DD, per-night >= champion per-night, >= 100 nights,
and the removed nights must be net negative with t <= -1.5 (so the gate removes a real drag, not noise). Multiplicity: 5 trials. No promotion to paper
without the gates; 2024-26 never scored.

# v1.3 exit-management experiment

All years have been inspected. 2020-2022 now become development data after failed transfer; 2025 selection is reused; 2026 audit is retrospective, not independent validation.

Tested 24 fixed configurations; shortlisted 6 changed configurations using 2020–2024. Selected **rr3.0_be1.5_trail0.0** before the 2026 audit.

Historical promotion gate passed: **False**. This is not readiness for funded trading.

| Period / execution | Saved v1.2 | Candidate v1.3 |
| --- | ---: | ---: |
| 2020, independent account | $431.18 | $-557.35 |
| 2021, independent account | $-2,012.47 | $-1,542.13 |
| 2022, independent account | $-1,512.58 | $-1,095.21 |
| 2023, independent account | $1,338.39 | $762.39 |
| 2024, independent account | $656.27 | $887.67 |
| 2025 H1, independent account | $25.50 | $-455.96 |
| 2025 H2, independent account | $1,639.91 | $704.57 |
| audit_2026 | $684.86 | $-536.79 |
| continuous_2020_2026 | $1,251.07 | $-1,832.80 |
| recent_october | $-200.68 | $4.83 |

Selected continuous 2025 with 4bp extra slippage: $153.26.

Annual and half-year rows start new accounts with causal indicator warm-up. Continuous replay is a separate account; fold sums are not its achieved P&L. Research execution includes next-open entries, fees, two ticks plus basis-point slippage, financing and stop-first handling. All configurations keep the same $100 planned risk and 5x maximum leverage. Stops tighten only after completed bars. Open positions remain marked at endpoints.

The recent October diagnostic was run after selection and cannot select parameters. It ends October 28 exclusive; missing later days are not fabricated. Earlier-regime data is now development data, so its results cannot be called an untouched transfer test. All candidates, negative results, source/data hashes and frozen selection remain in the artifact directory. No v1.2 file is overwritten and no orders are sent.

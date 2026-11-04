# Frozen formation robustness diagnostics

| Asset | Strategy | Scenario | Trades/week | Net | Intrabar bound |
| --- | --- | --- | ---: | ---: | ---: |
| ETH | triangle_30m_responsive | delay_extra_bar | 2.87 | $690 | 2.8% |
| ETH | triangle_30m_responsive | lower_capacity | 2.97 | $-368 | 3.4% |
| ETH | triangle_30m_responsive | crisis_costs | 2.97 | $-6,507 | 13.0% |
| ETH | triangle_30m_responsive | risk_050 | 2.97 | $-570 | 6.2% |
| ETH | triangle_30m_responsive | long_only | 1.58 | $287 | 2.5% |
| ETH | triangle_30m_responsive | short_only | 1.39 | $-294 | 2.6% |
| ETH | triangle_30m_responsive | lag24h | 1.75 | $-1,536 | 5.9% |
| ETH | triangle_30m_responsive | ATR_brackets | 3.02 | $-593 | 3.4% |
| ETH | triangle_30m_responsive | alternate_recognition | 1.61 | $-341 | 3.0% |
| BNB | triangle_30m_responsive | transfer_from_ETH | 2.90 | $-500 | 2.7% |
| ETH | head_shoulders_15m_responsive | delay_extra_bar | 3.69 | $-4,638 | 10.4% |
| ETH | head_shoulders_15m_responsive | lower_capacity | 3.72 | $-2,589 | 6.2% |
| ETH | head_shoulders_15m_responsive | crisis_costs | 3.74 | $-10,758 | 21.8% |
| ETH | head_shoulders_15m_responsive | risk_050 | 3.72 | $-5,783 | 13.8% |
| ETH | head_shoulders_15m_responsive | long_only | 1.66 | $-604 | 2.7% |
| ETH | head_shoulders_15m_responsive | short_only | 2.08 | $-2,753 | 6.4% |
| ETH | head_shoulders_15m_responsive | lag24h | 1.66 | $-1,546 | 4.6% |
| ETH | head_shoulders_15m_responsive | ATR_brackets | 3.72 | $-3,363 | 8.3% |
| ETH | head_shoulders_15m_responsive | alternate_recognition | 1.54 | $-955 | 3.6% |
| BNB | head_shoulders_15m_responsive | transfer_from_ETH | 3.57 | $-1,681 | 3.4% |
| BNB | pattern_mix_1h_selective | delay_extra_bar | 3.12 | $-383 | 3.6% |
| BNB | pattern_mix_1h_selective | lower_capacity | 3.10 | $-314 | 2.3% |
| BNB | pattern_mix_1h_selective | crisis_costs | 3.10 | $-4,711 | 9.6% |
| BNB | pattern_mix_1h_selective | risk_050 | 3.10 | $-239 | 5.4% |
| BNB | pattern_mix_1h_selective | long_only | 1.41 | $822 | 1.1% |
| BNB | pattern_mix_1h_selective | short_only | 1.73 | $-558 | 3.2% |
| BNB | pattern_mix_1h_selective | lag24h | 2.38 | $695 | 3.4% |
| BNB | pattern_mix_1h_selective | ATR_brackets | 3.15 | $-711 | 3.4% |
| BNB | pattern_mix_1h_selective | alternate_recognition | 6.33 | $-1,257 | 7.1% |
| ETH | pattern_mix_1h_selective | transfer_from_BNB | 3.46 | $-2,030 | 5.0% |
| BNB | head_shoulders_15m_responsive | delay_extra_bar | 3.51 | $-1,690 | 3.5% |
| BNB | head_shoulders_15m_responsive | lower_capacity | 3.57 | $-535 | 1.1% |
| BNB | head_shoulders_15m_responsive | crisis_costs | 3.57 | $-5,731 | 11.5% |
| BNB | head_shoulders_15m_responsive | risk_050 | 3.57 | $-2,626 | 5.3% |
| BNB | head_shoulders_15m_responsive | long_only | 2.08 | $-763 | 2.1% |
| BNB | head_shoulders_15m_responsive | short_only | 1.49 | $-912 | 2.0% |
| BNB | head_shoulders_15m_responsive | lag24h | 1.46 | $-884 | 2.0% |
| BNB | head_shoulders_15m_responsive | ATR_brackets | 3.59 | $-1,926 | 4.0% |
| BNB | head_shoulders_15m_responsive | alternate_recognition | 1.16 | $-908 | 2.1% |
| ETH | head_shoulders_15m_responsive | transfer_from_BNB | 3.74 | $-3,332 | 7.8% |

All runs are predeclared diagnostics; no failure is replaced. The alternate recognition changes pivot lag/tolerance together, so it does not isolate a single causal contribution. Cross-asset transfers reuse jointly inspected markets and are not independent holdouts.

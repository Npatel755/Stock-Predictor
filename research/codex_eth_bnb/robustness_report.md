# Robustness diagnostics

Every diagnostic is predeclared and does not choose a replacement after validation.

| Asset | Frozen candidate | Scenario | Net | Return | Intrabar bound | Trades |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| ETH | channel_4h_lookback20 | risk_050 | $2,833 | 5.7% | 6.9% | 111 |
| ETH | channel_4h_lookback20 | risk_100 | $5,579 | 11.2% | 13.5% | 111 |
| ETH | channel_4h_lookback20 | crisis_costs | $-383 | -0.8% | 4.5% | 111 |
| ETH | channel_4h_lookback20 | delay_one_extra_bar | $291 | 0.6% | 5.3% | 119 |
| ETH | channel_4h_lookback20 | low_capacity | $1,425 | 2.8% | 3.5% | 111 |
| ETH | channel_4h_lookback20 | outage_every20bars | $1,500 | 3.0% | 3.4% | 110 |
| ETH | channel_4h_lookback20 | trailing_stop | $1,399 | 2.8% | 3.4% | 113 |
| ETH | channel_4h_lookback20 | leverage_2x | $1,425 | 2.8% | 3.5% | 111 |
| ETH | channel_4h_lookback20 | long_only | $1,238 | 2.5% | 2.9% | 64 |
| ETH | channel_4h_lookback20 | short_only | $183 | 0.4% | 2.2% | 47 |
| ETH | channel_4h_lookback20 | lag24h | $-1,204 | -2.4% | 4.4% | 136 |
| ETH | channel_4h_lookback20 | null_blocks | $-1,437 | -2.9% | 3.2% | 229 |
| ETH | channel_4h_lookback20 | neighbor | $1,340 | 2.7% | 3.1% | 104 |
| ETH | channel_4h_lookback20 | ablate_regime | $1,425 | 2.8% | 3.5% | 111 |
| BNB | channel_4h_lookback20 | no_refit_transfer_from_ETH | $-22 | -0.0% | 3.6% | 109 |
| ETH | tsmom_4h_lookback96_threshold0.35 | risk_050 | $-441 | -0.9% | 9.6% | 153 |
| ETH | tsmom_4h_lookback96_threshold0.35 | risk_100 | $-1,135 | -2.3% | 18.4% | 153 |
| ETH | tsmom_4h_lookback96_threshold0.35 | crisis_costs | $-2,259 | -4.5% | 6.8% | 153 |
| ETH | tsmom_4h_lookback96_threshold0.35 | delay_one_extra_bar | $-1,929 | -3.9% | 7.1% | 170 |
| ETH | tsmom_4h_lookback96_threshold0.35 | low_capacity | $-190 | -0.4% | 4.9% | 153 |
| ETH | tsmom_4h_lookback96_threshold0.35 | outage_every20bars | $-255 | -0.5% | 5.0% | 154 |
| ETH | tsmom_4h_lookback96_threshold0.35 | trailing_stop | $-609 | -1.2% | 4.9% | 172 |
| ETH | tsmom_4h_lookback96_threshold0.35 | long_only | $1,581 | 3.2% | 2.0% | 73 |
| ETH | tsmom_4h_lookback96_threshold0.35 | short_only | $-1,715 | -3.4% | 4.1% | 80 |
| ETH | tsmom_4h_lookback96_threshold0.35 | lag24h | $-1,175 | -2.3% | 6.0% | 182 |
| ETH | tsmom_4h_lookback96_threshold0.35 | null_blocks | $-3,055 | -6.1% | 7.1% | 317 |
| ETH | tsmom_4h_lookback96_threshold0.35 | neighbor | $242 | 0.5% | 3.6% | 146 |
| ETH | tsmom_4h_lookback96_threshold0.35 | ablate_regime | $-190 | -0.4% | 4.9% | 153 |
| BNB | tsmom_4h_lookback96_threshold0.35 | no_refit_transfer_from_ETH | $-3,327 | -6.7% | 7.5% | 173 |
| BNB | tsmom_4h_lookback96_threshold0.35 | risk_050 | $-6,446 | -12.9% | 14.5% | 173 |
| BNB | tsmom_4h_lookback96_threshold0.35 | risk_100 | $-11,946 | -23.9% | 26.6% | 172 |
| BNB | tsmom_4h_lookback96_threshold0.35 | crisis_costs | $-5,907 | -11.8% | 12.1% | 173 |
| BNB | tsmom_4h_lookback96_threshold0.35 | delay_one_extra_bar | $-3,118 | -6.2% | 8.5% | 194 |
| BNB | tsmom_4h_lookback96_threshold0.35 | low_capacity | $-3,046 | -6.1% | 7.0% | 170 |
| BNB | tsmom_4h_lookback96_threshold0.35 | outage_every20bars | $-3,229 | -6.5% | 7.4% | 172 |
| BNB | tsmom_4h_lookback96_threshold0.35 | trailing_stop | $-3,210 | -6.4% | 7.5% | 185 |
| BNB | tsmom_4h_lookback96_threshold0.35 | long_only | $-1,707 | -3.4% | 4.8% | 108 |
| BNB | tsmom_4h_lookback96_threshold0.35 | short_only | $-1,676 | -3.4% | 3.8% | 65 |
| BNB | tsmom_4h_lookback96_threshold0.35 | lag24h | $-3,015 | -6.0% | 7.8% | 201 |
| BNB | tsmom_4h_lookback96_threshold0.35 | null_blocks | $-3,454 | -6.9% | 8.6% | 313 |
| BNB | tsmom_4h_lookback96_threshold0.35 | neighbor | $-4,098 | -8.2% | 10.5% | 174 |
| BNB | tsmom_4h_lookback96_threshold0.35 | ablate_regime | $-3,327 | -6.7% | 7.5% | 173 |
| ETH | tsmom_4h_lookback96_threshold0.35 | no_refit_transfer_from_BNB | $-190 | -0.4% | 4.9% | 153 |
| BNB | funding_fade_4h_threshold0.0005 | risk_050 | $148 | 0.3% | 0.4% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | risk_100 | $295 | 0.6% | 0.8% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | crisis_costs | $-12 | -0.0% | 0.2% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | delay_one_extra_bar | $-135 | -0.3% | 0.3% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | low_capacity | $74 | 0.1% | 0.2% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | outage_every20bars | $74 | 0.1% | 0.2% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | trailing_stop | $74 | 0.1% | 0.2% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | leverage_2x | $74 | 0.1% | 0.2% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | long_only | $74 | 0.1% | 0.2% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | short_only | $0 | 0.0% | 0.0% | 0 |
| BNB | funding_fade_4h_threshold0.0005 | lag24h | $-83 | -0.2% | 0.3% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | null_blocks | $-89 | -0.2% | 0.3% | 4 |
| BNB | funding_fade_4h_threshold0.0005 | neighbor | $105 | 0.2% | 0.2% | 3 |
| BNB | funding_fade_4h_threshold0.0005 | ablate_regime | $74 | 0.1% | 0.2% | 4 |
| ETH | funding_fade_4h_threshold0.0005 | no_refit_transfer_from_BNB | $4 | 0.0% | 0.1% | 1 |

Includes increased risk, adverse/crisis costs, delayed orders, entry outages, lower capacity, trailing stops, parameter neighbors, regime ablation,24h lag, seeded randomized daily-sign control, long/short isolation and cross-asset no-refit transfer. The randomized control is a falsification diagnostic, not a tradable rule. Conditional2x is tested only after positive base/adverse results; liquidation remains a last-price proxy.
Repeated timeframes/parameters are correlated; multiplicity adjustment is not a proof of generalization. CPCV/PBO and Deflated Sharpe are not reported because the inherited adaptive trial history is incomplete. All candidate failures remain in strategy_comparison.csv.

# Settled-funding entry rules: no learned models

Three fixed thresholds (0, 1, 2 basis points per eight hours). Accept an original trade only when its direction times the last known settled funding rate is below the threshold. Funding is normalized using each recorded settlement interval. Assumed publication delay is one hour; a fixed eight-hour delay is a later robustness diagnostic.

Raw monthly ETH funding ZIPs and published checksums are retained. Millisecond timestamps, including settlement jitter, are preserved. Missing/stale funding at a potential entry rejects the experiment. This feature does not replace the broker financing or certify Breakout fills.

Source months: 82; real settlements: 7476. All price outcomes were previously inspected; this is development research, not future validation.

| Signed funding cap | Training score | Eligible |
| --- | ---: | --- |
| 0.0bp | -289.09 | False |
| 1.0bp | 344.65 | False |
| 2.0bp | 244.47 | False |

Unfiltered training score: 410.06. Selected cap: **None**. 2024 check: `not evaluated: no eligible training candidate`.

| Period | Delay | Strategy | Fill cost | Net including open marks | Closed net | Drawdown |
| --- | ---: | --- | ---: | ---: | ---: | ---: |

Training and 2024 checks end December 25, leaving seven-day gaps before the next stage. The threshold freezes before 2024 and never changes on later outcomes. Every comparison receives causal 2020-2022 warm-up. No version is promoted and the future holdout remains sealed.

[Official funding-history API semantics](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History).

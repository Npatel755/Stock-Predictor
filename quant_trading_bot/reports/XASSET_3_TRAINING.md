# xasset_3 — bond-conditioned overnight leg inside Book A (training 2010–23 only; derived from xasset_2)

Protocol research/xasset_3/PROTOCOL.md; script scripts/xasset_3_pilot.py; raw reports/XASSET_3_TRAINING.json. Scoring = book_1 intraday-trailing marks
(overnight leg marked at every 1-min low, every intraday stop assumed hit). 490 nights; ZN day return (16:00 ET vs prior 16:00, Sunday nights use Friday) < 0 on 209.

| book | closed net | retained | marked DD | when | $2k touches | $2.5k |
|---|---|---|---|---|---|---|
| book_a (reference) | 28,317 | 1.000 | 2,043 | 2020-03-17 | 1 | 0 |
| **B1 skip bonds-down nights** | **26,481** | **0.935** | **1,506** | 2023-04-24 | **0** | 0 |
| C1 control: skip bonds-up nights | 19,243 | 0.680 | 1,996 | 2020-03-17 | 0 | 0 |
| placebo: 200 random 209-night skips | median 23,269 | – | median 1,839 | – | – | – |

B1 vs placebo: 193/200 random skips leave a worse marked DD, 192/200 a lower net. Pre-registered pass (DD < 2k, retained ≥ 0.8, ≥ 190/200, control fails): **PASS**.

## Reading
- The bond state removes exactly the kind of night that caused Book A's single floor touch: rates-driven selloffs (March 2020 dash-for-cash, 2022) where the
  dip did not recover overnight. Bonds-up dips (growth scare, flight to quality) are where the overnight premium is paid.
- Evidence quality: one split (2010–23), derived from xasset_2 on the same split; mechanism is prior-plausible and the control/placebo both fail, but it has
  not been scored on any sealed data and will not be. Forward paper is the next test.
- Deployment: `book_a_bond` as a separate paper version beside `book_a` (same legs, same router; overnight leg additionally requires prior ZN day return ≥ 0
  or missing). Live state needs a daily 10-yr note close feed; its sign must be parity-checked against the Databento 16:00 ET series before trusting it.

## Addendum — feed-definition robustness (pre-registered in the protocol addendum before deployment)
| ZN close definition | retained | marked DD | $2k touches | placebo DD worse | gate |
|---|---|---|---|---|---|
| 16:00 ET bar (research) | 0.935 | 1,506 | 0 | 193/200 | pass |
| 15:00 ET bar (settlement-like) | 0.876 | 1,676 | 0 | 147/200 | **fail** |

The sign of the two definitions agrees on 94 % of days; the 6 % that differ carry much of the effect, i.e. the information is largely the bond move during
equities' last hour. Plausible (it classifies the type of equity selloff) but definition-sensitive, which lowers confidence. Deployment therefore uses the
exact 16:00 ET close computed from yfinance ZN=F 1-minute bars (same feed family the runner already uses for MNQ/MES), not the daily settlement; the fragility
is stated in the ledger's provenance and `book_a_bond` is a challenger beside `book_a`, not a replacement. Forward divergence between the two cards measures the state.

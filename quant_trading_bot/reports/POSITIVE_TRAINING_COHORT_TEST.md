# All positive, sub-$2,000-drawdown training configurations: frozen test diagnostic

**3,243 results: 3,242 newly evaluated configurations and 1 prior completed result reused without rerunning.** Technical failures: 0. The full cohort of 3,243 was fixed before new test-price access.

Eligibility was exactly the user request across the two completed20k training batches: positive aggregate training net and maximum closing, realized-cash and intrabar fold drawdown strictly below$2,000. No additional minimum-trade, consistency or per-fold-profit gate was silently added. Those stronger flags remain visible separately.

Test results: **1,181** had positive net and all three drawdowns below$2,000; **228** also met the recorded minimum30 trades, consistency50%, no-lock and provisional funded-floor checks. **901** produced no trades. These counts are observations, not independent significance or deployment approval. Among the10 candidates that passed every original training gate, 7 passed the user's two test filters, but **0 passed all recorded test scenario gates**.

| Market | Frozen cohort | Completed | Positive net and DD<2000 | Full scenario checks |
|---|---:|---:|---:|---:|
| ES | 119 | 119 | 0 | 0 |
| NQ | 511 | 511 | 0 | 0 |
| MES | 445 | 445 | 284 | 77 |
| MNQ | 2168 | 2168 | 897 | 151 |

## Candidates that also passed every original training gate

Rows retain their pre-test training order. This is not a ranking by test performance. All other eligible cases, including every negative/zero outcome and failure, are retained in the full CSV.

| Candidate | Family | Training net | Test net | Test cash DD | Test intrabar DD | Trades | Positive test + DD<2000 | Full test scenario |
|---|---|---:|---:|---:|---:|---:|---|---|
| mass_aade3d08eb001ccc3d3e | momentum | $6,236.50 | $225.50 | $428.00 | $525.25 | 18 | True | False |
| mass_2eafe88e993469aedb12 | hybrid | $5,989.00 | $408.00 | $128.00 | $258.75 | 5 | True | False |
| mass_85721bb33e324b248878 | breakout | $8,421.00 | $-190.00 | $953.50 | $998.88 | 25 | False | False |
| mass_853576a710b834b0ad13 | trend | $6,330.50 | $14.50 | $637.50 | $655.50 | 42 | True | False |
| mass_4077260e9698c6a220bf | regime | $2,955.00 | $-11.00 | $214.50 | $265.75 | 9 | False | False |
| mass_8c8f64ec70a765ae6eb7 | trend | $5,989.00 | $148.00 | $283.00 | $385.25 | 13 | True | False |
| mass_44b8a3fc9ecea9420d38 | trend | $4,270.00 | $-248.00 | $248.00 | $312.00 | 12 | False | False |
| mass_d744bdc7bca1b354a2ea | hybrid | $4,668.50 | $534.00 | $263.00 | $302.75 | 18 | True | False |
| mass_a2ac4a632df00701ac49 | opening_range | $5,434.50 | $167.00 | $402.00 | $449.00 | 37 | True | False |
| mass_9c4239762fe64389ef65 | trend | $3,431.50 | $531.50 | $232.50 | $323.00 | 17 | True | False |

## Protocol and limitations

Each configuration was replayed once with its original execution/risk parameters and base costs on its own existing2026 test partition, using a single continuous$50,000 account. Exact complete15-minute bars, causal indicators, next-open entries, original risk locks, first96/last16 entry-bar suppression and all costs were unchanged. No validation data or warmup were accessed. No fitting, revised parameters, alternate cost scenarios or feedback from outcomes were used.

The2026 period was already observed for earlier strategies. Evaluating3,243 correlated configurations on this reused period creates substantial selection bias. The full report is an exploratory comparison, not an untouched final test or evidence to select/deploy a winner. Exact account compliance and actual all-in charges remain unverified. Earlier failed tests and all reservations remain preserved. No strategy was selected or modified from these results.

The initial launcher stopped on an omitted sys import before new price access or candidate execution. An archived launcher supplied that standard-library import only; the frozen cohort, strategy, original runner bytes and reservations were not changed. Subsequent candidate attempts were protected by exclusive reservations, an OS execution lock and a SQLite primary key; interrupted/failed attempts cannot silently replay.

Independent reconciliation covered all saved trades and curves. The evaluation performed 10,057 shared-simulator trade samples and 86,385 arithmetic trade checks, including the reused completed record. Verification replays use identical fixed trades; they are not parameter searches.

[Full results CSV](../runs/positive_training_cohort_test_v1/test_results.csv) · [All trade logs CSV](../runs/positive_training_cohort_test_v1/test_trades.csv) · [Frozen cohort and parameters](../runs/positive_training_cohort_test_v1/frozen_cohort.json)

Full-resolution equity/drawdown curves and per-candidate result JSON/trade Parquet files remain in curves/, results/ and trades/ under the run folder. No negative outcomes are removed. The full CSV remains in the frozen training order.

[Dashboard](http://127.0.0.1:8511/)

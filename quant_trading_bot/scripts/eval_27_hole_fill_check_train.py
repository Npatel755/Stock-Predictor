"""eval_27 (Claude, 2026-11-11): the eval_8 plan with the Jan-May 2019 training-data hole filled. TRAINING 2010-23 only. Information.

The training loader (mass_1m_search.load_bars) used NQ / ES bars before 2019-01-01 and MNQ / MES after, but the micros start 2019-05-05,
so Jan 1 - May 5, 2019 had no bars in every study that uses it. The NQ / ES train files do contain those months (~118k minute bars each).
This run sets TRAIN_MINI_UNTIL=2019-05-06 (E-mini bars up to the micro launch, as in 2010-18) and re-measures the incumbent with the same
harness. Nothing is chosen. Expect 2010-16 starts unchanged and 2017-23 to move (eval_26 C: starts whose window touched the hole passed 42.9%
vs 66.5% for the rest of 2017-23).
"""
import os, json
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
import pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness()
d = pd.Series(sorted(H.SESS)); hole = d[(d >= pd.Timestamp("2019-01-01").date()) & (d < pd.Timestamp("2019-05-06").date())]
r = H.pass_rate()
out = dict(mini_until=os.environ["TRAIN_MINI_UNTIL"], sessions_total=len(d), sessions_in_former_hole=len(hole), n_h1=len(H.A), n_h2=len(H.B),
           trades_in_former_hole=int(((H.BOOK.tout.dt.date >= pd.Timestamp("2019-01-01").date()) & (H.BOOK.tout.dt.date < pd.Timestamp("2019-05-06").date())).sum()),
           incumbent=r, previous=dict(h1=54.5, h2=65.6))
print(out, flush=True)
(ROOT / "reports/EVAL_27_HOLE_FILL_CHECK_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))

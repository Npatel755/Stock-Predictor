"""bookx_1b (Claude fork C, 2026-11-11): diagnostic for bookx_1 F4 (FA skipped 0 trades). Cross-tab of the MNQ noise-area state at entry vs
trade side, per sleeve group, and the same state computed at the trade's DECISION time (dec) instead of entry. Descriptive only. TRAINING."""
import sys
import numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
src = (ROOT / "scripts/bookx_1_book_internals_train.py").read_text(encoding="utf-8")
head = src.split("BOOK = book_from(PRE); F0 = frame_of(BOOK)")[0]
f4 = src.split("# ---------------- F4 noise-area direction filter")[1].split("cov = PRE[")[0]
NS = {"__name__": "bookx_1b", "__file__": str(ROOT / "scripts/bookx_1_book_internals_train.py")}
exec(head, NS); exec(f4, NS)
PRE, state = NS["PRE"], NS["state"]
e = PRE[PRE.risk_today <= 300.0].copy()
print("side values", e.side.value_counts().to_dict())
print(pd.crosstab([e.g, e.side], e.nstate, dropna=False))
e["dstate"] = [state(t) for t in e.dec]
print("state at decision time vs side"); print(pd.crosstab(e.side, e.dstate, dropna=False))
x = e[e.nstate.notna()].head(3)[["sleeve", "side", "tin", "dec", "entry", "nstate"]]; print(x)

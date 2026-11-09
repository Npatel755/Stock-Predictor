"""Research Script: Book D+ (Overnight Dip v2 + Architecture D+ Intraday).
STRICTLY TRAINING DATA ONLY (2010-2023).
Zero access to Validation (2024-2025) or Blind Test (2026).

Combines:
1. Overnight Leg: overnight_dip_v2 (1 MNQ long 18:05 -> 09:45 ET when both MNQ & MES reopen <= -0.5 sd below 16:00 close)
2. Intraday Leg: Architecture D+ (Crabel 15m at 10:00 ET + MNQ 30m trend + MNQ 60m trend + MES 30m idle trend; CBOE VIX backwardation gate on morning sleeves)
3. Constraint: Global strict 1-contract ceiling. (Overnight exits at 09:45 ET, so zero overlap with 10:00 Crabel; any 09:45 intraday decision while overnight is exiting is skipped).
"""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features
from research_vix_gate_architecture_d_train import run_backtest_with_vix_gate

# 1. Load Intraday Architecture D+ Trades
print("Loading Architecture D+ Intraday Backtest (2010-2023)...", flush=True)
res_d = run_backtest_with_vix_gate(vix_gate=True)
pnl_d = res_d['pnl_series'] # cumulative series on common_idx

# 2. Derive Overnight Dip v2 Trades on 2010-2023
print("Deriving Overnight Dip v2 Trades (2010-2023)...", flush=True)
# Load 1m bars for MNQ and MES from catalog or resampled stores
from quant_futures.ensemble_paper import CANDIDATES, _reopen_gaps, OVN_ECON, OVN_SEED_GAPS, OVN_SEED_GAPS_MES, OVN_TICK, OVN_SLIP_TICKS, OVN_COMM

# Let's inspect overnight_3_pilot method for exact bit-for-bit parity
src = (ROOT / "scripts/overnight_3_pilot.py").read_text()
# Let's see how overnight_3_pilot builds the trades

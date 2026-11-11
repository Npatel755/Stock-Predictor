"""Inspect Validation Trades and Simulation Logic."""
import sys, pandas as pd, numpy as np
from pathlib import Path
ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import audit_frozen_all_splits_gentle_fortress as af

dates, tr_dict = af.extract_partition_trades('validation', '2024-01-01', '2026-01-01')

print(f"Total validation sessions: {len(dates)}")
print(f"Total trade sessions: {len(tr_dict)}")

# Let's inspect trades
df_trades = pd.DataFrame(list(tr_dict.values()))
print("Trade summary:")
print(df_trades.describe())

# Trace first 10 evaluation trials
for trial in range(5):
    cum = 0.0
    hwm = 0.0
    busted = False
    passed = False
    start_d = dates[trial]
    history = []
    for step in range(90):
        d = dates[trial + step]
        tr = tr_dict.get(d, None)
        if tr is None: continue
        sz = 6
        pnl = tr["net_1c"] * sz
        mae = tr["mae_1c"] * sz
        cum += pnl
        if cum <= -2000.0 or (cum + mae) <= -2000.0:
            busted = True
            history.append((d, tr["type"], pnl, cum, mae, "BUSTED"))
            break
        if cum >= 4000.0:
            passed = True
            history.append((d, tr["type"], pnl, cum, mae, "PASSED"))
            break
        history.append((d, tr["type"], pnl, cum, mae, "OK"))
    print(f"\nTrial {trial} (Start: {start_d}) -> Busted: {busted}, Passed: {passed}, Final PnL: ${cum:.2f}")
    print("Last 3 events:")
    for h in history[-3:]:
        print("  ", h)

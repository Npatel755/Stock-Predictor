"""Compare explicitly normalized TradingView rows; never infer missing settings."""
from __future__ import annotations

import numpy as np
import pandas as pd


def compare_trades(local: pd.DataFrame, tradingview: pd.DataFrame, price_tolerance=.01, quantity_tolerance=.0005):
    columns = ["entry_bar_open", "exit_bar_open", "direction", "quantity", "entry_price", "exit_price"]
    for label, frame in [("local", local), ("TradingView", tradingview)]:
        if not set(columns).issubset(frame.columns):
            raise ValueError(f"{label} trade data requires normalized columns: {', '.join(columns)}")
    frames = []
    for raw in [local, tradingview]:
        frame = raw[columns].copy().reset_index(drop=True)
        for column in ["entry_bar_open", "exit_bar_open"]:
            # Reject ambiguous naive timestamps rather than guessing the chart timezone.
            if len(frame) and any(pd.Timestamp(value).tzinfo is None for value in frame[column]):
                raise ValueError("Trade timestamps must include a UTC offset")
            frame[column] = pd.to_datetime(frame[column], utc=True)
        frame["direction"] = frame.direction.str.upper()
        frames.append(frame)
    a, b = frames
    differences = []
    for i in range(max(len(a), len(b))):
        if i >= len(a) or i >= len(b):
            differences.append({"row": i, "field": "missing_trade", "local": i < len(a), "tradingview": i < len(b)})
            continue
        for column in columns:
            x, y = a.iloc[i][column], b.iloc[i][column]
            same = np.isclose(float(x), float(y), atol=quantity_tolerance if column == "quantity" else price_tolerance, rtol=0) if column in {"quantity", "entry_price", "exit_price"} else x == y
            if not same:
                differences.append({"row": i, "field": column, "local": str(x), "tradingview": str(y)})
    return {"summary": {"local_rows": len(a), "tradingview_rows": len(b), "differences": len(differences),
                         "matched_this_export": not differences, "parity_certified": False},
            "differences": pd.DataFrame(differences)}

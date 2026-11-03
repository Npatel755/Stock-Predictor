"""Inspect the saved ETHUSD research model using completed cached bars."""
import argparse
import json

import joblib
import numpy as np
import pandas as pd

from .data import ROOT
from .features import build_features, eligible_indices
from .neural import TorchClassifier
from .train import probability


def predict(bundle_path, bars_path):
    # Only load locally trained, trusted joblib artifacts.
    bundle = joblib.load(bundle_path)
    bars = pd.read_csv(bars_path)
    ticker = bundle["metadata"]["training_ticker"]
    if "ticker" not in bars or not bars.ticker.eq(ticker).all():
        raise ValueError(f"Prediction requires exclusively {ticker} data")
    now = pd.Timestamp.now(tz="UTC")
    bars = bars[pd.to_datetime(bars.timestamp, utc=True) + pd.Timedelta(minutes=5) <= now]
    frame, columns = build_features(bars, expected_ticker=ticker)
    if columns != bundle["feature_columns"]:
        raise ValueError("Feature schema does not match the saved model")
    indices = eligible_indices(frame, bundle["sequence_length"], labeled=False)
    if not len(indices) or indices[-1] != len(frame) - 1:
        raise ValueError("The newest bar has insufficient continuous feature history")
    model = (TorchClassifier.restore(bundle["model"], len(columns)) if bundle["kind"] == "torch" else bundle["model"])
    p = float(probability(model, frame[columns].to_numpy(dtype=np.float32), indices[-1:])[0])
    signal_time = frame.iloc[-1].information_time
    threshold = bundle["confidence_threshold"]
    stale = now - signal_time > pd.Timedelta(minutes=10)
    action = "WAIT" if threshold == 1 or max(p, 1 - p) < threshold else ("LONG" if p >= .5 else "SHORT")
    if stale:
        action = "WAIT_STALE_DATA"
    return {"instrument": "ETHUSD", "source": bundle["metadata"]["source"], "model": bundle["model_name"],
            "signal_time_utc": str(signal_time), "probability_up": p, "confidence_threshold": threshold,
            "research_action": action, "stale_data": stale, "ready_for_funded_trading": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=str, default=str(ROOT / "artifacts/ethusd/selected_model.joblib"))
    parser.add_argument("--bars", type=str, default=str(ROOT / "data/ethusd/perpetual/bars.csv"))
    args = parser.parse_args()
    print(json.dumps(predict(args.bundle, args.bars), indent=2))

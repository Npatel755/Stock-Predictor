"""ES/NQ reference training with physically separate MES/MNQ evaluation.

The relationship between contracts motivates transfer; it does not prove it.
No early micro observations, raw prices, volume or synthetic fills are invented.
"""
from typing import Literal
import numpy as np
import pandas as pd
from .config import ResearchConfig, Costs, Execution, RiskLimits
from .models import FEATURE_COLUMNS
from .research import load_dataset

PAIRS = {"ES": "MES", "NQ": "MNQ"}
EXCLUDED_TRANSFER_FEATURES = {"relative_volume", "volume_zscore", "price_volume_corr",
    "volume_imbalance_proxy", "vwap_deviation"}


class ReferenceConfig(ResearchConfig):
    instrument: Literal["ES", "NQ"] = "ES"


def transfer_features(features):
    """Dimensionless price/structure/time features; no contract volume mapping."""
    columns = [name for name in FEATURE_COLUMNS if name in features and name not in EXCLUDED_TRANSFER_FEATURES]
    if not columns:
        raise ValueError("No normalized reference-transfer features")
    return features[columns].copy()


def guarded_partition(symbol, role, minutes=15):
    if role not in ("train", "validation"):
        raise PermissionError("Transfer research cannot open the final test partition")
    if role == "train" and symbol not in PAIRS:
        raise PermissionError("Transfer fitting requires ES/NQ reference training partitions")
    if role == "validation" and symbol not in PAIRS.values():
        raise PermissionError("Transfer validation requires actual MES/MNQ partitions")
    bars, metadata, quality = load_dataset(symbol+":"+role, minutes=minutes)
    return validate_partition(bars, metadata, quality, symbol, role)


def validate_partition(bars, metadata, quality, symbol, role):
    if role not in ("train", "validation"):
        raise PermissionError("Final test is reserved")
    left, right = pd.Timestamp("2024-01-01T00:00Z"), pd.Timestamp("2026-01-01T00:00Z")
    if metadata.get("split_role") != role or metadata.get("instrument") != symbol or not bars.instrument.eq(symbol).all():
        raise ValueError("Partition identity or role mismatch")
    if role == "train":
        if symbol not in PAIRS or not (bars.timestamp_utc < left).all():
            raise PermissionError("Reference training must end before 2024")
    elif role == "validation":
        if symbol not in PAIRS.values() or not (bars.timestamp_utc.ge(left) & bars.timestamp_utc.lt(right)).all():
            raise PermissionError("Micro validation must be confined to 2024–2025")
    else:
        raise PermissionError("Final test is reserved")
    return bars, metadata, quality


def morning_indexes(bars):
    """Keep the full active window plus one real observation per flat session.

    No prices are filled. Trading decisions are disabled outside 09:45–11:30;
    the exact 12:00 exit bar is retained. The one-per-session observation keeps
    flat days in session-level metrics. This helper cannot shorten feature input.
    """
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    minute = local.dt.hour*60+local.dt.minute
    retained = minute.between(570, 720).to_numpy(copy=True)
    retained[np.flatnonzero(~bars.session_id.duplicated())] = True
    return np.flatnonzero(retained)


def trading_config(symbol, width=1, payoff=2, hold=8):
    reference = symbol in PAIRS
    if not reference and symbol not in PAIRS.values():
        raise ValueError("ES/NQ/MES/MNQ required")
    scale = 10 if reference else 1
    stop = (32 if symbol in ("ES", "MES") else 80)*width
    return (ReferenceConfig if reference else ResearchConfig)(instrument=symbol, initial_balance=50000*scale,
        timeframe_minutes=15, costs=Costs(commission_per_side=1.75 if reference else .5,
            exchange_per_side=0, regulatory_per_side=0),
        execution=Execution(stop_ticks=stop, target_ticks=stop*payoff, max_hold_bars=hold,
            max_gap_minutes=15, session_flat_minute_et=720),
        risk=RiskLimits(max_trade_risk=100*scale, max_open_risk=100*scale,
            max_daily_loss=200*scale, max_drawdown=1800*scale))

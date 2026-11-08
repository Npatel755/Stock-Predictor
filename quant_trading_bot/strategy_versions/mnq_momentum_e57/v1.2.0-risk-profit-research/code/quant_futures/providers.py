"""File import plus read-only data price estimates. No paid downloads are issued."""
from abc import ABC, abstractmethod
from pathlib import Path
import os
import pandas as pd
import requests
from .data import canonical
from .contracts import expiration


class HistoricalProvider(ABC):
    @abstractmethod
    def read(self): ...


class FileProvider(HistoricalProvider):
    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        return canonical(pd.read_parquet(self.path) if self.path.suffix == ".parquet" else pd.read_csv(self.path))


def databento_cost_estimate(symbols, start, end, key=None):
    """Only free metadata endpoint; direct REST avoids mandatory vendor SDK.

    Query explicit contracts; continuous aliases are not accepted for execution.
    API docs: https://databento.com/docs/api-historical/metadata/metadata-get-cost
    """
    raw_symbols = []
    for symbol in symbols:
        expiry = expiration(symbol)
        # CME raw symbols use the one-digit year (ESM2 in the API documentation).
        # The request date range disambiguates the decade; canonical storage does not.
        raw_symbols.append(symbol[:3]+{3: "H", 6: "M", 9: "U", 12: "Z"}[expiry.month]+str(expiry.year)[-1])
    key = key or os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise ValueError("DATABENTO_API_KEY is required for the free cost metadata endpoint")
    response = requests.post("https://hist.databento.com/v0/metadata.get_cost", auth=(key, ""),
        data=dict(dataset="GLBX.MDP3", symbols=",".join(raw_symbols), stype_in="raw_symbol",
                  schema="ohlcv-1m", start=start, end=end), timeout=30)
    response.raise_for_status()
    return dict(estimated_usd=response.json(), symbols=symbols, vendor_raw_symbols=raw_symbols, start=start, end=end,
                paid_download_submitted=False, license_check_required=True)


def normalize_vendor_ohlcv(frame, instrument, contract, timestamp_column="ts_event"):
    """Normalize an authorized vendor export; refuse unsupported contract aliases."""
    expiration(contract)
    b = frame.reset_index() if timestamp_column not in frame else frame.copy()
    b = b.rename(columns={timestamp_column: "timestamp_utc"})
    b["instrument"], b["contract"] = instrument, contract
    return canonical(b)

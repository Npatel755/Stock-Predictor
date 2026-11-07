import numpy as np
import pandas as pd
import pytest
from quant_futures.data import canonical


@pytest.fixture
def bars():
    rng = np.random.default_rng(11)
    n = 1000
    close = 6000 + np.cumsum(rng.choice([-0.5, -0.25, 0, 0.25, 0.5], n))
    opening = np.r_[close[0], close[:-1]]
    return canonical(pd.DataFrame(dict(timestamp_utc=pd.date_range("2026-01-05T14:30Z", periods=n, freq="1min"),
        instrument="MES", contract="MESH26", open=opening, high=np.maximum(opening, close)+0.5,
        low=np.minimum(opening, close)-0.5, close=close, volume=1000)))

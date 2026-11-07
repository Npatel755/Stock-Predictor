import numpy as np
import pandas as pd
from quant_futures.stream_features import FeatureState
from quant_futures.features import build_features


def test_cross_market_roll_gap_is_not_a_return(bars):
    from quant_futures.features import cross_market_features
    left, right = bars.iloc[:80].copy(), bars.iloc[:80].copy()
    right.loc[40:, "contract"] = "MESM26"
    right.loc[40:, "close"] += 1000
    result = cross_market_features(left, right)
    assert pd.isna(result.return_divergence.iloc[40])
    assert result.return_divergence.iloc[41] < .01


def test_online_matches_batch_across_window_and_session(bars):
    b = bars.iloc[:650].copy()
    state = FeatureState()
    rows = [state.update(record) for record in b.to_dict("records")]
    online = pd.DataFrame(rows).reset_index(drop=True)
    batch = build_features(b).reset_index(drop=True)
    pd.testing.assert_frame_equal(online, batch, check_dtype=False, rtol=1e-8, atol=1e-8)
    assert len(state.bars) == 200 and len(state.rows) == 200
    assert online.previous_session_high.notna().any()


def test_online_roll_reset_matches_batch(bars):
    b = bars.iloc[:120].copy()
    b.loc[60:, "contract"] = "MESM26"
    state = FeatureState()
    online = pd.DataFrame([state.update(x) for x in b.to_dict("records")]).reset_index(drop=True)
    pd.testing.assert_frame_equal(online, build_features(b), check_dtype=False, rtol=1e-8, atol=1e-8)

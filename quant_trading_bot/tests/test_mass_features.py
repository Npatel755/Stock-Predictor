from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import mass_features as study
import mass_configurations as universe
from quant_futures.data import canonical


def market(n=240):
    close = 20000+np.arange(n)*.5+np.sin(np.arange(n)/3)*2
    return canonical(pd.DataFrame(dict(timestamp_utc=pd.date_range("2023-01-02T23:00Z",periods=n,freq="15min"),
        instrument="NQ",contract="NQH23",open=close-.25,high=close+1,low=close-1,
        close=close,volume=1000+np.arange(n)%23)))


@pytest.mark.parametrize('lookback',[8,24,30,96])
def test_grouped_kernels_match_reference_on_resets(lookback):
    bars=market(480)
    bars.loc[160:,'contract']='NQM23'
    bars.loc[300:,'timestamp_utc']+=pd.Timedelta(hours=1)
    actual=study.features(bars,lookback)
    expected=study.features_reference(bars,lookback)
    for key in expected:
        np.testing.assert_allclose(actual[key],expected[key],equal_nan=True,atol=1e-8,err_msg=key)


def test_all_features_and_family_signals_are_prefix_invariant():
    bars = market()
    for lookback in (8,24,30,96):
        full = study.features(bars,lookback)
        prefix = study.features(bars.iloc[:155],lookback)
        changed = bars.copy()
        changed.loc[155:, ["open","high","low","close"]] *= 5
        perturbed = study.features(changed,lookback)
        for key in full:
            np.testing.assert_allclose(full[key][:155],prefix[key],equal_nan=True,err_msg=key)
            np.testing.assert_allclose(full[key][:155],perturbed[key][:155],equal_nan=True,err_msg=key)
        for family in universe.FAMILIES:
            if family == "opening_range" and lookback % 15:
                continue
            cfg = dict(family=family,threshold=universe.THRESHOLDS[family][0],lookback=lookback)
            np.testing.assert_array_equal(study.signal_for(cfg,full)[:155],study.signal_for(cfg,prefix))


def test_raw_contract_and_missing_gap_reset_rolling_and_ema_state():
    bars = market()
    for kind in ("roll","gap"):
        changed = bars.copy()
        if kind == "roll":
            changed.loc[130:,"contract"] = "NQM23"
        else:
            changed.loc[130:,"timestamp_utc"] += pd.Timedelta(hours=1)
        all_features = study.features(changed,24)
        restarted = study.features(changed.iloc[130:].reset_index(drop=True),24)
        for name in ("atr","trend","momentum","zscore","breakout_high","breakout_low","efficiency","vol_ratio","volume_ratio","htf","vwap_deviation"):
            np.testing.assert_allclose(all_features[name][130:],restarted[name],equal_nan=True,err_msg=name)
        assert np.isnan(all_features["trend"][130:153]).all()


def test_opening_range_publishes_only_complete_regular_window_without_evening_leak():
    bars = market(100)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    clock = local.dt.hour*60+local.dt.minute
    bars.loc[clock.ge(1080),"high"] = 999999
    f = study.features(bars,30)
    regular = np.flatnonzero(clock.between(570,585))
    assert len(regular) == 2
    start,end = regular
    assert not f["opening_ready"][start]
    assert np.isnan(f["opening_high"][start])
    assert f["opening_ready"][end]
    assert f["opening_high"][end] == bars.high.iloc[regular].max() < 999999
    assert f["opening_low"][end] == bars.low.iloc[regular].min()
    missing = bars.drop(index=start).reset_index(drop=True)
    mf = study.features(missing,30)
    same_session = missing.session_id.eq(bars.session_id.iloc[end]).to_numpy()
    assert not mf["opening_ready"][same_session].any()


def test_vwap_is_cumulative_within_session_not_full_session_or_future_volume():
    bars = market(150)
    f = study.features(bars,8)
    changed = bars.copy()
    changed.loc[70:,"volume"] = 10**9
    changed.loc[70:,"close"] += 1000
    cf = study.features(changed,8)
    np.testing.assert_allclose(f["vwap_deviation"][:70],cf["vwap_deviation"][:70],equal_nan=True)
    i = 60
    ids = np.flatnonzero(bars.session_id.eq(bars.session_id.iloc[i]).to_numpy() & (np.arange(len(bars)) <= i))
    typical = (bars.high.iloc[ids]+bars.low.iloc[ids]+bars.close.iloc[ids])/3
    vwap = float((typical*bars.volume.iloc[ids]).sum()/bars.volume.iloc[ids].sum())
    assert np.isclose(f["vwap_deviation"][i],(bars.close.iloc[i]-vwap)/f["atr"][i])


def test_zero_threshold_breakout_and_no_fitted_full_sample_thresholds():
    bars = market()
    f = study.features(bars,8)
    signal = study.signal_for(dict(family="breakout",lookback=8,threshold=0),f)
    assert signal.dtype == np.int8
    assert set(np.unique(signal)) <= {-1,0,1}
    assert not signal[:14].any()
    assert len(signal) == len(bars)
    with pytest.raises(ValueError,match="15-minute"):
        study.signal_for(dict(family="opening_range",lookback=8,threshold=.1),f)


def test_vwap_lookback_momentum_confirmation_is_an_active_signal_input():
    f = dict(close=np.array([100.,100.]),atr=np.array([1.,1.]),
             vwap_deviation=np.array([-2.,-2.]),momentum=np.array([.5,2.]))
    signal = study.signal_for(dict(family="vwap",lookback=8,threshold=1.),f)
    np.testing.assert_array_equal(signal,[1,0])

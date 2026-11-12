import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import pandas as pd
from stack_entry_quality_train import feature_frame,eligibility
from stack_continuous_core import continuous


def bars(n=400):
    x=np.arange(n,dtype=float)+100
    return pd.DataFrame(dict(timestamp_utc=pd.date_range('2020-01-01T00:00Z',periods=n,freq='h'),open=x,high=x+2,low=x-1,close=x+1,volume=x+10,contract='NQH0'))


def config(**updates):
    c=dict(er_length=16,er_min=.1,pressure_min=None,volume_min=None,cost_min=None,peer_align=False);c.update(updates);return c


def test_future_prices_and_volumes_do_not_change_prefix_features():
    a=bars();b=a.copy();b.loc[250:,['open','high','low','close','volume']]*=100
    x=feature_frame(a);y=feature_frame(b)
    for col in ('er8','er16','er32','pressure','relative_volume'):
        np.testing.assert_allclose(x.loc[:249,col],y.loc[:249,col],equal_nan=True)


def test_directional_efficiency_uses_past_observations():
    x=feature_frame(bars())
    np.testing.assert_allclose(x.er16.iloc[16:],1.)
    assert x.er16.iloc[:16].isna().all()


def test_contract_roll_invalidates_cross_contract_trend_window():
    b=bars();b.loc[200:,'contract']='NQM0';x=feature_frame(b)
    assert x.er16.iloc[200:216].isna().all() and np.isfinite(x.er16.iloc[216])


def test_volume_reference_excludes_current_volume():
    b=bars(700);a=feature_frame(b);b.loc[650,'volume']*=10;changed=feature_frame(b)
    np.testing.assert_allclose(changed.relative_volume.iloc[650],a.relative_volume.iloc[650]*10)


def test_current_trade_outcome_is_not_an_entry_feature():
    d=pd.DataFrame(dict(directional_er16=[.2],per=[100.],adverse=[-20.]))
    a=eligibility(d,config());d['per']=-5000;d['adverse']=-1e6
    np.testing.assert_array_equal(a,eligibility(d,config()))


def test_missing_required_feature_rejects_signal():
    d=pd.DataFrame(dict(directional_er16=[np.nan,.2]));np.testing.assert_array_equal(eligibility(d,config()),[False,True])


def test_unfiltered_control_requires_no_optional_features():
    d=pd.DataFrame(index=range(3));np.testing.assert_array_equal(eligibility(d,config(er_length=0,er_min=None)),[True]*3)


def test_omitted_signal_does_not_reserve_position_or_post_future_profit():
    args=(np.array([0,10]),np.array([100,20]),np.array([1000.,50.]),np.array([100.,100.]),np.array([0.,1.]),np.array([2.,2.]),
          np.array([-100.,-50.]),np.array([1000.,50.]),np.array([True,True]),np.array([0,0]),0,1000,1.,225.,1.,1800.,False,1.)
    x=continuous(*args);np.testing.assert_array_equal(x[3],[0,1]);assert x[0][0]==50

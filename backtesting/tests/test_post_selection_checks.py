import numpy as np
import pytest

from backtesting.post_selection_checks import paired_interval


def test_paired_bootstrap_preserves_constant_and_identical_series():
    zero=paired_interval(np.zeros(100),draws=100)
    assert zero['observed_difference']==0 and zero['interval_95']==[0.,0.]
    fixed=paired_interval(np.ones(100),draws=100)
    assert fixed['observed_difference']==100 and fixed['interval_95']==[100.,100.]
    assert not fixed['corrects_search_bias'] and not fixed['forward_validation']


def test_paired_bootstrap_is_reproducible_and_rejects_nonfinite_or_short_series():
    values=np.arange(100,dtype=float)-50
    assert paired_interval(values,draws=100)==paired_interval(values,draws=100)
    with pytest.raises(ValueError,match='finite paired'): paired_interval([0.,float('nan')]*10)
    with pytest.raises(ValueError,match='full block'): paired_interval([1.,2.])

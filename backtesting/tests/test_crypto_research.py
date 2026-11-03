import numpy as np
import pandas as pd
import pytest

from backtesting.crypto_research import data, lab


def frame(symbol='BTC', n=12, start='2024-01-01'):
    ts = pd.date_range(start, periods=n, freq='5min', tz='UTC')
    return pd.DataFrame(dict(timestamp=ts, ticker=data.ticker(symbol), open=100., high=101., low=99., close=100.5,
                             volume=1., exchange_close_time=ts+pd.Timedelta(minutes=4, seconds=59)))


def test_clean_rejects_other_tickers_and_bad_bars():
    good, quality = data.clean(frame(), 'BTC', '2024-01-01', '2024-01-01 01:00')
    assert len(good) == 12 and quality['missing_bars'] == 0 and 'available_at' in good
    with pytest.raises(ValueError):
        data.clean(frame('SOL'), 'BTC', '2024-01-01', '2024-01-01 01:00')
    bad = frame(); bad.loc[3, 'high'] = 98.
    with pytest.raises(ValueError):
        data.clean(bad, 'BTC')
    gapped = frame().drop(index=[4, 5])
    _, quality = data.clean(gapped, 'BTC', '2024-01-01', '2024-01-01 01:00')
    assert quality['missing_bars'] == 2


def test_candidates_are_fixed_and_include_eth_transplant():
    rows = lab.candidates()
    assert len(rows) == 25 and rows[-1]['id'] == lab.ETH_BASELINE_ID
    assert len({r['id'] for r in rows}) == 25 and 'ETH' not in data.UNIVERSE


def fold(net, legs=10, dd=.005, margin=0):
    return dict(closed_net=net, metrics=dict(closed_trade_legs=legs, max_intrabar_drawdown=dd, margin_call_events=margin))


def test_training_gate_requires_breadth_not_one_big_year():
    assert lab.training_rank([fold(500), fold(300), fold(-100)])['eligible']
    assert not lab.training_rank([fold(500), fold(300), fold(-100, dd=.02)])['eligible']  # drawdown penalty makes score negative
    assert not lab.training_rank([fold(5000), fold(-100), fold(-200)])['eligible']
    assert not lab.training_rank([fold(500), fold(300), fold(100, dd=.06)])['eligible']
    assert not lab.training_rank([fold(500), fold(300), fold(100, legs=3)])['eligible']
    assert lab.training_rank([fold(500), fold(300), fold(-100)])['score'] == pytest.approx(300-100-.5*.005*50000)


def test_validation_gate_and_deterministic_choice():
    training = dict(rank=dict(eligible=True, median_closed_net=400.))
    good = dict(closed_net=600., metrics=dict(closed_trade_legs=12, max_intrabar_drawdown=.01, margin_call_events=0))
    assert lab.validation_rank(training, good) == dict(eligible=True, score=pytest.approx(400-250))
    thin = dict(good, metrics=dict(good['metrics'], closed_trade_legs=9))
    assert not lab.validation_rank(training, thin)['eligible']
    rows = [dict(rank=dict(eligible=True, score=1.), candidate=dict(id='b')),
            dict(rank=dict(eligible=True, score=1.), candidate=dict(id='a')),
            dict(rank=dict(eligible=False, score=9.), candidate=dict(id='z'))]
    assert lab.choose(rows, key=lambda r: r['candidate']['id'])['candidate']['id'] == 'b'

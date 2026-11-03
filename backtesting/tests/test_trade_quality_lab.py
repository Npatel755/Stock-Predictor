import numpy as np
import pandas as pd
import pytest

from backtesting.trade_quality_lab import FEATURES, matrix, labels, make_model, predictions, filter_entries, score
from backtesting.alternative_strategies import SignalRule
from backtesting.regime_filters import prepare_features
from test_dvs import candles


def features():
    return prepare_features(candles(10000), SignalRule('ema_cross', lookback=20, slow=50))


def test_trade_quality_features_are_prefix_causal_and_finite_at_signals():
    frame = features()
    a = matrix(frame)
    b = matrix(prepare_features(candles(10000).iloc[:7003], SignalRule('ema_cross', lookback=20, slow=50)))
    pd.testing.assert_frame_equal(a.iloc[:7003], b, check_exact=True)
    assert np.isfinite(a.loc[frame.signal.ne(0)]).all().all()
    assert list(a.columns) == FEATURES


def test_training_labels_exclude_outcomes_unavailable_at_the_cutoff():
    frame = features()
    indices = frame.index[frame.signal.ne(0)][:2]
    times = frame.loc[indices, 'timestamp'].tolist()
    cutoff = times[1]+pd.Timedelta(hours=1)
    trades = pd.DataFrame(dict(entry_bar_open=[t+pd.Timedelta(minutes=5) for t in times],
                               exit_time=[times[0]+pd.Timedelta(hours=1), cutoff+pd.Timedelta(days=1)],
                               net_pnl=[250., 99999.]))
    result = labels(frame, trades, cutoff)
    assert len(result) == 1 and result.target_r.iloc[0] == 2.5
    assert pd.to_datetime(result.outcome_available_at, utc=True).le(cutoff).all()
    assert result.signal_time.iloc[0] == str(times[0])
    assert result[FEATURES].iloc[0].to_dict() == matrix(frame).loc[indices[0]].to_dict()


@pytest.mark.parametrize('name', ['ridge', 'xgboost', 'neural_mlp'])
def test_models_fit_training_only_and_return_reproducible_predictions(name):
    rng = np.random.default_rng(7)
    x = pd.DataFrame(rng.normal(size=(150, len(FEATURES))), columns=FEATURES)
    y = x.direction*.2+x.atr_pct*.1
    a, b = make_model(name), make_model(name)
    a.fit(x, y); b.fit(x, y)
    np.testing.assert_array_equal(a.predict(x), b.predict(x))
    median = x.median().to_numpy()
    np.testing.assert_array_equal(a.steps[0][1].center_, median)
    assert np.isfinite(a.predict(x)).all()


def test_filter_only_rejects_entries_and_never_changes_exit_features_or_invents_entries():
    frame = features()
    forecast = pd.Series(-1., index=frame.index)
    first = frame.index[frame.signal.ne(0)][0]
    forecast.loc[first] = .5
    result = filter_entries(frame, forecast, .25)
    assert result.signal.ne(0).sum() == 1 and result.signal.loc[first] == frame.signal.loc[first]
    pd.testing.assert_frame_equal(result.drop(columns='signal'), frame.drop(columns='signal'))
    with pytest.raises(ValueError, match='Prediction rows'):
        filter_entries(frame, forecast.iloc[:-1], .25)


def test_ml_selection_cannot_pass_on_accuracy_or_one_profitable_half():
    def row(net, count=20, dd=.01):
        return dict(closed_net=net, metrics=dict(closed_trade_legs=count, max_intrabar_drawdown=dd, margin_call_events=0))
    parent = [row(100.), row(100.)]
    assert score([row(200.), row(200.)], parent)['eligible']
    assert not score([row(9999.), row(-1.)], parent)['eligible']
    assert not score([row(20.), row(20.)], parent)['eligible']
    assert not score([row(200., count=3), row(200., count=3)], parent)['eligible']

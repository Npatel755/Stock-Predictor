import json

import pytest

from backtesting.paper_webhook import RejectedAlert, apply_fill, new_state, parse_alert, summary

SECRET = 'unit-secret'


def alert(**overrides):
    body = dict(secret=SECRET, ticker='ETHUSDT.P', action='buy', contracts='0.5', price='2000', position='0.5', id='Long', comment='', time='2026-11-04T10:00:00Z')
    body.update(overrides)
    return json.dumps(body).encode()


def test_parse_rejects_bad_secret_and_shapes():
    with pytest.raises(RejectedAlert):
        parse_alert(alert(secret='nope'), SECRET)
    with pytest.raises(RejectedAlert):
        parse_alert(b'not json', SECRET)
    with pytest.raises(RejectedAlert):
        parse_alert(alert(action='hold'), SECRET)
    with pytest.raises(RejectedAlert):
        parse_alert(alert(contracts='-1'), SECRET)
    fill = parse_alert(alert(), SECRET)
    assert fill['action'] == 'buy' and fill['contracts'] == .5 and fill['price'] == 2000. and fill['time'].startswith('2026-11-04T10:00:00+00:00')


def test_round_trip_long_books_pnl_and_fees():
    state = new_state()
    assert apply_fill(state, parse_alert(alert(), SECRET)) is None
    assert state['position'] == .5 and state['average_price'] == 2000.
    closed = apply_fill(state, parse_alert(alert(action='sell', price='2100', position='0', id='Long bracket', time='2026-11-04T18:00:00Z'), SECRET))
    assert closed['direction'] == 'long' and closed['gross_pnl'] == pytest.approx(50.)
    fees = .5*2000*4/10000+.5*2100*4/10000
    assert state['balance'] == pytest.approx(50000+50-fees) and state['position'] == 0. and not state['breaches']


def test_duplicate_alert_is_ignored():
    state = new_state()
    apply_fill(state, parse_alert(alert(), SECRET))
    apply_fill(state, parse_alert(alert(), SECRET))
    assert state['fills'] == 1 and state['duplicates'] == 1 and state['position'] == .5


def test_short_and_breakout_limits_are_flagged():
    state = new_state()
    apply_fill(state, parse_alert(alert(action='sell', contracts='10', price='2000', position='-10', id='Short'), SECRET))
    apply_fill(state, parse_alert(alert(action='buy', contracts='10', price='2160', position='0', id='Short bracket', time='2026-11-04T11:00:00Z'), SECRET))
    assert state['closed_trades'][-1]['gross_pnl'] == pytest.approx(-1600.)
    rules = {b['rule'] for b in state['breaches']}
    assert rules == {'daily_loss'}  # -1.6k plus fees is past 3% of 50k but above the 47k floor
    apply_fill(state, parse_alert(alert(action='buy', contracts='10', price='2000', position='10', id='Long', time='2026-11-05T11:00:00Z'), SECRET))
    apply_fill(state, parse_alert(alert(action='sell', contracts='10', price='1850', position='0', id='Long bracket', time='2026-11-05T12:00:00Z'), SECRET))
    assert {b['rule'] for b in state['breaches']} == {'daily_loss', 'static_max_drawdown'}
    assert summary(state)['account_alive'] is False


def test_daily_window_resets_at_0030_utc():
    state = new_state()
    apply_fill(state, parse_alert(alert(time='2026-11-04T00:20:00Z'), SECRET))
    first_day = state['trading_day']
    apply_fill(state, parse_alert(alert(action='sell', price='1990', position='0', time='2026-11-04T00:40:00Z'), SECRET))
    assert state['trading_day'] != first_day

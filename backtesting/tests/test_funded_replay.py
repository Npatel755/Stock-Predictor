import pandas as pd
import pytest

from backtesting.funded_replay import AccountReplay


def curve(cash, lows=None, positions=None, start='2026-01-01 00:05'):
    return pd.DataFrame(dict(timestamp=pd.date_range(start, periods=len(cash), freq='5min', tz='UTC'),
                             cash=cash, equity=cash, intrabar_worst_equity=lows or cash,
                             position_qty=positions or [0.]*len(cash)))


def test_evaluation_profit_is_not_a_payout_and_funded_balance_resets():
    account = AccountReplay(curve([55000., 54900., 55300.]))
    passed = account.stage(0, 3)
    assert passed['status'] == 'passed' and passed['index'] == 0
    funded = account.stage(1, 3, funded=True)
    assert funded['payouts'] == [dict(timestamp='2026-01-01 00:15:00+00:00', gross_debit=300., trader_amount=270.)]


def test_intrabar_breach_precedes_flat_profit_checkpoint():
    account = AccountReplay(curve([55000.], [46999.]))
    assert account.stage(0, 1)['status'] == 'breached'


def test_exact_equity_floor_breaches_even_if_close_recovers():
    account = AccountReplay(curve([50000.], [47000.]))
    assert account.stage(0, 1)['status'] == 'breached'


def test_only_post_split_minimum_is_payable_and_open_positions_block_payout():
    account = AccountReplay(curve([50055., 50100., 50100.], positions=[0., 1., 0.]))
    result = account.stage(0, 3, funded=True)
    assert len(result['payouts']) == 1
    assert result['payouts'][0]['trader_amount'] == 90.
    assert result['payouts'][0]['timestamp'].endswith('00:15:00+00:00')


def test_reset_0030_cash_applies_from_next_bar_and_uses_balance():
    # The old $48,500 floor applies through the bar ending 00:30. The next
    # bar uses 60,000 * .97 = 58,200, so its $58,000 intrabar low breaches.
    account = AccountReplay(curve([60000., 60000.], [49000., 58000.], positions=[1., 1.], start='2026-01-01 00:30'))
    result = account.stage(0, 2, funded=True)
    assert result['status'] == 'breached' and result['index'] == 1


def test_withdrawal_debits_gross_and_widens_daily_floor_then_resets():
    # At 00:30 balance is 60k; the floor becomes 58,200. At 00:35
    # withdrawing 10k must lower that floor to 48,200. Next day it resets
    # to 48,500 from the post-withdrawal 50k balance.
    data = curve([60000.]*290, positions=[1.]+[0.]*289, start='2026-01-01 00:30')
    data.loc[2, 'intrabar_worst_equity'] = 59000.
    account = AccountReplay(data)
    result = account.stage(0, len(data), funded=True)
    assert result['status'] == 'active'
    assert len(result['payouts']) == 1
    assert result['payouts'][0]['gross_debit'] == 10000.
    assert result['payouts'][0]['trader_amount'] == 9000.
    data.loc[289, 'intrabar_worst_equity'] = 58300.
    result = AccountReplay(data).stage(0, len(data), funded=True)
    assert result['status'] == 'breached' and result['index'] == 289


def test_incomplete_horizon_and_data_gaps_are_rejected():
    data = curve([50000., 50000.])
    with pytest.raises(ValueError, match='Incomplete'):
        AccountReplay(data).trial('2026-01-01', 90)
    data.loc[1, 'timestamp'] += pd.Timedelta(minutes=5)
    with pytest.raises(ValueError, match='gap-free'):
        AccountReplay(data)

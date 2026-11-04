import pandas as pd
from research.codex_eth_bnb.formations.activity import weekly_activity


def test_week_counts_include_zeros_and_ignore_partial_exit_legs():
    times=pd.date_range('2023-01-02',periods=28,freq='D',tz='UTC')
    curve=pd.DataFrame(dict(bar_open=times,timestamp=times+pd.Timedelta(days=1)))
    entries=pd.to_datetime(['2023-01-03','2023-01-03','2023-01-04','2023-01-17'],utc=True)
    metrics,weeks=weekly_activity(dict(equity=curve,trades=pd.DataFrame(dict(entry_time=entries))))
    assert weeks.entries.tolist()==[2,0,1,0]
    assert metrics['entries']==3 and metrics['multi_trade_week_fraction']==.25
    assert metrics['average_trades_per_week']==.75
    assert not metrics['meets_frequency']


def test_incomplete_calendar_weeks_are_not_used_in_regular_activity_fraction():
    times=pd.date_range('2023-01-04 12:00',periods=15,freq='D',tz='UTC')
    curve=pd.DataFrame(dict(bar_open=times,timestamp=times+pd.Timedelta(days=1)))
    metrics,weeks=weekly_activity(dict(equity=curve,trades=pd.DataFrame(columns=['entry_time'])))
    assert weeks.week_open.tolist()==[pd.Timestamp('2023-01-09',tz='UTC')]
    assert weeks.entries.tolist()==[0]

"""Successful entry frequency on full UTC weeks, including zero-trade weeks."""
import numpy as np
import pandas as pd


def weekly_activity(result):
    curve,trades=result['equity'],result['trades']
    start,end=curve.bar_open.iloc[0],curve.timestamp.iloc[-1]
    first=start.normalize()+pd.Timedelta(days=(7-start.weekday())%7)
    if first < start:
        first+=pd.Timedelta(days=7)
    weeks=pd.date_range(first,end-pd.Timedelta(days=7),freq='7D') if end-first>=pd.Timedelta(days=7) else pd.DatetimeIndex([],tz='UTC')
    entries=pd.DatetimeIndex(pd.to_datetime(trades.entry_time.drop_duplicates(),utc=True)) if len(trades) else pd.DatetimeIndex([],tz='UTC')
    counts=np.asarray([((entries>=day)&(entries<day+pd.Timedelta(days=7))).sum() for day in weeks],dtype=int)
    avg=len(entries)/((end-start)/pd.Timedelta(days=7))
    streak=longest=0
    for count in counts:
        streak=streak+1 if count==0 else 0
        longest=max(longest,streak)
    metrics=dict(entries=len(entries),average_trades_per_week=float(avg),complete_weeks=len(weeks),
                 median_trades_per_week=float(np.median(counts)) if len(counts) else 0.,
                 lower_quartile=float(np.quantile(counts,.25)) if len(counts) else 0.,
                 upper_quartile=float(np.quantile(counts,.75)) if len(counts) else 0.,
                 active_week_fraction=float((counts>0).mean()) if len(counts) else 0.,
                 multi_trade_week_fraction=float((counts>=2).mean()) if len(counts) else 0.,
                 longest_inactive_weeks=longest,
                 meets_frequency=bool(avg>=2 and len(counts)>0 and (counts>=2).mean()>=.5))
    return metrics,pd.DataFrame(dict(week_open=weeks,entries=counts))

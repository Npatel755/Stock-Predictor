"""Independent accounting metrics for aligned mass-research execution arrays.

This module never opens market files. Session-ending marks, not closed-trade
dates, define daily/monthly P&L. Cash drawdown includes entry commissions.
"""
import math
import numpy as np


DEFAULT_REGIME_LABELS = {0:"range",1:"trend",2:"high_volatility",3:"low_volatility",-1:"unknown"}


def _array(container,key,length=None,dtype=float):
    if key not in container:
        raise ValueError("Missing execution/data array: "+key)
    value = np.asarray(container[key],dtype=dtype)
    if value.ndim != 1 or (length is not None and len(value) != length):
        raise ValueError("Aligned one-dimensional array required: "+key)
    if not np.isfinite(value).all():
        raise ValueError("Finite values required: "+key)
    return value


def _index_array(container,key,length=None):
    if key not in container:
        raise ValueError("Missing execution/data array: "+key)
    raw = np.asarray(container[key])
    if raw.ndim != 1 or (length is not None and len(raw) != length):
        raise ValueError("Aligned one-dimensional array required: "+key)
    if raw.dtype.kind in "iu":
        if raw.dtype.kind == "u" and np.any(raw > np.iinfo(np.int64).max):
            raise ValueError("Integer array exceeds signed 64-bit range: "+key)
        return raw.astype(np.int64,copy=False)
    raw = _array(container,key,length=length)
    if not np.equal(raw,np.floor(raw)).all():
        raise ValueError("Integer values required: "+key)
    return raw.astype(np.int64)


def _drawdown(values,initial):
    peaks = np.maximum.accumulate(np.r_[float(initial),values])[1:]
    return float(np.max(peaks-values)) if len(values) else 0.


def _month_name(value):
    year,month = divmod(int(value),100)
    if year < 1900 or not 1 <= month <= 12:
        raise ValueError("Month must use integer YYYYMM encoding")
    return f"{year:04d}-{month:02d}"


def summarize_execution(result,data,initial=50000):
    """Reconcile a fully closed execution ledger and return JSON-safe metrics.

    ``data`` supplies session IDs, timestamps in nanoseconds and YYYYMM months.
    Optional ``regime`` values describe information available at entry; labels
    can be overridden with ``regime_labels``. Duration is holding bars × the
    fixed bar length (15 minutes unless ``timeframe_minutes`` is supplied).
    ``top_trade_share`` is the largest positive trade / sum of positive trades;
    ``top_trade_share_of_net`` separately reports concentration against net P&L.
    Neither a concentration statistic nor consistency arithmetic establishes
    eligibility under an unverified funded-account agreement.
    """
    initial = float(initial)
    if not math.isfinite(initial) or initial <= 0:
        raise ValueError("Positive finite initial capital required")
    equity = _array(result,"equity")
    n = len(equity)
    cash = _array(result,"cash",n)
    worst = _array(result,"worst",n)
    quantity = _index_array(result,"quantity",n)
    timestamp = _index_array(data,"timestamp",n)
    session = _index_array(data,"session",n)
    month = _index_array(data,"month",n)
    if n and (np.any(np.diff(timestamp) <= 0) or np.any(np.diff(session) < 0)):
        raise ValueError("Chronological bars and ordered session IDs required")
    if np.any(worst > equity+1e-8):
        raise ValueError("Intrabar adverse bound cannot exceed closing equity")
    entry = _index_array(result,"trade_entry")
    count = len(entry)
    exit_ = _index_array(result,"trade_exit",count)
    net = _array(result,"trade_net",count)
    fees = _array(result,"trade_fees",count)
    trade_qty = _index_array(result,"trade_qty",count)
    if np.any(fees < 0) or np.any(trade_qty < 1):
        raise ValueError("Nonnegative trade fees and positive integer quantities required")
    if count and (n == 0 or np.any(entry < 0) or np.any(exit_ < entry) or np.any(exit_ >= n)):
        raise ValueError("Invalid trade entry/exit indexes")
    if count > 1 and np.any(np.diff(exit_) < 0):
        raise ValueError("Closed trades must be chronological")
    if n and quantity[-1] != 0:
        raise ValueError("Metrics require terminal inventory to be closed")
    if n and not np.isclose(cash[-1],equity[-1],rtol=0,atol=1e-7):
        raise ValueError("Terminal cash and equity do not reconcile")
    terminal_net = float(equity[-1]-initial) if n else 0.
    tolerance = max(1e-7,abs(terminal_net)*1e-10)
    if not np.isclose(float(net.sum()),terminal_net,rtol=0,atol=tolerance):
        raise ValueError("Closed trade net P&L does not reconcile to terminal equity")
    if "trade_reason" in result:
        _index_array(result,"trade_reason",count)
    bar_minutes = float(data.get("timeframe_minutes",15))
    if not math.isfinite(bar_minutes) or bar_minutes <= 0:
        raise ValueError("Positive fixed bar duration required")
    ends = np.r_[np.flatnonzero(np.diff(session) != 0),n-1] if n else np.empty(0,dtype=np.int64)
    daily = np.diff(np.r_[initial,equity[ends]])
    returns = daily/initial
    std = float(np.std(returns,ddof=1)) if len(returns) > 1 else 0.
    sharpe = float(np.sqrt(252)*returns.mean()/std) if std > 0 else None
    monthly = {}
    annual = {}
    for i,value in zip(ends,daily):
        name = _month_name(month[i])
        monthly[name] = monthly.get(name,0.)+float(value)
        annual[name[:4]] = annual.get(name[:4],0.)+float(value)
    daily_pnl = {str(int(session[i])):float(value) for i,value in zip(ends,daily)}
    wins,losses = net[net > 0],net[net < 0]
    positive_sum = float(wins.sum())
    largest_trade = float(wins.max()) if len(wins) else 0.
    largest_day = float(max(0.,daily.max())) if len(daily) else 0.
    max_dd = _drawdown(equity,initial)
    close_peaks = np.maximum.accumulate(np.r_[initial,equity])[1:]
    intrabar_dd = float(np.max(close_peaks-worst)) if n else 0.
    exposure = float(np.count_nonzero(quantity)/n) if n else 0.
    regime_pnl = {}
    regime_trades = {}
    if "regime" in data:
        regimes = _index_array(data,"regime",n)
        labels = data.get("regime_labels",DEFAULT_REGIME_LABELS)
        for index,value in zip(entry,net):
            regime = int(regimes[index])
            name = str(labels.get(regime,labels.get(str(regime),f"regime_{regime}")))
            regime_pnl[name] = regime_pnl.get(name,0.)+float(value)
            regime_trades[name] = regime_trades.get(name,0)+1
    consistency = largest_day/terminal_net if terminal_net > 0 else None
    lock = int(result.get("lock",0))
    return dict(net_pnl=terminal_net,max_drawdown=max_dd,realized_drawdown=_drawdown(cash,initial),
        intrabar_drawdown=intrabar_dd,max_intraday_drawdown_bound=intrabar_dd,
        gross_pnl=float(net.sum()+fees.sum()),fees=float(fees.sum()),
        positive_trade_pnl=positive_sum,negative_trade_pnl=float(losses.sum()),
        profit_factor=positive_sum/abs(float(losses.sum())) if len(losses) else None,
        sharpe=sharpe,win_rate=float(len(wins)/count) if count else None,
        expectancy=float(net.mean()) if count else None,expected_value_per_trade=float(net.mean()) if count else None,
        trades=count,avg_duration=float(np.mean(exit_-entry)*bar_minutes) if count else None,
        avg_duration_bars=float(np.mean(exit_-entry)) if count else None,
        monthly_pnl=monthly,annual_pnl=annual,daily_pnl=daily_pnl,
        regime_pnl=regime_pnl,regime_trades=regime_trades,
        top_trade_share=largest_trade/positive_sum if positive_sum > 0 else None,
        top_trade_share_of_net=largest_trade/terminal_net if terminal_net > 0 else None,
        positive_months=sum(value > 0 for value in monthly.values()),total_months=len(monthly),
        consistency=consistency,largest_profitable_day=largest_day,
        consistency_50_pass=bool(consistency is not None and consistency <= .5),
        consistency_calculation="largest positive session mark-to-market P&L / total net; configured research diagnostic, not verified account eligibility",
        funded_failed=bool(result.get("funded_failed",False)),killed=lock > 0,lock=lock,
        trading_days=len(ends),active_trading_days=len(set(int(session[i]) for i in entry)) if count else 0,
        exposure_fraction=exposure,ledger_reconciled=True,
        annualization="252 observed trading sessions; constant initial capital; not future probability")

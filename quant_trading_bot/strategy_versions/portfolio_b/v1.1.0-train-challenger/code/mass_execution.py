"""Deterministic, JIT event simulator for governed training screens.

Signals are -1/0/1 and zero means HOLD. Entries execute at the following bar
open. Scheduled/time/protective exits are the only exits. The supported subset
has no quote/depth model, entry limits, random fills or signal reversals.
"""
import math
import numpy as np
from numba import njit


TRADE_REASONS = {1:"session_exit",2:"time_exit",3:"stop",4:"target",5:"gap_recovery",6:"risk_exit",7:"terminal_close"}
LOCK_REASONS = {0:None,1:"maximum_drawdown",2:"market_data_gap",3:"unreconciled_roll",4:"funded_floor"}


@njit(cache=True)
def _price(reference,side,tick,adverse):
    units = (reference+side*adverse)/tick
    return (math.ceil(units) if side > 0 else math.floor(units))*tick


@njit(cache=True)
def _close(reference,limit,side,qty,entry,entry_fee,tick,mult,adverse,fee):
    price = round(reference/tick)*tick if limit else _price(reference,-side,tick,adverse)
    gross = side*qty*(price-entry)*mult
    exit_fee = qty*fee
    return price,gross-exit_fee,gross-entry_fee-exit_fee,entry_fee+exit_fee


@njit(cache=True)
def _scan(timestamp,session,minute,contract,opening,high,low,close,volume,signal,atr,
          initial,tick,mult,fee,adverse,maxqty,trade_risk,open_risk,daily_loss,hard_dd,
          stop_atr,stop_ticks,target_ratio,hold_bars,entry_start,entry_end,flat_minute,
          max_gap_ns,participation,trailing_atr,max_losses,funded_drawdown,funded_cap):
    n = len(close)
    equity = np.full(n,initial)
    cash_curve = np.full(n,initial)
    worst_curve = np.full(n,initial)
    quantities = np.zeros(n,np.int64)
    floor_curve = np.full(n,initial-funded_drawdown)
    te = np.empty(n+1,np.int64)
    tx = np.empty(n+1,np.int64)
    ts = np.empty(n+1,np.int64)
    tq = np.empty(n+1,np.int64)
    tp = np.empty(n+1)
    xp = np.empty(n+1)
    tn = np.empty(n+1)
    tf = np.empty(n+1)
    tr = np.empty(n+1,np.int64)
    cash = initial
    peak = initial
    floor = initial-funded_drawdown
    eod_peak = initial
    day_start = initial
    day_locked = False
    funded_failed = False
    lock_code = 0
    losses = 0
    pending = 0
    pending_stop = 0.
    side = 0
    qty = 0
    entry = stop = target = entry_fee = 0.
    entry_index = -1
    trade_count = 0
    for i in range(n):
        gap = i > 0 and timestamp[i]-timestamp[i-1] > max_gap_ns
        roll = i > 0 and contract[i] != contract[i-1]
        if roll and side != 0:
            lock_code = 3
            break
        if gap or roll:
            pending = 0
        if i == 0 or session[i] != session[i-1]:
            if i > 0:
                # Only completed prior-session cash ratchets the EOD floor.
                eod_peak = max(eod_peak,cash)
                floor = max(floor,min(eod_peak-funded_drawdown,funded_cap))
            day_start = cash
            day_locked = False
            losses = 0
        no_entry = minute[i] >= flat_minute and minute[i] < 1080
        # Root supplies regular-session signal masks; UTC weekday is accurate
        # for those US-daytime bars and bars late on Saturday/Sunday are denied.
        weekday = (timestamp[i]//86400000000000+3)%7
        if weekday == 5 or (weekday == 6 and minute[i] < 1080):
            no_entry = True
        if i > 0 and side != 0 and trailing_atr > 0 and np.isfinite(atr[i-1]):
            proposed = close[i-1]-side*trailing_atr*atr[i-1]
            proposed = round(proposed/tick)*tick
            stop = max(stop,proposed) if side > 0 else min(stop,proposed)
        reason = 0
        exit_reference = 0.
        exit_limit = False
        if side != 0:
            if gap:
                reason = 5
                exit_reference = opening[i]
                lock_code = 2
            elif no_entry:
                reason = 1
                exit_reference = opening[i]
            elif i-entry_index >= hold_bars:
                reason = 2
                exit_reference = opening[i]
        # Scheduled/open exits precede the current bar's high and low.
        if reason:
            ex,delta,net,fees = _close(exit_reference,False,side,qty,entry,entry_fee,tick,mult,adverse,fee)
            cash += delta
            te[trade_count],tx[trade_count] = entry_index,i
            ts[trade_count],tq[trade_count] = side,qty
            tp[trade_count],xp[trade_count] = entry,ex
            tn[trade_count],tf[trade_count],tr[trade_count] = net,fees,reason
            trade_count += 1
            losses = losses+1 if net < 0 else 0
            side,qty = 0,0
            pending = 0
        if pending != 0:
            if not no_entry and not day_locked and lock_code == 0 and not funded_failed and side == 0:
                risk_per = pending_stop*mult+2*fee+(2*adverse+tick)*mult
                requested = min(maxqty,int(math.floor(min(trade_risk,open_risk)/risk_per)))
                cap = int(max(0.,volume[i-1])*participation) if i > 0 else 0
                fill_qty = min(requested,cap)
                if fill_qty > 0:
                    side,qty = pending,fill_qty
                    entry = _price(opening[i],side,tick,adverse)
                    entry_fee = qty*fee
                    cash -= entry_fee
                    stop = entry-side*pending_stop
                    target = entry+side*pending_stop*target_ratio
                    target = round(target/tick)*tick
                    entry_index = i
            pending = 0
        # A protective exit has an adverse excursion before its accounting
        # close. Preserve that bound even when the position closes this bar.
        worst = cash
        if side != 0:
            opening_stop = side*(opening[i]-stop) <= 0
            stop_hit = low[i] <= stop if side > 0 else high[i] >= stop
            target_hit = high[i] >= target+tick if side > 0 else low[i] <= target-tick
            reason = 0
            if opening_stop or stop_hit:
                reason = 3
                exit_reference = min(opening[i],stop) if side > 0 else max(opening[i],stop)
            elif target_hit:
                reason = 4
                exit_reference = target
                exit_limit = True
            adverse_bar = low[i] if side > 0 else high[i]
            # A stop executes before any deeper unobserved excursion; adverse
            # gap/fees are included by its actual exit price below.
            if reason == 3:
                worst = cash+side*qty*(exit_reference-entry)*mult-qty*fee-qty*adverse*mult
            else:
                worst = cash+side*qty*(adverse_bar-entry)*mult-qty*fee-qty*adverse*mult
            if reason:
                ex,delta,net,fees = _close(exit_reference,exit_limit,side,qty,entry,entry_fee,tick,mult,adverse,fee)
                cash += delta
                te[trade_count],tx[trade_count] = entry_index,i
                ts[trade_count],tq[trade_count] = side,qty
                tp[trade_count],xp[trade_count] = entry,ex
                tn[trade_count],tf[trade_count],tr[trade_count] = net,fees,reason
                trade_count += 1
                losses = losses+1 if net < 0 else 0
                side,qty = 0,0
                worst = min(worst,cash)
        mark = cash+side*qty*(close[i]-entry)*mult if side else cash
        worst = min(worst,mark,cash if side == 0 else worst)
        if peak-worst >= hard_dd-1e-8 and lock_code == 0:
            lock_code = 1
        if worst <= floor+1e-8:
            funded_failed = True
            if lock_code == 0:
                lock_code = 4
        if day_start-worst >= daily_loss-1e-8 or losses >= max_losses:
            day_locked = True
        if (lock_code != 0 or day_locked or funded_failed) and side != 0:
            reference = low[i] if side > 0 else high[i]
            ex,delta,net,fees = _close(reference,False,side,qty,entry,entry_fee,tick,mult,adverse,fee)
            cash += delta
            te[trade_count],tx[trade_count] = entry_index,i
            ts[trade_count],tq[trade_count] = side,qty
            tp[trade_count],xp[trade_count] = entry,ex
            tn[trade_count],tf[trade_count],tr[trade_count] = net,fees,6
            trade_count += 1
            losses = losses+1 if net < 0 else 0
            side,qty = 0,0
            mark = cash
            worst = min(worst,cash)
            if peak-worst >= hard_dd-1e-8 and lock_code == 0:
                lock_code = 1
            if worst <= floor+1e-8:
                funded_failed = True
                if lock_code == 0:
                    lock_code = 4
        peak = max(peak,mark)
        equity[i],cash_curve[i],worst_curve[i],quantities[i],floor_curve[i] = mark,cash,worst,side*qty,floor
        if lock_code == 0 and not funded_failed and not day_locked and not no_entry and side == 0:
            if signal[i] != 0 and entry_start <= minute[i] <= entry_end:
                distance = stop_ticks*tick if stop_ticks > 0 else atr[i]*stop_atr
                if np.isfinite(distance) and distance > 0:
                    pending_stop = max(tick,math.ceil(distance/tick)*tick)
                    pending = int(signal[i])
    if n > 0 and side != 0:
        ex,delta,net,fees = _close(close[-1],False,side,qty,entry,entry_fee,tick,mult,adverse,fee)
        cash += delta
        te[trade_count],tx[trade_count] = entry_index,n-1
        ts[trade_count],tq[trade_count] = side,qty
        tp[trade_count],xp[trade_count] = entry,ex
        tn[trade_count],tf[trade_count],tr[trade_count] = net,fees,7
        trade_count += 1
        equity[-1],cash_curve[-1],quantities[-1] = cash,cash,0
        worst_curve[-1] = min(worst_curve[-1],cash)
        if peak-worst_curve[-1] >= hard_dd-1e-8 and lock_code == 0:
            lock_code = 1
        if cash <= floor+1e-8:
            funded_failed = True
            if lock_code == 0:
                lock_code = 4
    return (equity,cash_curve,worst_curve,quantities,floor_curve,te[:trade_count],tx[:trade_count],ts[:trade_count],tq[:trade_count],
            tp[:trade_count],xp[:trade_count],tn[:trade_count],tf[:trade_count],tr[:trade_count],lock_code,funded_failed)


def execute(data,signal,atr,cfg):
    """Execute aligned array inputs and return every mark and closed trade.

    The wrapper rejects unsupported/nonfinite inputs instead of silently
    changing trade semantics. `factor` multiplies all cash/tick costs.
    """
    keys = ("timestamp","session","minute","contract","open","high","low","close","volume")
    n = len(data["close"])
    if any(len(data[key]) != n for key in keys) or len(signal) != n or len(atr) != n:
        raise ValueError("Aligned arrays required")
    if not np.isin(signal,[-1,0,1]).all():
        raise ValueError("Signals must be -1/0/1; zero means HOLD")
    signal = np.ascontiguousarray(signal,dtype=np.int8)
    atr = np.ascontiguousarray(atr,dtype=np.float64)
    integer = [np.ascontiguousarray(data[k],dtype=np.int64) for k in keys[:4]]
    prices = [np.ascontiguousarray(data[k],dtype=np.float64) for k in keys[4:]]
    timestamp = integer[0]
    if n and (np.any(np.diff(timestamp) <= 0) or any(not np.isfinite(p).all() for p in prices) or np.any(prices[4] < 0) or np.any(prices[4]%1 != 0)):
        raise ValueError("Chronological finite OHLCV required")
    if n and (np.any(prices[1] < np.maximum(prices[0],prices[3])) or np.any(prices[2] > np.minimum(prices[0],prices[3])) or np.any(prices[1] < prices[2])):
        raise ValueError("Invalid OHLC")
    get = cfg.get
    tick,mult = float(get("tick",.25)),float(get("multiplier",2.))
    factor = float(get("factor",1.))
    fee = float(get("commission_per_side",.5))+float(get("exchange_per_side",0.))+float(get("regulatory_per_side",0.))
    adverse_ticks = float(get("slippage_ticks",1.))+float(get("spread_ticks",1.))/2+float(get("impact_ticks",0.))
    maxqty = int(get("maxqty",1))
    numeric = [tick,mult,factor,fee,adverse_ticks,float(get("risk_per_trade",150.)),float(get("max_open_risk",150.)),
        float(get("daily_loss",300.)),float(get("hard_drawdown",1800.)),float(get("target_ratio",2.)),
        float(get("participation",.01)),float(get("trailing_atr",0.)),float(get("funded_drawdown",2000.))]
    if not all(math.isfinite(value) for value in numeric) or tick <= 0 or mult <= 0 or factor <= 0 or fee < 0 or adverse_ticks < 0 or maxqty < 1:
        raise ValueError("Positive economics and risk parameters required")
    if any(float(get(key,default)) <= 0 for key,default in (("risk_per_trade",150),("max_open_risk",150),("daily_loss",300),("hard_drawdown",1800),("target_ratio",2),("funded_drawdown",2000))) or not 0 < float(get("participation",.01)) <= 1:
        raise ValueError("Positive risk, target and participation limits required")
    if maxqty != float(get("maxqty",1)) or int(get("hold_bars",8)) < 1 or int(get("max_consecutive_losses",5)) < 1 or float(get("trailing_atr",0.)) < 0:
        raise ValueError("Integer positive sizing/holding limits and nonnegative trail required")
    if get("use_observed_quotes",False):
        raise ValueError("This OHLC screen does not support observed quotes")
    result = _scan(*integer,*prices,signal,atr,float(get("initial_balance",50000.)),tick,mult,fee*factor,
        tick*adverse_ticks*factor,maxqty,float(get("risk_per_trade",150.)),float(get("max_open_risk",150.)),
        float(get("daily_loss",300.)),float(get("hard_drawdown",1800.)),float(get("stop_atr",1.)),int(get("stop_ticks",0)),
        float(get("target_ratio",2.)),int(get("hold_bars",8)),int(get("entry_start",570)),int(get("entry_end",930)),
        int(get("flat_minute",955)),int(float(get("max_gap_minutes",20))*60000000000),float(get("participation",.01)),
        float(get("trailing_atr",0.)),int(get("max_consecutive_losses",5)),float(get("funded_drawdown",2000.)),float(get("funded_cap",50100.)))
    names = ("equity","cash","worst","quantity","funded_floor","trade_entry","trade_exit","trade_side","trade_qty",
        "trade_entryprice","trade_exitprice","trade_net","trade_fees","trade_reason","lock","funded_failed")
    output = dict(zip(names,result))
    output["lock_reason"] = LOCK_REASONS[output["lock"]]
    if output["lock"] == 3:
        raise RuntimeError("Open raw contract changed without an old-contract liquidation quote")
    return output

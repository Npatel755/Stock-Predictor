"""Past-only reserve/hysteresis controller over frozen TRAIN daily tables.

This retains the old model's approximate daily floor/stop accounting. It does
not provide an intrabar funded-account certification.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def replay_reserve(net, risk, dates, starts, ends, yearends, keep, gate_on,
                   gate_off, four_at):
    out = np.zeros((len(starts), 13))
    for si in range(len(starts)):
        bal = 0.; paid = 0; since = 0.; withdrawn = 0.; closed = 0.
        cons = 0.; low = 0.; first = 730.; pays1 = 0.; cash1 = 0.; pnl = 0.
        peak = 0.; drawdown = 0.; room = 2000.; switches = 0.; active = False
        a = np.searchsorted(dates, starts[si]); b = np.searchsorted(dates, ends[si])
        for j in range(a, b):
            old = active
            if active:
                if bal < gate_off: active = False
            elif bal >= gate_on:
                active = True
            switches += old != active
            bi = 2 if active else 0
            m = 1
            if bal >= 4000.: m = 2
            if bal >= 4600.: m = 3
            if bal >= four_at: m = 4
            floor = 0. if paid > 0 else -2000.
            if bal - risk[bi, m-1, j] <= floor: cons = 1.
            night = 1 if bal >= 500. else 0
            p = max(net[bi, m-1, night, j], -1000.)
            bal += p; since += p; pnl += p
            peak = max(peak, pnl); drawdown = max(drawdown, peak-pnl)
            room = min(room, bal-floor)
            if paid == 0: low = min(low, bal)
            if bal <= floor: closed = 1.; break
            w = 0.
            if paid == 0 and bal >= 6000.: w = 500.
            elif (since > 0. or paid == 0) and bal-keep >= 250.:
                w = min(1500., bal-keep)
            if w > 0.:
                bal -= w; withdrawn += w; paid += 1; since = 0.
                room = min(room, bal)
                if first == 730.: first = dates[j]-starts[si]
                if dates[j] < yearends[si]: pays1 += 1; cash1 += w
        out[si, :10] = np.array([withdrawn, closed, cons, 1. if low <= -1500. else 0.,
            first, pays1, cash1, bal, pnl, float(paid)])
        out[si, 10] = drawdown; out[si, 11] = room; out[si, 12] = switches
    return out


def reference(net, risk, dates, start, end, yearend, keep, gate_on, gate_off, four_at):
    """Independent ordinary-Python account ledger, one start at a time."""
    balance = cumulative = withdrawn = since = high = dd = 0.
    count = y1_count = 0; y1_cash = 0.; minimum = 0.; room = 2000.
    closed = flag = False; first = 730.; active = False; switches = 0
    for j, date in enumerate(dates):
        if not start <= date < end: continue
        next_active = balance >= (gate_off if active else gate_on)
        switches += int(next_active != active); active = next_active
        book = 2 if active else 0
        size = 4 if balance >= four_at else 3 if balance >= 4600 else 2 if balance >= 4000 else 1
        floor = 0. if count else -2000.
        flag |= balance-float(risk[book, size-1, j]) <= floor
        change = max(-1000., float(net[book, size-1, int(balance >= 500), j]))
        balance += change; cumulative += change; since += change
        high = max(high, cumulative); dd = max(dd, high-cumulative)
        room = min(room, balance-floor)
        if count == 0: minimum = min(minimum, balance)
        if balance <= floor: closed = True; break
        if count == 0 and balance >= 6000: cash = 500.
        elif balance >= keep+250 and (since > 0 or count == 0): cash = min(1500., balance-keep)
        else: cash = 0.
        if cash:
            balance -= cash; withdrawn += cash; count += 1; since = 0.
            room = min(room, balance)
            if first == 730: first = float(date-start)
            if date < yearend: y1_count += 1; y1_cash += cash
    return np.array([withdrawn, float(closed), float(flag), float(minimum <= -1500), first,
        y1_count, y1_cash, balance, cumulative, count, dd, room, switches])

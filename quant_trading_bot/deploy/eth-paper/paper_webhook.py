"""TradingView strategy-alert receiver with a Breakout-ruled paper ledger.

TradingView cannot auto-trade its own Paper Trading account and Breakout has
no API, so this process is the paper account: a Pine strategy fires an alert
on every simulated order fill, TradingView POSTs it here, and the fill is
appended to an immutable JSONL ledger and scored against the Breakout $50k
1-Step limits (static $47,000 floor, 3% daily loss measured from the balance
at 00:30 UTC). Nothing here routes orders anywhere.

One separate paper account per strategy, routed by the alert's ticker:
ETHUSDT.P -> ETH v1.11 (artifacts/paper_trading), BNBUSDT.P -> BNB
crypto_v0_1 (artifacts/paper_trading/bnb), SOLUSDT.P -> SOL crypto_v0_4
(artifacts/paper_trading/sol), BTCUSDT.P -> BTC crypto_v0_11
(artifacts/paper_trading/btc). A second strategy on the same coin is told apart
by the order comment its Pine script sets: SOLUSDT.P with comment "v0_91" ->
SOL crypto_v0_91 (artifacts/paper_trading/sol_v0_91). Alerts for any other
ticker are rejected. All alerts share the secret and the message JSON.

Alert message to paste into TradingView (valid JSON; placeholders are
expanded by TradingView):

{"secret":"YOUR_SECRET","ticker":"{{ticker}}","action":"{{strategy.order.action}}",
 "contracts":"{{strategy.order.contracts}}","price":"{{strategy.order.price}}",
 "position":"{{strategy.position_size}}","id":"{{strategy.order.id}}",
 "comment":"{{strategy.order.comment}}","time":"{{timenow}}"}
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import urllib.request

ROOT = Path('/opt/eth-paper')

DIRECTORY = ROOT/'artifacts/paper_trading'
FUTURES_SUMMARY = Path(os.environ.get('FUTURES_SUMMARY', '/opt/futures-paper/runs/dashboard.json'))
ACCOUNT_STATUS = Path(os.environ.get('ACCOUNT_STATUS', '/opt/futures-paper/runs/_account_static_daily/status.json'))  # Claude 2026-11-10
ACCOUNTS = {'ETHUSDT': dict(name='ETH v1.11', subdir='', ticker='ETHUSDT', risk_usd=150.),
            'BNBUSDT': dict(name='BNB crypto_v0_1', subdir='bnb', ticker='BNBUSDT', risk_usd=200.),
            'SOLUSDT': dict(name='SOL crypto_v0_4', subdir='sol', ticker='SOLUSDT', risk_usd=200.),
            'BTCUSDT': dict(name='BTC crypto_v0_11', subdir='btc', ticker='BTCUSDT', risk_usd=100.),
            'SOL_V0_91': dict(name='SOL crypto_v0_91', subdir='sol_v0_91', ticker='SOLUSDT', tag='v0_91', risk_usd=100.)}
INITIAL_CAPITAL, STATIC_FLOOR, DAILY_LOSS_FRACTION, COMMISSION_BPS = 50000., 47000., .03, 4.
DAY_RESET = timedelta(minutes=30)


class RejectedAlert(ValueError):
    pass


def new_state():
    return dict(initial_capital=INITIAL_CAPITAL, static_floor=STATIC_FLOOR, daily_loss_fraction=DAILY_LOSS_FRACTION,
                commission_bps=COMMISSION_BPS, position=0., average_price=0., balance=INITIAL_CAPITAL, realized_gross=0.,
                fees=0., closed_trades=[], fills=0, duplicates=0, trading_day=None, day_start_balance=INITIAL_CAPITAL,
                breaches=[], last_fill=None, seen=[])


def parse_alert(body, secret):
    try:
        payload = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RejectedAlert('Body is not JSON; the TradingView message must be the documented JSON template')
    if not isinstance(payload, dict) or not secrets.compare_digest(str(payload.get('secret', '')), secret):
        raise RejectedAlert('Missing or wrong secret')
    action = str(payload.get('action', '')).lower()
    if action not in {'buy', 'sell'}:
        raise RejectedAlert('action must be buy or sell')
    try:
        contracts, price = float(payload['contracts']), float(payload['price'])
        position = float(payload.get('position', 'nan'))
    except (KeyError, TypeError, ValueError):
        raise RejectedAlert('contracts, price and position must be numeric')
    if contracts <= 0 or price <= 0:
        raise RejectedAlert('contracts and price must be positive')
    raw = str(payload.get('time', ''))
    try:
        when = datetime.fromisoformat(raw.replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        when = datetime.now(timezone.utc)
    return dict(ticker=str(payload.get('ticker', '')), action=action, contracts=contracts, price=price,
                position_after=position, order_id=str(payload.get('id', '')), comment=str(payload.get('comment', '')),
                time=when.isoformat(), received_at=datetime.now(timezone.utc).isoformat())


def route(ticker, comment=''):
    """Account key for a TradingView ticker such as ETHUSDT.P or BINANCE:BNBUSDT.P. When two strategies trade the
    same coin, the Pine script of the newer one stamps every order comment with its tag (e.g. "v0_91")."""
    symbol = str(ticker).upper().split(':')[-1]
    matches = [key for key, spec in ACCOUNTS.items() if symbol.startswith(spec['ticker'])]
    if not matches:
        raise RejectedAlert(f'No paper account for ticker {ticker!r}')
    tagged = [key for key in matches if ACCOUNTS[key].get('tag') and ACCOUNTS[key]['tag'] in str(comment)]
    if tagged:
        return tagged[0]
    untagged = [key for key in matches if not ACCOUNTS[key].get('tag')]
    if not untagged:
        raise RejectedAlert(f'Ticker {ticker!r} needs a strategy tag in the order comment')
    return untagged[0]


def fill_key(fill):
    return hashlib.sha256(json.dumps([fill['time'], fill['action'], fill['contracts'], fill['price'], fill['order_id']]).encode()).hexdigest()[:24]


def trading_day(when):
    return (datetime.fromisoformat(when)-DAY_RESET).date().isoformat()


def apply_fill(state, fill):
    """Mutates state; returns the closed-trade record if the fill closed exposure."""
    key = fill_key(fill)
    if key in state['seen']:
        state['duplicates'] += 1
        return None
    state['seen'] = (state['seen']+[key])[-500:]
    if state['position'] == 0 and fill['position_after'] == 0:
        # Exit of a position the ledger never opened (the Pine script was already in a trade when the alert
        # was created). Booking it would open a phantom position, so it is logged and skipped.
        state['orphans'] = state.get('orphans', 0)+1
        state['last_orphan'] = fill
        return None
    day = trading_day(fill['time'])
    if day != state['trading_day']:
        state['trading_day'], state['day_start_balance'] = day, state['balance']
    signed = fill['contracts'] if fill['action'] == 'buy' else -fill['contracts']
    fee = abs(signed)*fill['price']*state['commission_bps']/10000
    position, average = state['position'], state['average_price']
    closed = None
    if position == 0 or (position > 0) == (signed > 0):
        total = position+signed
        average = (abs(position)*average+abs(signed)*fill['price'])/abs(total)
        position = total
    else:
        closing = min(abs(signed), abs(position))
        gross = closing*(fill['price']-average)*(1 if position > 0 else -1)
        state['realized_gross'] += gross
        closed = dict(direction='long' if position > 0 else 'short', quantity=closing, entry_price=average, exit_price=fill['price'],
                      gross_pnl=gross, exit_fee=fee, comment=fill['comment'], exit_time=fill['time'])
        state['closed_trades'] = (state['closed_trades']+[closed])[-1000:]
        position = position+signed
        average = fill['price'] if abs(position) > 1e-12 and (position > 0) == (signed > 0) else (average if abs(position) > 1e-12 else 0.)
        if abs(position) <= 1e-12:
            position = 0.
    state['fees'] += fee
    state['balance'] = state['initial_capital']+state['realized_gross']-state['fees']
    state['position'], state['average_price'] = position, average
    state['fills'] += 1
    state['last_fill'] = fill
    if state['balance'] <= state['static_floor'] and not any(b['rule'] == 'static_max_drawdown' for b in state['breaches']):
        state['breaches'].append(dict(rule='static_max_drawdown', balance=state['balance'], time=fill['time']))
    if state['balance'] <= state['day_start_balance']*(1-state['daily_loss_fraction']):
        if not any(b['rule'] == 'daily_loss' and b.get('day') == day for b in state['breaches']):
            state['breaches'].append(dict(rule='daily_loss', balance=state['balance'], day=day, time=fill['time']))
    return closed


def summary(state):
    trades = state['closed_trades']
    wins = [t for t in trades if t['gross_pnl'] > 0]
    return dict(balance=round(state['balance'], 2), net_pnl=round(state['balance']-state['initial_capital'], 2),
                floor_buffer=round(state['balance']-state['static_floor'], 2), position=state['position'], average_price=state['average_price'],
                closed_trades=len(trades), win_rate=round(len(wins)/len(trades), 3) if trades else None, fees=round(state['fees'], 2),
                fills=state['fills'], duplicates=state['duplicates'], orphan_exits=state.get('orphans', 0), breaches=state['breaches'], last_fill=state['last_fill'],
                account_alive=not state['breaches'], note='Balance uses closed fills only; open P&L is not marked here.')


class Ledger:
    def __init__(self, directory=DIRECTORY):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.state_path, self.events_path = directory/'state.json', directory/'fills.jsonl'
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else new_state()

    def record(self, fill):
        with self.lock:
            closed = apply_fill(self.state, fill)
            if self.state['last_fill'] is fill:
                with self.events_path.open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(dict(fill=fill, closed=closed, balance=self.state['balance']))+'\n')
                tmp = self.state_path.with_suffix('.tmp')
                tmp.write_text(json.dumps(self.state, indent=1))
                os.replace(tmp, self.state_path)
            return closed


def notify(url, fill, closed, state, name='ETH v1.11'):
    if not url:
        return
    side = fill['action'].upper()
    text = f"{name} paper {side} {fill['contracts']} @ {fill['price']:.2f} ({fill['comment'] or fill['order_id']})"
    if closed:
        text += f" | closed {closed['direction']} {closed['gross_pnl']:+.2f} gross"
    text += f" | balance {state['balance']:,.2f} | floor buffer {state['balance']-state['static_floor']:,.0f}"
    if state['breaches']:
        text += ' | BREACH: '+', '.join(b['rule'] for b in state['breaches'])
    try:
        request = urllib.request.Request(url, data=json.dumps(dict(content=text, text=text)).encode(), headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(request, timeout=5).read()
    except Exception as error:  # notification failures never block the ledger
        print('notify failed:', error, flush=True)


def open_ledgers(directory=DIRECTORY):
    return {key: Ledger(directory/spec['subdir'] if spec['subdir'] else directory) for key, spec in ACCOUNTS.items()}


def status(ledgers):
    return {ACCOUNTS[key]['name']: summary(ledger.state) for key, ledger in ledgers.items()}


COINGECKO_IDS = {'ETHUSDT': 'ethereum', 'BNBUSDT': 'binancecoin', 'SOLUSDT': 'solana', 'BTCUSDT': 'bitcoin', 'SOL_V0_91': 'solana'}
_PRICE_CACHE = dict(time=0., prices={})


def mark_prices(fetch=None, max_age=60.):
    """Best-effort spot marks from CoinGecko (cached); {} when unavailable so the dashboard still renders."""
    import time
    import urllib.request
    if time.time()-_PRICE_CACHE['time'] < max_age:
        return _PRICE_CACHE['prices']
    try:
        if fetch is None:
            url = 'https://api.coingecko.com/api/v3/simple/price?vs_currencies=usd&ids='+','.join(sorted(set(COINGECKO_IDS.values())))
            with urllib.request.urlopen(url, timeout=6) as response:
                raw = json.loads(response.read().decode())
        else:
            raw = fetch()
        prices = {key: float(raw[cg]['usd']) for key, cg in COINGECKO_IDS.items() if cg in raw}
    except Exception as error:
        print('mark prices unavailable:', error, flush=True)
        prices = {}
    _PRICE_CACHE.update(time=time.time(), prices=prices)
    return prices


# Exit rules of the deployed Pine scripts (stop/target/trail are reconstructed server-side because the alert only carries fills).
STRATEGY_RULES = {'ETHUSDT': dict(bar='1H', seconds=3600, stop_atr=1.5, reward_r=5.5, trail_atr=3., chart_bars=48),
                  'BNBUSDT': dict(bar='4H', seconds=14400, stop_atr=3., reward_r=5., trail_atr=4., chart_bars=42),
                  'SOLUSDT': dict(bar='4H', seconds=14400, stop_atr=3., reward_r=5., trail_atr=4., chart_bars=42),
                  'BTCUSDT': dict(bar='4H', seconds=14400, stop_atr=3., reward_r=None, trail_atr=3., chart_bars=42),  # trail-only, no target
                  'SOL_V0_91': dict(bar='4H', seconds=14400, stop_atr=3., reward_r=5., trail_atr=4., chart_bars=42)}
OKX_INSTRUMENTS = {'ETHUSDT': 'ETH-USDT-SWAP', 'BNBUSDT': 'BNB-USDT-SWAP', 'SOLUSDT': 'SOL-USDT-SWAP', 'BTCUSDT': 'BTC-USDT-SWAP',
                   'SOL_V0_91': 'SOL-USDT-SWAP'}
_CANDLE_CACHE = {}


def fetch_candles(key, fetch=None, max_age=60., limit=300):
    """OKX USDT-perp candles of the strategy's management timeframe, oldest first; [] when unavailable."""
    import time
    import urllib.request
    cache_key = (OKX_INSTRUMENTS[key], STRATEGY_RULES[key]['bar'])  # accounts sharing a coin share one fetch
    cached = _CANDLE_CACHE.get(cache_key)
    if cached and time.time()-cached['time'] < max_age:
        return cached['candles']
    try:
        if fetch is None:
            url = f"https://www.okx.com/api/v5/market/candles?instId={OKX_INSTRUMENTS[key]}&bar={STRATEGY_RULES[key]['bar']}&limit={limit}"
            request = urllib.request.Request(url, headers={'User-Agent': 'curl/8.5 paper-dashboard', 'Accept': 'application/json'})
            with urllib.request.urlopen(request, timeout=6) as response:
                raw = json.loads(response.read().decode())
        else:
            raw = fetch(key)
        candles = [dict(time=int(r[0])//1000, open=float(r[1]), high=float(r[2]), low=float(r[3]), close=float(r[4]), closed=r[8] == '1')
                   for r in raw['data']]
        candles.sort(key=lambda c: c['time'])
    except Exception as error:
        print('candles unavailable:', key, error, flush=True)
        candles = cached['candles'] if cached else []
    _CANDLE_CACHE[cache_key] = dict(time=time.time(), candles=candles)
    return candles


def all_candles(fetch=None):
    return {key: fetch_candles(key, fetch) for key in ACCOUNTS}


_FINE_CACHE = {}


def _okx_rows(url):
    import urllib.request
    request = urllib.request.Request(url, headers={'User-Agent': 'curl/8.5 paper-dashboard', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=6) as response:
        return json.loads(response.read().decode())['data']


def fetch_fine_candles(key, since, fetch=None, max_age=60., limit=100):
    """Completed OKX 5m candles from `since` (epoch seconds) to now, oldest first, extended incrementally per instrument;
    [] when unavailable. Pine ratchets the trail on 5m closes, so the bracket needs them (the ATR still comes from 1H/4H)."""
    import time
    inst = OKX_INSTRUMENTS[key]
    cached = _FINE_CACHE.get(inst)
    have = [c for c in cached['candles'] if c['time'] >= since] if cached and cached['since'] <= since else []
    if have and time.time()-cached['time'] < max_age:
        return have
    floor = have[-1]['time']+300 if have else since
    try:
        rows, after = [], None
        for _ in range(60):  # <= 6,000 candles (~3 weeks of 5m bars)
            url = (f"https://www.okx.com/api/v5/market/history-candles?instId={inst}&bar=5m&limit={limit}" if after else
                   f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar=5m&limit=300")+(f"&after={after}" if after else '')
            page = [dict(time=int(r[0])//1000, open=float(r[1]), high=float(r[2]), low=float(r[3]), close=float(r[4]), closed=r[8] == '1')
                    for r in (fetch(key, url) if fetch else _okx_rows(url))]
            if not page:
                break
            rows += page
            oldest = min(c['time'] for c in page)
            if oldest <= floor:
                break
            after = oldest*1000
        merged = {c['time']: c for c in have}
        merged.update({c['time']: c for c in rows if c['time'] >= floor and c['closed']})
        have = sorted(merged.values(), key=lambda c: c['time'])
    except Exception as error:
        print('fine candles unavailable:', key, error, flush=True)
        if not have:
            return []
    _FINE_CACHE[inst] = dict(time=time.time(), since=since, candles=have)
    return have


def all_fine(ledgers, fetch=None):
    """5m candles since the open position's entry for every account that holds one."""
    out = {}
    for key, ledger in ledgers.items():
        state = ledger.state
        if state['position'] and state['last_fill']:
            since = int(datetime.fromisoformat(state['last_fill']['time']).timestamp())
            out[key] = fetch_fine_candles(key, since-since % 300, fetch)
    return out


def atr_series(candles, period=14):
    """Pine ta.atr: RMA of true range, seeded with the simple mean; None until warm."""
    out, rma = [], None
    for i, c in enumerate(candles):
        tr = c['high']-c['low'] if i == 0 else max(c['high']-c['low'], abs(c['high']-candles[i-1]['close']), abs(c['low']-candles[i-1]['close']))
        if i+1 < period:
            out.append(None)
        elif i+1 == period:
            trs = [candles[0]['high']-candles[0]['low']]+[max(x['high']-x['low'], abs(x['high']-candles[j-1]['close']), abs(x['low']-candles[j-1]['close']))
                                                           for j, x in enumerate(candles) if 0 < j <= i]
            rma = sum(trs)/period
            out.append(rma)
        else:
            rma = (rma*(period-1)+tr)/period
            out.append(rma)
    return out


def bracket(state, candles, rules, fine=None):
    """Reconstructs the Pine script's active stop/target for the open position.
    Stop = signal close -/+ stop_atr x ATR(14) at the signal candle; target = reward_r x that distance. The trail ratchets
    the way the Pine scripts do - on every completed 5m close, using the ATR of the last completed 1H/4H candle (`fine`
    = 5m candles since entry; matched TradingView's ETH stop to 7 cents). Without 5m candles it falls back to the 1H/4H
    candle extremes, which overstates the stop."""
    position, fill = state['position'], state['last_fill']
    if not position or not fill or len(candles) < 16:
        return None
    direction = 1 if position > 0 else -1
    entry_time = datetime.fromisoformat(fill['time']).timestamp()
    atr = atr_series(candles)
    signal = max((i for i, c in enumerate(candles) if c['time']+rules['seconds'] <= entry_time), default=None)
    if signal is None or atr[signal] is None:
        return None
    reference, distance = candles[signal]['close'], rules['stop_atr']*atr[signal]
    stop = reference-direction*distance
    target = reference+direction*rules['reward_r']*distance if rules['reward_r'] else None  # trail-only rules have no target
    initial_stop = stop
    fine = [f for f in (fine or []) if f['time'] >= entry_time and f.get('closed', True)]
    if fine:
        index = {c['time']: i for i, c in enumerate(candles)}
        for f in fine:
            i = index.get(f['time']-f['time'] % rules['seconds'])
            if i is None:
                continue
            j = i if (f['time']+300) % rules['seconds'] == 0 else i-1   # Pine: htfClosed ? htfATR : previousATR
            management = atr[j] if j >= 0 else None
            if management is None:
                continue
            proposed = f['close']-direction*rules['trail_atr']*management
            if direction*(proposed-stop) > 0:
                stop = proposed
        method = '5m closes'
    else:
        for i in range(signal+1, len(candles)):
            management = atr[i-1]
            if management is None:
                continue
            extreme = candles[i]['high'] if direction > 0 else candles[i]['low']
            proposed = extreme-direction*rules['trail_atr']*management
            if direction*(proposed-stop) > 0:
                stop = proposed
        method = f"{rules['bar']} extremes (upper bound)"
    mark = fine[-1]['close'] if fine else candles[-1]['close']
    return dict(direction='long' if direction > 0 else 'short', reference=round(reference, 2), distance=round(distance, 2), stop=round(stop, 2),
                initial_stop=round(initial_stop, 2), target=round(target, 2) if target else None, trailing=stop != initial_stop,
                stop_pnl=round(position*(stop-state['average_price']), 2),
                target_pnl=round(position*(target-state['average_price']), 2) if target else None,
                r_now=round(direction*(mark-reference)/distance, 2) if distance else None, estimated=True, method=method)


def chart_svg(candles, bracket_, width=320, height=130):
    """Inline SVG snapshot: recent candles with entry (grey), stop (red) and target (green) levels."""
    if len(candles) < 2:
        return '<div class="nochart">chart unavailable</div>'
    levels = [bracket_['reference'], bracket_['stop']] if bracket_ else []
    lo, hi = min([c['low'] for c in candles]+levels), max([c['high'] for c in candles]+levels)
    span = hi-lo or 1.
    if bracket_ and bracket_['target'] and lo-span*.3 <= bracket_['target'] <= hi+span*.3:
        lo, hi = min(lo, bracket_['target']), max(hi, bracket_['target'])
    pad = (hi-lo)*.06 or 1.
    lo, hi = lo-pad, hi+pad
    top, bottom, left, right = 6, height-6, 2, width-40
    y = lambda v: bottom-(v-lo)/(hi-lo)*(bottom-top)
    step = (right-left)/len(candles)
    body = max(1., step*.6)
    parts = []
    for i, c in enumerate(candles):
        x = left+step*(i+.5)
        colour = '#2ecc71' if c['close'] >= c['open'] else '#ff5c5c'
        parts.append(f'<line x1="{x:.1f}" y1="{y(c["high"]):.1f}" x2="{x:.1f}" y2="{y(c["low"]):.1f}" stroke="{colour}" stroke-width="1"/>')
        y0, y1 = sorted((y(c['open']), y(c['close'])))
        parts.append(f'<rect x="{x-body/2:.1f}" y="{y0:.1f}" width="{body:.1f}" height="{max(y1-y0, 1):.1f}" fill="{colour}"/>')
    labels = [dict(y=y(candles[-1]['close']), text=f"{candles[-1]['close']:,.0f}", colour='#e6e6e6', weight='600')]
    if bracket_:
        for value, colour in ((bracket_['reference'], '#b8bec9'), (bracket_['stop'], '#ff5c5c'), (bracket_['target'], '#2ecc71')):
            if value is None:
                continue
            if lo <= value <= hi:
                yy = y(value)
                parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="{colour}" stroke-width="1" stroke-dasharray="4 3"/>')
                labels.append(dict(y=yy, text=f'{value:,.0f}', colour=colour, weight='400'))
            else:
                labels.append(dict(y=top if value > hi else bottom, text=f"{value:,.0f} {'&#8593;' if value > hi else '&#8595;'}", colour=colour, weight='400'))
    labels.sort(key=lambda l: l['y'])
    for i, label in enumerate(labels):  # keep the price tags readable: clamp to the box and push overlapping tags apart
        label['y'] = max(label['y'], top+4 if i == 0 else labels[i-1]['y']+10)
    for i in range(len(labels)-1, -1, -1):
        labels[i]['y'] = min(labels[i]['y'], bottom-3 if i == len(labels)-1 else labels[i+1]['y']-10)
    for label in labels:
        parts.append(f'<text x="{right+3}" y="{label["y"]+3.5:.1f}" fill="{label["colour"]}" font-size="9" font-weight="{label["weight"]}">{label["text"]}</text>')
    return f'<svg class="chart" viewBox="0 0 {width} {height}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'



def dashboard_rows(ledgers, prices, candles=None, fine=None):
    rows = []
    for key, ledger in ledgers.items():
        state, series = ledger.state, (candles or {}).get(key) or []
        mark = series[-1]['close'] if series else prices.get(key)
        open_pnl = round(state['position']*(mark-state['average_price']), 2) if mark and state['position'] else 0.
        trades = state['closed_trades']
        rows.append(dict(key=key, name=ACCOUNTS[key]['name'], balance=round(state['balance'], 2), net_pnl=round(state['balance']-state['initial_capital'], 2),
                         open_pnl=open_pnl, mark=mark, equity=round(state['balance']+open_pnl, 2), floor_buffer=round(state['balance']+open_pnl-state['static_floor'], 2),
                         position=state['position'], average_price=state['average_price'], closed_trades=len(trades),
                         wins=sum(1 for t in trades if t['gross_pnl'] > 0), fees=round(state['fees'], 2), last_fill=state['last_fill'],
                         alive=not state['breaches'], orphan_exits=state.get('orphans', 0), bracket=bracket(state, series, STRATEGY_RULES[key], (fine or {}).get(key)),
                         candles=series[-STRATEGY_RULES[key]['chart_bars']:]))
    return rows


def dashboard_payload(ledgers, prices, candles=None, fine=None):
    rows = dashboard_rows(ledgers, prices, candles, fine)
    total = dict(net_pnl=round(sum(r['net_pnl'] for r in rows), 2), open_pnl=round(sum(r['open_pnl'] for r in rows), 2),
                 closed_trades=sum(r['closed_trades'] for r in rows), wins=sum(r['wins'] for r in rows), fees=round(sum(r['fees'] for r in rows), 2))
    total['total_pnl'] = round(total['net_pnl']+total['open_pnl'], 2)
    return dict(generated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), marks=any(r['mark'] for r in rows), accounts=rows, total=total)


ICON_PNG = {512: """iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAIAAAB7GkOtAAAVsUlEQVR42u3deXgU9cHA8WTZxIQbQTyBACK3YKFWrVaxXu3jUVvFetSiIoKICiqgaBXFg3phWysVW6tv61Gf16uttlVEBRFFQJH7EhAwBiEgOSCJyfsHfXx8UWFms0l2dz6fvxRmdmdnlt93fnvMZu97QMcs/r/cvBZ2AmSYiu1b7YRdxI31ngQQ2X/sEa9C3JMAUIVo9iAewWMMsMexIgoxiEfkWAIkNoBkcAnimXrMAEwLohIAQz9QP+NMxmQgnhnHA6D+h510L0E8A44BgAlBVAJg6AdkIFoBMO4DqT9ApVEJ4um1ZwFMCJIlZvQHiObAFbcHAaI5FYin8o4DkIEIBcDQD8hA/Yil4D4CyOAMmAEY+gFTATMAoz9gKhDNABj9AQ1oEPGIP36Ahh0DG/DloFjDPnIAGYhWAIz+AA0+JMYj8jgBUr8B9fxyUKz+HyEAqTBIxjL1gQFoQEoEwOgPkGoDZiyTHgyABqRQAIz+AKk5eMbS/QEAaEDKBcDoD5DKA2ksHTcaQANSNABGf4DUH1Rj6bKhABqQ0gEw+gOkSwNiqbxxANTdMBtLzc0CoK4H21iqbRAA9TPkxu1KIqKgQ7u+fXoe3Lljhw4HtW3TplWrFnl5eTk5OVVfVFXsqKioqNy+Y3tx8dZNm4o3bd688bPN69ZtWLN23dqP15eVldt7ZKTsfQ/o6PQ/grp36/LnRx5I4g3W1NRUVlbuqKgsLyvfXLxl8+bi9RsKV6/+eOVHqxcuWlZRUdGA4/7pp518wvHH7Nt2n8Ru4bNNm5ctX7V4yfIlS5cvXrJ848ZNqXNcFi5aevGQkZ7P0VT7Hw+o7QzA6M9/TyWys3Nzc3Nzc5s1bdK2bZuv/lVlZdWiJcumz5g19bUZGz4prLdN6tSxw+VDBx191OHZ2dm1uZ02rfdu03rvo47ov/N/jzvxZ+Xl5gQ0vNy8FrVsQLyWd+8YsEc5OfE+vXv06d3jimEXz57z/hNPPTfz7dl1fY+XXnLBL847KxaL2f9oQF3NACCU7/br+91+fT9csPj+3zy8cNHSuriLVq1a3nPXr3r17GZvw+4lfn7k9J+E9e7V/ZHJ910+dFCjRo2Se8t7793y4d/fbfQnUpOA+g6A0Z/annrEsn95wcAHH7izadMmSfuXkJNz/923tm93oN2LBtRVAIz+JMthfXtN/t3EZs2aJuXWhl02qFvXg+1VNKBuZwCQLF0O7vTrO26Mx2v7dlSH9gedc/bp9ifUYQCc/pN03zns0GFDLqzljZz3858m/R0FyOxJQLyu7wACDt9Tp81YtHhZYqvn5MRPOuHYUKsUFha9+I9/z57z/tq160tKy3Jyclq0aNaiefN9923Tq0e3nj26du/WpUmTxg4N6dWAUJ8K9TFQUmMqGosNH3rR8KuuT2z13j27N26cH3z551546b5Jf6iorPzyT6qqqsrLywsLi5YuW/Hm9Fk7N6lvn17HH/f9E084tmWL5o4RmSdEAJz+R9luLjmQnZ3dpEnj5s2ade5c0Kd3jx+dPKBNm9YJ3EX/fn169ey2YOGSBNY95JDOwReeM3f+xHserKmp2f1i1dXVc+fNnztv/qTfTjnuB0eee86ZPl1Khk0CzACorZqampKS0pKS0g2fFE6fMWvylMdPP/Wkq664NC9vr7A3deqPT0gsAAfsv2/whZ/537/vcfT/qqqqqldfm/7qa9P7HNpz8MXnZYVZF1J65u30n+Sqqqp69vmXBg2+asvWz8Ou+8MBx8RiiVy3p0njEC/Wr1m7LrGH9sH8hSOuHle+fbujTIpPApIcAAjlo9VrR4+9tbo63Mly8+bNOnUsSODuKqsqQ9TCW7sQPABO/0nkfPnDRa9MfSPsWof27p7AfW3evCX4wof37+voYBIQKABGfxL29DMvhF2l3UGJXMhh/YYQV5k+4/RTcnK8+4UGeAmIurR4yfKSktJQqxx44H4J3NG7780LvvC+bfe58IKBjg7EnP5Td6qrq9d+vD7UKs0Sujbcxo2bli1fFXz5iy78eefOBQ4QEZ8EmAFQt7ZsCfdrFXl5eYnd0RNPPRt84Zyc+J233ZDEC5FCBs4AoJayQ/4mV02in7L/z6tvrFv/SfDlO7Q/aML4sX4yDAFIcPoAexT2Igrbt+9I7I6++OKLOyY+EKofR36v35hrhztGZLDdD+NOf6hDjRo1CvvzLNtKShK+uzlz54f93NFPTv/R5UMHOVKYATj9J8l69jgk7LeuNmz4NOG769ypQ/9+fcKu9csLBp5/7s8cLCI4CfBpaOrQOWf/JOwqYT81tFN2dvbAs06/YthFubm5Cax+5fBLtm0refEf/3bIiJS403/qyHf69v7hgKPDrvXhgsVhV2ncOP+2W8YcfdThtdna60eP2LatZNobb4Va69De3ac8dO8eF5v2+ltjb7zdU4IGnAR84yVCvQdAnejcqcPEO27Mzg53ZbetWz9f9dHqUKvst1/bRx66t5ajf1ZWViwWu/WW0d/t1zfUWgEvfP1p0UZPCVKQAJDsSWU8ftaZp/7p4UnNmzcLu+5rr88Idf24Lgd3+vOUScn6SlduTs7dd93Us0fX4KvsEywAhZ8KACn5r/UbJwv2C8FlZ2c3bpzfvHmzgzsV9Dm0Z8I/CJOVlfX3f74SfOGCgna/nXR7q5bJfLrm5+fff/f4y4aP/mj12iQG4JNPPvU8oWF946tA3gQmkJ49ur4z46U6vYvZc95fuGhpwIUP2H+/Bx+4M7mj/04tWjT/7f23Dx52TWFh0R4XbtfugCC3uXLVak8hUlDM6T+poLq6+veT/xxw4Zyc+J0TbmjTeu862ph99mn9u0l3tGrVco9L9undY4/LlJeXh/qKMtTdJGAPAYAG8cRTzy5avCzgwlcOH9yt68HB0zJ5yuNz5s4PtT3tDjrgN/dN2P3FggoK2gWJxIqVq2v8iiRpMQOA+jf3/Q8nT3k84MI9e3QdeNbpAReuqKi4buytjz721LVjxy9ZuiLUVh3SpdO9E2/ea69v/WJB30N7Bbmd+eE/2AoCQCQsX7FqzA0TKiurAi5/xeUXBz/3HzPu9hkz383KyiorK79q1I2r13wcatv69ul15203NGrU6Bv/9thjjghyI7Nnz3OUSYMAeAOAejbv/QVDrxjz+efbAi7fv1+f7/TtHXDhh//4l5lvz/7yf7ds/fzKkTeG/Uj+9486/FfjRn39Cw2t9251xPf67XH1ysqq9z9Y6ECTInYZ5M0AaBg1NTWP//WZ4VddH+onw0798YkBl1y5as3jf3lmlz/8tGjjiKvHFYf8iYJTThpwzdVDd/nDcwaeEeRS0nPnzS/fvt3hJg1mAFA/Fixccsllox586NEvvvgi+Fp5eXsd94MjAy786GNPfuONr1m77uprbiorKw+1wWf/7LRLLz7/y/9t1bLFWWeeGmTFf7/yusNNGgTA6z/Ug/fmfDBq9C2Dh14T/CP/Xzq0V4/8/PwgS5aWlr3x5tvf9rdLlq64Zsz4ioqKUPc++OLzzzn7jJ3/PXTIL4Nc5bSiouL1N2c66KSUrw71vghGnausrFq8ZPn0GbOmTpu+fkNhwrfTvVuXgEt+8OGiisrK3Swwd978cTffNfH2G0P9ItjIK4d8/vm2TZuKzzjt5CDLv/ra9NLSMk8AUpYAkBw1NTWVVVWVFZVlZeWbi7ds2ly84ZPC1as/Xrly9cLFS3fsqKj9XXTt2jngkkEu5PDm9FkT7px00w0jg1+xLjs7+6YbRm4rKQ24yl+ffNYTAwEg7S1ctPTiISMbdhuCf/W3ZFugN5b/+fKrzZs3u3rEpcG3oVGjRgF/5PLd2fNWrPzIM4dU9t/5rzcASH1NmzYNuGTjxvkBl3zy6ecefeypupgPBf9qG9SzLwd8nwIibTQJPKy3aRPiMkGTpzz+7PNJvs7dv/4zLYF3uaFhZgCQ+iqrgn5bOPjbxTvdfd+Dr0x9M1nbWVpa9uDkRx0vBACSpqws6CdqCjq0K+jQLvgtV1fX3HLbPW+/Mycp23nP/Q9t3LjJ8UIAIGlC/a7W2WedFurGq6qqxo6bMP/D2l64beq06S/9a6qDRdoEwDvApIU1a9cFX/inZ/y4c6cOoW5/+/Ydo0bfvHLl6oS3cOWqNbff9YAjRerbOeybAZA2FixYEuLUJhabMH5ss91e0P/rtm0rGTFyXGLfVtu0uXjUdb/yzS/SbAYAaWHuvPnV1dXBl+/UscPdd92cn5cXdhy/7vpbQ93RTh98sNCPvyMAUCe2lZTOenduqFUO69vr0UcmdWh/UKhVfn3HTaEuEbHT8QOOHjL4Fw4TacQ3gUknz7/w8lFH9A+1SseC9o/98YEnnnruyaef27bbS0/37NH1/HN/evxxRwe/OMQuLhl0blHRxudf/Fe97ZCePbq+MyPJX2JYs3bdwPOGeLIJAKSW6W/NWrlydefOBaHWys/Pv+Si8845+4wZM9+d9c6cJUtXFBdv2VZS2qxpk5YtWxx44P79Duvdv1/frod0rv0Wjrn2iqKNm776QzQgAJAE1dU1v3voT/ffc2sC6zZt2uSUkwacctKAOt3CWCx2x23XD7tizOIlyx0vUlzMZ0BJLzNnvffPl19N5S3Mz8u7/+7xBx6wn4NFKsvNa+FNYNLPvZMmB7ngcwNq1arlpHtvaxHsuqHQYDMAu4C0U1padvW1v9q0uTiVN7J9uwPvnXjzXnvlOl4IACRTYWHR0OGjU/xz9717db/tljGxWLbjhQBAMq39eP2lw65ZtHhZ/dzdjh0Vf5jyPytXrQm11rHHHHnNyGEOFgIASVZU9NmQy699+pkXqqtr6vSO3pw+6+cXDP3TY0+OGn3z5s1bQq171pmnXnj+2Q4WAgBJVllZdd8Dfxg8dFQdfezy3ffmXXLZqOuuv3XDJ4VZWVmFhUXXjh0f9ieOLx866OQTj3OwEABIvoWLlg4afNW1Y8bX/nrOO5WWlj3/4svnXThsxNXjFixcsst9jZ9wb01NiDlHdnb2TTeM6t+vjyNFSvFFMDLH9Lfemf7WOwUd2v3o5OOP/v7hnTsVhL2oQ1HRZ+/N/eD1N2a+Peu9isrKb1ts6rTpBz28/+WXDQp+yzk58Ym33zhk+HW1udw0JFd2u0597QUyUuu9W/Xq2a1Ll04dC9q33adN231aN23aJHev3Jx4vLKqqmJHRUlp2WefbSoq+mzN2nUrV61evHTFunUb7DcEAIAM5z0AAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAEAQAAAEAAABAAAAQBAAABIX3G7AMg8rf42IIMfXfHAaWYAAAgAAAIAgAAAIAAACAAAAgAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAAgCAAAAIAAACAIAAACAAAGSeuF1AsrT624AMfnTFA6c5xJgBACAAAAgAAAIAgAAAIAAACAAAAgCAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACACAAAAgAAAIAAACAIAAACAAAAgAAAIAgAAAIAAACAAAKSJuF0BKWXtUrwx+dO1nLnCIzQAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAAAQBAAAAQAAAyU9wuyMrKavW3ARn86IoHTnOIATMAAAQAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAABAAAAQBAAAAQAAAEAAABAEAAABAAAAQAAAEAQAAAEAAABAAAAQBAAACoI9ntOvXNvEc1YsRQhxZIor8cszR1NqZ44LSk3E7ccQWotzE3pXgJCCCiBABAAAAQAAAEAAABAEAAAEh3mflFMADMAAAQAAAEAAABABAAAAQAAAEAQAAAEAAABAAAAQAgjQJQsX2rvQAQNRXbt5oBAER1BmAXAAgAAAIAgAAAIAAAZFYAfBIUIFJ2DvtmAAARngEAIAAACAAAUQiA94EBIuLLAd8MACDaMwAABACAiAXA2wAAGe+rQ70ZAEDkZwAARDcAXgUCyGC7DPJmAABmAAAIAACRC4C3AQAy0teHdzMAADMAkwCAyJz+mwEAmAEAIABZXgUCyCDfNqSbAQCYAZgEAETm9N8MAMAMwCQAIEqn/2YAAGYAAAhA8OkDAClrjwO4GQCAGYBJAEBkTv+DzgA0ACDDRv8sLwEBRFbQAJgEAGTS6b8ZAIAZgEkAQJRO/80AAMwATAIAonT6n8gMQAMAMmD0z/ISEEBkJRIAkwCAdD/9T3wGoAEAaT36Z9XmJSANAEjf0T/LewAAkVWrAJgEAKTp6X8SZgAaAJCOo39WUl4C0gCAtBv9s7wHABBZyQmASQBAep3+J3MGoAEAaTT6ZyX3JSANAEiX0T8r6e8BaABAWoz+WXXxJrAGAKTF0BpLlw0FMPqnQQA0ACD1h9NYOm40gNE/pQOgAQCpPITG0v0BABj9UzQAGgCQmsNmLJMeDIDRP+UCoAEAqTZUxjL1gQEY/Xcv3iAPLzevhSMN0LDnx7HoPFQAo3/DB0ADABp8MIw3+MP2chBg6I/WDMBUADD6Rz0AGgAY/RtEPKV2h5eDAEN/tGYApgKA0T+6MwBTAcDQH/UAyABg6I90AGQAMPTXtZidCBDNgSueRrvSVAAw9EcuALvsViUAjPvRCoAJAWDoj3oAZAAw9Ec6ALscACUAjPvRCoAJAWDoj3oAvn54xAAw6EcoAN942JQAMO5HKwCmBYBBP+oB2M0B1gMw4kdW3OH/+h+qAhjro+D/AOg2QUoHlaDGAAAAAElFTkSuQmCC""", 180: """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"""}

MANIFEST = dict(name='Paper accounts P&L', short_name='Paper P&L', start_url='/', scope='/', display='standalone', background_color='#0f1115',
                theme_color='#0f1115', icons=[dict(src='/icon-512.png', sizes='512x512', type='image/png', purpose='any'),
                                             dict(src='/icon-180.png', sizes='180x180', type='image/png')])

SERVICE_WORKER = "self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>self.clients.claim());self.addEventListener('fetch',e=>{e.respondWith(fetch(e.request).catch(()=>new Response('<h1 style=font-family:sans-serif>Offline - reopen when you have signal</h1>',{headers:{'Content-Type':'text/html'}})))});"


def _money(value, signed=True):
    if value is None:
        return '-'
    sign = '+' if value > 0 and signed else ('-' if value < 0 else '')
    return f'{sign}${abs(value):,.2f}'


def futures_summary(path=None):
    """Latest MES/MNQ ensemble paper summary written by quant_futures.ensemble_paper (None if absent)."""
    path = Path(path) if path else FUTURES_SUMMARY
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


FUTURE_NOTE = ('Future strategies: pre-registered on 2010-23 and judged worth a forward record, but their drawdown does not fit a fresh $2k floor. '
               'Switch target once the account has banked the stated cushion above its locked floor; not for a current evaluation account.')


FUTURES_BARS_DIR = Path(os.environ.get('FUTURES_BARS_DIR', '/opt/futures-paper/runs/bars'))


def _bars_15m(instrument, minutes=15, max_rows=3000):
    """Last ~max_rows 1-minute bars of the ensemble feed aggregated to N-minute closes: [(utc datetime, close)]."""
    import csv
    from collections import deque
    path = FUTURES_BARS_DIR / f'{instrument}_1m.csv'
    try:
        with path.open() as fh:
            rows = deque(csv.DictReader(fh), maxlen=max_rows)
    except OSError:
        return []
    out, bucket, last = [], None, None
    for r in rows:
        try:
            ts = datetime.fromisoformat(r['timestamp_utc'].replace('Z', '+00:00')); close = float(r['close'])
        except (KeyError, ValueError):
            continue
        b = ts.replace(minute=(ts.minute // minutes) * minutes, second=0, microsecond=0)
        if bucket is not None and b != bucket:
            out.append((bucket, last))
        bucket, last = b, close
    if bucket is not None:
        out.append((bucket, last))
    return out


def futures_price_charts(summary):
    """Inline SVG line charts of MNQ and MES (15-minute closes, last ~2 days of the feed) with open paper positions marked."""
    try:
        from zoneinfo import ZoneInfo
        et = ZoneInfo('America/New_York')
    except Exception:
        et = timezone.utc
    mult = {'MNQ': 2.0, 'MES': 5.0}
    panels = []
    for inst in ('MNQ', 'MES'):
        pts = _bars_15m(inst)
        if len(pts) < 5:
            panels.append(f'<section class="card"><h2>{inst}</h2><p class="note">no bars yet</p></section>'); continue
        w, h, pl, pr, pt, pb = 560, 190, 54, 10, 12, 26
        ys = [c for _, c in pts]; lo, hi = min(ys), max(ys); span = (hi - lo) or 1.0
        def X(i): return pl + (w - pl - pr) * i / (len(pts) - 1)
        def Y(v): return pt + (h - pt - pb) * (1 - (v - lo) / span)
        poly = ' '.join(f'{X(i):.1f},{Y(c):.1f}' for i, (_, c) in enumerate(pts))
        # session boundaries (18:00 ET reopen) and the regular open (09:30 ET)
        marks = ''
        for i, (t, _) in enumerate(pts):
            loc = t.astimezone(et)
            if loc.hour == 18 and loc.minute == 0:
                marks += f'<line x1="{X(i):.1f}" y1="{pt}" x2="{X(i):.1f}" y2="{h-pb}" stroke="#2f3542" stroke-dasharray="3,3"/><text x="{X(i)+2:.1f}" y="{h-pb-3}" fill="#6b7280" font-size="9">{loc.strftime("%a")} 18:00</text>'
            elif loc.hour == 9 and loc.minute == 30:
                marks += f'<line x1="{X(i):.1f}" y1="{pt}" x2="{X(i):.1f}" y2="{h-pb}" stroke="#3b4252" stroke-dasharray="1,3"/><text x="{X(i)+2:.1f}" y="{pt+9}" fill="#6b7280" font-size="9">09:30</text>'
        # open paper positions on this instrument: entry level implied from last close and unrealized P&L (costs included, so approximate)
        pos_lines = ''; groups = {}
        for key, c in (summary or {}).get('candidates', {}).items():
            for name, p in c.get('positions', {}).items():
                q = p.get('quantity') or 0
                if not q or (('MES' in name) != (inst == 'MES')) or not p.get('last_close'):
                    continue
                entry = round(p['last_close'] - (p.get('unrealized') or 0.0) / (q * mult[inst]), 2)
                groups.setdefault((entry, 1 if q > 0 else -1), []).append(f'{key} x{abs(q)}')
        for n_i, ((entry, side), keys) in enumerate(sorted(groups.items())):
            if lo <= entry <= hi:
                col = '#2ecc71' if side > 0 else '#ff5c5c'
                pos_lines += (f'<line x1="{pl}" y1="{Y(entry):.1f}" x2="{w-pr}" y2="{Y(entry):.1f}" stroke="{col}" stroke-dasharray="4,3" opacity="0.8"/>'
                              f'<text x="{w-pr-2}" y="{Y(entry)-2-10*n_i:.1f}" fill="{col}" font-size="9" text-anchor="end">{"long" if side > 0 else "short"} @ {entry:,.2f}: {", ".join(keys)}</text>')
        last_t, last_c = pts[-1]; first_t = pts[0][0]
        day_chg = ''
        day_start = [c for t, c in pts if t.astimezone(et).date() == last_t.astimezone(et).date()]
        if len(day_start) > 1:
            d = last_c - day_start[0]; day_chg = f' <span class="{"pos" if d > 0 else "neg" if d < 0 else "flat"}">{d:+,.2f} ({d / day_start[0]:+.2%}) since 00:00 ET</span>'
        svg = (f'<svg viewBox="0 0 {w} {h}" width="100%" style="display:block;background:#11141b;border-radius:8px">'
               f'<text x="{pl-4}" y="{pt+8}" fill="#8a8f98" font-size="10" text-anchor="end">{hi:,.2f}</text>'
               f'<text x="{pl-4}" y="{h-pb}" fill="#8a8f98" font-size="10" text-anchor="end">{lo:,.2f}</text>'
               f'{marks}<polyline points="{poly}" fill="none" stroke="#8ab4f8" stroke-width="1.6"/>{pos_lines}'
               f'<circle cx="{X(len(pts)-1):.1f}" cy="{Y(last_c):.1f}" r="2.5" fill="#e6e6e6"/>'
               f'<text x="{pl}" y="{h-4}" fill="#6b7280" font-size="9">{first_t.astimezone(et).strftime("%a %m-%d %H:%M")} ET</text>'
               f'<text x="{w-pr}" y="{h-4}" fill="#6b7280" font-size="9" text-anchor="end">{last_t.astimezone(et).strftime("%a %m-%d %H:%M")} ET</text></svg>')
        panels.append(f'<section class="card"><h2>{inst} &middot; 15-min closes &middot; last {last_c:,.2f}{day_chg}</h2>{svg}'
                      f'<div class="sub" style="margin:6px 0 0">delayed public continuous front-month proxy (same feed the ledgers trade); dashed = open paper positions</div></section>')
    return f'<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(420px,1fr))">{"".join(panels)}</div>'


def futures_cards(summary, category='current'):
    def tone(v):
        return 'pos' if v > 0 else 'neg' if v < 0 else 'flat'
    cards = []
    for key, c in summary['candidates'].items():
        if c.get('category', 'current') != category:
            continue
        positions = []
        for name, pos in c['positions'].items():
            q = pos['quantity']
            positions.append(f"{name}: {'flat' if not q else ('long' if q > 0 else 'short') + ' ' + str(abs(q))}"
                             + (f" ({_money(pos['unrealized'])})" if q else ''))
        trades = ''.join(f"<li>{t['exit_ts'][:16].replace('T', ' ')}Z {t['sleeve']} {'long' if t['side'] > 0 else 'short'} x{t['qty']} "
                         f"{t['entry_price']:,.2f} &rarr; {t['exit_price']:,.2f} <b class=\"{tone(t['net'])}\">{_money(t['net'])}</b> <small>{t['reason']}</small></li>"
                         for t in reversed(c.get('last_trades', [])))
        locks = {k: v for k, v in c.get('locks', {}).items() if v}
        warn = ''
        if c.get('funded_failed'):
            warn = '<div class="warn">FUNDED FLOOR BREACH in simulation</div>'
        elif locks:
            warn = f"<div class=\"warn\">risk lock: {', '.join(f'{k} {v}' for k, v in locks.items())}</div>"
        if c.get('divergences'):
            warn += f"<div class=\"warn\">{c['divergences']} ledger divergence(s) - see ledger.jsonl</div>"
        cards.append(f"""<section class="card"><h2>{c['label']}</h2>
<div class="big {tone(c['net'])}">{_money(c['net'])}</div>
<div class="sub">realized {_money(c['realized'])} &middot; open {_money(c['unrealized'])} &middot; v{c['version']}</div>
<dl><dt>Max DD</dt><dd>{_money(c['intrabar_drawdown'], False)} intrabar <small>({_money(c['closed_drawdown'], False)} closed)</small></dd>
<dt>$2k buffer</dt><dd>{_money(c['funded_buffer'], False)}</dd>
<dt>Positions</dt><dd><small>{'<br>'.join(positions)}</small></dd>
<dt>Closed trades</dt><dd>{c['trades']} ({c['wins']} wins) &middot; fees {_money(c['fees'], False)}</dd>
<dt>Bars through</dt><dd><small>{c['bars_through'].get('MES', '')[:16].replace('T', ' ')}Z</small></dd></dl>
<ul class="trades">{trades or '<li><small>no closed trades yet</small></li>'}</ul>{warn}</section>""")
    return cards


def family_grid(summary, category='current'):
    """Cards grouped by architecture family (status['family'] from the runner), each family with its own net subtotal (Nick, 2026-11-09)."""
    def tone(v):
        return 'pos' if v > 0 else 'neg' if v < 0 else 'flat'
    keys_in = [k for k, c in summary['candidates'].items() if c.get('category', 'current') == category]
    cards = dict(zip(keys_in, futures_cards(summary, category)))
    groups = {}
    for k in keys_in:
        groups.setdefault(summary['candidates'][k].get('family', 'Other'), []).append(k)
    out = []
    for fam in sorted(groups):
        keys = groups[fam]
        net = sum(summary['candidates'][k]['net'] for k in keys)
        out.append(f'<section class="family"><h3>{fam} <small>({len(keys)} ledger{"s" if len(keys) != 1 else ""})</small>'
                   f'<span class="famnet {tone(net)}">{_money(net)}</span></h3><div class="grid">{"".join(cards[k] for k in keys)}</div></section>')
    return ''.join(out)


def regime_line(summary):
    r = (summary or {}).get("regime") or {}
    if not r or r.get("error"):
        return ""
    col = "#ff5c5c" if r["slope"] < 0 else "#2ecc71"
    return (f'<div class="muted" style="margin-top:8px">Vol regime (prior close {r["as_of"]}): VIX {r["vix"]} / VIX3M {r["vix3m"]} &middot; '
            f'<b style="color:{col}">{r["state"]}</b> (slope {r["slope"]:+.1%}, VIX 1y pct {r["vix_rank_1y"]:.0%}) &middot; {r["note"]}</div>')


def account_block(path=None):
    """Topstep $50K Static Daily Payouts+ paper replay (scripts/paper_account_static_daily.py on the futures droplet; Claude 2026-11-10).
    Reads its own status file; any problem hides the section instead of breaking the page."""
    try:
        a = json.loads((Path(path) if path else ACCOUNT_STATUS).read_text())
        f, e = a['funded'], a['evaluation']
        def tone(v):
            return 'pos' if v > 0 else 'neg' if v < 0 else 'flat'
        def roll(x):
            r = x.get('rolling')
            if not r: return ''
            return (f'<dt>Rolling starts</dt><dd><small>{r["starts"]} started (one per weekday): {r["passed"]} passed, {r["failed"]} failed, '
                    f'{r["expired"]} expired, {r["open"]} still open</small></dd>')
        st = {'open': 'in progress', 'passed': 'PASSED', 'failed': 'FAILED', 'expired': 'expired (90 days)'}.get(e['status'], e['status'])
        ewarn = '<div class="warn">Evaluation failed in simulation</div>' if e['status'] == 'failed' else ''
        need = max(0.0, e['target'] - e['balance'])
        ecard = (f'<section class="card"><h2>Evaluation - $50K Static Combine ({e.get("name", "payout book at 3x")})</h2>'
                 f'<div class="big {tone(e["balance"])}">{_money(e["balance"])}</div>'
                 f'<div class="sub">{st}{" on " + e["on"] if e.get("on") else ""} &middot; target {_money(e["target"], False)} &middot; {e["days_left"]} days left (expires {e["expires"]})</div>'
                 f'<dl><dt>Still needed</dt><dd>{_money(need, False)}</dd><dt>Best day</dt><dd>{_money(e["best_day"])} <small>(55% rule raises the target above $4,000 if one day is too big)</small></dd>'
                 f'<dt>Rules</dt><dd><small>3x the book, max $900 risk per trade, $700 daily stop, floor -$2,000</small></dd>{roll(e)}</dl>{ewarn}</section>')
        c = a.get('evaluation_combined')
        ccard = ''
        if c:
            cst = {'open': 'in progress', 'passed': 'PASSED', 'failed': 'FAILED', 'expired': 'expired (90 days)'}.get(c['status'], c['status'])
            cwarn = '<div class="warn">Evaluation failed in simulation</div>' if c['status'] == 'failed' else ''
            ccard = (f'<section class="card" style="border-color:#1f4a6b"><h2>Evaluation challenger - {c.get("name", "combined rule")}</h2>'
                     f'<div class="big {tone(c["balance"])}">{_money(c["balance"])}</div>'
                     f'<div class="sub">{cst}{" on " + c["on"] if c.get("on") else ""} &middot; target {_money(c["target"], False)} &middot; {c["days_left"]} days left'
                     f'{" &middot; size now " + c["size_now"] if c.get("size_now") else ""}</div>'
                     f'<dl><dt>Still needed</dt><dd>{_money(max(0.0, c["target"] - c["balance"]), False)}</dd>'
                     f'<dt>Rules</dt><dd><small>{c.get("rule", "")}</small></dd>'
                     f'<dt>Codex sleeves</dt><dd><small>{c.get("extra_trades", 0)} paper trades, {c.get("extra_taken", 0)} taken after routing, '
                     f'{_money(c.get("extra_net_per_micro", 0.0))} per micro</small></dd>{roll(c)}</dl>'
                     f'<div class="note" style="margin-top:8px">{c.get("caution", "")}</div>{cwarn}</section>')
        pays = ''.join(f'<li>{p["date"]} <b class="pos">{_money(p["amount"])}</b></li>' for p in reversed(f['payouts'][-5:]))
        days = ''.join(f'<li>{d["date"]} <b class="{tone(d["pnl"])}">{_money(d["pnl"])}</b> &middot; balance {_money(d["balance"])} <small>{d.get("size", "")}</small></li>'
                       for d in reversed(f['days'][-5:]))
        fwarn = f'<div class="warn">ACCOUNT CLOSED in simulation on {f["closed_on"]}</div>' if f.get('closed_on') else ''
        fcard = (f'<section class="card"><h2>Funded - {f.get("name", "Static Daily Payouts+")} ({f.get("ladder", "1x / 2x from $4,000")}; '
                 f'withdraw above {_money(f.get("keep", 6000.0), False)}; size trimmed to $900 risk)</h2>'
                 f'<div class="big {tone(f["balance"])}">{_money(f["balance"])}</div>'
                 f'<div class="sub">size {f["size_stage"]} &middot; floor {_money(f["floor"])} &middot; {f["payouts_count"]} payouts &middot; withdrawn {_money(f["withdrawn"], False)}</div>'
                 f'<dl><dt>Next payout</dt><dd>{"closed" if f.get("closed_on") else "needs " + _money(f["next_payout_needs"], False) + " more"}</dd>'
                 f'<dt>Payouts</dt><dd><ul class="trades">{pays or "<li><small>none yet</small></li>"}</ul></dd></dl>'
                 f'<ul class="trades">{days or "<li><small>no trading days yet</small></li>"}</ul>{fwarn}</section>')
        g = a.get('aegis')
        acard = ''
        if g:
            gpays = ''.join(f'<li>{p["date"]} <b class="pos">{_money(p["amount"])}</b></li>' for p in reversed(g['payouts'][-5:]))
            gwarn = f'<div class="warn">ACCOUNT CLOSED in simulation on {g["closed_on"]}</div>' if g.get('closed_on') else ''
            acard = (f'<section class="card" style="border-color:#5a4a1a"><h2>Comparison - {g.get("name", "Aegis Apex 4X")} <small>(not adopted)</small></h2>'
                     f'<div class="big {tone(g["balance"])}">{_money(g["balance"])}</div>'
                     f'<div class="sub">size {g["size_stage"]} &middot; floor {_money(g["floor"])} &middot; {g["payouts_count"]} payouts &middot; withdrawn {_money(g["withdrawn"], False)}</div>'
                     f'<dl><dt>Rules</dt><dd><small>{g.get("ladder", "")}; withdraw above {_money(g.get("keep", 7500), False)}; overnight exit {g.get("overnight_exit", "")} '
                     f'({g.get("overnight_trades", 0)} nights so far); size trimmed to $900 risk</small></dd>'
                     f'<dt>Next payout</dt><dd>{"closed" if g.get("closed_on") else "needs " + _money(g["next_payout_needs"], False) + " more"}</dd>'
                     f'<dt>Payouts</dt><dd><ul class="trades">{gpays or "<li><small>none yet</small></li>"}</ul></dd></dl>'
                     f'<div class="note" style="margin-top:8px">{g.get("caution", "")}</div>{gwarn}</section>')
        rows = ''.join(f'<li><b>{x["name"]}</b> <small>{x["instrument"]} {x["bar_minutes"]}-min bars</small> &middot; {x["trades"]} trade{"" if x["trades"] == 1 else "s"} '
                       f'<b class="{tone(x["net_1x"])}">{_money(x["net_1x"])}</b></li>' for x in a.get('strategies', []))
        scard = (f'<section class="card"><h2>Strategies in this account ({a.get("book", "D+ v5.2 payout build + overnight leg")})</h2>'
                 f'<ul class="trades">{rows or "<li><small>strategy list not available yet</small></li>"}</ul>'
                 f'<div class="sub" style="margin-top:8px">paper trades at 1 micro each since {a["paper_start"]}; the cards above size them up. The two Codex sleeves count only in the evaluation challenger.</div></section>')
        return (f'<h1 style="margin-top:22px">Topstep account - paper replay</h1>'
                f'<div class="muted">{a.get("book", "v5.2 payout build + overnight leg")} ledgers replayed through the Static Daily Payouts+ rules &middot; paper start {a["paper_start"]} '
                f'&middot; updated {a["updated"][:16].replace("T", " ")}Z &middot; simulated, nothing routed</div><div class="grid">{ecard}{ccard}{fcard}{acard}{scard}</div>')
    except Exception:  # noqa: BLE001
        return ''


def render_futures(summary):
    def tone(v):
        return 'pos' if v > 0 else 'neg' if v < 0 else 'flat'
    if not summary:
        body = '<p class="note">No futures paper summary yet - the ensemble paper job has not produced a dashboard file.</p>'
        updated = ''
    else:
        cards = futures_cards(summary); _fut = False
        body = (regime_line(summary) + account_block() + futures_price_charts(summary) + f'{family_grid(summary, 'future' if _fut else 'current')}'
                f'<section class="total"><h2>All {len(cards)} candidates combined</h2><div class="big {tone(summary["total_net"])}">{_money(summary["total_net"])}</div>'
                f'<div class="sub">paper start {summary["start"][:10]} &middot; {summary["source"]}</div></section>' + future_block(summary))
        updated = f"Updated {summary['updated'][:16].replace('T', ' ')}Z &middot; "
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="120"><title>Futures paper</title><meta name="theme-color" content="#0f1115"><style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0f1115;color:#e6e6e6;margin:0;padding:16px}}
h1{{font-size:20px;margin:0 0 4px}} .muted{{color:#8a8f98;font-size:13px}} .grid{{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));margin-top:14px}}
.card{{background:#171a21;border:1px solid #262b35;border-radius:12px;padding:16px}} h2{{font-size:15px;margin:0 0 8px;color:#b8bec9}}
.big{{font-size:30px;font-weight:700}} .pos{{color:#2ecc71}} .neg{{color:#ff5c5c}} .flat{{color:#e6e6e6}} .sub{{color:#8a8f98;font-size:13px;margin-bottom:10px}}
dl{{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;margin:0;font-size:14px}} dt{{color:#8a8f98}} dd{{margin:0}} small{{color:#8a8f98}}
ul.trades{{list-style:none;padding:0;margin:10px 0 0;font-size:12px;color:#b8bec9}} ul.trades li{{padding:3px 0;border-top:1px solid #262b35}}
.family{{margin-top:18px;border-top:1px solid #262b35;padding-top:8px}} .family h3{{display:flex;justify-content:space-between;align-items:baseline;font-size:15px;color:#b8bec9;margin:0 0 6px}} .famnet{{font-size:20px;font-weight:700}}
.total{{background:#1d2230;border-radius:12px;padding:16px;margin-top:14px}} .warn{{color:#ff5c5c;font-weight:600;margin-top:8px}} .note{{color:#f1c40f;font-size:13px}}
</style></head><body><h1>Futures paper - MES/MNQ ensembles</h1>
<div class="muted">{updated}simulated fills from the research engine on 15-min bars (public delayed continuous front-month proxy) &middot; one $50k paper account per candidate &middot; no orders are routed anywhere &middot; <a href="/" style="color:#8ab4f8">crypto accounts</a> &middot; <a href="/futures.json" style="color:#8ab4f8">JSON</a></div>
{body}</body></html>"""


def future_block(summary):
    def tone(v):
        return 'pos' if v > 0 else 'neg' if v < 0 else 'flat'
    cards = futures_cards(summary, 'future'); _fut = True
    if not cards:
        return ''
    net = summary.get('future_net', 0.0)
    return (f'<h1 style="margin-top:26px">Future strategies <small style="font-weight:400;color:#8a8f98">(need banked cushion first)</small></h1>'
            f'<div class="muted">{FUTURE_NOTE}</div>{family_grid(summary, 'future' if _fut else 'current')}'
            f'<section class="total"><h2>Future strategies combined ({len(cards)}) - not in the total above</h2><div class="big {tone(net)}">{_money(net)}</div></section>')


def futures_section(summary):
    if not summary:
        return '<h1 style="margin-top:22px">Futures paper - MES/MNQ</h1><p class="note">No futures summary yet.</p>'
    def tone(v):
        return 'pos' if v > 0 else 'neg' if v < 0 else 'flat'
    cards = futures_cards(summary); _fut = False
    return (f'<h1 style="margin-top:22px">Futures paper - MES/MNQ ensembles</h1>'
            f'<div class="muted">updated {summary["updated"][:16].replace("T", " ")}Z &middot; research engine on 15-min bars, delayed public proxy feed &middot; $50k paper account per candidate &middot; <a href="/futures" style="color:#8ab4f8">details</a></div>'
            + regime_line(summary) + account_block() + futures_price_charts(summary) + f'{family_grid(summary, 'future' if _fut else 'current')}'
            f'<section class="total"><h2>All {len(cards)} futures candidates combined</h2><div class="big {tone(summary["total_net"])}">{_money(summary["total_net"])}</div>'
            f'<div class="sub">paper start {summary["start"][:10]}</div></section>' + future_block(summary))


def render_dashboard(payload):
    def tone(v):
        return 'pos' if v > 0 else 'neg' if v < 0 else 'flat'
    cards = []
    for r in payload['accounts']:
        pos = 'flat' if not r['position'] else f"{'long' if r['position'] > 0 else 'short'} {abs(r['position']):g} @ {r['average_price']:,.2f}"
        last = r['last_fill']
        last_text = f"{last['time'][:16].replace('T', ' ')} UTC {last['action']} {last['contracts']:g} @ {last['price']:,.2f} ({last['order_id']})" if last else 'no fills yet'
        mark = f"mark {r['mark']:,.2f}" if r['mark'] else 'mark unavailable'
        b = r.get('bracket')
        rules = STRATEGY_RULES[r['key']]
        target_rule = f"{rules['reward_r']:g}R" if rules['reward_r'] else 'none (trail only)'
        if b:
            target_row = (f"<dt>Target</dt><dd>{b['target']:,.2f} <small>({_money(b['target_pnl'])}, {rules['reward_r']:g}R)</small></dd>" if b['target']
                          else "<dt>Target</dt><dd><small>none - exits on the trailing stop</small></dd>")
            levels = (f"<dt>Stop</dt><dd>{b['stop']:,.2f} <small>({_money(b['stop_pnl'])}{', trailing' if b['trailing'] else ''})</small></dd>"
                      f"{target_row}<dt>Progress</dt><dd>{b['r_now']:+.2f}R <small>{'of '+target_rule+' ' if b['target'] else ''}&middot; est. from {b['method']}</small></dd>")
        else:
            levels = f"<dt>Rules</dt><dd><small>stop {rules['stop_atr']:g} ATR({rules['bar']}) &middot; target {target_rule} &middot; trail {rules['trail_atr']:g} ATR &middot; risk ${ACCOUNTS[r['key']]['risk_usd']:g}</small></dd>"
        cards.append(f"""<section class="card {'' if r['alive'] else 'dead'}"><h2>{r['name']}</h2>
<div class="big {tone(r['net_pnl']+r['open_pnl'])}">{_money(r['net_pnl']+r['open_pnl'])}</div>
<div class="sub">realized {_money(r['net_pnl'])} &middot; open {_money(r['open_pnl'])}</div>
{chart_svg(r.get('candles') or [], b)}<div class="caption">last {len(r.get('candles') or [])} x {rules['bar']} candles, OKX {r['key'][:3]} perp{' &middot; <span class="e">entry</span> <span class="s">stop</span> <span class="t">target</span>' if b else ''}</div>
<dl><dt>Balance</dt><dd>{_money(r['balance'], False)}</dd><dt>Floor buffer</dt><dd>{_money(r['floor_buffer'], False)}</dd>
<dt>Position</dt><dd>{pos}<br><small>{mark}</small></dd>{levels}<dt>Closed trades</dt><dd>{r['closed_trades']} ({r['wins']} wins)</dd>
<dt>Fees</dt><dd>{_money(r['fees'], False)}</dd><dt>Last fill</dt><dd><small>{last_text}</small></dd></dl>
{'' if r['alive'] else '<div class="warn">RULE BREACH - account would be closed</div>'}</section>""")
    t = payload['total']
    note = '' if payload['marks'] else '<p class="note">Live marks unavailable right now; open P&amp;L shows 0 until the price feed answers.</p>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60"><title>Paper P&amp;L</title><link rel="manifest" href="/manifest.webmanifest"><meta name="theme-color" content="#0f1115"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><meta name="apple-mobile-web-app-title" content="Paper P&amp;L"><link rel="apple-touch-icon" href="/icon-180.png"><link rel="icon" href="/icon-180.png"><style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0f1115;color:#e6e6e6;margin:0;padding:16px}}
h1{{font-size:20px;margin:0 0 4px}} .muted{{color:#8a8f98;font-size:13px}} .grid{{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));margin-top:14px}}
.card{{background:#171a21;border:1px solid #262b35;border-radius:12px;padding:16px}} .card.dead{{border-color:#c0392b}} h2{{font-size:15px;margin:0 0 8px;color:#b8bec9}}
.big{{font-size:30px;font-weight:700}} .pos{{color:#2ecc71}} .neg{{color:#ff5c5c}} .flat{{color:#e6e6e6}} .sub{{color:#8a8f98;font-size:13px;margin-bottom:10px}}
dl{{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;margin:0;font-size:14px}} dt{{color:#8a8f98}} dd{{margin:0}} small{{color:#8a8f98}}
.chart{{width:100%;height:130px;display:block;background:#0f1115;border-radius:8px;margin:2px 0 2px}} .caption{{color:#5f6672;font-size:11px;margin-bottom:10px}} .nochart{{color:#5f6672;font-size:12px;padding:12px 0}} .e{{color:#b8bec9}} .s{{color:#ff5c5c}} .t{{color:#2ecc71}}
.total{{background:#1d2230;border-radius:12px;padding:16px;margin-top:14px}} .warn{{color:#ff5c5c;font-weight:600;margin-top:8px}} .note{{color:#f1c40f;font-size:13px}}
ul.trades{{list-style:none;padding:0;margin:10px 0 0;font-size:12px;color:#b8bec9}} ul.trades li{{padding:3px 0;border-top:1px solid #262b35}}
</style></head><body><h1>Paper accounts - Breakout 50k rules</h1>
<div class="muted">Updated {payload['generated_at'].replace('T', ' ')} &middot; auto-refresh 60 s &middot; realized P&amp;L from webhook fills, open P&amp;L marked to the OKX perp (CoinGecko spot fallback) &middot; stop/target reconstructed from the strategy rules</div>
<div class="grid">{''.join(cards)}</div>
<section class="total"><h2>All {len(payload['accounts'])} accounts combined</h2><div class="big {tone(t['total_pnl'])}">{_money(t['total_pnl'])}</div>
<div class="sub">realized {_money(t['net_pnl'])} &middot; open {_money(t['open_pnl'])} &middot; {t['closed_trades']} closed trades ({t['wins']} wins) &middot; fees {_money(t['fees'], False)}</div></section>
{futures_section(futures_summary())}
{note}<p class="muted">Futures paper: <a href="/futures" style="color:#8ab4f8">/futures</a> &middot; Raw JSON: <a href="/status" style="color:#8ab4f8">/status</a> &middot; <a href="/dashboard.json" style="color:#8ab4f8">/dashboard.json</a></p><script>if('serviceWorker' in navigator){{navigator.serviceWorker.register('/sw.js').catch(()=>{{}})}}</script></body></html>"""


def make_handler(ledgers, secret, notify_url):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, body, content_type):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html):
            self._send_bytes(html.encode(), 'text/html; charset=utf-8')

        def do_GET(self):
            if self.path.startswith('/status'):
                self._send(200, status(ledgers))
            elif self.path.startswith('/dashboard.json'):
                self._send(200, dashboard_payload(ledgers, mark_prices(), all_candles(), all_fine(ledgers)))
            elif self.path in ('/', '/dashboard', '/index.html'):
                self._send_html(render_dashboard(dashboard_payload(ledgers, mark_prices(), all_candles(), all_fine(ledgers))))
            elif self.path.startswith('/futures.json'):
                self._send(200, futures_summary() or dict(error='no futures summary yet'))
            elif self.path.startswith('/futures'):
                self._send_html(render_futures(futures_summary()))
            elif self.path.startswith('/manifest.webmanifest'):
                self._send_bytes(json.dumps(MANIFEST).encode(), 'application/manifest+json')
            elif self.path.startswith('/sw.js'):
                self._send_bytes(SERVICE_WORKER.encode(), 'application/javascript')
            elif self.path.startswith('/icon-'):
                size = 512 if '512' in self.path else 180
                self._send_bytes(base64.b64decode(ICON_PNG[size]), 'image/png')
            elif self.path.startswith('/health'):
                self._send(200, dict(ok=True))
            else:
                self._send(404, dict(error='not found'))

        def do_POST(self):
            if not self.path.startswith('/tradingview'):
                return self._send(404, dict(error='not found'))
            length = int(self.headers.get('Content-Length', '0') or 0)
            body = self.rfile.read(min(length, 65536))
            try:
                fill = parse_alert(body, secret)
                key = route(fill['ticker'], fill['comment'])
            except RejectedAlert as error:
                print('rejected alert:', error, flush=True)
                return self._send(400, dict(error=str(error)))
            ledger, name = ledgers[key], ACCOUNTS[key]['name']
            closed = ledger.record(fill)
            print('fill', name, fill['time'], fill['action'], fill['contracts'], fill['price'], 'balance', round(ledger.state['balance'], 2), flush=True)
            threading.Thread(target=notify, args=(notify_url, fill, closed, ledger.state, name), daemon=True).start()
            self._send(200, dict(ok=True, account=name, balance=ledger.state['balance'], closed=closed))

        def log_message(self, *args):
            pass
    return Handler


def load_secret(directory=DIRECTORY):
    env = os.environ.get('PAPER_WEBHOOK_SECRET')
    if env:
        return env
    path = directory/'secret.txt'
    directory.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(24))
    return path.read_text().strip()


def serve(port, directory=DIRECTORY, notify_url=None):
    ledgers = open_ledgers(directory)
    secret = load_secret(directory)
    server = ThreadingHTTPServer(('0.0.0.0', port), make_handler(ledgers, secret, notify_url or os.environ.get('PAPER_NOTIFY_URL')))
    print(f'paper webhook listening on port {port}; secret file {directory/"secret.txt"}; status at /status', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=int(os.environ.get('PAPER_WEBHOOK_PORT', '8787')))
    parser.add_argument('--status', action='store_true', help='print the ledger summary and exit')
    args = parser.parse_args()
    if args.status:
        print(json.dumps(status(open_ledgers()), indent=2))
    else:
        serve(args.port)

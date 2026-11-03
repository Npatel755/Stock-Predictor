"""TradingView strategy-alert receiver with a Breakout-ruled paper ledger.

TradingView cannot auto-trade its own Paper Trading account and Breakout has
no API, so this process is the paper account: the ETH v1.11 Pine strategy
fires an alert on every simulated order fill, TradingView POSTs it here, and
the fill is appended to an immutable JSONL ledger and scored against the
Breakout $50k 1-Step limits (static $47,000 floor, 3% daily loss measured
from the balance at 00:30 UTC). Nothing here routes orders anywhere.

Alert message to paste into TradingView (valid JSON; placeholders are
expanded by TradingView):

{"secret":"YOUR_SECRET","ticker":"{{ticker}}","action":"{{strategy.order.action}}",
 "contracts":"{{strategy.order.contracts}}","price":"{{strategy.order.price}}",
 "position":"{{strategy.position_size}}","id":"{{strategy.order.id}}",
 "comment":"{{strategy.order.comment}}","time":"{{timenow}}"}
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import secrets
import threading
import urllib.request

from .paths import ROOT

DIRECTORY = ROOT/'artifacts/paper_trading'
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
                fills=state['fills'], duplicates=state['duplicates'], breaches=state['breaches'], last_fill=state['last_fill'],
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


def notify(url, fill, closed, state):
    if not url:
        return
    side = fill['action'].upper()
    text = f"ETH v1.11 paper {side} {fill['contracts']} @ {fill['price']:.2f} ({fill['comment'] or fill['order_id']})"
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


def make_handler(ledger, secret, notify_url):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith('/status'):
                self._send(200, summary(ledger.state))
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
            except RejectedAlert as error:
                print('rejected alert:', error, flush=True)
                return self._send(400, dict(error=str(error)))
            closed = ledger.record(fill)
            print('fill', fill['time'], fill['action'], fill['contracts'], fill['price'], 'balance', round(ledger.state['balance'], 2), flush=True)
            threading.Thread(target=notify, args=(notify_url, fill, closed, ledger.state), daemon=True).start()
            self._send(200, dict(ok=True, balance=ledger.state['balance'], closed=closed))

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
    ledger = Ledger(directory)
    secret = load_secret(directory)
    server = ThreadingHTTPServer(('0.0.0.0', port), make_handler(ledger, secret, notify_url or os.environ.get('PAPER_NOTIFY_URL')))
    print(f'paper webhook listening on port {port}; secret file {directory/"secret.txt"}; status at /status', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=int(os.environ.get('PAPER_WEBHOOK_PORT', '8787')))
    parser.add_argument('--status', action='store_true', help='print the ledger summary and exit')
    args = parser.parse_args()
    if args.status:
        print(json.dumps(summary(Ledger().state), indent=2))
    else:
        serve(args.port)

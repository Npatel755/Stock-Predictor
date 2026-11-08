"""Paper order matching. Intrabar sequencing is conservative and explicit."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
import math
import re
import numpy as np
import pandas as pd
from .contracts import SPECS
from .config import Costs


class EventType(StrEnum):
    MARKET = "market_data"
    SIGNAL = "signal"
    SUBMIT = "order_submission"
    ACCEPT = "order_acceptance"
    PARTIAL = "partial_fill"
    FILL = "full_fill"
    CANCEL = "order_cancellation"
    STOP = "stop_execution"
    POSITION = "position_update"
    RISK = "risk_violation"
    SESSION = "session_close"
    LOCK = "account_lockout"
    REJECT = "order_rejection"


class Action(StrEnum):
    HOLD = "HOLD"
    LONG = "LONG"
    SHORT = "SHORT"
    EXIT = "EXIT"
    REDUCE_POSITION = "REDUCE_POSITION"


@dataclass
class Order:
    order_id: str
    instrument: str
    contract: str
    side: int
    quantity: int
    submitted_at: pd.Timestamp
    kind: str = "market"
    limit_price: float | None = None
    stop_price: float | None = None
    accepted_at: pd.Timestamp | None = None
    filled: int = 0
    triggered: bool = False
    status: str = "new"
    triggered_at: pd.Timestamp | None = None

    def __post_init__(self):
        if self.side not in (-1, 1) or self.quantity < 1 or int(self.quantity) != self.quantity:
            raise ValueError("Integer contracts and directional side required")
        if self.instrument not in SPECS or not self.contract.startswith(self.instrument):
            raise ValueError("Unsupported contract")
        if self.kind not in ("market", "limit", "stop_market", "stop_limit"):
            raise ValueError("Unknown order type")
        if self.kind in ("limit", "stop_limit") and (self.limit_price is None or self.limit_price <= 0 or not math.isfinite(self.limit_price)):
            raise ValueError("Limit price required")
        if self.kind.startswith("stop") and (self.stop_price is None or self.stop_price <= 0 or not math.isfinite(self.stop_price)):
            raise ValueError("Stop price required")
        self.submitted_at = pd.Timestamp(self.submitted_at)
        if self.submitted_at.tzinfo is None:
            raise ValueError("Aware order timestamp required")
        tick = SPECS[self.instrument].tick
        for price in (self.limit_price, self.stop_price):
            if price is not None and not np.isclose(price/tick, round(price/tick), rtol=0, atol=1e-6):
                raise ValueError("Off-tick order price")


class BrokerAdapter(ABC):
    @abstractmethod
    def connect(self): ...
    @abstractmethod
    def submit_order(self, order): ...
    @abstractmethod
    def cancel_order(self, order_id): ...
    @abstractmethod
    def get_positions(self): ...
    @abstractmethod
    def get_account_state(self): ...


class PaperBroker(BrokerAdapter):
    def __init__(self, costs: Costs | None = None):
        self.costs = costs or Costs()
        self.connected = False
        self.orders = {}
        self.positions = {}
        self.events = []
        self.realized = self.fees = 0.0
        self.sequence_high_water = {}

    def emit(self, kind, timestamp, **values):
        self.events.append(dict(event=str(kind), timestamp=str(timestamp), **values))

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False
        for oid in list(self.orders):
            self.cancel_order(oid)

    def submit_order(self, order):
        if order.order_id in self.orders:
            raise ValueError("Duplicate order id")
        if not self.connected:
            raise ConnectionError("Broker disconnected")
        sequence = re.fullmatch(r"(entry|exit|sim)-(\d{8,})", order.order_id)
        if sequence:
            prefix, number = sequence[1], int(sequence[2])
            if number <= self.sequence_high_water.get(prefix, -1):
                raise ValueError("Duplicate or retired order sequence")
            self.sequence_high_water[prefix] = number
        self.orders[order.order_id] = order
        order.status = "accepted"
        order.accepted_at = order.submitted_at
        self.emit(EventType.SUBMIT, order.submitted_at, order_id=order.order_id)
        self.emit(EventType.ACCEPT, order.accepted_at, order_id=order.order_id)
        return order.order_id

    def cancel_order(self, order_id):
        order = self.orders[order_id]
        if order.status in ("accepted", "partial"):
            order.status = "cancelled"
            self.emit(EventType.CANCEL, order.submitted_at, order_id=order_id)

    def market_price(self, reference, side, instrument, bid=None, ask=None):
        spec = SPECS[instrument]
        observed = bid is not None and ask is not None and np.isfinite(bid) and np.isfinite(ask) and 0 < bid <= ask
        if observed:
            reference = ask if side > 0 else bid
        points = spec.tick*(self.costs.slippage_ticks+(0 if observed else self.costs.spread_ticks/2)+self.costs.impact_ticks)
        return spec.round_price(reference+side*points, side)

    def fill(self, order, price, quantity, timestamp):
        if not self.connected or order.status not in ("accepted", "partial"):
            raise RuntimeError("Only connected accepted orders may fill")
        if pd.Timestamp(timestamp) < order.accepted_at:
            raise ValueError("Fill predates exchange acceptance")
        if quantity < 1 or quantity > order.quantity-order.filled:
            raise ValueError("Invalid fill quantity")
        order.filled += quantity
        order.status = "filled" if order.filled == order.quantity else "partial"
        fee = quantity*self.costs.fee
        self.fees += fee
        # Weighted average cost and realized economics for independent broker users.
        oldq, avg = self.positions.get(order.contract, (0, 0.0))
        delta = order.side*quantity
        if oldq == 0 or np.sign(oldq) == np.sign(delta):
            newq = oldq+delta
            newavg = (abs(oldq)*avg+quantity*price)/abs(newq)
        else:
            closed = min(abs(oldq), quantity)
            self.realized += closed*np.sign(oldq)*(price-avg)*SPECS[order.instrument].multiplier
            newq = oldq+delta
            newavg = price if newq and np.sign(newq) != np.sign(oldq) else (avg if newq else 0.0)
        self.positions[order.contract] = (newq, newavg)
        self.emit(EventType.FILL if order.status == "filled" else EventType.PARTIAL, timestamp,
                  order_id=order.order_id, quantity=quantity, price=price, fee=fee,
                  signal_timestamp=str(order.submitted_at), acceptance_timestamp=str(order.accepted_at))
        return dict(quantity=quantity, price=price, fee=fee)

    def match(self, order, bar, previous_volume, participation=0.01):
        if not self.connected:
            raise ConnectionError("Disconnected matcher")
        if order.status not in ("accepted", "partial"):
            return None
        timestamp = pd.Timestamp(bar.timestamp_utc)
        if timestamp < order.submitted_at or bar.contract != order.contract:
            return None
        capacity = int(max(0, previous_volume)*participation)
        qty = min(order.quantity-order.filled, capacity)
        if qty < 1:
            return None
        spec = SPECS[order.instrument]
        reference = bar.open
        if order.kind.startswith("stop"):
            triggered = bar.high >= order.stop_price if order.side > 0 else bar.low <= order.stop_price
            if not order.triggered and not triggered:
                return None
            if not order.triggered:
                order.triggered = True
                order.triggered_at = timestamp
                # Stop-limit: defer all fills to a later candle because trigger and
                # limit touch ordering is unavailable. No optimistic same-bar fills.
                if order.kind == "stop_limit":
                    return None
            elif order.kind == "stop_limit" and timestamp <= order.triggered_at:
                return None
            reference = max(bar.open, order.stop_price) if order.side > 0 else min(bar.open, order.stop_price)
        if order.kind in ("limit", "stop_limit"):
            # Strict trade-through by one tick, never fill a mere touch.
            hit = bar.low <= order.limit_price-spec.tick if order.side > 0 else bar.high >= order.limit_price+spec.tick
            if not hit:
                return None
            price = order.limit_price
        else:
            quote = {}
            if order.kind == "market":
                quote = dict(bid=getattr(bar, "bid", None), ask=getattr(bar, "ask", None))
            price = self.market_price(reference, order.side, order.instrument, **quote)
        return self.fill(order, price, qty, timestamp)

    def get_positions(self):
        return {c: dict(quantity=q, average_price=p) for c, (q, p) in self.positions.items() if q}

    def get_account_state(self):
        return dict(mode="paper", connected=self.connected, realized_gross=self.realized,
                    fees=self.fees, realized_net=self.realized-self.fees)

    def reconcile(self, expected):
        actual = {c: v["quantity"] for c, v in self.get_positions().items()}
        if actual != expected:
            self.disconnect()
            raise RuntimeError("Unexpected position; paper broker disconnected")


def live_adapter(*args, **kwargs):
    raise PermissionError("Live trading is not implemented or activatable by configuration")

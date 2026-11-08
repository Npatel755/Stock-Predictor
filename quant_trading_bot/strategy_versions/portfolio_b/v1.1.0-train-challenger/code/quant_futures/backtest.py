"""One sequential simulator shared by historical replay and paper bar streaming."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .config import ResearchConfig
from .contracts import SPECS
from .data import canonical, validate
from .execution import PaperBroker, Order, EventType, Action
from .risk import RiskManager, fixed_dollar_size


@dataclass
class Position:
    side: int
    quantity: int
    entry: float
    stop: float
    target: float
    entry_index: int
    entry_time: pd.Timestamp
    entry_fee: float
    contract: str


class Simulator:
    def __init__(self, config=None, account=None):
        self.cfg = config or ResearchConfig()
        self.spec = SPECS[self.cfg.instrument]
        self.broker = PaperBroker(self.cfg.costs)
        self.broker.connect()
        self.risk = RiskManager(self.cfg.risk, self.cfg.initial_balance)
        self.account = account
        self.cash = self.cfg.initial_balance
        self.position = None
        self.pending = None
        self.previous = None
        self.index = -1
        self.trades, self.curve = [], []
        self.rng = np.random.default_rng(self.cfg.seed)
        self.external_risk = False
        self.portfolio_context = dict(open_risk=0, correlated_contracts=0)
        self.triggered_stop = None
        self.active_quote = None
        self.no_entry = False
        self.order_sequence = 0

    def next_order_id(self, prefix):
        self.order_sequence += 1
        return f"{prefix}-{self.order_sequence:08d}"

    def _order(self, side, quantity, timestamp):
        oid = self.next_order_id("sim")
        return Order(oid, self.cfg.instrument, self.previous.contract if self.previous is not None else "", side, quantity, timestamp)

    def _close(self, reference, timestamp, reason, limit=False, quantity=None):
        p = self.position
        q = p.quantity if quantity is None else min(p.quantity, int(quantity))
        if q < 1:
            raise ValueError("Positive exit quantity required")
        quote = {}
        if self.cfg.execution.use_observed_quotes and self.active_quote is not None and reason in ("signal_exit", "reduce_position", "session_close", "time_exit", "delayed_stop", "roll_exit", "gap_recovery"):
            quote = dict(bid=getattr(self.active_quote, "bid", None), ask=getattr(self.active_quote, "ask", None))
        price = self.spec.round_price(reference) if limit else self.broker.market_price(reference, -p.side, self.cfg.instrument, **quote)
        order = Order(self.next_order_id("exit"), self.cfg.instrument, p.contract, -p.side, q, timestamp)
        self.broker.submit_order(order)
        self.risk.order_times.append(timestamp)  # Protective exits bypass the rate gate but count toward later entries.
        fill = self.broker.fill(order, price, q, timestamp)
        gross = p.side*q*(price-p.entry)*self.spec.multiplier
        self.cash += gross-fill["fee"]
        entry_fee = p.entry_fee*q/p.quantity
        net = gross-entry_fee-fill["fee"]
        self.trades.append(dict(trade_id=order.order_id, entry_time=str(p.entry_time), exit_time=str(timestamp), contract=p.contract,
            side=p.side, quantity=q, entry_price=p.entry, exit_price=price, gross_pnl=gross,
            fees=entry_fee+fill["fee"], net_pnl=net, reason=reason, holding_bars=self.index-p.entry_index))
        self.risk.trade_closed(net)
        p.entry_fee -= entry_fee
        p.quantity -= q
        if not p.quantity:
            self.position = None
        self.triggered_stop = None
        self.broker.emit(EventType.POSITION, timestamp, quantity=0 if self.position is None else p.side*p.quantity)

    def queue_decision(self, signal):
        if signal is None or signal == Action.HOLD or self.previous is None:
            return
        if isinstance(signal, str):
            signal = Action(signal)
        if signal == Action.REDUCE_POSITION:
            if not self.position:
                return
            desired = signal
        else:
            desired = {Action.LONG: 1, Action.SHORT: -1, Action.EXIT: 0}.get(signal, signal)
            if desired not in (-1, 0, 1):
                raise ValueError("Unknown trading action")
        if self.risk.killed or self.risk.day_locked or self.no_entry:
            return
        if self.pending is None or signal == Action.EXIT:
            if (self.position.side if self.position else 0) != desired:
                decision = self.previous.timestamp_utc+pd.Timedelta(minutes=self.cfg.timeframe_minutes)
                self.pending = (self.index+self.cfg.execution.delay_bars, desired, decision, self.previous.contract)

    def roll_to(self, old_contract_quote, new_contract_quote):
        if old_contract_quote.timestamp_utc != new_contract_quote.timestamp_utc:
            raise ValueError("Roll requires simultaneous raw contract quotes")
        if old_contract_quote.instrument != new_contract_quote.instrument or new_contract_quote.instrument != self.cfg.instrument:
            raise ValueError("Roll instrument mismatch")
        if self.position:
            if self.position.contract != old_contract_quote.contract:
                raise ValueError("Old roll quote does not match the open position")
            self.active_quote = old_contract_quote
            self._close(old_contract_quote.open, old_contract_quote.timestamp_utc, "roll_exit")
        self.pending = None
        self.broker.emit(EventType.CANCEL, new_contract_quote.timestamp_utc, reason="contract_roll", old_contract=old_contract_quote.contract, new_contract=new_contract_quote.contract)

    def step(self, bar, signal=0):
        self.index += 1
        timestamp = pd.Timestamp(bar.timestamp_utc)
        if bar.instrument != self.cfg.instrument:
            raise ValueError("One instrument per simulator; use portfolio guard for multiple sleeves")
        if signal is not None and not isinstance(signal, (Action, str)) and (signal not in (-1, 0, 1) or not np.isfinite(signal)):
            raise ValueError("Signal must be desired direction -1, 0, 1")
        self.active_quote = bar
        if self.previous is not None:
            if timestamp <= self.previous.timestamp_utc:
                self.risk.kill("duplicate_or_out_of_order_bar")
                raise ValueError("Chronological unique bars required")
            gap = timestamp-self.previous.timestamp_utc > pd.Timedelta(minutes=max(self.cfg.timeframe_minutes, self.cfg.execution.max_gap_minutes))
            roll = bar.contract != self.previous.contract
            if roll and self.position:
                self.risk.kill("unreconciled_roll")
                raise RuntimeError("Open raw contract changed without an old-contract liquidation quote")
            if gap or roll:
                self.pending = None
                if gap and self.position:
                    self._close(bar.open, timestamp, "gap_recovery")
                    self.risk.kill("market_data_gap")
        if not self.external_risk:
            self.risk.begin_session(bar.session_id, self.cash)
        self.broker.emit(EventType.MARKET, timestamp, contract=bar.contract)
        local = timestamp.tz_convert("America/New_York")
        minute = local.hour*60+local.minute
        no_entry = ((self.cfg.execution.session_flat_minute_et <= minute < 1080) or local.weekday() == 5 or
                    (local.weekday() == 6 and minute < 1080) or (local.weekday() == 4 and minute >= self.cfg.execution.session_flat_minute_et))
        self.no_entry = no_entry
        # Scheduled/time exits are known at the open. Book them before inspecting
        # this bar's high/low; an intrabar target cannot precede that open exit.
        if self.position and (no_entry or self.index-self.position.entry_index >= self.cfg.execution.max_hold_bars):
            self._close(bar.open, timestamp, "session_close" if no_entry else "time_exit")
            self.pending = None
            if no_entry:
                self.broker.emit(EventType.SESSION, timestamp)
        if self.triggered_stop and self.position and self.index >= self.triggered_stop:
            self._close(bar.open, timestamp, "delayed_stop")
            self.pending = None
        if self.pending and self.pending[0] <= self.index:
            _, desired, decision_time, contract = self.pending
            self.pending = None
            if contract == bar.contract:
                if desired == Action.REDUCE_POSITION:
                    if self.position:
                        self._close(bar.open, timestamp, "reduce_position", quantity=max(1, self.position.quantity//2))
                    desired = self.position.side if self.position else 0
                if self.position and desired != self.position.side:
                    self._close(bar.open, timestamp, "signal_exit")
                if desired and not self.position and not no_entry and self.rng.random() >= self.cfg.execution.missed_entry_fraction:
                    stop_points = self.cfg.execution.stop_ticks*self.spec.tick
                    adverse = self.spec.tick*(self.cfg.costs.slippage_ticks+self.cfg.costs.spread_ticks/2+self.cfg.costs.impact_ticks)
                    risk_per = stop_points*self.spec.multiplier + 2*self.cfg.costs.fee + (2*adverse+self.spec.tick)*self.spec.multiplier
                    quantity = fixed_dollar_size(self.cfg.risk.max_trade_risk, stop_points, self.spec.multiplier,
                        roundtrip_cost=2*self.cfg.costs.fee+(2*adverse+self.spec.tick)*self.spec.multiplier, maximum=self.cfg.risk.max_contracts)
                    permitted, why = self.risk.permit(timestamp=timestamp, quantity=quantity, risk_per_contract=risk_per,
                        **self.portfolio_context,
                        slippage_ticks=self.cfg.costs.slippage_ticks+self.cfg.costs.impact_ticks)
                    if self.account is not None and not self.account.permit_position(quantity):
                        permitted, why = False, "funded_position_limit_or_lockout"
                    if permitted:
                        order = Order(self.next_order_id("entry"), self.cfg.instrument, bar.contract, desired, quantity, decision_time)
                        self.broker.submit_order(order)
                        fill = self.broker.match(order, bar, self.previous.volume, self.cfg.execution.participation)
                        if fill:
                            q, price = fill["quantity"], fill["price"]
                            self.cash -= fill["fee"]
                            self.position = Position(desired, q, price, price-desired*stop_points,
                                price+desired*self.cfg.execution.target_ticks*self.spec.tick, self.index, timestamp, fill["fee"], bar.contract)
                            self.broker.emit(EventType.POSITION, timestamp, quantity=desired*q)
                        if order.status != "filled":
                            self.broker.cancel_order(order.order_id)  # IOC remainder
                    else:
                        self.broker.emit(EventType.REJECT, timestamp, reason=why)
        if self.position:
            p = self.position
            stop = bar.low <= p.stop if p.side > 0 else bar.high >= p.stop
            target = bar.high >= p.target+self.spec.tick if p.side > 0 else bar.low <= p.target-self.spec.tick
            opening_stop = p.side*(bar.open-p.stop) <= 0
            if opening_stop or stop:
                reference = min(bar.open, p.stop) if p.side > 0 else max(bar.open, p.stop)
                self.broker.emit(EventType.STOP, timestamp, ambiguous=bool(target and not opening_stop))
                if self.cfg.execution.stop_delay_bars:
                    if self.triggered_stop is None:
                        self.triggered_stop = self.index+self.cfg.execution.stop_delay_bars
                else:
                    self._close(reference, timestamp, "stop_ambiguous" if target else "stop")
            elif target and self.triggered_stop is None:
                self._close(p.target, timestamp, "target", limit=True)
        equity = self.cash
        worst = equity
        if self.position:
            p = self.position
            equity += p.side*p.quantity*(bar.close-p.entry)*self.spec.multiplier
            adverse_price = bar.low if p.side > 0 else bar.high
            worst += p.side*p.quantity*(adverse_price-p.entry)*self.spec.multiplier
        why = None if self.external_risk else self.risk.observe(worst)
        if not why and not self.external_risk:
            why = self.risk.observe(equity)
        if self.account is not None and not self.external_risk:
            self.account.mark(worst, session=bar.session_id, closing_balance=self.cash)
            if self.account.failed or self.account.day_locked:
                why = "funded_account_limit"
                self.risk.kill(why) if self.account.failed else setattr(self.risk, "day_locked", True)
        if why:
            self.pending = None
            self.broker.emit(EventType.LOCK, timestamp, reason=why)
            if self.position:
                # Worst-price forced liquidation is conservative; no claim of known path.
                self._close(bar.low if self.position.side > 0 else bar.high, timestamp, "risk_exit")
                equity = worst = self.cash
        self.curve.append(dict(timestamp_utc=timestamp, session_id=bar.session_id, equity=equity,
            cash=self.cash, intrabar_worst_bound=min(worst, equity), quantity=self.position.side*self.position.quantity if self.position else 0))
        if signal is not None:
            self.broker.emit(EventType.SIGNAL, timestamp+pd.Timedelta(minutes=self.cfg.timeframe_minutes), desired=str(signal) if isinstance(signal, str) else int(signal))
        # A close decision is actionable only on a later bar. Zero computational
        # latency at the next boundary is a declared bar-resolution approximation;
        # delay_bars > 1 models additional whole-bar latency.
        self.previous = bar
        self.queue_decision(signal)
        self.broker.reconcile({self.position.contract: self.position.side*self.position.quantity} if self.position else {})
        return self.curve[-1]

    def finish(self):
        if self.position:
            self._close(self.previous.close, self.previous.timestamp_utc+pd.Timedelta(minutes=self.cfg.timeframe_minutes), "terminal_accounting_close")
            self.curve[-1].update(equity=self.cash, cash=self.cash, quantity=0)
        self.pending = None
        if self.account:
            self.account.end_session(self.cash)
        return dict(curve=pd.DataFrame(self.curve), trades=pd.DataFrame(self.trades), events=self.broker.events)


def run_backtest(bars, signals, config=None, account=None):
    cfg = config or ResearchConfig()
    bars, report = validate(bars, cfg.timeframe_minutes)
    if report["fatal"] or bars.timestamp_utc.duplicated().any():
        raise ValueError("Invalid selected market data")
    if len(bars) != len(signals):
        raise ValueError("Signal length mismatch")
    sim = Simulator(cfg, account)
    for bar, signal in zip(bars.itertuples(index=False), signals):
        sim.step(bar, signal)
    return sim.finish()

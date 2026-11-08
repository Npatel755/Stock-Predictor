from dataclasses import dataclass, field
from collections import deque
import math
import pandas as pd
from .config import RiskLimits


def fixed_dollar_size(risk_dollars, stop_points, multiplier, roundtrip_cost=0, maximum=1):
    if not all(math.isfinite(x) for x in (risk_dollars, stop_points, multiplier, roundtrip_cost)) or stop_points <= 0 or multiplier <= 0 or risk_dollars <= 0 or roundtrip_cost < 0:
        raise ValueError("Invalid sizing inputs")
    return max(0, min(maximum, math.floor(risk_dollars/(stop_points*multiplier+roundtrip_cost))))


def portfolio_exposure(positions, multipliers):
    # Gross sum intentionally grants no diversification credit to MES/MNQ.
    return sum(abs(p["quantity"])*p["price"]*multipliers[p["instrument"]] for p in positions)


@dataclass
class RiskManager:
    limits: RiskLimits
    initial: float
    peak: float = field(init=False)
    day_start: float = field(init=False)
    session: str | None = None
    consecutive_losses: int = 0
    killed: bool = False
    day_locked: bool = False
    reason: str | None = None
    order_times: deque = field(default_factory=deque)

    def __post_init__(self):
        self.peak = self.day_start = self.initial

    def begin_session(self, session, equity):
        if self.session != session:
            self.session, self.day_start = session, equity
            self.day_locked = False
            self.consecutive_losses = 0
            if not self.killed:
                self.reason = None
            self.order_times.clear()

    def observe(self, equity):
        if not math.isfinite(equity):
            self.kill("nonfinite_equity")
            return self.reason
        self.peak = max(self.peak, equity)
        if self.peak-equity >= self.limits.max_drawdown-1e-8:
            self.kill("maximum_drawdown")
        elif self.day_start-equity >= self.limits.max_daily_loss-1e-8:
            self.day_locked, self.reason = True, "daily_loss"
        elif self.consecutive_losses >= self.limits.max_consecutive_losses:
            self.day_locked, self.reason = True, "losing_streak"
        return self.reason if self.killed or self.day_locked else None

    def permit(self, *, timestamp, quantity, risk_per_contract, open_risk=0, correlated_contracts=0, slippage_ticks=0):
        if self.killed or self.day_locked:
            return False, self.reason
        if quantity < 1 or quantity != int(quantity) or quantity > self.limits.max_contracts:
            return False, "position_limit"
        if not math.isfinite(risk_per_contract) or risk_per_contract <= 0:
            return False, "invalid_risk"
        if quantity*risk_per_contract > self.limits.max_trade_risk:
            return False, "trade_risk"
        if open_risk+quantity*risk_per_contract > self.limits.max_open_risk:
            return False, "open_risk"
        if quantity+abs(correlated_contracts) > self.limits.max_correlated_contracts:
            return False, "correlated_exposure"
        if slippage_ticks > self.limits.max_slippage_ticks:
            return False, "slippage_limit"
        while self.order_times and timestamp-self.order_times[0] >= pd.Timedelta(minutes=1):
            self.order_times.popleft()
        if len(self.order_times) >= self.limits.max_orders_per_minute:
            return False, "order_rate"
        self.order_times.append(timestamp)
        return True, None

    def trade_closed(self, pnl):
        self.consecutive_losses = self.consecutive_losses+1 if pnl < 0 else 0

    def kill(self, reason="emergency_stop"):
        self.killed, self.reason = True, reason


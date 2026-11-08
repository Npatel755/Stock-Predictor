"""Configurable account state machine; unknown operational rules block eligibility."""
from dataclasses import dataclass, field
from pathlib import Path
import math
import yaml


@dataclass
class AccountRules:
    nominal: float = 50000
    drawdown: float = 2000
    method: str = "eod_trailing"
    lock_floor: float | None = 50100
    lock_trigger: float | None = 52100
    profit_target: float | None = 3000
    consistency: float | None = None
    daily_loss: float | None = None
    minimum_days: int | None = None
    verified: bool = False
    phase: str = "evaluation"
    maximum_contracts: int = 40

    def __post_init__(self):
        if self.method not in ("static", "trailing", "eod_trailing", "intraday_trailing"):
            raise ValueError("Unverified drawdown method")
        if not math.isfinite(self.nominal) or not math.isfinite(self.drawdown) or self.nominal <= 0 or self.drawdown <= 0:
            raise ValueError("Invalid account amounts")
        if self.consistency is not None and not 0 < self.consistency <= 1:
            raise ValueError("Invalid consistency")
        if self.phase not in ("evaluation", "funded"):
            raise ValueError("Account phase must be evaluation or funded")
        if self.maximum_contracts < 1 or self.maximum_contracts != int(self.maximum_contracts):
            raise ValueError("Positive integer account size limit required")
        for value in (self.daily_loss, self.profit_target):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError("Invalid optional account threshold")


@dataclass
class FundedAccount:
    rules: AccountRules
    floor: float = field(init=False)
    balance: float = field(init=False)
    peak: float = field(init=False)
    day_start: float = field(init=False)
    session: str | None = None
    failed: bool = False
    day_locked: bool = False
    locked_floor: bool = False
    profits: list = field(default_factory=list)
    violations: list = field(default_factory=list)
    session_closed: bool = False
    last_closed_balance: float = field(init=False)

    def __post_init__(self):
        self.floor = self.rules.nominal-self.rules.drawdown
        self.balance = self.peak = self.day_start = self.rules.nominal
        self.last_closed_balance = self.rules.nominal

    def _trail(self, reference):
        if self.rules.method == "static" or self.locked_floor:
            return
        self.peak = max(self.peak, reference)
        candidate = self.peak-self.rules.drawdown
        if self.rules.lock_trigger is not None and self.peak > self.rules.lock_trigger:
            self.locked_floor = True
            candidate = self.rules.lock_floor
        elif self.rules.lock_floor is not None:
            candidate = min(candidate, self.rules.lock_floor)
        self.floor = max(self.floor, candidate)

    def end_session(self, closing_balance):
        if self.session is not None and not self.session_closed:
            self.profits.append(closing_balance-self.day_start)
        self.session_closed = True
        self.balance = closing_balance
        self.last_closed_balance = closing_balance
        if self.rules.method == "eod_trailing":
            self._trail(closing_balance)
        self.day_start = closing_balance

    def mark(self, equity, *, session, closing_balance=None):
        if not math.isfinite(equity):
            raise ValueError("Finite account equity required")
        if self.session != session:
            if self.session is not None:
                self.end_session(self.balance)
            self.session = session
            self.session_closed = False
            self.day_locked = False
        if self.rules.method in ("trailing", "intraday_trailing"):
            self._trail(equity)
        if equity <= self.floor+1e-8:
            self.failed = True
            self.violations.append(dict(session=session, reason="max_loss_limit", equity=equity, floor=self.floor))
        if self.rules.daily_loss is not None and equity <= self.day_start-self.rules.daily_loss+1e-8:
            self.day_locked = True
            self.violations.append(dict(session=session, reason="daily_loss_soft_lockout", equity=equity))
        self.balance = equity if closing_balance is None else closing_balance

    def permit_position(self, quantity):
        maximum = self.rules.maximum_contracts
        if self.rules.phase == "funded":
            profit = self.last_closed_balance-self.rules.nominal
            maximum = min(maximum, 40 if profit >= 2000 else 30 if profit >= 1000 else 20)
        return not self.failed and not self.day_locked and 0 <= quantity <= maximum

    def payout(self, amount):
        if amount <= 0 or amount > max(0, self.balance-self.rules.nominal):
            raise ValueError("Invalid payout")
        self.balance -= amount
        if self.rules.lock_floor is not None:
            self.floor, self.locked_floor = self.rules.lock_floor, True
        if self.balance <= self.floor:
            self.failed = True

    def summary(self):
        profit = self.balance-self.rules.nominal
        ratio = max([0.0]+self.profits)/profit if profit > 0 else None
        consistency_pass = ratio is not None and self.rules.consistency is not None and ratio <= self.rules.consistency
        target = self.rules.profit_target is not None and profit >= self.rules.profit_target
        enough_days = self.rules.minimum_days is not None and len(self.profits) >= self.rules.minimum_days
        return dict(balance=self.balance, floor=self.floor, drawdown_buffer=self.balance-self.floor,
            day_loss_buffer=None if self.rules.daily_loss is None else self.balance-self.day_start+self.rules.daily_loss,
            profit=profit, consistency_ratio=ratio, consistency_pass=consistency_pass,
            target_reached=target, trading_days=len(self.profits), failed=self.failed,
            day_locked=self.day_locked, violations=self.violations,
            simulated_objectives_met=bool(target and consistency_pass and enough_days and not self.failed),
            operationally_eligible=bool(self.rules.verified and target and consistency_pass and enough_days and not self.failed))


def load_rule_scenarios(path):
    source = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    scenarios = {}
    for consistency in source["consistency_scenarios"]:
        for dll in (None, 300):  # $300 = explicit analyst stress scenario, not Lucid's unverified DLL amount.
            name = f"consistency_{consistency}_dll_{dll}"
            scenarios[name] = AccountRules(nominal=source["nominal_size"], drawdown=source["maximum_drawdown"],
                method=source["drawdown_method"], lock_floor=source["drawdown_lock_floor"],
                lock_trigger=source["drawdown_lock_trigger"], profit_target=source["profit_target"],
                consistency=consistency, daily_loss=dll, minimum_days=None, verified=False)
    return scenarios


def payout_economics(payouts, evaluation_fee=None, activation_fee=0, attempts=1, profit_split=.9):
    gross = sum(payouts)
    return dict(simulated_payouts=gross, trader_share=gross*profit_split,
        net_economics=None if evaluation_fee is None else gross*profit_split-attempts*evaluation_fee-activation_fee,
        evaluation_fee_verified=evaluation_fee is not None)


def funded_payout_eligibility(daily_profits, cycle_profit, requested, previous_payouts=0):
    # Verified $50K funded constraints; scaling and account agreement checks remain external.
    return (sum(x >= 150 for x in daily_profits) >= 5 and cycle_profit > 0 and
            500 <= requested <= min(.5*cycle_profit, 2000) and previous_payouts < 5)

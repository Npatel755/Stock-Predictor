"""Pine inputs and explicitly separate research execution settings."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class StrategyConfig:
    mode: Literal["parity", "research"] = "parity"
    strategy_version: Literal["v1", "v1.1"] = "v1.1"
    initial_capital: float = 50000.
    risk_usd: float = 100.
    reward_r: float = 2.
    max_leverage: float = 5.
    max_daily_loss: float = 300.
    max_trades_day: int = 3
    max_setup_bars: int = 24
    breakout_rvol: float = 1.5
    entry_rvol: float = 1.2
    retest_atr: float = .25
    stop_atr: float = .1
    tick_size: float = .01
    commission_bps: float | None = None
    point_value: float = 1.
    slippage_ticks: int = 2
    margin_ratio: float = .2
    entry_timing: Literal["signal_close", "next_open"] = "signal_close"
    intrabar_policy: Literal["tradingview", "stop_first"] = "tradingview"
    gap_policy: Literal["reject", "segment"] = "reject"
    slippage_bps: float = 0.
    swap_daily_bps: float = 0.
    profit_share: float = .9
    # Experimental changes are available only in Research mode.
    min_stop_bps: float = 0.
    min_stop_atr: float = 0.
    risk_includes_costs: bool = False
    min_reward_cost_ratio: float = 0.
    min_atr_bps: float = 0.
    max_atr_bps: float = 0.  # zero disables the upper bound
    min_trend_gap_bps: float = 0.
    trade_direction: Literal["both", "long", "short"] = "both"
    session: Literal["all", "europe_us", "us", "asia"] = "all"
    allow_weekends: bool = True
    cooldown_bars: int = 0
    breakeven_r: float = 0.  # close-based activation, effective next bar
    trail_atr: float = 0.
    max_holding_bars: int = 0

    def __post_init__(self):
        if self.strategy_version not in {"v1", "v1.1"}:
            raise ValueError("Unknown Pine strategy version")
        expected_commission = 4. if self.strategy_version == "v1.1" else 5.
        if self.commission_bps is None:
            object.__setattr__(self, "commission_bps", expected_commission)
        if self.mode not in {"parity", "research"} or self.entry_timing not in {"signal_close", "next_open"}:
            raise ValueError("Unknown strategy mode or entry timing")
        if self.intrabar_policy not in {"tradingview", "stop_first"} or self.gap_policy not in {"reject", "segment"}:
            raise ValueError("Unknown execution or gap policy")
        if min(self.initial_capital, self.risk_usd, self.max_daily_loss, self.tick_size, self.point_value) <= 0:
            raise ValueError("Capital, risk, loss limit and tick size must be positive")
        if not 1 <= self.max_leverage <= 5 or self.reward_r < 1 or not 0 < self.margin_ratio <= 1:
            raise ValueError("Invalid leverage, reward or margin")
        if min(self.max_trades_day, self.max_setup_bars) < 1:
            raise ValueError("Daily entries and retest window must be positive")
        if min(self.breakout_rvol, self.entry_rvol) <= 0 or min(self.retest_atr, self.stop_atr, self.commission_bps,
                                                              self.slippage_ticks, self.slippage_bps, self.swap_daily_bps) < 0:
            raise ValueError("Invalid thresholds or costs")
        if not 0 < self.profit_share <= 1:
            raise ValueError("Profit share must be a fraction")
        research_numbers = [self.min_stop_bps, self.min_stop_atr, self.min_reward_cost_ratio, self.min_atr_bps,
                            self.max_atr_bps, self.min_trend_gap_bps, self.cooldown_bars,
                            self.breakeven_r, self.trail_atr, self.max_holding_bars]
        if min(research_numbers) < 0:
            raise ValueError("Research thresholds cannot be negative")
        if self.max_atr_bps and self.max_atr_bps < self.min_atr_bps:
            raise ValueError("Maximum ATR must be >= minimum ATR")
        if self.trade_direction not in {"both", "long", "short"} or self.session not in {"all", "europe_us", "us", "asia"}:
            raise ValueError("Unknown research direction or session")
        if self.mode == "parity" and (any(research_numbers) or self.risk_includes_costs or
                                       self.trade_direction != "both" or self.session != "all" or not self.allow_weekends):
            raise ValueError("Experimental signal and risk rules require research mode")
        if self.mode == "parity" and (self.commission_bps != expected_commission or self.slippage_ticks != 2 or self.margin_ratio != .2
                                      or self.entry_timing != "signal_close" or self.intrabar_policy != "tradingview"
                                      or self.gap_policy != "reject" or self.slippage_bps or self.swap_daily_bps):
            raise ValueError("Pine-fixed execution settings cannot be changed in parity mode; use research mode")

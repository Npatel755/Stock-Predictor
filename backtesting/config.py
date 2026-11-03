"""Pine inputs and explicitly separate research execution settings."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class StrategyConfig:
    mode: Literal["parity", "research"] = "parity"
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
    commission_bps: float = 5.
    slippage_ticks: int = 2
    margin_ratio: float = .2
    entry_timing: Literal["signal_close", "next_open"] = "signal_close"
    intrabar_policy: Literal["tradingview", "stop_first"] = "tradingview"
    gap_policy: Literal["reject", "segment"] = "reject"
    slippage_bps: float = 0.
    swap_daily_bps: float = 0.
    profit_share: float = .9

    def __post_init__(self):
        if self.mode not in {"parity", "research"} or self.entry_timing not in {"signal_close", "next_open"}:
            raise ValueError("Unknown strategy mode or entry timing")
        if self.intrabar_policy not in {"tradingview", "stop_first"} or self.gap_policy not in {"reject", "segment"}:
            raise ValueError("Unknown execution or gap policy")
        if min(self.initial_capital, self.risk_usd, self.max_daily_loss, self.tick_size) <= 0:
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
        if self.mode == "parity" and (self.commission_bps != 5 or self.slippage_ticks != 2 or self.margin_ratio != .2
                                      or self.entry_timing != "signal_close" or self.intrabar_policy != "tradingview"
                                      or self.gap_policy != "reject" or self.slippage_bps or self.swap_daily_bps):
            raise ValueError("Pine-fixed execution settings cannot be changed in parity mode; use research mode")

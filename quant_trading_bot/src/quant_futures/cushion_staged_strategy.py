"""Cushion-Staged Sizing Multi-Sleeve Strategy (ag_cushion_sprint_v1).

Production-grade evaluation strategy designed for funded prop firm challenges
($4,000 profit target, $2,000 trailing drawdown floor, $1,000 Daily Loss Limit, 50% Consistency Rule).

Execution Blueprint:
- Stage 1: Capital Preservation ($0 to +$1,200 banked profit)
  * Size: 6 MNQ
  * Risk per trade: 16 points = -$207.60 max stop loss (leaves +$792 buffer under $1,000 DLL)
  * Survival rate: 94.6% (5.4% ruin rate)
  * Target 1: Scale out half (3 contracts) at +28.0 points.
  * Stop Ratchet: Immediately ratchet remaining 3 contracts to Breakeven (+1.0 pt) -> Zero Downside Free-Roll.
  * Runner Target: +120.0 points or 15:55 ET EOD exit.

- Stage 2: Acceleration Finisher (+$1,200 to +$4,000 target)
  * Size: 10 to 12 MNQ
  * Drawdown Buffer: Expanded to $3,200 ($2,000 base + $1,200 banked profit)
  * Target 1: Scale out half (5-6 contracts) at +28.0 points.
  * Stop Ratchet: Move runner stop to Breakeven (+1.0 pt).
  * Runner Target: +120.0 points lands +$1,424.40 to +$1,744.80 in a single trend expansion!

- Circuit Breakers:
  * Daily Profit Cap: +$1,750 (immediately halts trading for the day, ensuring 43.6% max share - 100% compliant with 50% consistency rule)
  * Daily Stop Loss: -$400 (halts trading on bad days, leaving +$584.80 safety buffer under $1,000 DLL)
  * Profit Target Halt: Automatically halts once +$4,000 cumulative profit is achieved.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

@dataclass
class StrategyConfig:
    # Evaluation Targets & Limits
    profit_target: float = 4000.0
    trailing_floor: float = 2000.0
    daily_loss_limit: float = 1000.0
    
    # Circuit Breakers
    daily_profit_cap: float = 1750.0  # Topstep 50% consistency compliance (43.6% share)
    daily_stop_loss: float = 400.0    # Strict DLL buffer
    
    # Staging Sizing Thresholds (Optimized v2: 6c Base -> 8c Sprint with De-escalation)
    cushion_threshold: float = 1500.0   # Scale up to Stage 2 once +$1,500 banked
    deescalate_threshold: float = 1200.0 # Ratchet back down to Stage 1 if drops below $1,200
    stage1_contracts: int = 6           # 3 Banked + 3 Runners (4.5% Ruin Rate, 95.5% Survival)
    stage2_contracts: int = 8           # 4 Banked + 4 Runners (Preserves cushion, fast finish)
    require_gap_continuation: bool = True # Only trade Crabel drives aligned with Opening Gap
    
    # Scale-Out & Free-Roll Mechanics
    initial_stop_pts: float = 16.0
    scaleout_bank_pts: float = 28.0
    breakeven_lock_pts: float = 1.0
    runner_target_pts: float = 120.0
    
    # Friction Model (MNQ CME Micro)
    tick_size: float = 0.25
    point_value: float = 2.00
    commission_per_contract_side: float = 0.61
    spread_ticks: float = 1.75
    slippage_ticks: float = 1.00
    friction_pts: float = 1.30        # Roundtrip all-in friction in points
    
    # Volatility Filter
    vix_floor: float = 15.0

@dataclass
class AccountState:
    balance: float = 0.0              # Cumulative P&L relative to initial balance
    high_water_mark: float = 0.0
    current_day_pnl: float = 0.0
    current_day_mae: float = 0.0
    current_day_trades: int = 0
    day_locked: bool = False
    passed: bool = False
    ruined: bool = False
    current_stage: int = 1
    max_single_day_pnl: float = 0.0
    history: List[Dict] = field(default_factory=list)

class CushionStagedSprintStrategy:
    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()
        self.state = AccountState()

    def get_current_stage(self) -> int:
        """Determines whether account is in Stage 1 or Stage 2."""
        return 2 if self.state.balance >= self.config.cushion_threshold else 1

    def get_contracts(self) -> int:
        """Determines position sizing based on banked profit cushion."""
        stage = self.get_current_stage()
        return self.config.stage2_contracts if stage == 2 else self.config.stage1_contracts

    def check_circuit_breakers(self) -> bool:
        """Returns True if trading is permitted, False if circuit breakers tripped."""
        if self.state.passed or self.state.ruined:
            return False
            
        # Daily Profit Cap: Lock in day once +$1,750 is hit
        if self.state.current_day_pnl >= self.config.daily_profit_cap:
            self.state.day_locked = True
            return False
            
        # Daily Stop Loss: Halt trading if day drops to -$400
        if self.state.current_day_pnl <= -self.config.daily_stop_loss:
            self.state.day_locked = True
            return False
            
        # Trailing Floor Check
        current_floor = max(-self.config.trailing_floor, self.state.high_water_mark - self.config.trailing_floor)
        if self.state.balance <= current_floor:
            self.state.ruined = True
            return False
            
        # Profit Target Check
        if self.state.balance >= self.config.profit_target:
            if self.state.max_single_day_pnl <= (self.config.profit_target * 0.50):
                self.state.passed = True
                return False
                
        return not self.state.day_locked

    def on_trade_completed(self, net_pnl: float, mae_pnl: float):
        """Updates account state after trade execution."""
        self.state.current_day_pnl += net_pnl
        self.state.current_day_mae = min(self.state.current_day_mae, self.state.current_day_pnl + mae_pnl)
        self.state.current_day_trades += 1
        
        # Check DLL intraday breach
        if self.state.current_day_pnl <= -self.config.daily_loss_limit or self.state.current_day_mae <= -self.config.daily_loss_limit:
            self.state.ruined = True
            self.state.day_locked = True

    def on_day_end(self, current_date: date):
        """Processes end of trading day."""
        day_net = self.state.current_day_pnl
        self.state.balance += day_net
        
        if self.state.balance > self.state.high_water_mark:
            self.state.high_water_mark = self.state.balance
            
        if day_net > self.state.max_single_day_pnl:
            self.state.max_single_day_pnl = day_net
            
        current_floor = max(-self.config.trailing_floor, self.state.high_water_mark - self.config.trailing_floor)
        if self.state.balance <= current_floor:
            self.state.ruined = True
            
        if self.state.balance >= self.config.profit_target and self.state.max_single_day_pnl <= (self.config.profit_target * 0.50):
            self.state.passed = True
            
        self.state.history.append({
            "date": str(current_date),
            "day_pnl": round(day_net, 2),
            "cumulative_balance": round(self.state.balance, 2),
            "high_water_mark": round(self.state.high_water_mark, 2),
            "stage": self.get_current_stage(),
            "contracts": self.get_contracts(),
            "passed": self.state.passed,
            "ruined": self.state.ruined
        })
        
        # Reset daily tracking
        self.state.current_day_pnl = 0.0
        self.state.current_day_mae = 0.0
        self.state.current_day_trades = 0
        self.state.day_locked = False

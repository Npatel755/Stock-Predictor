from __future__ import annotations

from pathlib import Path
from typing import Literal
import hashlib
import json
import yaml
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Costs(StrictModel):
    # Illustrative research assumptions, not a verified broker fee schedule.
    commission_per_side: float = Field(0.65, ge=0)
    exchange_per_side: float = Field(0.35, ge=0)
    regulatory_per_side: float = Field(0.02, ge=0)
    spread_ticks: float = Field(1, ge=0)
    slippage_ticks: float = Field(1, ge=0)
    impact_ticks: float = Field(0, ge=0)

    @property
    def fee(self):
        return self.commission_per_side + self.exchange_per_side + self.regulatory_per_side

    def scaled(self, factor):
        return Costs(**{k: v * factor for k, v in self.model_dump().items()})


class Execution(StrictModel):
    delay_bars: int = Field(1, ge=1)
    participation: float = Field(0.01, gt=0, le=1)
    stop_ticks: int = Field(16, ge=1)
    target_ticks: int = Field(24, ge=1)
    max_hold_bars: int = Field(20, ge=1)
    max_gap_minutes: int = Field(5, ge=1)
    session_flat_minute_et: int = Field(1000, ge=0, le=1439)
    missed_entry_fraction: float = Field(0, ge=0, le=1)
    stop_delay_bars: int = Field(0, ge=0, le=10)
    use_observed_quotes: bool = True


class RiskLimits(StrictModel):
    max_contracts: int = Field(1, ge=1)
    max_trade_risk: float = Field(75, gt=0)
    max_open_risk: float = Field(150, gt=0)
    max_daily_loss: float = Field(300, gt=0)
    max_drawdown: float = Field(1000, gt=0)
    max_consecutive_losses: int = Field(5, ge=1)
    max_orders_per_minute: int = Field(4, ge=1)
    max_correlated_contracts: int = Field(1, ge=1)
    max_slippage_ticks: float = Field(4, ge=0)


class ResearchConfig(StrictModel):
    seed: int = 20261106
    initial_balance: float = Field(50000, gt=0)
    instrument: Literal["MES", "MNQ"] = "MES"
    calendar_schedule: str | None = None
    timeframe_minutes: int = Field(1, ge=1)
    label_horizon: int = Field(5, ge=1)
    embargo_bars: int = Field(5, ge=0)
    holdout_fraction: float = Field(0.2, gt=0, lt=0.5)
    minimum_training_bars: int = Field(240, ge=50)
    validation_bars: int = Field(120, ge=10)
    maximum_trials: int = Field(32, ge=1)
    maximum_runtime_seconds: int = Field(600, ge=1)
    maximum_parallel_jobs: Literal[1] = 1
    maximum_disk_gb: float = Field(2, gt=0)
    minimum_trades: int = Field(100, ge=1)
    minimum_oos_days: int = Field(60, ge=1)
    models: list[str] = ["logistic", "ridge", "tree", "lightgbm", "xgboost"]
    calibration: Literal["sigmoid", "isotonic", "none"] = "sigmoid"
    probability_threshold: float = Field(0.57, gt=0.5, lt=1)
    costs: Costs = Costs()
    execution: Execution = Execution()
    risk: RiskLimits = RiskLimits()
    objectives: list[Literal["direction", "return", "triple_barrier"]] = ["direction"]
    label_horizons: list[int] = [1, 3, 5, 10, 20]
    nested_trials: int = Field(1, ge=1, le=100)
    neural_epochs: int = Field(3, ge=1, le=100)
    rl_timesteps: int = Field(256, ge=64, le=1000000)
    maximum_training_rows: int = Field(100000, ge=100)
    validation_mode: Literal["fixed", "walk_forward"] = "fixed"


def load_config(path: str | Path) -> ResearchConfig:
    return ResearchConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def file_hash(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


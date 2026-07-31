from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator, model_validator

from api_response import success
from services.trading_tools import (
    calculate_cost_impact,
    calculate_drawdown,
    calculate_expectancy,
    calculate_monte_carlo,
    calculate_position_size,
)


router = APIRouter(prefix="/api/trading-tools", tags=["trading-tools"])


class PositionSizeRequest(BaseModel):
    asset_class: Literal["stock", "forex", "crypto", "futures"]
    symbol: str = Field(min_length=1, max_length=40)
    direction: Literal["long", "short"]
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    target_price: float | None = Field(default=None, gt=0)
    account_size: float = Field(gt=0)
    risk_percent: float = Field(gt=0, le=100)
    point_value: float | None = Field(default=None, gt=0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized

    @model_validator(mode="after")
    def validate_price_risk(self):
        if self.entry_price == self.stop_loss:
            raise ValueError("entry and stop must differ")
        return self


class ExpectancyRequest(BaseModel):
    win_rate: float = Field(ge=0, le=100)
    avg_win: float = Field(ge=0)
    avg_loss: float = Field(ge=0)
    cost_per_trade: float = Field(default=0, ge=0)
    target_profit: float | None = Field(default=None, gt=0)


class DrawdownRequest(BaseModel):
    starting_equity: float = Field(gt=0)
    current_equity: float = Field(gt=0)
    max_drawdown_percent: float = Field(gt=0, lt=100)
    risk_per_trade_percent: float = Field(gt=0, lt=100)


class MonteCarloRequest(BaseModel):
    starting_equity: float = Field(gt=0)
    target_return_percent: float = Field(gt=0)
    max_drawdown_percent: float = Field(gt=0, lt=100)
    win_rate: float = Field(ge=0, le=100)
    avg_win_r: float = Field(gt=0)
    avg_loss_r: float = Field(gt=0)
    risk_per_trade_percent: float = Field(gt=0, lt=100)
    trades: int = Field(default=100, ge=1, le=2000)
    simulations: int = Field(default=1000, ge=100, le=5000)
    seed: int = 42


class CostImpactRequest(BaseModel):
    trades_count: int = Field(gt=0, le=1_000_000)
    gross_pnl: float
    commission_per_trade: float = Field(default=0, ge=0)
    slippage_per_trade: float = Field(default=0, ge=0)
    spread_per_trade: float = Field(default=0, ge=0)


@router.post("/position-size")
async def position_size(req: PositionSizeRequest):
    return success(calculate_position_size(**req.model_dump()))


@router.post("/expectancy")
async def expectancy(req: ExpectancyRequest):
    return success(calculate_expectancy(**req.model_dump()))


@router.post("/drawdown")
async def drawdown(req: DrawdownRequest):
    return success(calculate_drawdown(**req.model_dump()))


@router.post("/monte-carlo")
async def monte_carlo(req: MonteCarloRequest):
    return success(calculate_monte_carlo(**req.model_dump()))


@router.post("/cost-impact")
async def cost_impact(req: CostImpactRequest):
    return success(calculate_cost_impact(**req.model_dump()))

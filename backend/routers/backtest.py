import math
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from api_response import error, success
from auth_dependency import get_current_user
from backtest_schema import BacktestStatus, StrategyConfigModel
from db import get_db
from services.backtest import BacktestService

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class CreateStrategyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    config: StrategyConfigModel


class UpdateStrategyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    config: StrategyConfigModel | None = None


class CreateRunRequest(BaseModel):
    strategy_id: str
    date_from: str | None = None
    date_to: str | None = None


class ParameterGridRequest(BaseModel):
    parameter: Literal[
        "stop_loss_pct",
        "take_profit_pct",
        "trailing_stop_pct",
        "breakeven_trigger_pct",
        "max_holding_bars",
        "position_size",
    ]
    values: list[float] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_values(self) -> "ParameterGridRequest":
        if any(value <= 0 or not math.isfinite(value) for value in self.values):
            raise ValueError("Optimization values must be finite and positive")
        if self.parameter == "max_holding_bars" and any(
            not value.is_integer() for value in self.values
        ):
            raise ValueError("Maximum holding bars must use whole numbers")
        if self.parameter == "position_size" and any(
            not (0 < value < 1 or value.is_integer())
            for value in self.values
        ):
            raise ValueError(
                "Position size must be a positive whole unit or a fraction below 1"
            )
        return self


class OptimizationRequest(CreateRunRequest):
    objective: Literal[
        "total_return_pct",
        "sharpe_ratio",
        "profit_factor",
        "max_drawdown_pct",
    ] = "sharpe_ratio"
    grids: list[ParameterGridRequest] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def validate_trial_count(self) -> "OptimizationRequest":
        parameters = [grid.parameter for grid in self.grids]
        if len(set(parameters)) != len(parameters):
            raise ValueError("Optimization parameters must be unique")
        trial_count = math.prod(len(grid.values) for grid in self.grids)
        if trial_count > 200:
            raise ValueError("Parameter search is limited to 200 trials")
        return self


class ValidationRequest(CreateRunRequest):
    train_ratio: float = Field(default=0.7, ge=0.5, le=0.9)


class WalkForwardRequest(OptimizationRequest):
    train_bars: int = Field(default=500, ge=3)
    test_bars: int = Field(default=100, ge=3)
    step_bars: int = Field(default=100, ge=3)


def _sanitize_floats(obj):
    """Replace inf/-inf/nan with JSON-safe values."""
    if isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {key: _sanitize_floats(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_floats(value) for value in obj]
    return obj


@router.post("/strategies")
async def create_strategy(
    req: CreateStrategyRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        strategy = BacktestService(db).create_strategy(
            user_id=user_id,
            name=req.name,
            config=req.config.model_dump(mode="json"),
        )
    except ValueError as exc:
        return error(message=str(exc), code=400, status_code=400)
    return success(strategy)


@router.get("/strategies")
async def list_strategies(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    return success(BacktestService(db).list_strategies(user_id))


@router.put("/strategies/{strategy_id}")
async def update_strategy(
    strategy_id: str,
    req: UpdateStrategyRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    fields = {}
    if req.name is not None:
        fields["name"] = req.name
    if req.config is not None:
        fields["config"] = req.config.model_dump(mode="json")
    try:
        strategy = BacktestService(db).update_strategy(
            user_id,
            strategy_id,
            **fields,
        )
    except ValueError as exc:
        return error(message=str(exc), code=400, status_code=400)
    if strategy is None:
        return error(message="Strategy not found", code=404, status_code=404)
    return success(strategy)


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(
    strategy_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    if not BacktestService(db).delete_strategy(user_id, strategy_id):
        return error(message="Strategy not found", code=404, status_code=404)
    return success(None)


@router.post("/runs")
async def create_run(
    req: CreateRunRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        run = BacktestService(db).create_run(
            user_id=user_id,
            strategy_id=req.strategy_id,
            date_from=req.date_from,
            date_to=req.date_to,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Strategy not found" else 400
        return error(message=str(exc), code=status_code, status_code=status_code)
    return success(run)


@router.get("/runs")
async def list_runs(
    strategy_id: str | None = None,
    status: BacktestStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    service = BacktestService(db)
    runs = service.list_runs(
        user_id,
        strategy_id=strategy_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    total = service.count_runs(
        user_id,
        strategy_id=strategy_id,
        status=status,
    )
    return success(
        {
            "items": runs,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.post("/runs/optimization")
async def create_optimization_run(
    req: OptimizationRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        run = BacktestService(db).create_analysis_run(
            user_id,
            req.strategy_id,
            run_kind="optimization",
            analysis_config={
                "objective": req.objective,
                "grids": [
                    grid.model_dump(mode="json")
                    for grid in req.grids
                ],
            },
            date_from=req.date_from,
            date_to=req.date_to,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Strategy not found" else 400
        return error(message=str(exc), code=status_code, status_code=status_code)
    return success(run)


@router.post("/runs/validation")
async def create_validation_run(
    req: ValidationRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        run = BacktestService(db).create_analysis_run(
            user_id,
            req.strategy_id,
            run_kind="validation",
            analysis_config={"train_ratio": req.train_ratio},
            date_from=req.date_from,
            date_to=req.date_to,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Strategy not found" else 400
        return error(message=str(exc), code=status_code, status_code=status_code)
    return success(run)


@router.post("/runs/walk-forward")
async def create_walk_forward_run(
    req: WalkForwardRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    try:
        run = BacktestService(db).create_analysis_run(
            user_id,
            req.strategy_id,
            run_kind="walk_forward",
            analysis_config={
                "objective": req.objective,
                "grids": [
                    grid.model_dump(mode="json")
                    for grid in req.grids
                ],
                "train_bars": req.train_bars,
                "test_bars": req.test_bars,
                "step_bars": req.step_bars,
            },
            date_from=req.date_from,
            date_to=req.date_to,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Strategy not found" else 400
        return error(message=str(exc), code=status_code, status_code=status_code)
    return success(run)


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    run = BacktestService(db).get_run(user_id, run_id)
    if run is None:
        return error(message="Backtest run not found", code=404, status_code=404)
    return success(_sanitize_floats(run))


@router.post("/runs/{run_id}/rerun")
async def rerun(
    run_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    run = BacktestService(db).rerun(user_id, run_id)
    if run is None:
        return error(message="Backtest run not found", code=404, status_code=404)
    return success(run)


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    if not BacktestService(db).delete_run(user_id, run_id):
        return error(
            message="Completed or failed backtest run not found",
            code=404,
            status_code=404,
        )
    return success(None)


# Compatibility routes for clients created before persistent runs.
@router.post("/run")
async def create_run_compat(
    req: CreateRunRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    return await create_run(req, db, user_id)


@router.get("/jobs/{job_id}")
async def get_run_compat(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    return await get_run(job_id, db, user_id)

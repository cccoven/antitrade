"""Pure calculations exposed by the Trading Lab."""

import math
import random

from services.risk_engine import (
    PositionRiskInput,
    calculate_position_risk,
)


def calculate_position_size(**values) -> dict:
    return calculate_position_risk(PositionRiskInput(**values)).to_dict()


def calculate_expectancy(
    *,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    cost_per_trade: float = 0,
    target_profit: float | None = None,
) -> dict:
    probability = win_rate / 100
    gross_expectancy = probability * avg_win - (1 - probability) * avg_loss
    expectancy = gross_expectancy - cost_per_trade
    denominator = avg_win + avg_loss
    break_even_win_rate = (
        (avg_loss + cost_per_trade) / denominator * 100 if denominator > 0 else None
    )
    gross_profit_factor = (
        probability * avg_win / ((1 - probability) * avg_loss)
        if probability < 1 and avg_loss > 0
        else None
    )
    trades_to_target = (
        math.ceil(target_profit / expectancy)
        if target_profit is not None and target_profit > 0 and expectancy > 0
        else None
    )
    return {
        "gross_expectancy": gross_expectancy,
        "expectancy": expectancy,
        "break_even_win_rate": break_even_win_rate,
        "gross_profit_factor": gross_profit_factor,
        "cost_drag": cost_per_trade,
        "trades_to_target": trades_to_target,
    }


def calculate_drawdown(
    *,
    starting_equity: float,
    current_equity: float,
    max_drawdown_percent: float,
    risk_per_trade_percent: float,
) -> dict:
    drawdown_amount = max(starting_equity - current_equity, 0)
    drawdown_percent = drawdown_amount / starting_equity * 100
    recovery_gain_percent = (
        (starting_equity / current_equity - 1) * 100 if current_equity < starting_equity else 0
    )
    floor_equity = starting_equity * (1 - max_drawdown_percent / 100)
    remaining_loss_budget = max(current_equity - floor_equity, 0)
    remaining_budget_percent = remaining_loss_budget / current_equity * 100
    risk_fraction = risk_per_trade_percent / 100
    if current_equity <= floor_equity:
        losses_until_limit = 0
    elif floor_equity <= 0:
        losses_until_limit = None
    else:
        losses_until_limit = max(
            math.floor(math.log(floor_equity / current_equity) / math.log(1 - risk_fraction)),
            0,
        )
    return {
        "drawdown_amount": drawdown_amount,
        "drawdown_percent": drawdown_percent,
        "recovery_gain_percent": recovery_gain_percent,
        "floor_equity": floor_equity,
        "remaining_loss_budget": remaining_loss_budget,
        "remaining_budget_percent": remaining_budget_percent,
        "losses_until_limit": losses_until_limit,
        "limit_breached": current_equity <= floor_equity,
    }


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def calculate_monte_carlo(
    *,
    starting_equity: float,
    target_return_percent: float,
    max_drawdown_percent: float,
    win_rate: float,
    avg_win_r: float,
    avg_loss_r: float,
    risk_per_trade_percent: float,
    trades: int,
    simulations: int,
    seed: int = 42,
) -> dict:
    rng = random.Random(seed)
    target_equity = starting_equity * (1 + target_return_percent / 100)
    ruin_floor = starting_equity * (1 - max_drawdown_percent / 100)
    probability = win_rate / 100
    risk_fraction = risk_per_trade_percent / 100
    paths: list[list[float]] = []
    endings: list[float] = []
    max_drawdowns: list[float] = []
    target_hits = 0
    ruin_hits = 0

    for _ in range(simulations):
        equity = starting_equity
        peak = starting_equity
        max_drawdown = 0.0
        target_hit = False
        ruined = False
        path = [equity]
        for _trade in range(trades):
            risk_amount = equity * risk_fraction
            if rng.random() < probability:
                equity += risk_amount * avg_win_r
            else:
                equity -= risk_amount * avg_loss_r
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
            path.append(equity)
            target_hit = target_hit or equity >= target_equity
            if equity <= ruin_floor:
                ruined = True
                path.extend([equity] * (trades - _trade - 1))
                break
        paths.append(path)
        endings.append(equity)
        max_drawdowns.append(max_drawdown)
        target_hits += int(target_hit)
        ruin_hits += int(ruined)

    percentile_bands = []
    for step in range(trades + 1):
        values = [path[step] for path in paths]
        percentile_bands.append({
            "trade": step,
            "p10": _percentile(values, 0.10),
            "p50": _percentile(values, 0.50),
            "p90": _percentile(values, 0.90),
        })

    return {
        "target_equity": target_equity,
        "ruin_floor": ruin_floor,
        "target_probability": target_hits / simulations * 100,
        "risk_of_ruin": ruin_hits / simulations * 100,
        "median_ending_equity": _percentile(endings, 0.50),
        "p10_ending_equity": _percentile(endings, 0.10),
        "p90_ending_equity": _percentile(endings, 0.90),
        "median_max_drawdown": _percentile(max_drawdowns, 0.50),
        "p90_max_drawdown": _percentile(max_drawdowns, 0.90),
        "percentile_bands": percentile_bands,
        "simulations": simulations,
        "seed": seed,
    }


def calculate_cost_impact(
    *,
    trades_count: int,
    gross_pnl: float,
    commission_per_trade: float,
    slippage_per_trade: float,
    spread_per_trade: float,
) -> dict:
    cost_per_trade = commission_per_trade + slippage_per_trade + spread_per_trade
    total_cost = cost_per_trade * trades_count
    net_pnl = gross_pnl - total_cost
    gross_average = gross_pnl / trades_count
    net_average = net_pnl / trades_count
    cost_drag_percent = total_cost / abs(gross_pnl) * 100 if gross_pnl != 0 else None
    return {
        "cost_per_trade": cost_per_trade,
        "total_cost": total_cost,
        "net_pnl": net_pnl,
        "gross_average": gross_average,
        "net_average": net_average,
        "cost_drag_percent": cost_drag_percent,
        "break_even_gross_per_trade": cost_per_trade,
    }

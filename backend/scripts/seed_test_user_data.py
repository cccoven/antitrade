"""Seed realistic demo data for one existing AntiTrade user.

Run from backend/:
    ./.venv/bin/python scripts/seed_test_user_data.py demo@example.com

The generated IDs are deterministic, so rerunning the script is safe. Existing
user data is never deleted or overwritten. Automation demo records are
inserted directly; seeding does not execute automation workflows.

Sample files for the Journal import dialog live in scripts/demo_data/.
"""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from db import SessionLocal  # noqa: E402
from models import (  # noqa: E402
    AgentFinding,
    AssistantMemory,
    AutomationRun,
    AutomationTask,
    BacktestRun,
    BacktestStrategy,
    ChatConversation,
    ChatMessage,
    DailyReview,
    FeedBookmark,
    FeedItem,
    JournalSettings,
    Portfolio,
    PortfolioEntry,
    Strategy,
    Trade,
    TradingRule,
    User,
)


BASE_TIME = datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc)
RNG = random.Random(20260711)


def _id(user_id: str, kind: str, index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"antitrade-demo:{user_id}:{kind}:{index}"))


def _iso(value: datetime) -> str:
    return value.isoformat()


def _add_if_missing(session, model, row) -> bool:
    if session.get(model, row.id) is not None:
        return False
    session.add(row)
    return True


def _seed_strategies(session, user_id: str) -> tuple[list[str], int]:
    setups = [
        ("黄金伦敦盘回调", "XAUUSD", "趋势回调"),
        ("纳指开盘区间突破", "NQ1!", "区间突破"),
        ("比特币四小时动量", "BTCUSD", "动量跟随"),
        ("欧元美元均值回归", "EURUSD", "均值回归"),
        ("标普纽约午盘反转", "ES1!", "流动性反转"),
        ("英伟达缺口延续", "NVDA", "缺口交易"),
    ]
    ids: list[str] = []
    inserted = 0
    for i in range(150):
        title, symbol, setup = setups[i % len(setups)]
        strategy_id = _id(user_id, "strategy", i)
        ids.append(strategy_id)
        created = BASE_TIME - timedelta(days=220 - i, hours=i % 9)
        body = f"""# {title} · 模拟版本 {i + 1:03d}

**适用品种**：{symbol}  
**核心结构**：{setup}  
**风险预算**：单笔账户权益的 {0.4 + (i % 5) * 0.1:.1f}%

## 入场条件

- 高周期方向与 EMA20/EMA50 排列一致
- 关键时段出现流动性扫取后产生位移
- 回踩失衡区或突破位时分批入场

## 退出规则

- 初始止损放在结构失效点外侧
- 达到 1R 后减仓，并将剩余仓位保护至成本附近
- 重大数据公布前不新增仓位

> 模拟数据：用于测试策略搜索、筛选和 Markdown 展示。
"""
        row = Strategy(
            id=strategy_id,
            user_id=user_id,
            title=f"{title} · 模拟 {i + 1:03d}",
            body=body,
            tags=json.dumps([symbol, setup, "模拟数据"], ensure_ascii=False),
            created_at=_iso(created),
            updated_at=_iso(created + timedelta(days=i % 17)),
        )
        inserted += _add_if_missing(session, Strategy, row)
    return ids, inserted


def _seed_journal(session, user_id: str, strategy_ids: list[str]) -> dict[str, int]:
    markets = [
        ("XAUUSD", "COMEX", 2380.0, 1.0),
        ("BTCUSD", "COINBASE", 98000.0, 0.08),
        ("NQ1!", "CME", 21800.0, 0.4),
        ("ES1!", "CME", 6000.0, 1.2),
        ("EURUSD", "FX", 1.085, 80000.0),
        ("USDJPY", "FX", 148.0, 600.0),
        ("NVDA", "NASDAQ", 145.0, 40.0),
        ("AAPL", "NASDAQ", 225.0, 35.0),
    ]
    tags = ["计划内", "突破", "回调", "FVG", "新闻行情", "减仓", "复仇交易", "高质量"]
    notes = [
        "等待确认后入场，执行符合计划。",
        "进场略早，下一次等待收线确认。",
        "分批止盈有效，尾仓按移动止损退出。",
        "波动放大时主动降低仓位，风险控制良好。",
        "错过首次机会后没有追价，等待二次回踩。",
    ]
    inserted_trades = 0
    daily_pnl: dict[str, list[float]] = {}
    for i in range(180):
        symbol, exchange, anchor, quantity = markets[i % len(markets)]
        direction = "long" if (i * 7) % 11 < 6 else "short"
        opened = BASE_TIME - timedelta(days=179 - i, hours=12 - (i % 10), minutes=(i * 13) % 60)
        is_open = i % 19 == 0
        closed = None if is_open else opened + timedelta(minutes=25 + (i * 17) % 430)
        drift = math.sin(i / 8) * 0.035 + (i - 90) * 0.00008
        open_price = anchor * (1 + drift)
        move_pct = max(-0.018, min(0.024, RNG.gauss(0.0022, 0.008)))
        signed_move = move_pct if direction == "long" else -move_pct
        close_price = None if is_open else open_price * (1 + signed_move)
        fees = round(max(0.6, abs(open_price * quantity) * 0.00004), 2)
        pnl = None
        if close_price is not None:
            raw_pnl = (close_price - open_price) * quantity
            if direction == "short":
                raw_pnl = -raw_pnl
            pnl = round(raw_pnl - fees, 2)
            daily_pnl.setdefault(opened.date().isoformat(), []).append(pnl)
        trade_id = _id(user_id, "trade", i)
        row = Trade(
            id=trade_id,
            user_id=user_id,
            symbol=symbol,
            direction=direction,
            open_price=round(open_price, 5),
            close_price=round(close_price, 5) if close_price is not None else None,
            quantity=quantity,
            open_time=_iso(opened),
            close_time=_iso(closed) if closed else None,
            fees=fees,
            pnl=pnl,
            tags=json.dumps([tags[i % len(tags)], "模拟数据"], ensure_ascii=False),
            notes=f"{notes[i % len(notes)]}（模拟交易 #{i + 1:03d}）",
            ai_review=(
                "结构识别清晰，风险暴露合理。建议继续记录入场前后的情绪变化。"
                if i % 3 == 0 else None
            ),
            exchange=exchange,
            source=["manual", "file_import", "recognition", "screenshot"][i % 4],
            strategy_id=strategy_ids[i % len(strategy_ids)],
            created_at=_iso(opened + timedelta(minutes=2)),
            updated_at=_iso((closed or opened) + timedelta(minutes=3)),
        )
        inserted_trades += _add_if_missing(session, Trade, row)

    inserted_reviews = 0
    for i in range(120):
        review_day = (BASE_TIME - timedelta(days=119 - i)).date()
        values = daily_pnl.get(review_day.isoformat(), [])
        day_total = sum(values)
        wins = sum(value > 0 for value in values)
        review_id = _id(user_id, "daily-review", i)
        created = datetime.combine(review_day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=22)
        body = f"""## 当日执行

- 完成交易 {len(values)} 笔，盈利交易 {wins} 笔
- 当日净盈亏：{day_total:+.2f}
- 主要关注开盘区间、流动性扫取与回踩确认

## 做得好的地方

按计划控制风险，没有因为连续盈亏改变单笔仓位。

## 下一交易日改进

减少低波动时段的尝试，入场前再次确认高周期方向。

_模拟复盘记录 {i + 1:03d}_
"""
        row = DailyReview(
            id=review_id,
            user_id=user_id,
            review_date=review_day.isoformat(),
            title=f"{review_day.isoformat()} 交易复盘（模拟）",
            body=body,
            tags=json.dumps(["日复盘", "纪律", "模拟数据"], ensure_ascii=False),
            created_at=_iso(created),
            updated_at=_iso(created + timedelta(minutes=20)),
        )
        inserted_reviews += _add_if_missing(session, DailyReview, row)

    if session.get(JournalSettings, user_id) is None:
        session.add(JournalSettings(user_id=user_id, starting_capital=100_000.0, updated_at=_iso(BASE_TIME)))

    return {"trades": inserted_trades, "daily_reviews": inserted_reviews}


def _backtest_result(index: int, symbol: str, direction: str) -> dict:
    trades = []
    equity_curve = []
    equity = 0.0
    for j in range(18 + index % 15):
        entry = BASE_TIME - timedelta(days=200 - j * 5 - index % 4)
        base = 100 + index * 0.2 + j * 0.35
        pnl = round(RNG.gauss(1.3, 2.7), 3)
        exit_price = base + pnl if direction == "long" else base - pnl
        equity += pnl
        trades.append({
            "direction": direction,
            "entry_price": round(base, 3),
            "exit_price": round(exit_price, 3),
            "entry_time": _iso(entry),
            "exit_time": _iso(entry + timedelta(hours=4 + j % 8)),
            "pnl": pnl,
        })
        equity_curve.append({"time": trades[-1]["exit_time"], "equity": round(equity, 3)})
    wins = [row["pnl"] for row in trades if row["pnl"] > 0]
    losses = [row["pnl"] for row in trades if row["pnl"] <= 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    peak = 0.0
    max_drawdown = 0.0
    for point in equity_curve:
        peak = max(peak, point["equity"])
        max_drawdown = max(max_drawdown, peak - point["equity"])
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    return {
        "symbol": symbol,
        "total_pnl": round(equity, 3),
        "total_trades": len(trades),
        "winners": len(wins),
        "win_rate": len(wins) / len(trades),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "max_drawdown": round(max_drawdown, 3),
        "sharpe_ratio": round(0.4 + (index % 18) * 0.11, 3),
        "avg_win": round(avg_win, 3),
        "avg_loss": round(avg_loss, 3),
        "win_loss_ratio": round(avg_win / abs(avg_loss), 3) if avg_loss else 0.0,
        "equity_curve": equity_curve,
        "trades": trades,
    }


def _seed_backtests(session, user_id: str) -> dict[str, int]:
    symbols = ["XAUUSD", "NQ1!", "ES1!", "BTCUSD", "EURUSD", "NVDA"]
    intervals = ["15", "60", "240", "D"]
    inserted_strategies = 0
    inserted_results = 0
    for i in range(120):
        symbol = symbols[i % len(symbols)]
        direction = "long" if i % 3 else "short"
        strategy_id = _id(user_id, "backtest-strategy", i)
        created = BASE_TIME - timedelta(days=240 - i)
        config = {
            "symbol": symbol,
            "interval": intervals[i % len(intervals)],
            "direction": direction,
            "entry_conditions": [{
                "left": {"type": "ema", "params": {"period": 10 + i % 5}},
                "operator": "cross_above" if direction == "long" else "cross_below",
                "right": {"type": "ema", "params": {"period": 30 + i % 10}},
            }],
            "exit_conditions": [{
                "left": {"type": "rsi", "params": {"period": 14}},
                "operator": ">" if direction == "long" else "<",
                "right": {"type": "value", "value": 68 if direction == "long" else 32},
            }],
            "stop_loss_pct": round(0.8 + (i % 6) * 0.2, 2),
            "take_profit_pct": round(1.6 + (i % 8) * 0.3, 2),
            "stop_loss": round(0.8 + (i % 6) * 0.2, 2),
            "take_profit": round(1.6 + (i % 8) * 0.3, 2),
            "lookback_months": 6 + i % 7,
        }
        strategy = BacktestStrategy(
            id=strategy_id,
            user_id=user_id,
            name=f"{symbol} {intervals[i % len(intervals)]}m 模拟回测 {i + 1:03d}",
            config=json.dumps(config, ensure_ascii=False),
            created_at=_iso(created),
            updated_at=_iso(created + timedelta(days=2)),
        )
        inserted_strategies += _add_if_missing(session, BacktestStrategy, strategy)
        session.flush()

        result = BacktestRun(
            id=_id(user_id, "backtest-result", i),
            strategy_id=strategy_id,
            user_id=user_id,
            strategy_name=strategy.name,
            strategy_config=strategy.config,
            status="completed",
            requested_date_from=(created - timedelta(days=180)).date().isoformat(),
            requested_date_to=created.date().isoformat(),
            actual_date_from=(created - timedelta(days=180)).date().isoformat(),
            actual_date_to=created.date().isoformat(),
            result=json.dumps(_backtest_result(i, symbol, direction), ensure_ascii=False),
            error=None,
            created_at=_iso(created + timedelta(hours=1)),
            started_at=_iso(created + timedelta(minutes=1)),
            completed_at=_iso(created + timedelta(hours=1)),
            updated_at=_iso(created + timedelta(hours=1)),
        )
        inserted_results += _add_if_missing(session, BacktestRun, result)
    return {"backtest_strategies": inserted_strategies, "backtest_runs": inserted_results}


def _seed_portfolios(session, user_id: str) -> dict[str, int]:
    portfolio_specs = [
        ("长期配置（模拟）", "CNY"),
        ("交易账户（模拟）", "USD"),
        ("家庭资产（模拟）", "CNY"),
        ("海外投资（模拟）", "USD"),
        ("退休计划（模拟）", "CNY"),
        ("高风险实验仓（模拟）", "USD"),
    ]
    asset_names = ["沪深300 ETF", "标普500 ETF", "黄金 ETF", "货币基金", "银行存款", "英伟达", "苹果", "比特币", "国债", "保险现金价值"]
    categories = ["证券", "证券", "实物资产", "现金", "现金", "证券", "证券", "其他", "证券", "保险/信托", "负债"]
    platforms = ["富途", "盈透证券", "招商银行", "支付宝", "Coinbase", "工商银行"]
    portfolio_ids: list[str] = []
    inserted_portfolios = 0
    for i, (name, currency) in enumerate(portfolio_specs):
        portfolio_id = _id(user_id, "portfolio", i)
        portfolio_ids.append(portfolio_id)
        created = BASE_TIME - timedelta(days=400 - i * 27)
        row = Portfolio(
            id=portfolio_id,
            user_id=user_id,
            name=name,
            currency=currency,
            created_at=_iso(created),
            updated_at=_iso(BASE_TIME - timedelta(days=i)),
        )
        inserted_portfolios += _add_if_missing(session, Portfolio, row)
    session.flush()

    inserted_entries = 0
    for i in range(180):
        category = categories[i % len(categories)]
        is_liability = category == "负债"
        name = (f"住房贷款分项 {i + 1:03d}" if is_liability else f"{asset_names[i % len(asset_names)]} 分项 {i + 1:03d}")
        amount = round((8_000 + (i * 7_919) % 420_000) * (0.8 + (i % 5) * 0.1), 2)
        updated = BASE_TIME - timedelta(days=179 - i, hours=i % 12)
        row = PortfolioEntry(
            id=_id(user_id, "portfolio-entry", i),
            portfolio_id=portfolio_ids[i % len(portfolio_ids)],
            name=name,
            category=category,
            platform=platforms[i % len(platforms)],
            amount=amount,
            notes=f"模拟资产记录 #{i + 1:03d}，用于测试筛选、排序与汇总。",
            created_at=_iso(updated - timedelta(days=60)),
            updated_at=_iso(updated),
        )
        inserted_entries += _add_if_missing(session, PortfolioEntry, row)
    return {"portfolios": inserted_portfolios, "portfolio_entries": inserted_entries}


def _seed_assistant(session, user_id: str) -> dict[str, int]:
    questions = [
        "总结我最近一个月的交易表现。",
        "找出亏损最多的品种并给出改进建议。",
        "我的多头和空头交易胜率有什么差异？",
        "帮我回顾今天的交易纪律。",
        "哪些策略最近表现更稳定？",
        "检查资产配置里是否有过高集中度。",
    ]
    answers = [
        "从模拟交易记录看，近期执行一致性有所提升。盈利主要来自顺势交易，建议继续控制逆势尝试的频率。",
        "亏损集中在波动扩张后的追价。可以把确认条件改为收线后回踩，并把单笔风险限制在账户权益的 0.5%。",
        "多空表现存在差异，但样本仍受行情阶段影响。建议按品种和时段拆分后再判断方向偏好。",
        "今日大部分交易遵循计划，主要改进点是减少低波动时段的频繁试单，并保留入场截图。",
        "趋势回调类策略的收益曲线更平滑，突破类策略回撤较大。下一步可比较相同风险预算下的期望值。",
        "当前证券类资产权重较高。可结合现金需求和最大回撤承受度，设置单一平台与单一品种的上限。",
    ]
    inserted_conversations = 0
    inserted_messages = 0
    for i in range(80):
        created = BASE_TIME - timedelta(days=79 - i, hours=i % 8)
        conversation_id = _id(user_id, "conversation", i)
        conversation = ChatConversation(
            id=conversation_id,
            user_id=user_id,
            title=f"{questions[i % len(questions)][:18]} · 模拟 {i + 1:03d}",
            created_at=_iso(created),
            updated_at=_iso(created + timedelta(minutes=3)),
            pending_state=None,
            pending_at=None,
        )
        inserted_conversations += _add_if_missing(session, ChatConversation, conversation)
        session.flush()
        user_message = ChatMessage(
            id=_id(user_id, "chat-message-user", i),
            conversation_id=conversation_id,
            role="user",
            content=f"{questions[i % len(questions)]}（模拟会话 #{i + 1:03d}）",
            created_at=_iso(created + timedelta(minutes=1)),
        )
        assistant_message = ChatMessage(
            id=_id(user_id, "chat-message-assistant", i),
            conversation_id=conversation_id,
            role="assistant",
            content=answers[i % len(answers)],
            created_at=_iso(created + timedelta(minutes=3)),
        )
        inserted_messages += _add_if_missing(session, ChatMessage, user_message)
        inserted_messages += _add_if_missing(session, ChatMessage, assistant_message)

    memory_templates = [
        "偏好等待关键位确认，不追第一波快速行情。",
        "单笔风险通常控制在账户权益的 0.5% 以内。",
        "主要交易时段是伦敦盘与纽约开盘后的两小时。",
        "连续亏损两笔后暂停交易并重新评估市场结构。",
        "更擅长黄金、纳指和比特币的日内趋势交易。",
        "希望复盘重点关注执行纪律、入场质量和持仓管理。",
    ]
    inserted_memories = 0
    for i in range(120):
        created = BASE_TIME - timedelta(days=160 - i)
        row = AssistantMemory(
            id=_id(user_id, "assistant-memory", i),
            user_id=user_id,
            content=f"{memory_templates[i % len(memory_templates)]}（模拟偏好 {i + 1:03d}）",
            created_at=_iso(created),
            updated_at=_iso(created + timedelta(days=i % 12)),
        )
        inserted_memories += _add_if_missing(session, AssistantMemory, row)
    return {
        "chat_conversations": inserted_conversations,
        "chat_messages": inserted_messages,
        "assistant_memories": inserted_memories,
    }


def _seed_radar_bookmarks(session, user_id: str) -> int:
    existing_item_ids = set(
        session.execute(
            select(FeedBookmark.feed_item_id).where(FeedBookmark.user_id == user_id)
        ).scalars()
    )
    needed = max(0, 150 - len(existing_item_ids))
    if needed == 0:
        return 0
    item_ids = session.execute(
        select(FeedItem.id)
        .where(FeedItem.id.not_in(existing_item_ids))
        .order_by(func.coalesce(FeedItem.published_at, FeedItem.fetched_at).desc())
        .limit(needed)
    ).scalars().all()
    inserted = 0
    for i, item_id in enumerate(item_ids):
        row = FeedBookmark(
            id=_id(user_id, "feed-bookmark", i),
            user_id=user_id,
            feed_item_id=item_id,
            created_at=_iso(BASE_TIME - timedelta(minutes=i * 17)),
        )
        inserted += _add_if_missing(session, FeedBookmark, row)
    return inserted


def _seed_automations(session, user_id: str) -> dict[str, int]:
    """Seed visible automation states without executing any workflow."""
    seeded_at = max(BASE_TIME, datetime.now(timezone.utc))
    task_specs = [
        {
            "name": "每日账户风险守卫（模拟）",
            "task_type": "risk_guardian",
            "status": "active",
            "schedule_kind": "daily",
            "schedule_config": {"time": "07:30"},
            "scope": {},
            "notification_config": {"enabled": True, "min_severity": "warning"},
        },
        {
            "name": "持仓资讯影响监控（模拟）",
            "task_type": "news_impact",
            "status": "active",
            "schedule_kind": "interval",
            "schedule_config": {"minutes": 30},
            "scope": {"symbols": ["XAUUSD", "NQ1!", "BTCUSD", "NVDA"]},
            "notification_config": {"enabled": True, "min_severity": "warning"},
        },
        {
            "name": "美股盘前事件雷达（模拟）",
            "task_type": "news_impact",
            "status": "paused",
            "schedule_kind": "daily",
            "schedule_config": {"time": "20:30"},
            "scope": {"symbols": ["NVDA", "AAPL", "TSLA"]},
            "notification_config": {"enabled": False, "min_severity": "info"},
        },
        {
            "name": "主要品种每小时行情播报（模拟）",
            "task_type": "market_watch",
            "status": "active",
            "schedule_kind": "interval",
            "schedule_config": {"minutes": 60},
            "scope": {"symbols": ["MNQ", "XAUUSD", "BTCUSD"], "interval": "1h"},
            "notification_config": {"enabled": True, "min_severity": "info"},
        },
        {
            "name": "NQ 波动条件监控（模拟）",
            "task_type": "condition_monitor",
            "status": "active",
            "schedule_kind": "interval",
            "schedule_config": {"minutes": 15},
            "scope": {
                "symbols": ["MNQ"],
                "interval": "15min",
                "condition_kind": "percent_change",
                "threshold": 1.0,
            },
            "notification_config": {"enabled": True, "min_severity": "warning"},
        },
        {
            "name": "美股收盘时段报告（模拟）",
            "task_type": "session_report",
            "status": "active",
            "schedule_kind": "daily",
            "schedule_config": {"time": "05:15"},
            "scope": {"symbols": ["SPY", "QQQ", "GLD"], "interval": "1day"},
            "notification_config": {"enabled": False, "min_severity": "info"},
        },
        {
            "name": "活跃交易计划守卫（模拟）",
            "task_type": "plan_guardian",
            "status": "paused",
            "schedule_kind": "interval",
            "schedule_config": {"minutes": 30},
            "scope": {"interval": "15min", "proximity_percent": 0.5},
            "notification_config": {"enabled": False, "min_severity": "warning"},
        },
    ]
    task_ids: list[str] = []
    inserted_tasks = 0
    for index, spec in enumerate(task_specs):
        task_id = _id(user_id, "automation-task", index)
        task_ids.append(task_id)
        created = BASE_TIME - timedelta(days=14 - index)
        row = AutomationTask(
            id=task_id,
            user_id=user_id,
            name=spec["name"],
            task_type=spec["task_type"],
            status=spec["status"],
            schedule_kind=spec["schedule_kind"],
            schedule_config=spec["schedule_config"],
            timezone="Asia/Shanghai",
            scope=spec["scope"],
            notification_config=spec["notification_config"],
            next_run_at=_iso(seeded_at + timedelta(minutes=30 + index * 15)),
            last_run_at=_iso(BASE_TIME - timedelta(minutes=20 + index * 10)),
            consecutive_failures=0,
            created_at=_iso(created),
            updated_at=_iso(BASE_TIME - timedelta(minutes=10 + index)),
        )
        inserted_tasks += _add_if_missing(session, AutomationTask, row)
    session.flush()

    inserted_runs = 0
    for task_index, task_id in enumerate(task_ids):
        for run_index in range(8):
            scheduled = BASE_TIME - timedelta(
                days=7 - run_index,
                minutes=task_index * 20,
            )
            status = "succeeded"
            if task_index == 0:
                summary = "未发现违反当前规则的风险。"
            elif task_index in {1, 2}:
                summary = "没有发现与当前交易上下文直接相关的新资讯。"
            elif task_index == 3:
                summary = (
                    f"行情快照：MNQ {20240 + run_index * 8} "
                    f"(+{0.18 + run_index * 0.03:.2f}%)；"
                    f"XAUUSD {2410 + run_index * 2} "
                    f"({-0.12 + run_index * 0.02:+.2f}%)；"
                    f"BTCUSD {66200 + run_index * 120} "
                    f"(+{0.35 + run_index * 0.04:.2f}%)"
                )
            elif task_index == 4:
                summary = "检查 1 个品种，发现 0 个条件已触发。"
            elif task_index == 5:
                summary = (
                    f"行情快照：SPY {548 + run_index * 0.6:.1f} "
                    f"(+{0.12 + run_index * 0.02:.2f}%)；"
                    f"QQQ {482 + run_index * 0.8:.1f} "
                    f"(+{0.18 + run_index * 0.03:.2f}%)；"
                    f"GLD {224 + run_index * 0.2:.1f} "
                    f"({-0.08 + run_index * 0.01:+.2f}%)；"
                    "未来 24 小时有 2 个重要经济事件。"
                )
            else:
                summary = "检查 3 个活跃交易计划，发现 1 个需要关注的变化。"
            error_code = None
            if task_index == 0 and run_index == 6:
                status = "partial"
                summary = "发现 2 个风险或数据问题。"
            elif task_index == 1 and run_index == 5:
                summary = "发现 3 条与当前交易上下文相关的资讯影响。"
            elif task_index == 2 and run_index == 3:
                status = "failed"
                summary = ""
                error_code = "demo_feed_temporarily_unavailable"
            row = AutomationRun(
                id=_id(user_id, "automation-run", task_index * 100 + run_index),
                task_id=task_id,
                user_id=user_id,
                trigger_kind="manual" if run_index == 0 else "scheduled",
                status=status,
                scheduled_for=_iso(scheduled),
                started_at=_iso(scheduled + timedelta(seconds=2)),
                finished_at=_iso(scheduled + timedelta(seconds=8)),
                lease_expires_at=None,
                input_as_of=_iso(scheduled),
                summary=summary,
                output={
                    "status": status,
                    "summary": summary,
                    "summary_en": (
                        "Scheduled simulated market report."
                        if task_index in {3, 5} else ""
                    ),
                    "output_kind": "report" if task_index in {3, 5} else "finding",
                    "evidence": (
                        [
                            {
                                "kind": "market_snapshot",
                                "symbol": symbol,
                                "price": price + run_index * step,
                                "percent_change": change + run_index * 0.03,
                                "provider": "demo",
                                "as_of": _iso(scheduled),
                            }
                            for symbol, price, step, change in (
                                (
                                    ("MNQ", 20240, 8, 0.18),
                                    ("XAUUSD", 2410, 2, -0.12),
                                    ("BTCUSD", 66200, 120, 0.35),
                                )
                                if task_index == 3 else
                                (
                                    ("SPY", 548, 0.6, 0.12),
                                    ("QQQ", 482, 0.8, 0.18),
                                    ("GLD", 224, 0.2, -0.08),
                                )
                            )
                        ]
                        if task_index in {3, 5} else []
                    ),
                    "metrics": {
                        "candidate_count": 18 + run_index,
                        "finding_count": 2 if status == "partial" else 0,
                    },
                    "demo": True,
                },
                error_code=error_code,
                created_at=_iso(scheduled),
            )
            inserted_runs += _add_if_missing(session, AutomationRun, row)
    session.flush()

    findings = [
        {
            "task": 0, "run": 6, "type": "risk", "severity": "critical", "status": "open",
            "title": "当日亏损已超过限制",
            "body": "已实现亏损为 2.35%，限制为 1.50%。建议暂停新增仓位并复盘最近三笔交易。",
            "subject_type": "account", "subject_id": "",
            "payload": {"rule_type": "max_daily_realized_loss_percent", "current": 2.35, "threshold": 1.5},
        },
        {
            "task": 0, "run": 6, "type": "risk", "severity": "warning", "status": "open",
            "title": "总计划风险已超过限制",
            "body": "未平仓交易与活跃计划合计风险为 3.40%，限制为 2.50%。",
            "subject_type": "account", "subject_id": "",
            "payload": {"rule_type": "max_total_open_risk_percent", "current": 3.4, "threshold": 2.5},
        },
        {
            "task": 0, "run": 6, "type": "data_quality", "severity": "warning", "status": "open",
            "title": "XAUUSD 风险数据不完整",
            "body": "该未平仓记录缺少止损，暂时无法确定真实风险。",
            "subject_type": "trade", "subject_id": _id(user_id, "trade", 0),
            "payload": {"missing_fields": ["stop_loss"]},
        },
        {
            "task": 0, "run": 5, "type": "risk", "severity": "warning", "status": "acknowledged",
            "title": "连续亏损达到冷静期阈值",
            "body": "连续亏损 3 笔，已确认并进入冷静期。",
            "subject_type": "account", "subject_id": "",
            "payload": {"rule_type": "max_consecutive_losses", "current": 3, "threshold": 3},
        },
        {
            "task": 0, "run": 4, "type": "risk", "severity": "info", "status": "resolved",
            "title": "当日交易次数曾超过限制",
            "body": "该问题已在下一个交易日自动恢复。",
            "subject_type": "account", "subject_id": "",
            "payload": {"rule_type": "max_trades_per_day", "current": 7, "threshold": 6},
        },
        {
            "task": 1, "run": 5, "type": "news", "severity": "warning", "status": "open",
            "title": "NQ1! 出现相关宏观资讯",
            "body": "美联储官员讲话可能放大美股指数短线波动，请核对止损与事件窗口。",
            "subject_type": "watch", "subject_id": "NQ1",
            "payload": {"materiality": "watch", "direction": "unknown", "confidence": 0.72, "symbol": "NQ1!"},
        },
        {
            "task": 1, "run": 5, "type": "news", "severity": "warning", "status": "open",
            "title": "BTCUSD 出现 ETF 资金流资讯",
            "body": "现货 ETF 单日资金流明显变化，可能影响比特币短线波动与流动性。",
            "subject_type": "watch", "subject_id": "BTCUSD",
            "payload": {"materiality": "watch", "direction": "unknown", "confidence": 0.68, "symbol": "BTCUSD"},
        },
        {
            "task": 1, "run": 5, "type": "news", "severity": "info", "status": "acknowledged",
            "title": "XAUUSD 出现通胀数据前瞻",
            "body": "市场正在调整对通胀数据的预期，当前仅列为观察事项。",
            "subject_type": "watch", "subject_id": "XAUUSD",
            "payload": {"materiality": "watch", "direction": "unknown", "confidence": 0.58, "symbol": "XAUUSD"},
        },
        {
            "task": 2, "run": 2, "type": "news", "severity": "warning", "status": "resolved",
            "title": "NVDA 财报事件窗口",
            "body": "财报发布窗口已经结束，该资讯影响已自动过期。",
            "subject_type": "watch", "subject_id": "NVDA",
            "payload": {"materiality": "material", "direction": "unknown", "confidence": 0.81, "symbol": "NVDA"},
        },
        {
            "task": 4, "run": 7, "type": "market", "severity": "warning", "status": "open",
            "title": "MNQ 波动达到监控条件",
            "body": "当前 15 分钟涨跌幅为 +1.18%，监控阈值为 1.00%。",
            "subject_type": "symbol", "subject_id": "MNQ",
            "payload": {
                "condition_kind": "percent_change",
                "current": 1.18,
                "threshold": 1.0,
                "symbol": "MNQ",
            },
        },
        {
            "task": 6, "run": 7, "type": "plan", "severity": "warning", "status": "open",
            "title": "AAPL 接近计划入场价",
            "body": "当前价格距离计划入场价约 0.32%，请重新核对入场条件。",
            "subject_type": "plan", "subject_id": _id(user_id, "trade-plan", 0),
            "payload": {
                "condition": "entry",
                "distance_percent": 0.32,
                "symbol": "AAPL",
            },
        },
    ]
    inserted_findings = 0
    for index, spec in enumerate(findings):
        observed = BASE_TIME - timedelta(hours=len(findings) - index)
        resolved_at = _iso(observed + timedelta(hours=2)) if spec["status"] == "resolved" else None
        row = AgentFinding(
            id=_id(user_id, "agent-finding", index),
            user_id=user_id,
            task_id=task_ids[spec["task"]],
            run_id=_id(user_id, "automation-run", spec["task"] * 100 + spec["run"]),
            finding_type=spec["type"],
            severity=spec["severity"],
            status=spec["status"],
            fingerprint=f"demo:{spec['type']}:{user_id}:{index}",
            subject_type=spec["subject_type"],
            subject_id=spec["subject_id"],
            title=spec["title"],
            body=spec["body"],
            evidence=[{
                "kind": "demo_snapshot",
                "as_of": _iso(observed),
                "source": "seed_test_user_data",
                "notice": "模拟数据，仅用于界面演示",
            }],
            payload={**spec["payload"], "demo": True},
            first_seen_at=_iso(observed - timedelta(minutes=30)),
            last_seen_at=_iso(observed),
            resolved_at=resolved_at,
            expires_at=_iso(BASE_TIME + timedelta(days=2)) if spec["type"] == "news" else None,
            created_at=_iso(observed - timedelta(minutes=30)),
            updated_at=resolved_at or _iso(observed),
        )
        inserted_findings += _add_if_missing(session, AgentFinding, row)

    rule_specs = [
        ("单日最大亏损 1.5%", "max_daily_realized_loss_percent", 1.5, "critical"),
        ("总风险上限 2.5%", "max_total_open_risk_percent", 2.5, "critical"),
        ("连续亏损 3 笔后暂停", "max_consecutive_losses", 3, "important"),
        ("每日最多 6 笔交易", "max_trades_per_day", 6, "important"),
        ("未平仓交易必须设置止损", "require_stop_loss", 0, "critical"),
    ]
    inserted_rules = 0
    for index, (name, rule_type, threshold, weight) in enumerate(rule_specs):
        row = TradingRule(
            id=_id(user_id, "automation-rule", index),
            user_id=user_id,
            name=f"{name}（模拟）",
            rule_type=rule_type,
            threshold=threshold,
            weight=weight,
            active=1,
            created_at=_iso(BASE_TIME - timedelta(days=30)),
            updated_at=_iso(BASE_TIME),
        )
        inserted_rules += _add_if_missing(session, TradingRule, row)

    return {
        "automation_tasks": inserted_tasks,
        "automation_runs": inserted_runs,
        "agent_findings": inserted_findings,
        "trading_rules": inserted_rules,
    }


def _counts(session, user_id: str) -> dict[str, int]:
    return {
        "交易": session.scalar(select(func.count()).select_from(Trade).where(Trade.user_id == user_id)),
        "每日复盘": session.scalar(select(func.count()).select_from(DailyReview).where(DailyReview.user_id == user_id)),
        "策略": session.scalar(select(func.count()).select_from(Strategy).where(Strategy.user_id == user_id)),
        "回测策略": session.scalar(select(func.count()).select_from(BacktestStrategy).where(BacktestStrategy.user_id == user_id)),
        "回测结果": session.scalar(select(func.count()).select_from(BacktestRun).where(BacktestRun.user_id == user_id)),
        "资产组合": session.scalar(select(func.count()).select_from(Portfolio).where(Portfolio.user_id == user_id)),
        "资产条目": session.scalar(
            select(func.count()).select_from(PortfolioEntry).join(Portfolio).where(Portfolio.user_id == user_id)
        ),
        "助手会话": session.scalar(select(func.count()).select_from(ChatConversation).where(ChatConversation.user_id == user_id)),
        "助手消息": session.scalar(
            select(func.count()).select_from(ChatMessage).join(ChatConversation).where(ChatConversation.user_id == user_id)
        ),
        "助手记忆": session.scalar(select(func.count()).select_from(AssistantMemory).where(AssistantMemory.user_id == user_id)),
        "雷达收藏": session.scalar(select(func.count()).select_from(FeedBookmark).where(FeedBookmark.user_id == user_id)),
        "自动化任务": session.scalar(select(func.count()).select_from(AutomationTask).where(AutomationTask.user_id == user_id)),
        "自动化运行": session.scalar(select(func.count()).select_from(AutomationRun).where(AutomationRun.user_id == user_id)),
        "Agent 发现": session.scalar(select(func.count()).select_from(AgentFinding).where(AgentFinding.user_id == user_id)),
        "风险规则": session.scalar(select(func.count()).select_from(TradingRule).where(TradingRule.user_id == user_id)),
    }


def main() -> int:
    email = sys.argv[1].strip() if len(sys.argv) > 1 else "demo@example.com"
    with SessionLocal() as session:
        user = session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        ).scalar_one_or_none()
        if user is None:
            print(f"User not found: {email}", file=sys.stderr)
            return 1

        try:
            strategy_ids, strategy_count = _seed_strategies(session, user.id)
            changes = {"strategies": strategy_count}
            session.flush()
            changes.update(_seed_journal(session, user.id, strategy_ids))
            changes.update(_seed_backtests(session, user.id))
            changes.update(_seed_portfolios(session, user.id))
            changes.update(_seed_assistant(session, user.id))
            changes["feed_bookmarks"] = _seed_radar_bookmarks(session, user.id)
            changes.update(_seed_automations(session, user.id))
            session.commit()
        except Exception:
            session.rollback()
            raise

        print(f"Seeded data for {user.name} <{user.email}> ({user.id})")
        print("Inserted:")
        for name, count in changes.items():
            print(f"  {name}: {count}")
        print("Current totals:")
        for name, count in _counts(session, user.id).items():
            print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

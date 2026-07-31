"""One-shot: seed a few strategies for the Zayn test user.

Run from backend/:
    ./.venv/bin/python scripts/seed_strategies_zayn.py
"""
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal  # noqa: E402
from models import Strategy, User  # noqa: E402

USER_ID = "4d3b0351-8bf1-48e8-ac8d-2264945ce9e6"
SAMPLE_ASSET_ID = "691d1a03-216f-4823-9298-fa01e1bf9e06"  # one of Zayn's MGC screenshots


STRATEGIES = [
    {
        "title": "黄金日内趋势回调（High 2 狙击版）",
        "tags": ["XAUUSD", "趋势回调", "intraday"],
        "body": """**核心逻辑**：放弃完美的"三推结构"，在 High 2（第二个高点）出现弱势确认时提前进场。用高胜率的小波段（吃到 Fibo 0.382）来积累利润，并通过减仓来博弈后续跌幅。

# 1. 寻找交易机会（Setup）

- 时间窗口：伦敦 + 纽约重叠时段（北京 21:00~24:00）
- 趋势确认：H4 EMA20 < EMA50，且 H1 收阴
- 入场触发：M15 出现 High 2 失败 + 量能背离

# 2. 入场与仓位

- 仓位：单笔 0.5%~0.8% 风险
- 止损：High 2 顶 + 1 ATR(M15)
- 止盈分批：0.382（50% 平仓）→ 0.618（30%）→ 1.0（剩余 20% 移动止损）

# 3. 退出与复盘

- 若 0.382 未达成且 K 线收回 EMA20，平仓离场
- 复盘要点：是否提前进场、止损是否合理、是否过早离场
""",
    },
    {
        "title": "XAUUSD 跨市场相关性权重表",
        "tags": ["XAUUSD", "相关性", "macro"],
        "body": """每日盘前快速估值的权重锚。任一指标偏离趋势 > 1σ 时单独标注。

| 维度       | 标的         | 权重 | 方向 |
|------------|--------------|------|------|
| 美元强弱   | DXY          | 40%  | 反向 |
| 实际利率   | TIPS 10Y     | 25%  | 反向 |
| 风险偏好   | VIX          | 15%  | 同向 |
| 通胀预期   | Breakeven 10Y| 10%  | 同向 |
| 央行流动性 | Fed RRP      | 10%  | 反向 |

权重每月一次校准（用 60 日滚动相关性回归）。
""",
    },
    {
        "title": "Pip vs Tick (Point) 实战换算",
        "tags": ["基础", "MT4", "scaling"],
        "body": """这是你在 MT4 上设置止损止盈时最容易晕的地方，因为 MT4 的距离通常是用 Points (Ticks) 算的，而不是 Pips。

- 1 pip = 10 points（5 位报价）
- XAUUSD: 1 pip = 0.1，1 point = 0.01
- 设止损 200 points → 实际 20 pips → 黄金 \\$2.0

**口诀**：MT4 看到的距离数字 ÷ 10 才是 pip 数。账户参数面板写的 Stop Level 是 points。
""",
    },
    {
        "title": "DXY 美元指数定义与读法",
        "tags": ["DXY", "macro", "reference"],
        "body": """## 一、美元指数（DXY）的定义

美元指数（U.S. Dollar Index，简称 DXY）是用来衡量美元相对于一篮子主要货币的总体强弱的综合指数。

## 二、构成

- 欧元 EUR：57.6%
- 日元 JPY：13.6%
- 英镑 GBP：11.9%
- 加元 CAD：9.1%
- 瑞典克朗 SEK：4.2%
- 瑞士法郎 CHF：3.6%

## 三、读法

DXY 上升 → 美元升值 → 黄金通常承压。但当 DXY 与黄金同向上涨时，往往说明避险情绪在主导（典型如 2022 年 H1）。
""",
    },
    {
        "title": "K 线截图复盘示例",
        "tags": ["复盘", "image", "MGC"],
        "body": f"""![黄金 H4](/api/uploads/{SAMPLE_ASSET_ID})

# 这笔交易的关键节点

- 入场：H4 跌破 EMA20 后回撤不破前低，M15 出现 High 2
- 止损：30 points（按 200 倍杠杆 0.5% 风险）
- 止盈：1:2.5 RR，收割于伦敦尾盘

**反思**：进场偏早 5 根 K 线，导致初期承担了 1/3 ATR 的浮亏。下次等 M15 收阴后再开仓。
""",
    },
]


def main() -> int:
    session = SessionLocal()
    try:
        user = session.get(User, USER_ID)
        if user is None:
            print(f"User {USER_ID} not found", file=sys.stderr)
            return 1
        print(f"Seeding strategies for: {user.name} ({user.id})")

        base = datetime.now(timezone.utc)
        inserted = 0
        for offset, s in enumerate(STRATEGIES):
            # Spread updated_at across recent days so RelativeTime shows variety.
            ts = (base - timedelta(hours=offset * 6)).isoformat()
            session.add(
                Strategy(
                    id=str(uuid.uuid4()),
                    user_id=USER_ID,
                    title=s["title"],
                    body=s["body"],
                    tags=json.dumps(s["tags"], ensure_ascii=False),
                    created_at=ts,
                    updated_at=ts,
                )
            )
            inserted += 1
            print(f"  + {s['title']}")

        session.commit()
        print(f"Inserted {inserted} strategies.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())

"""Persist canonical market series IDs.

Revision ID: market02_canonical_series_ids
Revises: market01_market_candle_cache
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "market02_canonical_series_ids"
down_revision: Union[str, None] = "market01_market_candle_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _compact(column: str) -> str:
    return (
        f"replace(replace(replace(upper({column}), '/', ''), '-', ''), '_', '')"
    )


def upgrade() -> None:
    op.add_column("trades", sa.Column("series_id", sa.String(), nullable=True))
    op.create_index("idx_trades_series_id", "trades", ["series_id"])
    op.add_column("trade_plans", sa.Column("series_id", sa.String(), nullable=True))
    op.create_index(
        "idx_trade_plans_series_id",
        "trade_plans",
        ["series_id"],
    )

    trade_symbol = _compact("symbol")
    plan_symbol = _compact("symbol")
    verified = {
        "XAUUSD": ("series:spot:xau-usd:consolidated", "forex"),
        "XAGUSD": ("series:spot:xag-usd:consolidated", "forex"),
        "EURUSD": ("series:spot:eur-usd:consolidated", "forex"),
        "GBPUSD": ("series:spot:gbp-usd:consolidated", "forex"),
        "USDJPY": ("series:spot:usd-jpy:consolidated", "forex"),
        "NQ": ("series:futures:nq:front", "futures"),
        "MNQ": ("series:futures:mnq:front", "futures"),
        "ES": ("series:futures:es:front", "futures"),
        "MES": ("series:futures:mes:front", "futures"),
        "GC": ("series:futures:gc:front", "futures"),
        "MGC": ("series:futures:mgc:front", "futures"),
        "AAPL": ("series:equity:aapl:xnas", "stock"),
        "TSLA": ("series:equity:tsla:xnas", "stock"),
        "SPY": ("series:equity:spy:arcx", "stock"),
        "QQQ": ("series:equity:qqq:arcx", "stock"),
        "GLD": ("series:equity:gld:arcx", "stock"),
        "SPX500": ("series:index:spx500:consolidated", None),
    }
    for symbol, (series_id, plan_market) in verified.items():
        op.execute(
            sa.text(
                f"UPDATE trades SET series_id = :series_id "
                f"WHERE series_id IS NULL AND {trade_symbol} = :symbol"
            ).bindparams(series_id=series_id, symbol=symbol),
        )
        if plan_market is not None:
            op.execute(
                sa.text(
                    f"UPDATE trade_plans SET series_id = :series_id "
                    f"WHERE series_id IS NULL AND {plan_symbol} = :symbol "
                    "AND lower(market) = :market"
                ).bindparams(
                    series_id=series_id,
                    symbol=symbol,
                    market=plan_market,
                ),
            )

    crypto = {
        ("BTCUSD", "COINBASE"): "series:crypto:btc-usd:coinbase",
        ("BTCUSD", "BINANCE"): "series:crypto:btc-usd:binance",
        ("ETHUSD", "COINBASE"): "series:crypto:eth-usd:coinbase",
        ("ETHUSD", "BINANCE"): "series:crypto:eth-usd:binance",
    }
    for (symbol, exchange), series_id in crypto.items():
        op.execute(
            sa.text(
                f"UPDATE trades SET series_id = :series_id "
                f"WHERE series_id IS NULL AND {trade_symbol} = :symbol "
                "AND upper(exchange) = :exchange"
            ).bindparams(
                series_id=series_id,
                symbol=symbol,
                exchange=exchange,
            ),
        )


def downgrade() -> None:
    op.drop_index("idx_trade_plans_series_id", table_name="trade_plans")
    op.drop_column("trade_plans", "series_id")
    op.drop_index("idx_trades_series_id", table_name="trades")
    op.drop_column("trades", "series_id")

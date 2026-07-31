"""Persist canonical Instrument IDs in feed tags.

Revision ID: market03_feed_instrument_ids
Revises: market02_canonical_series_ids
"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "market03_feed_instrument_ids"
down_revision: Union[str, None] = "market02_canonical_series_ids"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_LEGACY_TO_CANONICAL = {
    "COINBASE:BTCUSD": "instrument:crypto:btc-usd",
    "COINBASE:ETHUSD": "instrument:crypto:eth-usd",
    "OANDA:XAUUSD": "instrument:spot:xau-usd",
    "OANDA:XAGUSD": "instrument:spot:xag-usd",
    "TVC:USOIL": "instrument:commodity:wti",
    "OANDA:EURUSD": "instrument:spot:eur-usd",
    "OANDA:USDJPY": "instrument:spot:usd-jpy",
    "NASDAQ:NDX": "instrument:index:ndx",
    "SP:SPX": "instrument:index:spx500",
}


def _rewrite_symbols(mapping: dict[str, str]) -> None:
    feed_items = sa.table(
        "feed_items",
        sa.column("id", sa.String()),
        sa.column("symbols", sa.JSON()),
    )
    connection = op.get_bind()
    rows = list(
        connection.execute(
            sa.select(feed_items.c.id, feed_items.c.symbols),
        ).mappings(),
    )
    for row in rows:
        values = row["symbols"] or []
        if isinstance(values, str):
            values = json.loads(values)
        migrated = list(dict.fromkeys(mapping.get(value, value) for value in values))
        if migrated != values:
            connection.execute(
                sa.update(feed_items)
                .where(feed_items.c.id == row["id"])
                .values(symbols=migrated),
            )


def upgrade() -> None:
    _rewrite_symbols(_LEGACY_TO_CANONICAL)


def downgrade() -> None:
    _rewrite_symbols({
        canonical: legacy
        for legacy, canonical in _LEGACY_TO_CANONICAL.items()
    })

"""Add persistent market candle cache.

Revision ID: market01_market_candle_cache
Revises: mfa01_account_mfa
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "market01_market_candle_cache"
down_revision: Union[str, None] = "mfa01_account_mfa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_candles",
        sa.Column("provider_id", sa.String(), nullable=False),
        sa.Column("series_id", sa.String(), nullable=False),
        sa.Column("timeframe", sa.String(), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "provider_id",
            "series_id",
            "timeframe",
            "open_time",
        ),
    )
    op.create_index(
        "idx_market_candles_lookup",
        "market_candles",
        ["provider_id", "series_id", "timeframe", "open_time"],
        unique=False,
    )

    op.create_table(
        "market_candle_coverage",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("provider_id", sa.String(), nullable=False),
        sa.Column("series_id", sa.String(), nullable=False),
        sa.Column("instrument_id", sa.String(), nullable=False),
        sa.Column("listing_id", sa.String(), nullable=True),
        sa.Column("timeframe", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("requested_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_symbol", sa.String(), nullable=False),
        sa.Column("provider_exchange", sa.String(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quality_status", sa.String(), nullable=False),
        sa.Column(
            "quality_warnings",
            sa.Text(),
            server_default="[]",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id",
            "series_id",
            "timeframe",
            "purpose",
            "requested_start",
            "requested_end",
            name="uq_market_candle_coverage_request",
        ),
    )
    op.create_index(
        "idx_market_candle_coverage_lookup",
        "market_candle_coverage",
        [
            "provider_id",
            "series_id",
            "timeframe",
            "purpose",
            "requested_start",
            "requested_end",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_market_candle_coverage_lookup",
        table_name="market_candle_coverage",
    )
    op.drop_table("market_candle_coverage")
    op.drop_index("idx_market_candles_lookup", table_name="market_candles")
    op.drop_table("market_candles")

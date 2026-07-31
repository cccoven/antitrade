"""feed tables

Revision ID: feed01_feed_tables
Revises: 7438d7eaf40e
Create Date: 2026-07-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "feed01_feed_tables"
down_revision: Union[str, None] = "7438d7eaf40e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feed_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("url", sa.String(), nullable=False, unique=True),
        sa.Column("source_key", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_at", sa.String(), nullable=True),
        sa.Column("fetched_at", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False, server_default="general"),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("lang", sa.String(), nullable=False, server_default="en"),
    )
    op.create_index("idx_feed_items_published", "feed_items", [sa.text("published_at DESC")])
    op.create_index("idx_feed_items_category", "feed_items", ["category"])
    op.create_index("idx_feed_items_source", "feed_items", ["source_key"])

    op.create_table(
        "feed_briefings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("generated_at", sa.String(), nullable=False),
        sa.Column("lang", sa.String(), nullable=False),
        sa.Column("window", sa.String(), nullable=False, server_default="6h"),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(), nullable=False, server_default=""),
    )
    op.create_index("idx_feed_briefings_lang_generated", "feed_briefings",
                    ["lang", sa.text("generated_at DESC")])

    op.create_table(
        "feed_bookmarks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("feed_item_id", sa.String(),
                  sa.ForeignKey("feed_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("user_id", "feed_item_id", name="uq_feed_bookmarks_user_item"),
    )
    op.create_index("idx_feed_bookmarks_user", "feed_bookmarks", ["user_id"])


def downgrade() -> None:
    op.drop_table("feed_bookmarks")
    op.drop_table("feed_briefings")
    op.drop_table("feed_items")

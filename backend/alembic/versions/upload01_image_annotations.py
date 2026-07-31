"""Persist point-and-click notes for uploaded images.

Revision ID: upload01_image_annotations
Revises: market04_dashboard_snapshots
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "upload01_image_annotations"
down_revision: Union[str, None] = "market04_dashboard_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "image_annotations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column("x_ratio", sa.Float(), nullable=False),
        sa.Column("y_ratio", sa.Float(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "x_ratio >= 0 AND x_ratio <= 1",
            name="ck_image_annotations_x_ratio",
        ),
        sa.CheckConstraint(
            "y_ratio >= 0 AND y_ratio <= 1",
            name="ck_image_annotations_y_ratio",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["uploaded_assets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_id",
            "sort_order",
            name="uq_image_annotations_asset_order",
        ),
    )
    op.create_index(
        "idx_image_annotations_asset_id",
        "image_annotations",
        ["asset_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_image_annotations_asset_id",
        table_name="image_annotations",
    )
    op.drop_table("image_annotations")

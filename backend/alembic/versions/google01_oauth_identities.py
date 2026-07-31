"""store external OAuth identities

Revision ID: google01_oauth_identities
Revises: upload01_image_annotations
Create Date: 2026-07-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "google01_oauth_identities"
down_revision: Union[str, None] = "upload01_image_annotations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "password_set",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.create_table(
        "user_oauth_identities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "subject",
            name="uq_user_oauth_provider_subject",
        ),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            name="uq_user_oauth_user_provider",
        ),
    )
    op.create_index(
        "idx_user_oauth_identities_user",
        "user_oauth_identities",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_user_oauth_identities_user",
        table_name="user_oauth_identities",
    )
    op.drop_table("user_oauth_identities")
    op.drop_column("users", "password_set")

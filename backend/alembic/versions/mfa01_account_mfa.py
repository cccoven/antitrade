"""Add account TOTP MFA, recovery codes, and login challenges.

Revision ID: mfa01_account_mfa
Revises: agent02_market_agent_types
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "mfa01_account_mfa"
down_revision: Union[str, None] = "agent02_market_agent_types"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False),
    )

    op.create_table(
        "user_mfa_factors",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("factor_type", sa.String(), server_default="totp", nullable=False),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("last_used_step", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("enabled_at", sa.String(), nullable=True),
        sa.CheckConstraint(
            "factor_type IN ('totp')",
            name="ck_user_mfa_factors_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','enabled')",
            name="ck_user_mfa_factors_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "factor_type",
            name="uq_user_mfa_factors_user_type",
        ),
    )
    op.create_index(
        "idx_user_mfa_factors_user_status",
        "user_mfa_factors",
        ["user_id", "status"],
        unique=False,
    )

    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("used_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(
        "idx_mfa_recovery_codes_user_unused",
        "mfa_recovery_codes",
        ["user_id", "used_at"],
        unique=False,
    )

    op.create_table(
        "mfa_login_challenges",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.String(), nullable=False),
        sa.Column("attempts_remaining", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("consumed_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "idx_mfa_login_challenges_user_expires",
        "mfa_login_challenges",
        ["user_id", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_mfa_login_challenges_user_expires",
        table_name="mfa_login_challenges",
    )
    op.drop_table("mfa_login_challenges")
    op.drop_index(
        "idx_mfa_recovery_codes_user_unused",
        table_name="mfa_recovery_codes",
    )
    op.drop_table("mfa_recovery_codes")
    op.drop_index(
        "idx_user_mfa_factors_user_status",
        table_name="user_mfa_factors",
    )
    op.drop_table("user_mfa_factors")
    op.drop_column("users", "auth_version")

"""seed preset portfolio categories

Revision ID: e855069e4529
Revises: 297a3c541635
Create Date: 2026-06-29 15:22:29.832369

"""
from typing import Sequence, Union

import uuid
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e855069e4529'
down_revision: Union[str, None] = '297a3c541635'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    presets = [
        ("证券", "asset", 10), ("现金", "asset", 20), ("保险/信托", "asset", 40),
        ("实物资产", "asset", 50), ("其他", "asset", 60), ("负债", "liability", 70),
    ]
    t = sa.table(
        "portfolio_categories",
        sa.column("id", sa.String), sa.column("user_id", sa.String),
        sa.column("name", sa.String), sa.column("kind", sa.String),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(t, [
        {"id": str(uuid.uuid4()), "user_id": None, "name": n, "kind": k, "sort_order": o}
        for (n, k, o) in presets
    ])


def downgrade() -> None:
    op.execute("DELETE FROM portfolio_categories WHERE user_id IS NULL")

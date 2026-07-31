"""pgvector rag

Revision ID: 7438d7eaf40e
Revises: e855069e4529
Create Date: 2026-06-29 23:58:30.727507

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '7438d7eaf40e'
down_revision: Union[str, None] = 'e855069e4529'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "strategy_embeddings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("strategy_id", sa.String(), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_strategy_embeddings_user", "strategy_embeddings", ["user_id"])
    op.create_index("idx_strategy_embeddings_strategy", "strategy_embeddings", ["strategy_id"])
    op.execute("CREATE INDEX idx_strategy_embeddings_hnsw ON strategy_embeddings USING hnsw (embedding vector_cosine_ops)")
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_knowledge_chunks_source", "knowledge_chunks", ["source"])
    op.execute("CREATE INDEX idx_knowledge_chunks_hnsw ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_table("strategy_embeddings")

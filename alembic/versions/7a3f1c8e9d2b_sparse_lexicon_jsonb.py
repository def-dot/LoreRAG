"""sparse_lexicon jsonb

Revision ID: 7a3f1c8e9d2b
Revises: 55231b806db4
Create Date: 2026-05-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

# revision identifiers, used by Alembic.
revision: str = "7a3f1c8e9d2b"
down_revision: Union[str, Sequence[str], None] = "55231b806db4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 删除旧的 TSVECTOR 列
    op.drop_column("document_chunks", "sparse_vector")

    # 2. 添加 JSONB 列存储 BGE-M3 稀疏词权重
    op.add_column("document_chunks", sa.Column("sparse_lexicon", JSONB, nullable=True))

    # 3. HNSW 索引加速稠密向量 cosine 检索
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_dense_vector "
        "ON document_chunks USING hnsw (dense_vector vector_cosine_ops);"
    )

    # 4. GIN 索引加速 JSONB ?| 等稀疏词权重查询
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_sparse_lexicon "
        "ON document_chunks USING gin (sparse_lexicon);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_sparse_lexicon;")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_dense_vector;")
    op.drop_column("document_chunks", "sparse_lexicon")
    op.add_column("document_chunks", sa.Column("sparse_vector", TSVECTOR, nullable=True))

"""replace sparse_lexicon with tsvector + zhparser

Revision ID: d5e7f9a1b2c3
Revises: c4d2e6f8a9b1
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd5e7f9a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c4d2e6f8a9b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 tsv_content tsvector 列, 创建 GIN 索引和触发器, 删除 sparse_lexicon"""

    # 0. 确保 zhparser 扩展和 chinese 文本搜索配置已注册（幂等）
    op.execute("CREATE EXTENSION IF NOT EXISTS zhparser")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'chinese') THEN
                CREATE TEXT SEARCH CONFIGURATION chinese (PARSER = zhparser);
                ALTER TEXT SEARCH CONFIGURATION chinese
                    ADD MAPPING FOR n,v,a,i,e,l WITH simple;
            END IF;
        END
        $$;
    """)

    # 1. 添加 tsv_content 列 (tsvector 类型)
    op.add_column(
        'document_chunks',
        sa.Column('tsv_content', postgresql.TSVECTOR(), nullable=True),
    )

    # 2. 创建 GIN 索引加速全文检索
    op.create_index(
        'ix_document_chunks_tsv_content',
        'document_chunks',
        ['tsv_content'],
        postgresql_using='gin',
    )

    # 3. 创建触发器: INSERT/UPDATE 时自动用 zhparser 中文分词填充 tsv_content
    op.execute("""
        CREATE TRIGGER tsvectorupdate
        BEFORE INSERT OR UPDATE ON document_chunks
        FOR EACH ROW EXECUTE FUNCTION
        tsvector_update_trigger(tsv_content, 'pg_catalog.chinese', raw_content)
    """)

    # 4. 删除不再使用的 sparse_lexicon 列
    op.drop_column('document_chunks', 'sparse_lexicon')


def downgrade() -> None:
    """回滚: 恢复 sparse_lexicon, 删除触发器和 tsv_content 列"""

    # 1. 恢复 sparse_lexicon 列
    op.add_column(
        'document_chunks',
        sa.Column('sparse_lexicon', postgresql.JSONB(), nullable=True),
    )

    # 2. 删除触发器
    op.execute("DROP TRIGGER IF EXISTS tsvectorupdate ON document_chunks")

    # 3. 删除 GIN 索引
    op.drop_index(
        'ix_document_chunks_tsv_content',
        table_name='document_chunks',
        postgresql_using='gin',
    )

    # 4. 删除 tsv_content 列
    op.drop_column('document_chunks', 'tsv_content')

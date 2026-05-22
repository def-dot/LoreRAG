"""DocumentChunk 模型 — pgvector 向量检索 + TSVECTOR 全文检索"""

from pgvector.sqlalchemy import VECTOR  # type: ignore[import-untyped]
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER, TSVECTOR
from sqlmodel import Field, SQLModel

from app.core.config import settings


class DocumentChunk(SQLModel, table=True):
    __tablename__ = "document_chunks"

    id: int | None = Field(default=None, primary_key=True)
    file_name: str | None = Field(default=None, max_length=255)

    page_numbers: list[int] | None = Field(default=None, sa_type=ARRAY(INTEGER))  # type: ignore[call-overload]
    heading_context: str | None = Field(default=None, sa_type=Text)
    raw_content: str | None = Field(default=None, sa_type=Text)
    enriched_content: str | None = Field(default=None, sa_type=Text)

    dense_vector: list[float] | None = Field(default=None, sa_type=VECTOR(settings.EMBEDDING_DIMENSION))

    sparse_vector: str | None = Field(default=None, sa_type=TSVECTOR)


class DocumentInfo(SQLModel):
    """文档概要信息"""

    file_name: str
    chunk_count: int
    page_numbers: list[int]

    model_config = {"from_attributes": True}

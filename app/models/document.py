"""DocumentChunk 模型 — pgvector 向量检索 + TSVECTOR 全文检索"""

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlmodel import Field, SQLModel

from app.core.config import settings


class DocumentChunk(SQLModel, table=True):
    __tablename__ = "document_chunks"

    id: int | None = Field(default=None, primary_key=True)
    file_name: str | None = Field(default=None, sa_column=Column(String(255)))
    page_numbers: list[int] | None = Field(default=None, sa_column=Column(ARRAY(Integer)))
    heading_context: str | None = Field(default=None, sa_column=Column(Text))
    raw_content: str | None = Field(default=None, sa_column=Column(Text))
    enriched_content: str | None = Field(default=None, sa_column=Column(Text))
    dense_vector: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(settings.EMBEDDING_DIMENSION)),
    )
    sparse_vector: Any | None = Field(default=None, sa_column=Column(TSVECTOR))


class DocumentInfo(SQLModel):
    """文档概要信息"""

    file_name: str
    chunk_count: int
    page_numbers: list[int]

    model_config = {"from_attributes": True}

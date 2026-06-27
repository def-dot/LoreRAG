"""文档模型 — Document 记录表 + DocumentChunk 切片表"""

from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import VECTOR  # type: ignore[import-untyped]
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER, TSVECTOR
from sqlmodel import Field, SQLModel

from app.core.config import settings


# ---------- 枚举 ----------

class DocumentStatus(StrEnum):
    """文档处理状态"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------- 文档记录表 ----------

class Document(SQLModel, table=True):
    """文档元信息与处理状态"""

    __tablename__ = "documents"

    id: int | None = Field(default=None, primary_key=True)
    file_name: str = Field(max_length=255, index=True)
    file_path: str | None = Field(default=None, max_length=500, description="文件存储路径")
    file_size: int | None = Field(default=None, description="文件大小（字节）")
    file_ext: str | None = Field(default=None, max_length=20, description="文件后缀，如 .pdf")
    status: str = Field(default=DocumentStatus.PENDING, max_length=20)
    chunk_count: int = Field(default=0, description="切片数量")
    error_message: str | None = Field(default=None, sa_type=Text)
    retry_count: int = Field(default=0, description="解析重试次数")
    created_at: datetime | None = Field(default=None, description="上传时间")
    parse_started_at: datetime | None = Field(default=None, description="开始解析时间")
    parse_completed_at: datetime | None = Field(default=None, description="解析完成时间")
    updated_at: datetime | None = Field(default=None)


# ---------- 切片表 ----------

class DocumentChunk(SQLModel, table=True):
    __tablename__ = "document_chunks"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int | None = Field(default=None, foreign_key="documents.id", index=True)
    file_name: str | None = Field(default=None, max_length=255)

    page_numbers: list[int] | None = Field(default=None, sa_type=ARRAY(INTEGER))  # type: ignore[call-overload]
    heading_context: str | None = Field(default=None, sa_type=Text)
    raw_content: str | None = Field(default=None, sa_type=Text)
    enriched_content: str | None = Field(default=None, sa_type=Text)

    dense_vector: list[float] | None = Field(default=None, sa_type=VECTOR(settings.EMBEDDING_DIMENSION))

    tsv_content: str | None = Field(default=None, sa_type=TSVECTOR)


# ---------- 非表 Schema ----------

class DocumentInfo(SQLModel):
    """文档概要信息（兼容旧接口）"""

    file_name: str
    chunk_count: int
    page_numbers: list[int]

    model_config = {"from_attributes": True}

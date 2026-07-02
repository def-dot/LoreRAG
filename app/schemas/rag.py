"""RAG 请求/响应 Schema"""

from datetime import datetime

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """知识库检索请求"""

    query: str = Field(description="检索查询文本")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")
    mode: str = Field(default="hybrid", description="检索模式: bm25 | vector | hybrid")


class SearchResult(BaseModel):
    """单条检索结果"""

    chunk_id: int = Field(description="切片 ID")
    document_id: int = Field(description="所属文档 ID")
    file_name: str = Field(description="来源文件名")
    page_numbers: list[int] = Field(default=[], description="页码")
    heading_context: str = Field(default="", description="章节上下文")
    content: str = Field(description="原始内容（Markdown 表格 / LaTeX 公式 / 图片描述）")
    score: float = Field(description="Reranker 相关性分数 ∈ [0,1]，1.0 表示完全相关")


class SearchResponse(BaseModel):
    """检索结果列表"""

    results: list[SearchResult] = Field(description="检索结果")
    total: int = Field(description="结果数量")


class UploadResponse(BaseModel):
    """文档上传响应"""

    document_id: int = Field(description="文档 ID")
    file_name: str = Field(description="文件名")
    status: str = Field(default="processing", description="处理状态")


class DocumentListItem(BaseModel):
    """文档列表项"""

    id: int = Field(description="文档 ID")
    file_name: str = Field(description="文件名")
    file_path: str | None = Field(default=None, description="文件存储路径")
    file_size: int | None = Field(default=None, description="文件大小（字节）")
    file_ext: str | None = Field(default=None, description="文件后缀")
    status: str = Field(description="处理状态")
    chunk_count: int = Field(default=0, description="切片数量")
    retry_count: int = Field(default=0, description="重试次数")
    error_message: str | None = Field(default=None, description="错误信息")
    created_at: datetime | None = Field(default=None, description="上传时间")
    parse_started_at: datetime | None = Field(default=None, description="开始解析时间")
    parse_completed_at: datetime | None = Field(default=None, description="解析完成时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class DocumentListResponse(BaseModel):
    """文档列表响应"""

    items: list[DocumentListItem] = Field(description="文档列表")
    total: int = Field(description="文档总数")


class DocumentDetail(BaseModel):
    """文档详情"""

    id: int = Field(description="文档 ID")
    file_name: str = Field(description="文件名")
    file_path: str | None = Field(default=None, description="文件存储路径")
    file_size: int | None = Field(default=None, description="文件大小（字节）")
    file_ext: str | None = Field(default=None, description="文件后缀")
    status: str = Field(description="处理状态")
    chunk_count: int = Field(default=0, description="切片数量")
    error_message: str | None = Field(default=None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")
    created_at: datetime | None = Field(default=None, description="上传时间")
    parse_started_at: datetime | None = Field(default=None, description="开始解析时间")
    parse_completed_at: datetime | None = Field(default=None, description="解析完成时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class ChunkItem(BaseModel):
    """单条切片信息"""

    id: int = Field(description="切片 ID")
    document_id: int = Field(description="所属文档 ID")
    file_name: str = Field(description="文件名称")
    page_numbers: list[int] = Field(default=[], description="页码")
    heading_context: str = Field(default="", description="章节上下文")
    raw_content: str = Field(default="", description="原始内容（Markdown / LaTeX / 图片描述）")


class ChunkListResponse(BaseModel):
    """切片列表响应"""

    items: list[ChunkItem] = Field(description="切片列表")
    total: int = Field(description="切片总数")


class DeleteResponse(BaseModel):
    """删除响应"""

    deleted_chunks: int = Field(description="删除的切片数量")
    file_name: str = Field(description="文件名")

"""RAG 请求/响应 Schema"""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """知识库检索请求"""

    query: str = Field(description="检索查询文本")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")


class SearchResult(BaseModel):
    """单条检索结果"""

    chunk_id: int = Field(description="切片 ID")
    file_name: str = Field(description="来源文件名")
    page_numbers: list[int] = Field(default=[], description="页码")
    heading_context: str = Field(default="", description="章节上下文")
    content: str = Field(description="原始内容（Markdown 表格 / LaTeX 公式 / 图片描述）")
    score: float = Field(description="相似度得分")


class SearchResponse(BaseModel):
    """检索结果列表"""

    results: list[SearchResult] = Field(description="检索结果")
    total: int = Field(description="结果数量")


class UploadResponse(BaseModel):
    """文档上传响应"""

    file_name: str = Field(description="文件名")
    chunk_count: int = Field(default=0, description="切片数量")
    status: str = Field(default="processing", description="处理状态")


class DocumentListItem(BaseModel):
    """文档列表项"""

    file_name: str = Field(description="文件名")
    chunk_count: int = Field(description="切片数量")
    page_numbers: list[int] = Field(default=[], description="涉及页码")


class DocumentListResponse(BaseModel):
    """文档列表响应"""

    items: list[DocumentListItem] = Field(description="文档列表")
    total: int = Field(description="文档总数")


class DeleteResponse(BaseModel):
    """删除响应"""

    deleted_chunks: int = Field(description="删除的切片数量")
    file_name: str = Field(description="文件名")

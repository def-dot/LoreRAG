"""文档处理服务 — Docling 全能力：OCR + 表格 + 公式 + 图表 + 图片描述"""

import os
from typing import Any

from docling.chunking import HybridChunker  # type: ignore[attr-defined]
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    ChartExtractionModelOptions,
    PdfPipelineOptions,
    PictureDescriptionApiOptions,
    RapidOcrOptions,
    TableStructureOptions,
    TableFormerMode,
)
from docling.document_converter import (
    AsciiDocFormatOption,
    CsvFormatOption,
    DocumentConverter,
    ExcelFormatOption,
    HTMLFormatOption,
    ImageFormatOption,
    LatexFormatOption,
    MarkdownFormatOption,
    PdfFormatOption,
    PowerpointFormatOption,
    WordFormatOption,
)

from app.core.config import settings


def _build_picture_description_options() -> PictureDescriptionApiOptions | None:
    """构建图片描述选项：如果配置了 VLM API 则使用外部 VLM，否则返回 None（使用 Docling 内置默认）"""
    if settings.VLM_PROVIDER == "qwen" and settings.VLM_API_URL:
        return PictureDescriptionApiOptions(
            url=settings.VLM_API_URL,
            headers={"Authorization": f"Bearer {settings.VLM_API_KEY}"} if settings.VLM_API_KEY else {},
            prompt="请详细描述这张图片中的内容，包括图表数据、架构、文字等关键信息。",
            timeout=60.0,
            concurrency=2,
        )
    return None


def _init_converter() -> DocumentConverter:
    """
    初始化 Docling 转换引擎 — 全能力模式

    能力清单：
    - OCR（RapidOCR，中英文识别）
    - 表格结构提取（TableFormer ACCURATE 模式）
    - 公式识别 + LaTeX 转换
    - 代码块识别
    - 图片分类（自动识别图片类型：照片/图表/流程图等）
    - 图片描述（VLM 生成文字描述，用于检索）
    - 图表数据提取（柱状图/饼图/折线图 → CSV/代码/摘要）
    - 图片提取（生成独立图片文件）
    """
    pipeline_options = PdfPipelineOptions()

    # ---- OCR ----
    pipeline_options.do_ocr = True
    pipeline_options.ocr_options = RapidOcrOptions(lang=["chinese", "english"])

    # ---- 表格 ----
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options = TableStructureOptions(
        do_cell_matching=True,
        mode=TableFormerMode.ACCURATE,
    )

    # ---- 公式 & 代码 ----
    pipeline_options.do_formula_enrichment = True
    pipeline_options.do_code_enrichment = True

    # ---- 图片分类 ----
    pipeline_options.do_picture_classification = True

    # ---- 图片描述（VLM） ----
    pipeline_options.do_picture_description = True
    picture_desc_opts = _build_picture_description_options()
    if picture_desc_opts is not None:
        pipeline_options.picture_description_options = picture_desc_opts

    # ---- 图表提取 ----
    pipeline_options.do_chart_extraction = True
    pipeline_options.chart_extraction_options = ChartExtractionModelOptions(
        chart2csv=True,
        chart2code=True,
        chart2summary=True,
    )

    # ---- 图片提取（生成独立图片供 VLM 使用） ----
    pipeline_options.generate_page_images = True
    pipeline_options.generate_picture_images = True
    pipeline_options.generate_table_images = True
    pipeline_options.images_scale = 2.0

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            InputFormat.DOCX: PdfFormatOption(pipeline_options=pipeline_options),
            InputFormat.PPTX: PowerpointFormatOption(),
            InputFormat.HTML: HTMLFormatOption(),
            InputFormat.MD: MarkdownFormatOption(),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
            InputFormat.CSV: CsvFormatOption(),
            InputFormat.XLSX: ExcelFormatOption(),
            InputFormat.ASCIIDOC: AsciiDocFormatOption(),
            InputFormat.LATEX: LatexFormatOption(),
        }
    )


def process_document(file_path: str) -> list[dict[str, Any]]:
    """
    解析文档 → 智能切片

    全能力处理链：
    Docling 解析（OCR + 表格 + 公式 + 代码 + 图片分类 + 图片描述 + 图表提取） → HybridChunker 切片

    返回格式: [{"enriched_text": ..., "raw_text": ..., "metadata": {...}}, ...]
    """
    converter = _init_converter()
    result = converter.convert(file_path)
    doc = result.document

    chunker = HybridChunker(max_tokens=settings.CHUNK_SIZE, overlap_tokens=settings.CHUNK_OVERLAP)  # type: ignore[call-arg]
    doc_chunks = list(chunker.chunk(doc))

    # 格式化输出
    formatted: list[dict[str, Any]] = []
    for i, chunk in enumerate(doc_chunks):
        chunk_text = chunk.text

        headings = getattr(chunk.meta, "headings", []) or []
        heading_ctx = " > ".join(h if isinstance(h, str) else h.text for h in headings) if headings else "Root"
        pages = list(getattr(chunk.meta, "page_numbers", [])) or [1]

        enriched = f"[章节上下文: {heading_ctx}]\n{chunk_text}"

        formatted.append(
            {
                "enriched_text": enriched,
                "raw_text": chunk_text,
                "metadata": {
                    "source_file": os.path.basename(file_path),
                    "chunk_id": i,
                    "heading_context": heading_ctx,
                    "page_numbers": pages,
                },
            }
        )

    return formatted

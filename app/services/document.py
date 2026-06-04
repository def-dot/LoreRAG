"""文档处理服务 — Docling PDF 全能力管线"""

import os
from typing import Any

from docling.chunking import HybridChunker  # type: ignore[attr-defined]
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    ChartExtractionModelOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
    TableStructureOptions,
    TableFormerMode,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

from app.core.config import settings


def _init_converter() -> DocumentConverter:
    """初始化 Docling 转换引擎 — 仅 PDF"""
    """构建 PDF 全能力管线选项（使用 Docling 内置 SmolVLM 默认图片描述）"""
    opts = PdfPipelineOptions()

    opts.document_timeout = 300.0

    # ---- OCR ----
    opts.do_ocr = True
    opts.ocr_options = RapidOcrOptions()

    opts.do_table_structure = True

    opts.do_formula_enrichment = True
    opts.do_code_enrichment = True

    opts.do_picture_classification = True

    opts.do_picture_description = True

    # ---- 图表提取 ----
    # opts.do_chart_extraction = True
    # opts.chart_extraction_options = ChartExtractionModelOptions(
    #     chart2csv=True,
    #     chart2code=True,
    #     chart2summary=True,
    # )

    # ---- 图片生成 ----
    opts.generate_page_images = True
    opts.generate_picture_images = True
    opts.generate_table_images = True
    opts.images_scale = 2.0

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=opts),
        }
    )


def process_document(file_path: str) -> list[dict[str, Any]]:
    """
    解析 PDF → 智能切片

    处理链：
    Docling PDF 全能力管线（OCR + 表格 + 公式 + 代码 + 图片分类 + 图片描述 + 图表提取） → HybridChunker 切片

    返回格式: [{"enriched_text": ..., "raw_text": ..., "metadata": {...}}, ...]
    """
    converter = _init_converter()
    result = converter.convert(file_path)
    doc = result.document

    chunker = HybridChunker(max_tokens=settings.CHUNK_SIZE, overlap_tokens=settings.CHUNK_OVERLAP)  # type: ignore[call-arg]
    doc_chunks = list(chunker.chunk(doc))

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

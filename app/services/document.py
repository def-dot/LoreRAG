"""文档处理服务 — Docling 解析 + 多模态回填 + 智能切片"""

import os
from typing import Any

from docling.chunking import HybridChunker  # type: ignore[attr-defined]
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    PowerpointFormatOption,
    WordFormatOption,
)

from app.core.config import settings
from app.services.vlm import get_vlm_service


def _init_converter() -> DocumentConverter:
    """初始化 Docling 转换引擎：RapidOCR + 公式 + 图片提取"""
    pipeline_options = PdfPipelineOptions()
    pipeline_options = PdfPipelineOptions()
    pipeline_options.ocr_options = RapidOcrOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_formula_enrichment = True
    pipeline_options.generate_page_images = True

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            InputFormat.DOCX: WordFormatOption(),
            InputFormat.PPTX: PowerpointFormatOption(),
        }
    )


def process_document(file_path: str) -> list[dict[str, Any]]:
    """
    解析文档 → 多模态回填 → 智能切片

    返回格式: [{"enriched_text": ..., "raw_text": ..., "metadata": {...}}, ...]
    """
    converter = _init_converter()
    result = converter.convert(file_path)
    doc = result.document
    vlm = get_vlm_service()

    # 多模态回填：遍历图片元素，用 VLM 生成描述并回填到文本属性
    for element, _level in doc.iterate_items():
        if getattr(element, "label", None) == "figure" and hasattr(element, "image") and element.image is not None:
            tmp_path = f"tmp_vlm_{id(element)}.png"
            try:
                element.image.save(tmp_path)
                description = vlm.describe_image(tmp_path)
                text = getattr(element, "text", "")
                element.text = f"{text}\n{description}" if text else description  # type: ignore[attr-defined]
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    # HybridChunker 智能层级切片（保证表格/公式不被截断）
    chunker = HybridChunker(max_tokens=settings.CHUNK_SIZE, overlap_tokens=settings.CHUNK_OVERLAP)  # type: ignore[call-arg]
    doc_chunks = chunker.chunk(doc)

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

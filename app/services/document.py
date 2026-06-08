"""文档处理服务 — Docling PDF 全能力管线（重量级库延迟导入，单例复用）"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _get_converter():
    """单例 DocumentConverter — 首次调用时加载 docling，之后复用"""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()

    opts.document_timeout = 300.0

    # ---- OCR ----
    opts.do_ocr = True
    opts.ocr_options = RapidOcrOptions()

    opts.do_table_structure = True

    opts.do_formula_enrichment = True
    opts.do_code_enrichment = True

    # opts.do_picture_classification = True
    # opts.do_picture_description = True

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


@lru_cache(maxsize=1)
def _get_chunker():
    """单例 HybridChunker — 首次调用时加载 transformers + docling 切片模块"""
    from transformers import AutoTokenizer
    from docling.chunking import HybridChunker  # type: ignore[attr-defined]
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

    bge_tok = AutoTokenizer.from_pretrained("./hub/bge-m3")
    tokenizer = HuggingFaceTokenizer(tokenizer=bge_tok, max_tokens=512)
    return HybridChunker(tokenizer=tokenizer)


def process_document(file_path: str) -> list[dict[str, Any]]:
    """
    解析 PDF → 智能切片

    处理链：
    Docling PDF 全能力管线（OCR + 表格 + 公式 + 代码 + 图片分类 + 图片描述 + 图表提取） → HybridChunker 切片

    返回格式: [{"enriched_text": ..., "raw_text": ..., "metadata": {...}}, ...]

    converter 和 chunker 通过 lru_cache 单例复用，首次调用时加载重量级库，
    后续调用零开销。
    """
    converter = _get_converter()
    result = converter.convert(file_path)
    doc = result.document

    chunker = _get_chunker()
    doc_chunks = list(chunker.chunk(doc))

    formatted: list[dict[str, Any]] = []
    for i, chunk in enumerate(doc_chunks):
        chunk_text = chunk.text
        chunk_text = chunk_text.replace("\x00 ", "-")

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

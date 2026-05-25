"""文档处理服务 — Docling 解析 + 多模态回填 + 智能切片"""

import os
from collections import defaultdict
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


def _collect_picture_descriptions(
    doc: Any, vlm: Any
) -> tuple[dict[str, str], dict[str, int]]:
    """遍历文档元素，用 VLM 生成图片描述，返回 {self_ref: description} 和 {self_ref: position}。"""
    picture_descs: dict[str, str] = {}
    item_positions: dict[str, int] = {}

    for idx, (element, _level) in enumerate(doc.iterate_items()):
        item_positions[element.self_ref] = idx

        if (
            getattr(element, "label", None) == "picture"
            and hasattr(element, "image")
            and element.image is not None
        ):
            tmp_path = f"tmp_vlm_{id(element)}.png"
            try:
                element.image.pil_image.save(tmp_path)
                description = vlm.describe_image(tmp_path)
                picture_descs[element.self_ref] = description
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    return picture_descs, item_positions


def _map_pictures_to_chunks(
    picture_descs: dict[str, str],
    item_positions: dict[str, int],
    doc_chunks: list[Any],
) -> dict[int, list[str]]:
    """根据文档遍历顺序，将每张图片的描述映射到最近的 chunk（优先前一个）。"""
    chunk_descs: dict[int, list[str]] = defaultdict(list)
    if not picture_descs:
        return chunk_descs

    # 预计算每个 chunk 的 doc_item 位置
    chunk_item_positions: list[list[int]] = []
    for chunk in doc_chunks:
        positions = [
            item_positions[di.self_ref]
            for di in chunk.meta.doc_items
            if di.self_ref in item_positions
        ]
        chunk_item_positions.append(positions)

    for pic_ref, desc in picture_descs.items():
        pic_pos = item_positions.get(pic_ref)
        if pic_pos is None:
            continue

        # 找到距离该图片最近的 chunk（严格 < 保证等距时取前一个）
        best_chunk_idx = 0
        best_distance = float("inf")
        for ci, positions in enumerate(chunk_item_positions):
            if not positions:
                continue
            closest = min(abs(p - pic_pos) for p in positions)
            if closest < best_distance:
                best_distance = closest
                best_chunk_idx = ci

        chunk_descs[best_chunk_idx].append(desc)

    return chunk_descs


def process_document(file_path: str) -> list[dict[str, Any]]:
    """
    解析文档 → 多模态回填 → 智能切片

    返回格式: [{"enriched_text": ..., "raw_text": ..., "metadata": {...}}, ...]
    """
    converter = _init_converter()
    result = converter.convert(file_path)
    doc = result.document
    vlm = get_vlm_service()

    picture_descs, item_positions = _collect_picture_descriptions(doc, vlm)

    chunker = HybridChunker(max_tokens=settings.CHUNK_SIZE, overlap_tokens=settings.CHUNK_OVERLAP)  # type: ignore[call-arg]
    doc_chunks = list(chunker.chunk(doc))

    chunk_descs = _map_pictures_to_chunks(picture_descs, item_positions, doc_chunks)

    # 阶段 4：格式化输出
    formatted: list[dict[str, Any]] = []
    for i, chunk in enumerate(doc_chunks):
        chunk_text = chunk.text

        # 追加属于本 chunk 的图片描述
        if i in chunk_descs:
            chunk_text += "\n" + "\n".join(chunk_descs[i])

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

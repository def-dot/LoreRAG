"""文档智能切片器（单例复用）"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from docling_core.types.doc import DoclingDocument  # type: ignore[attr-defined]

from app.services.rag_convert import document_convert
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_chunker():
    """返回 HybridChunker 单例（BGE-M3 tokenizer, max_tokens=512）"""
    from transformers import AutoTokenizer

    from docling.chunking import HybridChunker  # type: ignore[attr-defined]
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

    bge_tok = AutoTokenizer.from_pretrained("./hub/bge-m3")
    tokenizer = HuggingFaceTokenizer(tokenizer=bge_tok, max_tokens=512)
    return HybridChunker(tokenizer=tokenizer)


def document_chunk(file_path: str, *, doc: DoclingDocument = None) -> list[dict[str, Any]]:
    """将文档切片为带元数据的文本块。可传入已转换的 doc 避免重复解析"""
    if doc is None:
        logger.info("start converting......")
        doc = document_convert(file_path)

    debug_dir = Path("debug")
    debug_dir.mkdir(exist_ok=True)
    doc.save_as_json(debug_dir / f"{Path(file_path).stem}.json")
    
    logger.info("start chunking......")
    doc_chunks = list(_get_chunker().chunk(doc))

    logger.info("start formating......")
    source_file = os.path.basename(file_path)
    formatted: list[dict[str, Any]] = []
    for i, chunk in enumerate(doc_chunks):
        text = chunk.text.replace("\x00 ", "-")

        headings = getattr(chunk.meta, "headings", []) or []
        heading_ctx = (
            " > ".join(h if isinstance(h, str) else h.text for h in headings)
            if headings
            else "Root"
        )
        pages = list(getattr(chunk.meta, "page_numbers", [])) or [1]

        formatted.append(
            {
                "enriched_text": f"[章节上下文: {heading_ctx}]\n{text}",
                "raw_text": text,
                "metadata": {
                    "source_file": source_file,
                    "chunk_id": i,
                    "heading_context": heading_ctx,
                    "page_numbers": pages,
                },
            }
        )
    logger.info("document chunk successed")
    return formatted

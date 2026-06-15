"""文档智能切片器（单例复用）"""

import os
from functools import lru_cache
from typing import Any

from app.services.rag_convert import document_convert


@lru_cache(maxsize=1)
def _get_chunker():
    """返回 HybridChunker 单例（BGE-M3 tokenizer, max_tokens=512）"""
    from transformers import AutoTokenizer

    from docling.chunking import HybridChunker  # type: ignore[attr-defined]
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

    bge_tok = AutoTokenizer.from_pretrained("./hub/bge-m3")
    tokenizer = HuggingFaceTokenizer(tokenizer=bge_tok, max_tokens=512)
    return HybridChunker(tokenizer=tokenizer)


def document_chunk(file_path: str) -> list[dict[str, Any]]:
    """将文档切片为带元数据的文本块"""
    doc = document_convert(file_path)
    doc_chunks = list(_get_chunker().chunk(doc))

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

    return formatted

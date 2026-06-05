"""
使用 Docling HybridChunker 智能分块

HybridChunker 结合层级分块和滑动窗口：
1. 先按文档结构（标题、段落、表格）做层级分块
2. 再按 token 长度拆分超长块（滑动窗口 + overlap）
3. 合并相邻的同级小块（merge_peers）

运行: python examples/docling_chunk/test_hybird_chunk.py
"""
from pathlib import Path
from docling.chunking import HybridChunker
from examples.docling_chunk.utils import _init_converter

PDF_PATH = Path(__file__).resolve().parent.parent / "test.pdf"


def test_hybrid_chunker():
    """使用 HybridChunker 分块"""
    print("=" * 60)
    print("HybridChunker 智能分块测试")
    print("=" * 60)

    converter = _init_converter()
    result = converter.convert(str(PDF_PATH))
    doc = result.document

    chunker = HybridChunker(merge_peers=True)

    chunks = list(chunker.chunk(doc))

    print(f"\n文档分块数: {len(chunks)}")
    print()

    for i, chunk in enumerate(chunks):
        meta = chunk.meta
        headings = getattr(meta, "headings", []) or []
        heading_ctx = " > ".join(headings) if headings else "Root"
        text = chunk.text

        print(f"--- Chunk [{i}]  chars={len(text)}  heading=[{heading_ctx}]")
        print(f"  {text[:200]}{'...' if len(text) > 200 else ''}")
        print()

    return chunks


if __name__ == "__main__":
    test_hybrid_chunker()

"""
使用 Docling PageChunker 按页分块

PageChunker 每页生成一个 chunk，适合：
- 保留页面粒度的文档结构
- 按页检索场景

运行: python -m examples.docling_chunk.test_page_chunk
"""
from pathlib import Path
from docling_core.transforms.chunker.page_chunker import PageChunker
from examples.docling_chunk.utils import _init_converter

PDF_PATH = Path(__file__).resolve().parent.parent / "test.pdf"


def test_page_chunker():
    """使用 PageChunker 按页分块"""
    print("=" * 60)
    print("PageChunker 按页分块测试")
    print("=" * 60)

    converter = _init_converter()
    result = converter.convert(str(PDF_PATH))
    doc = result.document

    # 按页分块
    chunker = PageChunker()
    chunks = list(chunker.chunk(doc))

    print(f"\n总页数: {len(doc.pages)}")
    print(f"分块数: {len(chunks)} (每页一个 chunk)")

    for i, chunk in enumerate(chunks):
        meta = chunk.meta
        doc_items = getattr(meta, "doc_items", [])
        text = chunk.text
        char_count = len(text)

        # 统计该页包含的文档元素类型
        item_types = {}
        for item in doc_items:
            label = getattr(item, "label", "unknown")
            item_types[label] = item_types.get(label, 0) + 1
        types_str = ", ".join(f"{k}:{v}" for k, v in item_types.items())

        print(f"--- Page [{i}]  chars={char_count}  items=[{types_str}]")
        print(f"  {text[:200]}{'...' if len(text) > 200 else ''}")
        print()

    return chunks


if __name__ == "__main__":
    test_page_chunker()

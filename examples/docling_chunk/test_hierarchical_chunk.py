"""
使用 Docling HierarchicalChunker 按文档层级结构分块

HierarchicalChunker 按照文档的标题层级（Title / SectionHeader）进行分块：
1. 遇到标题时，记录当前层级路径（如 "第1章" > "1.1 节"）
2. 标题下的段落、列表、表格等内容归入对应层级的 chunk
3. 每个 chunk 保留 headings 元数据，方便溯源

适合：
- 需要保留文档章节结构的检索场景
- 长文档的层级化拆分

运行: python -m examples.docling_chunk.test_hierarchical_chunk
"""
from pathlib import Path
from docling_core.transforms.chunker.hierarchical_chunker import HierarchicalChunker
from examples.docling_chunk.utils import _init_converter

PDF_PATH = Path(__file__).resolve().parent.parent / "test_20260608014054.pdf"


def test_hierarchical_chunker():
    """使用 HierarchicalChunker 按层级结构分块"""
    print("=" * 60)
    print("HierarchicalChunker 层级分块测试")
    print("=" * 60)

    converter = _init_converter()
    result = converter.convert(str(PDF_PATH))
    doc = result.document

    chunker = HierarchicalChunker()
    chunks = list(chunker.chunk(doc))

    print(f"\n文档分块数: {len(chunks)}")
    print()

    for i, chunk in enumerate(chunks):
        meta = chunk.meta
        headings = getattr(meta, "headings", []) or []
        heading_ctx = " > ".join(headings) if headings else "Root"
        doc_items = getattr(meta, "doc_items", [])
        text = chunk.text

        # 统计该 chunk 包含的文档元素类型
        item_types = {}
        for item in doc_items:
            label = getattr(item, "label", "unknown")
            item_types[label] = item_types.get(label, 0) + 1
        types_str = ", ".join(f"{k}:{v}" for k, v in item_types.items())

        print(f"--- Chunk [{i}]  chars={len(text)}  heading=[{heading_ctx}]  items=[{types_str}]")
        print(f"  {text[:200]}{'...' if len(text) > 200 else ''}")
        print()

    return chunks


if __name__ == "__main__":
    test_hierarchical_chunker()

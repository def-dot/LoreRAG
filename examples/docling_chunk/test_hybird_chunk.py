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
from docling_core.transforms.chunker.tokenizer.huggingface_tokenizer import HuggingFaceTokenizer
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

    # 初始化 tokenizer（HybridChunker 需要 tokenizer 来计算 token 数）
    tokenizer = HuggingFaceTokenizer(model_name="sentence-transformers/all-MiniLM-L6-v2")

    chunker = HybridChunker(
        tokenizer=tokenizer,
        merge_peers=True,
    )

    chunks = list(chunker.chunk(doc))

    print(f"\n文档分块数: {len(chunks)}")
    print()

    total_tokens = 0
    for i, chunk in enumerate(chunks):
        meta = chunk.meta
        headings = getattr(meta, "headings", []) or []
        heading_ctx = " > ".join(headings) if headings else "Root"
        text = chunk.text
        token_count = len(tokenizer.tokenize(text))
        total_tokens += token_count

        print(f"--- Chunk [{i}]  tokens={token_count}  heading=[{heading_ctx}]")
        print(f"  {text[:200]}{'...' if len(text) > 200 else ''}")
        print()

    print(f"总 chunks: {len(chunks)}  总 tokens: {total_tokens}")

    return chunks


if __name__ == "__main__":
    test_hybrid_chunker()

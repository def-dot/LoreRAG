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
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer
from examples.docling_chunk.utils import _init_converter

PDF_PATH = Path(__file__).resolve().parent.parent / "test.pdf"

CHUNK_SIZE = 256


def test_hybrid_chunker():
    """使用 HybridChunker 分块"""
    print("=" * 60)
    print("HybridChunker 智能分块测试")
    print("=" * 60)

    converter = _init_converter()
    result = converter.convert(str(PDF_PATH))
    doc = result.document

    # 先加载 transformers 的 tokenizer，再包装为 HuggingFaceTokenizer
    hf_tok = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    tokenizer = HuggingFaceTokenizer(tokenizer=hf_tok, max_tokens=CHUNK_SIZE)

    chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)

    chunks = list(chunker.chunk(doc))

    print(f"\n文档分块数: {len(chunks)}")
    print()

    for i, chunk in enumerate(chunks):
        meta = chunk.meta
        headings = getattr(meta, "headings", []) or []
        heading_ctx = " > ".join(headings) if headings else "Root"
        text = chunk.text
        token_count = len(hf_tok.tokenize(text))

        print(f"--- Chunk [{i}]  chars={len(text)}  tokens={token_count}  heading=[{heading_ctx}]")
        print(f"  {text}")
        print()

    return chunks


if __name__ == "__main__":
    test_hybrid_chunker()

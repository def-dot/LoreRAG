"""BGE-Reranker-v2-m3 精排服务 — 单例懒加载,GPU 可用则用 GPU(fp16),否则 CPU"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import torch

from app.core.logging import get_logger

logger = get_logger(__name__)


# # Monkey-patch: 新版 transformers 移除了 prepare_for_model，FlagEmbedding 还在调用
# def _patch_tokenizer() -> None:
#     """为 tokenizer 补上被移除的 prepare_for_model 方法"""
#     try:
#         from transformers import XLMRobertaTokenizer

#         if not hasattr(XLMRobertaTokenizer, "prepare_for_model"):
#             XLMRobertaTokenizer.prepare_for_model = lambda self, *args, **kwargs: kwargs
#     except ImportError:
#         pass


# _patch_tokenizer()


@lru_cache(maxsize=1)
def _get_reranker() -> Any:
    """延迟加载 BGE-Reranker-v2-m3;GPU 可用则 fp16 走 GPU,否则 CPU"""
    from FlagEmbedding import FlagReranker  # type: ignore[import-untyped]

    use_fp16 = torch.cuda.is_available()
    device = "cuda" if use_fp16 else "cpu"
    reranker = FlagReranker(
        "./hub/bge-reranker-v2-m3",
        use_fp16=use_fp16,
        devices=device,
        normalize=True,  # sigmoid 归一化,分数 ∈ (0,1),直接作为「相关度」展示
    )
    logger.info("Reranker 已加载(device=%s, fp16=%s)", device, use_fp16)
    return reranker


def rerank(query: str, passages: list[str]) -> list[float]:
    """对 (query, passage) 对用 cross-encoder 打分,返回 sigmoid 相关性分数 ∈ (0,1)"""
    if not passages:
        return []
    reranker = _get_reranker()
    pairs = [[query, p] for p in passages]
    scores = reranker.compute_score(pairs)
    # 单条时 compute_score 返回 float,统一成 list
    if isinstance(scores, (int, float)):
        scores = [scores]
    return [float(s) for s in scores]

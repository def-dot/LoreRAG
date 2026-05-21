"""BGE-M3 向量嵌入服务 — 单例懒加载"""

from functools import lru_cache

from app.core.config import settings


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.EMBEDDING_MODEL)


def encode(text: str) -> list[float]:
    """单条文本编码为稠密向量"""
    model = _get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def encode_batch(texts: list[str]) -> list[list[float]]:
    """批量文本编码为稠密向量"""
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()

"""LLM 总结服务 — OpenAI 兼容接口"""

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def chat(query: str, results: list[str] | None = None) -> str:
    """调用 LLM 回答"""
    if not settings.LLM_API_URL:
        raise RuntimeError("LLM_API_URL 未配置")

    if results:
        context = "\n\n---\n\n".join(
            f"[来源 {i + 1}]\n{r}" for i, r in enumerate(results)
        )
        system = "根据参考资料回答问题。资料不足就说未找到。回答简洁，每个事实后面标注来源编号。"
        user = f"问题：{query}\n\n参考资料：\n{context}\n\n请回答问题，在每个引用处标注来源编号如 [1] [2]。格式示例：'AI可用于故障检测 [1]，同时能优化流程 [2]。'"
    else:
        system = "你是一个智能助手。直接回答用户的问题，回答简洁（200 字以内）。"
        user = query

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{settings.LLM_API_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            logger.error("LLM HTTP %d: %s", e.response.status_code, e.response.text[:200])
            return f"AI 服务返回错误 (HTTP {e.response.status_code})"
        except httpx.TimeoutException:
            logger.error("LLM 请求超时")
            return "AI 服务响应超时，请稍后重试"
        except Exception as e:
            logger.error("LLM 调用失败: %s", e)
            return "AI 服务暂时不可用"

"""LLM 总结服务 — OpenAI 兼容接口"""

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def chat(query: str, results: list[str] | None = None) -> str:
    """调用 LLM 回答。配置缺失抛异常，网络错误返回友好提示。"""
    if not settings.LLM_API_URL:
        raise RuntimeError("LLM_API_URL 未配置")

    if results:
        context = "\n\n---\n\n".join(
            f"[来源 {i + 1}]\n{r}" for i, r in enumerate(results)
        )
        system = "你是一个知识库助手。根据参考资料回答用户问题。如果资料不足以回答，就说'资料中未找到相关信息'。回答简洁（200 字以内），引用来处标注来源编号如 [1] [2]。"
        user = f"用户问题：{query}\n\n参考资料：\n{context}"
    else:
        system = "你是一个智能助手。直接回答用户的问题，回答简洁（200 字以内）。"
        user = query

    async with httpx.AsyncClient(timeout=60.0) as client:
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

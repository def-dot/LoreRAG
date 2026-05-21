"""VLM 视觉语言模型服务 — 抽象接口 + Mock / Qwen 实现"""

from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings


class VLMService(ABC):
    """视觉语言模型抽象接口"""

    @abstractmethod
    def describe_image(self, image_path: str) -> str:
        """对图片生成深度文本描述"""
        ...


class MockVLMService(VLMService):
    """Mock VLM — 开发阶段使用"""

    def describe_image(self, image_path: str) -> str:
        return "[图片多模态增强描述] 此处为占位描述，生产环境请切换到 Qwen2.5-VL。"


class QwenVLService(VLMService):
    """Qwen2.5-VL 视觉语言模型服务 — 通过 HTTP API 调用"""

    def __init__(self) -> None:
        import httpx

        self._client = httpx.Client(timeout=60.0)
        self._api_url = settings.VLM_API_URL
        self._api_key = settings.VLM_API_KEY

    def describe_image(self, image_path: str) -> str:
        import base64
        from pathlib import Path

        image_bytes = Path(image_path).read_bytes()
        b64 = base64.b64encode(image_bytes).decode()

        resp = self._client.post(
            self._api_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": "qwen2.5-vl-7b-instruct",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                            {"type": "text", "text": "请详细描述这张图片中的内容，包括图表、架构、文字等关键信息。"},
                        ],
                    }
                ],
            },
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return str(data["choices"][0]["message"]["content"])


def get_vlm_service() -> VLMService:
    """工厂函数：根据配置返回 VLM 实现"""
    match settings.VLM_PROVIDER:
        case "qwen":
            return QwenVLService()
        case _:
            return MockVLMService()

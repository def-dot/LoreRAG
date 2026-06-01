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

    @abstractmethod
    def analyze_chart(self, image_path: str) -> str:
        """对图表图片提取数据（CSV + 摘要）"""
        ...

    @abstractmethod
    def classify_and_describe(self, image_path: str) -> str:
        """自动分类图片类型并生成对应描述/数据提取"""
        ...


class MockVLMService(VLMService):
    """Mock VLM — 开发阶段使用"""

    def describe_image(self, image_path: str) -> str:
        return "[图片描述] 此处为占位描述，生产环境请切换到 Qwen2.5-VL。"

    def analyze_chart(self, image_path: str) -> str:
        return "[图表数据] 占位数据，生产环境请切换到 Qwen2.5-VL。"

    def classify_and_describe(self, image_path: str) -> str:
        return "[图片分类+描述] 占位内容，生产环境请切换到 Qwen2.5-VL。"


class QwenVLService(VLMService):
    """Qwen2.5-VL 视觉语言模型服务 — 通过 HTTP API 调用"""

    def __init__(self) -> None:
        import httpx

        self._client = httpx.Client(timeout=60.0)
        self._api_url = settings.VLM_API_URL
        self._api_key = settings.VLM_API_KEY

    def _call_vlm(self, image_path: str, prompt: str) -> str:
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
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return str(data["choices"][0]["message"]["content"])

    def describe_image(self, image_path: str) -> str:
        prompt = "请详细描述这张图片中的内容，包括图表数据、架构、文字等关键信息。"
        return self._call_vlm(image_path, prompt)

    def analyze_chart(self, image_path: str) -> str:
        prompt = (
            "这是一张图表，请完成以下任务：\n"
            "1. 判断图表类型（柱状图/饼图/折线图/散点图/其他）\n"
            "2. 提取所有数据，以 CSV 格式输出\n"
            "3. 用一段文字总结图表的关键信息和趋势\n\n"
            "请按以下格式输出：\n"
            "【图表类型】...\n"
            "【数据CSV】\n...\n"
            "【数据摘要】..."
        )
        return self._call_vlm(image_path, prompt)

    def classify_and_describe(self, image_path: str) -> str:
        prompt = (
            "请分析这张图片，完成以下任务：\n"
            "1. 判断图片类型，从以下选择：柱状图/饼图/折线图/散点图/流程图/架构图/表格截图/"
            "照片/截图/其他\n"
            "2. 根据类型生成对应内容：\n"
            "   - 如果是图表（柱状图/饼图/折线图/散点图），提取数据为 CSV 格式并总结关键信息\n"
            "   - 如果是流程图/架构图，描述结构和关系\n"
            "   - 如果是表格截图，提取为结构化文本\n"
            "   - 如果是照片/截图，描述内容\n\n"
            "请按以下格式输出：\n"
            "【图片类型】...\n"
            "【详细内容】..."
        )
        return self._call_vlm(image_path, prompt)


def get_vlm_service() -> VLMService:
    """工厂函数：根据配置返回 VLM 实现"""
    match settings.VLM_PROVIDER:
        case "qwen":
            return QwenVLService()
        case _:
            return MockVLMService()

"""RapidOCR 使用测试"""

from pathlib import Path

import pytest


def test_rapidocr_direct():
    """直接调用 RapidOCR 识别本地图片"""
    from rapidocr import RapidOCR

    img_path = Path(__file__).resolve().parent / "test_ocr.png"
    if not img_path.exists():
        pytest.skip("测试图片 test_ocr.png 不存在")

    reader = RapidOCR()
    result = reader(str(img_path))

    print("OCR 识别结果:", result.txts)


if __name__ == "__main__":
    test_rapidocr_direct()

"""
Stage 2: OCR — 对位图区域做 OCR，补充文本单元格
使用 RapidOCR，det -> cls -> rec
结果会和 Stage 1 的文本单元格合并，cell.from_ocr=True 表示来自 OCR 新增
"""
from docling.datamodel.document import ConversionResult
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.pipeline_options import RapidOcrOptions
from docling.models.factories import get_ocr_factory
from docling.datamodel.base_models import Page

from .utils import timed


@timed("Stage 2: OCR")
def run(conv_res: ConversionResult, pages: list[Page]):
    factory = get_ocr_factory()
    ocr_model = factory.create_instance(
        options=RapidOcrOptions(),
        enabled=True,
        artifacts_path=None,
        accelerator_options=AcceleratorOptions(),
    )

    print("\n" + "=" * 60)
    print("Stage 2: OCR")
    print("=" * 60)
    for page in pages:
        print(f"\n--- 输入: page_no={page.page_no}, cells数={len(page.cells)}")

    processed = list(ocr_model(conv_res, pages))

    for page in processed:
        print(f"\n--- 输出: page_no={page.page_no}")
        print(f"  OCR 后 cells 数: {len(page.cells)}")
        ocr_cells = [c for c in page.cells if getattr(c, "from_ocr", False)]
        print(f"  其中 OCR 新增: {len(ocr_cells)}")
        for i, cell in enumerate(ocr_cells[:5]):
            print(f"    [{i}] text=[{cell.text[:60]}]")

    return conv_res, processed

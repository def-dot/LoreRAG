"""
Stage 1: Preprocess — 加载页面图像 + 提取文本单元格
使用 docling parse，基于文本流的提取
"""
from pathlib import Path
from docling.datamodel.document import ConversionResult, InputDocument
from docling.models.stages.page_preprocessing.page_preprocessing_model import (
    PagePreprocessingModel,
    PagePreprocessingOptions,
)
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.datamodel.base_models import InputFormat, Page

from .utils import timed

PDF_PATH = Path(__file__).resolve().parent.parent / "test.pdf"


@timed("Stage 1: Preprocess")
def run(conv_res: ConversionResult, pages: list[Page]):
    model = PagePreprocessingModel(options=PagePreprocessingOptions(images_scale=1.0))

    print("=" * 60)
    print("Stage 1: Preprocess")
    print("=" * 60)

    processed = list(model(conv_res, pages))

    for page in processed:
        print(f"\n--- 输出: page_no={page.page_no}")
        print(f"  parsed_page: {'有' if page.parsed_page else '无'}")
        print(f"  textline_cells 数: {len(page.cells)}")
        img = page.get_image(scale=1.0)
        print(f"  image 尺寸: {img.size if img else '无'}")
        for i, cell in enumerate(page.cells[:5]):
            print(f"    [{i}] text=[{cell.text[:60]}]")
        if len(page.cells) > 5:
            print(f"    ... 共 {len(page.cells)} 个 cell")

    return conv_res, processed

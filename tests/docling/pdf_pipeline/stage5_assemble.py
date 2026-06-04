"""
Stage 5: Assemble — 将预测结果组装成结构化文档元素
将 layout，table，picture 等结果进行合并，生成元素列表（Element）
"""
from docling.datamodel.document import ConversionResult
from docling.models.stages.page_assemble.page_assemble_model import (
    PageAssembleModel,
    PageAssembleOptions,
)
from docling.datamodel.base_models import AssembledUnit, Page

from .utils import timed


@timed("Stage 5: Assemble")
def run(conv_res: ConversionResult, pages: list[Page]):
    model = PageAssembleModel(options=PageAssembleOptions())

    print("\n" + "=" * 60)
    print("Stage 5: Assemble")
    print("=" * 60)

    processed = list(model(conv_res, pages))

    for page in processed:
        print(f"\n--- 输出: page_no={page.page_no}")
        if page.assembled:
            print(f"  elements 数: {len(page.assembled.elements)}")
            for i, elem in enumerate(page.assembled.elements[:10]):
                label = getattr(elem, "label", "?")
                text = getattr(elem, "text", "")
                print(f"    [{i}] label={label}  text=[{text}]")
            if len(page.assembled.elements) > 10:
                print(f"    ... 共 {len(page.assembled.elements)} 个元素")
        else:
            print("  assembled: 无")

    # 将 processed 页面写回 conv_res，供后续 ReadingOrderModel 使用
    conv_res.pages = processed
    elements, headers, body = [], [], []
    for p in processed:
        if p.assembled:
            elements.extend(p.assembled.elements)
            headers.extend(p.assembled.headers)
            body.extend(p.assembled.body)
    conv_res.assembled = AssembledUnit(elements=elements, headers=headers, body=body)

    return conv_res, processed

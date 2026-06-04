"""
Stage 10: Code & Formula — 识别代码块和数学公式
公式解析为 LaTeX，代码解析为伪代码
使用模型：docling-project/code-formula-v2
"""
from docling.datamodel.document import ConversionResult
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.models.stages.code_formula.code_formula_model import (
    CodeFormulaModel,
    CodeFormulaModelOptions,
)
from docling.datamodel.base_models import ItemAndImageEnrichmentElement
from docling.datamodel.document import PictureItem

from .utils import timed


@timed("Stage 10: Code & Formula")
def run(conv_res: ConversionResult):
    # 构造 enrichment batch（所有有图片的元素）
    element_batch = []
    for element, _level in conv_res.document.iterate_items():
        if isinstance(element, PictureItem) and element.image is not None:
            element_batch.append(
                ItemAndImageEnrichmentElement(
                    item=element,
                    image=element.image.pil_image,
                )
            )

    print("\n" + "=" * 60)
    print("Stage 10: Code & Formula (公式代码解析)")
    print("=" * 60)
    print(f"  待处理的图片元素: {len(element_batch)} 个")

    if not element_batch:
        print("  （未检测到图片元素，跳过）")
        return conv_res

    model = CodeFormulaModel(
        enabled=True,
        artifacts_path=None,
        options=CodeFormulaModelOptions(
            do_code_enrichment=True,
            do_formula_enrichment=True,
        ),
        accelerator_options=AcceleratorOptions(),
    )

    results = list(model(conv_res.document, element_batch))

    for i, item in enumerate(results):
        print(f"\n--- 元素 [{i}]  label={item.label}")
        text = getattr(item, "text", "")
        orig = getattr(item, "orig", "")
        if orig and orig != text:
            print(f"  原文: {orig[:200]}")
        print(f"  文本: {text[:200]}")

    return conv_res

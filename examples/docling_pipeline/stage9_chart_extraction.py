"""
Stage 9: Chart Extraction — 使用 Granite Vision VLM 从图表中提取 CSV 数据、Python 代码、摘要
使用模型：ibm-granite/granite-vision-3.3-2b
模型2B参数，大小8G，CPU下运行测试超慢
"""
from docling.datamodel.document import ConversionResult
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.models.stages.chart_extraction.granite_vision import (
    ChartExtractionModelGraniteVisionV4,
    ChartExtractionModelOptions,
)
from docling.datamodel.base_models import ItemAndImageEnrichmentElement
from docling.datamodel.document import PictureItem

from .utils import timed

CHART_LABELS = {
    "pie_chart", "bar_chart", "stacked_bar_chart", "line_chart",
    "scatter_chart", "heatmap", "flow_chart", "stratigraphic_chart",
}


@timed("Stage 9: Chart Extraction")
def run(conv_res: ConversionResult):
    # 只处理分类为图表类型的 PictureItem
    element_batch = []
    for element, _level in conv_res.document.iterate_items():
        if not isinstance(element, PictureItem) or element.image is None:
            continue
        # 检查分类结果
        if element.meta and element.meta.classification and element.meta.classification.predictions:
            top_class = element.meta.classification.predictions[0].class_name
            if top_class in CHART_LABELS:
                element_batch.append(
                    ItemAndImageEnrichmentElement(
                        item=element,
                        image=element.image.pil_image,
                    )
                )

    print("\n" + "=" * 60)
    print("Stage 9: Chart Extraction (图表解析)")
    print("=" * 60)
    print(f"  待解析的图表元素: {len(element_batch)} 个")

    if not element_batch:
        print("  （未检测到图表元素，跳过解析）")
        return conv_res

    model = ChartExtractionModelGraniteVisionV4(
        enabled=True,
        artifacts_path=None,
        options=ChartExtractionModelOptions(
            chart2csv=True,
            chart2code=True,
            chart2summary=True,
        ),
        accelerator_options=AcceleratorOptions(),
    )

    results = list(model(conv_res.document, element_batch))

    for i, item in enumerate(results):
        print(f"\n--- 图表 [{i}]  label={item.label}")
        for ann in item.annotations:
            kind = getattr(ann, "kind", "?")
            if hasattr(ann, "text"):
                print(f"  [{kind}] {ann.text[:300]}")
            elif hasattr(ann, "data"):
                print(f"  [{kind}] {str(ann.data)[:300]}")
            else:
                print(f"  [{kind}] {str(ann)[:300]}")

    return conv_res

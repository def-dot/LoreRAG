"""
Stage 3: Layout — 布局分析，检测标题、段落、图片、表格等区域
使用模型：docling-project/docling-layout-heron
postprocess: 将 stage 2 的文本单元格分配到布局区域中；Cluster 去重、重叠、包含处理
"""
from docling.datamodel.document import ConversionResult
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.pipeline_options import LayoutOptions
from docling.models.factories import get_layout_factory
from docling.datamodel.base_models import Page

from .utils import timed


@timed("Stage 3: Layout")
def run(conv_res: ConversionResult, pages: list[Page]):
    factory = get_layout_factory()
    layout_model = factory.create_instance(
        options=LayoutOptions(),
        artifacts_path=None,
        accelerator_options=AcceleratorOptions(),
        enable_remote_services=False,
    )

    print("\n" + "=" * 60)
    print("Stage 3: Layout")
    print("=" * 60)

    processed = list(layout_model(conv_res, pages))

    for page in processed:
        layout = page.predictions.layout
        print(f"\n--- 输出: page_no={page.page_no}")
        if layout is None:
            print("  layout 预测: 无")
            continue
        print(f"  检测到 {len(layout.clusters)} 个区域")
        for i, cluster in enumerate(layout.clusters):
            print(f"    [{i}] label={cluster.label}  confidence={cluster.confidence:.2f}  "
                  f"bbox=({cluster.bbox.l:.1f},{cluster.bbox.t:.1f},{cluster.bbox.r:.1f},{cluster.bbox.b:.1f})")

    return conv_res, processed

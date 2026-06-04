"""
Stage 8: Picture Description — 使用 VLM 对图片/图表生成文字描述
使用模型：HuggingFaceTB/SmolVLM-256M-Instruct
"""
from docling.datamodel.document import ConversionResult
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.models.factories import get_picture_description_factory
from docling.datamodel.base_models import ItemAndImageEnrichmentElement
from docling.datamodel.document import PictureItem

from .utils import timed


@timed("Stage 8: Picture Description")
def run(conv_res: ConversionResult):
    # 构造 enrichment batch（只处理有图片的 PictureItem）
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
    print("Stage 8: Picture Description (图片描述)")
    print("=" * 60)
    print(f"  待描述的图片元素: {len(element_batch)} 个")

    if not element_batch:
        print("  （未检测到图片元素，跳过描述）")
        return conv_res

    # 使用 PdfPipelineOptions 默认配置（SmolVLM-256M）
    desc_opts = PdfPipelineOptions().picture_description_options

    factory = get_picture_description_factory()
    desc_model = factory.create_instance(
        options=desc_opts,
        enabled=True,
        artifacts_path=None,
        accelerator_options=AcceleratorOptions(),
        enable_remote_services=False,
    )

    # 运行描述
    results = list(desc_model(conv_res.document, element_batch))

    # 打印结果
    for i, item in enumerate(results):
        print(f"\n--- 图片 [{i}]  label={item.label}")
        if item.meta and item.meta.description:
            print(f"  描述: {item.meta.description.text}")
        else:
            print("  描述: 无")

    return conv_res

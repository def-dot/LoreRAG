"""
Stage 7: Picture Classifier — 对文档中的图片/图表进行分类
使用模型：docling-project/DocumentFigureClassifier-v2.5
"""
from docling.datamodel.document import ConversionResult
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.models.stages.picture_classifier.document_picture_classifier import (
    DocumentPictureClassifier,
)
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import ItemAndImageEnrichmentElement
from docling.datamodel.document import PictureItem

from .utils import timed


@timed("Stage 7: Picture Classifier")
def run(conv_res: ConversionResult):
    # 构造 enrichment batch
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
    print("Stage 7: Picture Classification (图表分类)")
    print("=" * 60)
    print(f"  待分类的图片元素: {len(element_batch)} 个")

    if not element_batch:
        print("  （未检测到图片元素，跳过分类）")
        return conv_res

    # 使用 PdfPipelineOptions 默认配置，禁用 torch.compile（无 MSVC 编译器）
    pic_opts = PdfPipelineOptions().picture_classification_options
    pic_opts.engine_options.compile_model = False

    classifier = DocumentPictureClassifier(
        enabled=True,
        artifacts_path=None,
        options=pic_opts,
        accelerator_options=AcceleratorOptions(),
    )

    # 运行分类
    results = list(classifier(conv_res.document, element_batch))

    # 打印结果
    for i, item in enumerate(results):
        print(f"\n--- 图片 [{i}]  label={item.label}")
        if item.meta and item.meta.classification:
            preds = item.meta.classification.predictions
            print(f"  {preds[0].class_name}  confidence={preds[0].confidence:.4f}")
        else:
            print("  分类结果: 无")

    return conv_res

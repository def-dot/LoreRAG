"""test: 使用 docling-project/DocumentFigureClassifier-v2.5 模型对文档图片进行分类"""

import sys

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    RapidOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption


def classify_pictures(file_path: str) -> None:
    """解析文档，使用 DocumentFigureClassifier-v2.5 对图片进行分类"""
    pipeline_options = PdfPipelineOptions()
    # pipeline_options.ocr_options = RapidOcrOptions()
    pipeline_options.do_ocr = False
    pipeline_options.generate_page_images = True
    pipeline_options.do_picture_classification = True

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )

    result = converter.convert(file_path)
    doc = result.document

    pic_count = 0
    for element, level in doc.iterate_items():
        label = getattr(element, "label", None)
        if label != "picture":
            continue

        pic_count += 1
        text = getattr(element, "text", "")

        print("=" * 60)
        print(f"[图片 #{pic_count}] 层级: {level}")
        if text:
            print(f"  伴随文本: {text[:200]}")

        # 分类结果
        classification = getattr(element, "classification", None)
        if classification is not None:
            print(f"  分类结果: {classification}")
            if hasattr(classification, "label"):
                print(f"  分类标签: {classification.label}")
            if hasattr(classification, "confidence"):
                print(f"  置信度: {classification.confidence:.4f}")
        else:
            print("  (未获取到分类结果)")

        # 保存图片
        if hasattr(element, "image") and element.image is not None:
            out_path = f"test2_pic_{pic_count}.png"
            element.image.pil_image.save(out_path)
            print(f"  图片已保存: {out_path}")

        print()

    if pic_count == 0:
        print("文档中未检测到图片元素")
    else:
        print(f"共检测到 {pic_count} 张图片")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "1.pdf"
    classify_pictures(target)

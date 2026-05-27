"""test: 使用 docling do_chart_extraction 解析文档图表中的数值"""

import os
import sys

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    ChartExtractionModelOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption


def parse_document(file_path: str) -> None:
    """解析文档，提取文本与图表数值"""
    if not os.path.isfile(file_path):
        print(f"文件不存在: {file_path}")
        sys.exit(1)

    pipeline_options = PdfPipelineOptions()
    pipeline_options.ocr_options = RapidOcrOptions()
    pipeline_options.do_ocr = True
    pipeline_options.generate_page_images = True
    # 启用图表提取：csv + 摘要
    pipeline_options.do_chart_extraction = True
    pipeline_options.chart_extraction_options = ChartExtractionModelOptions(
        chart2csv=True,
        chart2summary=True,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )

    result = converter.convert(file_path)
    doc = result.document

    chart_count = 0

    for element, level in doc.iterate_items():
        label = getattr(element, "label", None)
        text = getattr(element, "text", "")

        # 图表 / 图片
        if label == "picture":
            chart_count += 1
            print("=" * 60)
            print(f"[图表 #{chart_count}] 层级: {level}")
            if text:
                print(f"  伴随文本: {text[:200]}")

            # 保存图片
            if hasattr(element, "image") and element.image is not None:
                out_path = f"test_chart_{chart_count}.png"
                element.image.pil_image.save(out_path)
                print(f"  图片已保存: {out_path}")

            # 提取 chart extraction 结果
            meta = getattr(element, "meta", None)
            if meta is not None:
                # CSV 数值数据 → 表格形式输出
                tabular = getattr(meta, "tabular_chart", None)
                if tabular is not None and hasattr(tabular, "chart_data"):
                    chart_data = tabular.chart_data
                    print(f"  图表数据 (CSV):")
                    if hasattr(chart_data, "grid"):
                        for row in chart_data.grid:
                            cells = [c.text for c in row]
                            print(f"    {' | '.join(cells)}")

                # 文字摘要
                desc = getattr(meta, "description", None)
                if desc is not None:
                    desc_text = getattr(desc, "text", str(desc))
                    print(f"  图表摘要: {desc_text}")

                # Python 代码
                code = getattr(meta, "code", None)
                if code is not None:
                    code_text = getattr(code, "text", str(code))
                    print(f"  图表代码:\n{code_text}")

            if meta is None:
                print("  (未提取到图表元数据)")
            print()

        # 表格
        elif label == "table":
            print("=" * 60)
            print(f"[表格] 层级: {level}")
            if text:
                print(f"  内容:\n{text[:500]}")
            print()

    # 导出完整 Markdown
    md = doc.export_to_markdown()
    print("\n" + "=" * 60)
    print("完整 Markdown 导出:")
    print("=" * 60)
    print(md[:2000])


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "1.pdf"
    parse_document(target)

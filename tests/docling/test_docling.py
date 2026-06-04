"""
手动逐步执行 Docling StandardPdfPipeline 的各个阶段
每个阶段的实现拆分在 pdf_pipeline/ 目录下
"""
from pathlib import Path
from docling.datamodel.document import ConversionResult, InputDocument
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.datamodel.base_models import InputFormat, Page

from tests.docling.pdf_pipeline import (
    stage1_preprocess,
    stage2_ocr,
    stage3_layout,
    stage4_table,
    stage5_assemble,
    stage6_reading_order,
    stage7_picture_classifier,
    stage8_picture_description,
    stage9_chart_extraction,
    stage10_code_formula,
)

PDF_PATH = Path(__file__).resolve().parent / "test.pdf"


def _init_document(pdf_path: Path = PDF_PATH):
    """加载 PDF，创建 conv_res 和 pages"""
    in_doc = InputDocument(
        path_or_stream=pdf_path,
        format=InputFormat.PDF,
        backend=DoclingParseDocumentBackend,
    )
    conv_res = ConversionResult(input=in_doc)

    pages = []
    for i in range(in_doc.page_count):
        page = Page(page_no=i + 1)
        page._backend = in_doc._backend.load_page(i)
        if page._backend.is_valid():
            page.size = page._backend.get_size()
        pages.append(page)

    return conv_res, pages


def run_all():
    """运行完整流水线"""
    conv_res, pages = _init_document()

    # ── Page-level stages ──
    conv_res, pages = stage1_preprocess.run(conv_res, pages)
    conv_res, pages = stage2_ocr.run(conv_res, pages)
    conv_res, pages = stage3_layout.run(conv_res, pages)
    conv_res, pages = stage4_table.run(conv_res, pages)
    conv_res, pages = stage5_assemble.run(conv_res, pages)

    # ── Document-level stages ──
    conv_res = stage6_reading_order.run(conv_res, pages)
    conv_res = stage7_picture_classifier.run(conv_res)
    conv_res = stage8_picture_description.run(conv_res)
    conv_res = stage9_chart_extraction.run(conv_res)
    conv_res = stage10_code_formula.run(conv_res)

    return conv_res


if __name__ == "__main__":
    run_all()

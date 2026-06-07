from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    RapidOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption


def _init_converter() -> DocumentConverter:
    """初始化 Docling 转换引擎 — 仅 PDF"""
    """构建 PDF 全能力管线选项（使用 Docling 内置 SmolVLM 默认图片描述）"""
    opts = PdfPipelineOptions()

    opts.document_timeout = 300.0

    # ---- OCR ----
    opts.do_ocr = True
    opts.ocr_options = RapidOcrOptions()

    opts.do_table_structure = True

    # opts.do_formula_enrichment = True
    # opts.do_code_enrichment = True

    # opts.do_picture_classification = True

    opts.do_picture_description = True

    # ---- 图表提取 ----
    # opts.do_chart_extraction = True
    # opts.chart_extraction_options = ChartExtractionModelOptions(
    #     chart2csv=True,
    #     chart2code=True,
    #     chart2summary=True,
    # )

    # ---- 图片生成 ----
    # opts.generate_page_images = True
    # opts.generate_picture_images = True
    # opts.generate_table_images = True
    opts.images_scale = 2.0

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=opts),
        }
    )

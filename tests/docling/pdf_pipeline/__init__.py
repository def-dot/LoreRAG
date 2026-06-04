"""
PDF Pipeline 手动逐步执行 Docling StandardPdfPipeline 的各个阶段

流水线:
  preprocess → ocr → layout → table → assemble → reading_order
  → picture_classifier → picture_description → chart_extraction → code_formula
"""
from . import (
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

__all__ = [
    "stage1_preprocess",
    "stage2_ocr",
    "stage3_layout",
    "stage4_table",
    "stage5_assemble",
    "stage6_reading_order",
    "stage7_picture_classifier",
    "stage8_picture_description",
    "stage9_chart_extraction",
    "stage10_code_formula",
]

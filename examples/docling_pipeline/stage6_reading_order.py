"""
Stage 6: Reading Order — 确定文档阅读顺序，将 assembled elements 组装成 DoclingDocument
左->右、上->下，caption/footnote 等特殊元素的归属关系
"""
from docling.datamodel.document import ConversionResult
from docling.models.stages.reading_order.readingorder_model import (
    ReadingOrderModel,
    ReadingOrderOptions,
)
from docling.datamodel.base_models import Page

from .utils import timed, generate_element_images


@timed("Stage 6: Reading Order")
def run(conv_res: ConversionResult, pages: list[Page]):
    model = ReadingOrderModel(options=ReadingOrderOptions())

    print("\n" + "=" * 60)
    print("Stage 6: Reading Order")
    print("=" * 60)

    doc = model(conv_res)
    conv_res.document = doc

    # 为 table/picture 元素生成裁剪图片
    img_count = generate_element_images(conv_res)
    print(f"  生成元素图片: {img_count} 张")

    # 统计文档元素
    texts, tables, pictures = [], [], []
    for element, level in doc.iterate_items():
        if hasattr(element, "label"):
            lbl = element.label
            if lbl == "table":
                tables.append(element)
            elif lbl in ("picture", "chart"):
                pictures.append(element)
            else:
                texts.append(element)

    print(f"\n  DoclingDocument 元素统计:")
    print(f"    texts:      {len(texts)}")
    print(f"    tables:     {len(tables)}")
    print(f"    pictures:   {len(pictures)}")

    # 按阅读顺序打印
    print(f"\n  阅读顺序:")
    for i, (element, level) in enumerate(doc.iterate_items()):
        label = getattr(element, "label", "?")
        text = getattr(element, "text", "")
        prov = getattr(element, "prov", None)
        page_no = prov[0].page_no if prov else "?"
        indent = "  " * level
        print(f"    [{i}] {indent}{label:20s}  page={page_no}  text=[{text[:50]}]")

    # 打印表格概览
    for i, tbl in enumerate(tables):
        data = getattr(tbl, "data", None)
        prov = getattr(tbl, "prov", None)
        page_no = prov[0].page_no if prov else "?"
        rows = getattr(data, "num_rows", 0) if data else 0
        cols = getattr(data, "num_cols", 0) if data else 0
        print(f"\n  表格 [{i}]  page={page_no}  {rows}行 x {cols}列")

    # 打印图片/图表概览
    for i, pic in enumerate(pictures):
        prov = getattr(pic, "prov", None)
        page_no = prov[0].page_no if prov else "?"
        caps = getattr(pic, "captions", [])
        cap_text = ""
        if caps:
            cap_text = getattr(caps[0].resolve(doc) if hasattr(caps[0], "resolve") else caps[0], "text", "")[:50]
        print(f"  图片/图表 [{i}]  page={page_no}  caption=[{cap_text}]")

    return conv_res

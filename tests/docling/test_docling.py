"""
手动逐步执行 Docling StandardPdfPipeline 的各个阶段，
流水线: preprocess → ocr → layout → table → assemble → reading_order → picture_classifier
"""

from pathlib import Path
from docling.datamodel.document import ConversionResult, InputDocument
from docling.models.stages.page_preprocessing.page_preprocessing_model import (
    PagePreprocessingModel,
    PagePreprocessingOptions,
)
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.datamodel.base_models import InputFormat, Page

PDF_PATH = Path(__file__).resolve().parent / "test.pdf"


# ── Stage 1: Preprocess ─────────────────────────────────────────────────
def test_stage_preprocess():
    """preprocess: 加载页面图像 + 提取文本单元格"""
    in_doc = InputDocument(
        path_or_stream=PDF_PATH,
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

    model = PagePreprocessingModel(options=PagePreprocessingOptions(images_scale=2.0))

    print("=" * 60)
    print("Stage 1: Preprocess")
    print("=" * 60)

    processed = list(model(conv_res, pages))

    for page in processed:
        print(f"\n--- 输出: page_no={page.page_no}")
        print(f"  parsed_page: {'有' if page.parsed_page else '无'}")
        print(f"  textline_cells 数: {len(page.cells)}")
        img = page.get_image(scale=1.0)
        print(f"  image 尺寸: {img.size if img else '无'}")
        for i, cell in enumerate(page.cells[:5]):
            print(f"    [{i}] text=[{cell.text[:60]}]")
        if len(page.cells) > 5:
            print(f"    ... 共 {len(page.cells)} 个 cell")

    return conv_res, processed


# ── Stage 2: OCR ────────────────────────────────────────────────────────
def test_stage_ocr():
    """ocr: 对位图区域做 OCR，补充文本单元格"""
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import RapidOcrOptions
    from docling.models.factories import get_ocr_factory

    conv_res, pages = test_stage_preprocess()

    factory = get_ocr_factory()
    ocr_model = factory.create_instance(
        options=RapidOcrOptions(),
        enabled=True,
        artifacts_path=None,
        accelerator_options=AcceleratorOptions(),
    )

    print("\n" + "=" * 60)
    print("Stage 2: OCR")
    print("=" * 60)
    for page in pages:
        print(f"\n--- 输入: page_no={page.page_no}, cells数={len(page.cells)}")

    processed = list(ocr_model(conv_res, pages))

    for page in processed:
        print(f"\n--- 输出: page_no={page.page_no}")
        print(f"  OCR 后 cells 数: {len(page.cells)}")
        ocr_cells = [c for c in page.cells if getattr(c, "from_ocr", False)]
        print(f"  其中 OCR 新增: {len(ocr_cells)}")
        for i, cell in enumerate(ocr_cells[:5]):
            print(f"    [{i}] text=[{cell.text[:60]}]")

    return conv_res, processed


# ── Stage 3: Layout ─────────────────────────────────────────────────────
def test_stage_layout():
    """layout: 布局分析，检测标题、段落、图片、表格等区域"""
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import LayoutOptions
    from docling.models.factories import get_layout_factory

    conv_res, pages = test_stage_ocr()

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


# ── Stage 4: Table ──────────────────────────────────────────────────────
def test_stage_table():
    """table: 识别表格结构（行、列、合并单元格）"""
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import TableStructureOptions
    from docling.models.factories import get_table_structure_factory

    conv_res, pages = test_stage_layout()

    factory = get_table_structure_factory()
    table_model = factory.create_instance(
        options=TableStructureOptions(),
        enabled=True,
        artifacts_path=None,
        accelerator_options=AcceleratorOptions(),
        enable_remote_services=False,
    )

    print("\n" + "=" * 60)
    print("Stage 4: Table Structure")
    print("=" * 60)
    for page in pages:
        layout = page.predictions.layout
        tables = [c for c in (layout.clusters if layout else []) if c.label == "table"]
        print(f"\n--- 输入: page_no={page.page_no}, 表格区域数={len(tables)}")

    processed = list(table_model(conv_res, pages))

    for page in processed:
        ts = page.predictions.tablestructure
        print(f"\n--- 输出: page_no={page.page_no}")
        if ts is None:
            print("  表格结构: 无")
            continue
        tables = ts.table_map
        print(f"  识别到 {len(tables)} 个表格结构")
        for i, tbl in tables.items():
            if hasattr(tbl, "num_rows") and hasattr(tbl, "num_cols"):
                print(f"    [{i}] {tbl.num_rows}行 x {tbl.num_cols}列")
            else:
                print(f"    [{i}] {tbl}")

    return conv_res, processed


# ── Stage 5: Assemble ──────────────────────────────────────────────────
def test_stage_assemble():
    """assemble: 将预测结果组装成结构化文档元素"""
    from docling.models.stages.page_assemble.page_assemble_model import (
        PageAssembleModel,
        PageAssembleOptions,
    )
    from docling.datamodel.base_models import AssembledUnit

    conv_res, pages = test_stage_table()

    model = PageAssembleModel(options=PageAssembleOptions())

    print("\n" + "=" * 60)
    print("Stage 5: Assemble")
    print("=" * 60)

    processed = list(model(conv_res, pages))

    for page in processed:
        print(f"\n--- 输出: page_no={page.page_no}")
        if page.assembled:
            print(f"  elements 数: {len(page.assembled.elements)}")
            for i, elem in enumerate(page.assembled.elements[:10]):
                label = getattr(elem, "label", "?")
                text = getattr(elem, "text", "")
                print(f"    [{i}] label={label}  text=[{text}]")
            if len(page.assembled.elements) > 10:
                print(f"    ... 共 {len(page.assembled.elements)} 个元素")
        else:
            print("  assembled: 无")

    # 将 processed 页面写回 conv_res，供后续 ReadingOrderModel 使用
    conv_res.pages = processed
    elements, headers, body = [], [], []
    for p in processed:
        if p.assembled:
            elements.extend(p.assembled.elements)
            headers.extend(p.assembled.headers)
            body.extend(p.assembled.body)
    conv_res.assembled = AssembledUnit(elements=elements, headers=headers, body=body)

    return conv_res, processed


# ── Stage 6: Reading Order ───────────────────────────────────────────────
def test_stage_reading_order():
    """reading_order: 确定文档阅读顺序，将 assembled elements 组装成 DoclingDocument"""
    from docling.models.stages.reading_order.readingorder_model import (
        ReadingOrderModel,
        ReadingOrderOptions,
    )
    from docling.datamodel.document import PictureItem, TableItem

    conv_res, pages = test_stage_assemble()

    model = ReadingOrderModel(options=ReadingOrderOptions())

    print("\n" + "=" * 60)
    print("Stage 6: Reading Order")
    print("=" * 60)

    doc = model(conv_res)
    conv_res.document = doc

    # 统计文档元素
    headings, texts, tables, pictures, list_items, groups = [], [], [], [], [], []
    for element, level in doc.iterate_items(with_groups=True):
        if hasattr(element, "label"):
            lbl = element.label
            if lbl == "section_header":
                headings.append(element)
            elif lbl == "table":
                tables.append(element)
            elif lbl in ("picture", "chart"):
                pictures.append(element)
            elif lbl == "list_item":
                list_items.append(element)
            else:
                texts.append(element)
        else:
            groups.append(element)

    print(f"\n  DoclingDocument 元素统计:")
    print(f"    headings:   {len(headings)}")
    print(f"    texts:      {len(texts)}")
    print(f"    tables:     {len(tables)}")
    print(f"    pictures:   {len(pictures)}")
    print(f"    list_items: {len(list_items)}")
    print(f"    groups:     {len(groups)}")

    # 按阅读顺序打印前 20 个元素
    print(f"\n  阅读顺序（前 20 项）:")
    for i, (element, level) in enumerate(doc.iterate_items()):
        if i >= 20:
            print(f"    ... 共 {sum(1 for _ in doc.iterate_items())} 个元素（省略）")
            break
        label = getattr(element, "label", "?")
        text = getattr(element, "text", "")
        prov = getattr(element, "prov", None)
        page_no = prov[0].page_no if prov else "?"
        indent = "  " * level
        print(f"    [{i}] {indent}{label:20s}  page={page_no}  text=[{text[:50]}]")

    # 打印标题结构
    if headings:
        print(f"\n  标题层级:")
        for h in headings:
            text = getattr(h, "text", "")[:60]
            prov = getattr(h, "prov", None)
            page_no = prov[0].page_no if prov else "?"
            print(f"    page={page_no}  [{text}]")

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

    return conv_res, doc


# ── Stage 7: Picture Classification (图表分类) ────────────────────────────
def test_stage_picture_classifier():
    """picture_classifier: 对文档中的图片/图表进行分类（饼图、柱状图、折线图等）"""
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.models.stages.picture_classifier.document_picture_classifier import (
        DocumentPictureClassifier,
        DocumentPictureClassifierOptions,
    )
    from docling_core.types.doc.document import ImageRef
    from docling.datamodel.base_models import ItemAndImageEnrichmentElement
    from docling.datamodel.document import PictureItem

    # 先完成 Stage 1-6
    conv_res, doc = test_stage_reading_order()

    # 生成图片元素的裁剪图像（ImageRef）
    scale = 2.0
    for element, _level in doc.iterate_items():
        if not isinstance(element, PictureItem) or len(element.prov) == 0:
            continue
        page_no = element.prov[0].page_no
        page = next((p for p in conv_res.pages if p.page_no == page_no), None)
        if page is None or page.size is None or page.image is None:
            continue
        crop_bbox = (
            element.prov[0]
            .bbox.scaled(scale=scale)
            .to_top_left_origin(page_height=page.size.height * scale)
        )
        cropped = page.image.crop(crop_bbox.as_tuple())
        element.image = ImageRef.from_pil(cropped, dpi=int(72 * scale))

    # 构造 enrichment batch
    element_batch = []
    for element, _level in doc.iterate_items():
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
        return conv_res, doc

    # 初始化分类器
    classifier = DocumentPictureClassifier(
        enabled=True,
        artifacts_path=None,
        options=DocumentPictureClassifierOptions(),
        accelerator_options=AcceleratorOptions(),
    )

    # 运行分类
    results = list(classifier(doc, element_batch))

    # 打印结果
    for i, item in enumerate(results):
        print(f"\n--- 图片 [{i}]  label={item.label}")
        if item.meta and item.meta.classification:
            preds = item.meta.classification.predictions
            for j, pred in enumerate(preds[:5]):
                print(f"  [{j}] {pred.class_name:30s}  confidence={pred.confidence:.4f}")
            if len(preds) > 5:
                print(f"  ... 共 {len(preds)} 个类别")
        else:
            print("  分类结果: 无")

    return conv_res, doc


if __name__ == "__main__":
    # test_stage_preprocess()
    # test_stage_ocr()
    # test_stage_layout()
    # test_stage_table()
    # test_stage_assemble()
    test_stage_reading_order()
    # test_stage_picture_classifier()

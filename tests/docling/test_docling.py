"""
手动逐步执行 Docling StandardPdfPipeline 的各个阶段，
流水线: preprocess → ocr → layout → table → assemble → reading_order → picture_classifier → picture_description
"""

from pathlib import Path
from docling.datamodel.document import ConversionResult, InputDocument
from docling.models.stages.page_preprocessing.page_preprocessing_model import (
    PagePreprocessingModel,
    PagePreprocessingOptions,
)
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.datamodel.base_models import InputFormat, Page

from app.routers.items import list_items

PDF_PATH = Path(__file__).resolve().parent / "test.pdf"


# ── Stage 1: Preprocess ─────────────────────────────────────────────────
def test_stage_preprocess():
    """
    preprocess: 加载页面图像 + 提取文本单元格,
    使用docling parse，基于文本流的提取
    """
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
    """
    ocr: 对位图区域做 OCR，补充文本单元格，
    使用： RapidOCR，det -> cls -> rec
    结果会和Stage 1的文本单元格合并，cell.from_ocr=True 表示该单元格来自 OCR 新增
    """
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
    """
    layout: 布局分析，检测标题、段落、图片、表格等区域
    使用模型：docling-project/docling-layout-heron
    postprocess: 将stage 2的文本单元格分配到布局区域中；Cluster去重，重叠，包含处理（特殊的Cluster， 如图片、表格、Form等会包括Text类型的Cluster）
    """
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
    """
    table: 识别表格结构（行、列、合并单元格）
    使用模型：docling-project--docling-models/model_artifacts/tableformer
    返回Table对象：table_cells,nrow,ncols
    """
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
    """
    assemble: 将预测结果组装成结构化文档元素
    将layout，table，picture等结果进行合并，生成元素列表（Element），每个元素包含文本、位置、类型等信息
    """
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


# ── Helper: 为 table/picture 元素生成裁剪图片 ─────────────────────────────
def _generate_element_images(conv_res: ConversionResult, scale: float = 2.0):
    """从页面图像中裁剪 table/picture 元素图片，写入 element.image (ImageRef) 并保存到本地"""
    from docling_core.types.doc.document import ImageRef
    from docling.datamodel.document import PictureItem, TableItem

    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(exist_ok=True)

    page_map = {p.page_no: p for p in conv_res.pages}
    count = 0
    for element, _level in conv_res.document.iterate_items():
        if not isinstance(element, (PictureItem, TableItem)):
            continue
        if len(element.prov) == 0:
            continue
        page = page_map.get(element.prov[0].page_no)
        if page is None or page.size is None or page.image is None:
            continue
        crop_bbox = (
            element.prov[0]
            .bbox.scaled(scale=scale)
            .to_top_left_origin(page_height=page.size.height * scale)
        )
        cropped_im = page.image.crop(crop_bbox.as_tuple())
        element.image = ImageRef.from_pil(cropped_im, dpi=int(72 * scale))

        # 保存到本地
        label = element.label
        page_no = element.prov[0].page_no
        filename = out_dir / f"{label}_p{page_no}_{count}.png"
        cropped_im.save(filename)
        print(f"    保存: {filename}")
        count += 1
    return count


# ── Stage 6: Reading Order ───────────────────────────────────────────────
def test_stage_reading_order():
    """
    reading_order: 确定文档阅读顺序，左->右、上->下，caption/footnote等特殊元素的归属关系
    """
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

    # 为 table/picture 元素生成裁剪图片
    img_count = _generate_element_images(conv_res)
    print(f"  生成元素图片: {img_count} 张")

    # 统计文档元素
    texts, tables, pictures= [], [], []
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


# ── Stage 7: Picture Classification (图表分类) ────────────────────────────
def test_stage_picture_classifier():
    """
    picture_classifier: 对文档中的图片/图表进行分类（饼图、柱状图、折线图等）
    使用模型：docling-project/DocumentFigureClassifier-v2.5
    """
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.models.stages.picture_classifier.document_picture_classifier import (
        DocumentPictureClassifier,
    )
    from docling_core.types.doc.document import ImageRef
    from docling.datamodel.base_models import ItemAndImageEnrichmentElement
    from docling.datamodel.document import PictureItem

    # 先完成 Stage 1-6（图片已在 Stage 6 生成）
    conv_res = test_stage_reading_order()

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
    from docling.datamodel.pipeline_options import PdfPipelineOptions
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


# ── Stage 8: Picture Description (图片描述) ──────────────────────────────
def test_stage_picture_description():
    """
    picture_description: 使用 VLM (SmolVLM-256M) 对图片/图表生成文字描述
    使用模型：HuggingFaceTB/SmolVLM-256M-Instruct
    """
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.models.factories import get_picture_description_factory
    from docling.datamodel.base_models import ItemAndImageEnrichmentElement
    from docling.datamodel.document import PictureItem

    # 先完成 Stage 1-7
    conv_res = test_stage_picture_classifier()

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


if __name__ == "__main__":
    # test_stage_preprocess()
    # test_stage_ocr()
    # test_stage_layout()
    # test_stage_table()
    # test_stage_assemble()
    # test_stage_reading_order()
    # test_stage_picture_classifier()
    test_stage_picture_description()

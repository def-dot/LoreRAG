"""
手动逐步执行 Docling StandardPdfPipeline 的各个阶段，
流水线: preprocess → ocr → layout → table → assemble
"""

from pathlib import Path

PDF_PATH = Path(__file__).resolve().parent / "test.pdf"


def _prepare():
    """准备 ConversionResult + 页面列表（手动加载 backend）"""
    from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
    from docling.datamodel.base_models import InputFormat, Page
    from docling.datamodel.document import ConversionResult, InputDocument

    in_doc = InputDocument(
        path_or_stream=PDF_PATH,
        format=InputFormat.PDF,
        backend=DoclingParseDocumentBackend,
    )
    conv_res = ConversionResult(input=in_doc)

    pages = []
    for i in range(in_doc.page_count):
        page = Page(page_no=i + 1)
        page_backend = in_doc._backend.load_page(i)
        page._backend = page_backend
        if page_backend.is_valid():
            page.size = page_backend.get_size()
        pages.append(page)

    return conv_res, pages


# ── Stage 1: Preprocess ─────────────────────────────────────────────────
def test_stage_preprocess():
    """preprocess: 加载页面图像 + 提取文本单元格"""
    if not PDF_PATH.exists():
        return print("跳过: PDF 不存在"), []

    from docling.models.stages.page_preprocessing.page_preprocessing_model import (
        PagePreprocessingModel,
        PagePreprocessingOptions,
    )

    conv_res, pages = _prepare()
    model = PagePreprocessingModel(options=PagePreprocessingOptions(images_scale=2.0))

    print("=" * 60)
    print("Stage 1: Preprocess")
    print("=" * 60)
    for page in pages:
        print(f"\n--- 输入: page_no={page.page_no}, size={page.size}, cells数={len(page.cells)}")

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
    if not PDF_PATH.exists():
        return print("跳过: PDF 不存在"), []

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
    if not PDF_PATH.exists():
        return print("跳过: PDF 不存在"), []

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
    if not PDF_PATH.exists():
        return print("跳过: PDF 不存在"), []

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
        tables = ts.table_predictions if hasattr(ts, "table_predictions") else []
        print(f"  识别到 {len(tables)} 个表格结构")
        for i, tbl in enumerate(tables[:3]):
            if hasattr(tbl, "num_rows") and hasattr(tbl, "num_cols"):
                print(f"    [{i}] {tbl.num_rows}行 x {tbl.num_cols}列")
            else:
                print(f"    [{i}] {tbl}")

    return conv_res, processed


# ── Stage 5: Assemble ──────────────────────────────────────────────────
def test_stage_assemble():
    """assemble: 将预测结果组装成结构化文档元素"""
    if not PDF_PATH.exists():
        return print("跳过: PDF 不存在"), []

    from docling.models.stages.page_assemble.page_assemble_model import (
        PageAssembleModel,
        PageAssembleOptions,
    )

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
                text = getattr(elem, "text", "")[:60]
                print(f"    [{i}] label={label}  text=[{text}]")
            if len(page.assembled.elements) > 10:
                print(f"    ... 共 {len(page.assembled.elements)} 个元素")
        else:
            print("  assembled: 无")

    return conv_res, processed


if __name__ == "__main__":
    test_stage_preprocess()
    test_stage_ocr()
    test_stage_layout()
    test_stage_table()
    test_stage_assemble()

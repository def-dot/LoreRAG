"""
Stage 4: Table — 识别表格结构（行、列、合并单元格）
使用模型：docling-project--docling-models/model_artifacts/tableformer
返回 Table 对象：table_cells, num_rows, num_cols
"""
from docling.datamodel.document import ConversionResult
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.pipeline_options import TableStructureOptions
from docling.models.factories import get_table_structure_factory
from docling.datamodel.base_models import Page

from .utils import timed


@timed("Stage 4: Table")
def run(conv_res: ConversionResult, pages: list[Page]):
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

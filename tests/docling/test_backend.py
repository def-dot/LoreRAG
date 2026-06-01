"""DoclingParseDocumentBackend 测试"""

from pathlib import Path


def _make_input_doc():
    from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.document import InputDocument

    pdf_path = Path(__file__).resolve().parent / "test.pdf"
    return InputDocument(
        path_or_stream=pdf_path,
        format=InputFormat.PDF,
        backend=DoclingParseDocumentBackend,
    )


def test_page_count():
    in_doc = _make_input_doc()
    assert in_doc.valid
    assert in_doc.page_count > 0
    print(f"页数: {in_doc.page_count}")
    in_doc._backend.unload()


def test_load_page():
    in_doc = _make_input_doc()
    page = in_doc._backend.load_page(0)

    assert page.is_valid()
    size = page.get_size()
    assert size.width > 0 and size.height > 0
    print(f"页面尺寸: {size.width:.1f} x {size.height:.1f}")

    page.unload()
    in_doc._backend.unload()


def test_get_text_cells():
    """提取页面文本单元格（包含位置、字体等信息）"""
    in_doc = _make_input_doc()
    page = in_doc._backend.load_page(0)
    cells = list(page.get_text_cells())

    print(f"\n文本单元格数: {len(cells)}")
    for i, cell in enumerate(cells):
        bbox = cell.rect.to_bounding_box().to_top_left_origin(page.get_size().height)
        print(
            f"  [{i}] font_key={cell.font_key}  "
            f"y={bbox.t:.1f}  x=[{bbox.l:.1f}, {bbox.r:.1f}]  "
            f"text=[{cell.text}]"
        )

    page.unload()
    in_doc._backend.unload()


def test_get_page_image():
    """渲染 PDF 页面为图像"""
    in_doc = _make_input_doc()
    page = in_doc._backend.load_page(0)
    image = page.get_page_image(scale=1.0)

    assert image.size[0] > 0 and image.size[1] > 0
    print(f"页面图像尺寸: {image.size}")

    out_path = Path(__file__).resolve().parent / "test_page_image.png"
    image.save(out_path)
    print(f"已保存: {out_path}")

    page.unload()
    in_doc._backend.unload()


def test_get_page_images():
    """提取 PDF 页面中嵌入的图片"""
    in_doc = _make_input_doc()
    page = in_doc._backend.load_page(0)

    page._ensure_parsed()
    bitmaps = page._dpage.bitmap_resources

    print(f"\n嵌入图片数: {len(bitmaps)}")
    for i, bmp in enumerate(bitmaps):
        print(f"  [{i}] rect={bmp.rect}  mode={bmp.mode}")
        if bmp.image is not None:
            out_path = Path(__file__).resolve().parent / f"test_bitmap_{i}.png"
            bmp.image.pil_image.save(out_path)
            print(f"       已保存: {out_path}  尺寸={bmp.image.pil_image.size}")
        else:
            print(f"       无图片数据 (mode={bmp.mode})")

    page.unload()
    in_doc._backend.unload()


if __name__ == "__main__":
    test_page_count()
    test_load_page()
    test_get_text_cells()
    test_get_page_image()
    test_get_page_images()


import time
import functools
from pathlib import Path
from docling.datamodel.document import ConversionResult
from docling_core.types.doc.document import ImageRef
from docling.datamodel.document import PictureItem, TableItem


def generate_element_images(conv_res: ConversionResult, scale: float = 2.0):
    """从页面图像中裁剪 table/picture 元素图片，写入 element.image (ImageRef) 并保存到本地"""
    out_dir = Path(__file__).resolve().parent.parent / "output"
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


def timed(stage_name: str):
    """装饰器：为 stage 函数计时并打印耗时"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print(f"\n⏱  {stage_name} 开始...")
            t0 = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - t0
            print(f"⏱  {stage_name} 完成，耗时: {elapsed:.2f}s")
            return result
        return wrapper
    return decorator

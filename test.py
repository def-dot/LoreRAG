"""
使用 CLIP 模型进行零样本图片分类。
无需 docling，只需 transformers + torch。
首次运行会自动下载模型 (~600MB)。
"""
from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

# ---------------------------------------------------------------------------
# 可自定义分类标签
# ---------------------------------------------------------------------------
CANDIDATE_LABELS = [
    "a bar chart",
    "a pie chart",
    "a line chart",
    "a scatter plot",
    "a flowchart or diagram",
    "a table",
    "a natural photograph",
    "a screenshot of a user interface",
    "a map",
    "a mathematical formula",
    "a logo or icon",
    "a scanned document page with text only",
]

MODEL_ID = "openai/clip-vit-base-patch32"


def load_model(model_id: str = MODEL_ID) -> tuple[CLIPModel, CLIPProcessor]:
    """加载 CLIP 模型和处理器。"""
    model = CLIPModel.from_pretrained(model_id)
    processor = CLIPProcessor.from_pretrained(model_id)
    model.eval()
    return model, processor


def classify_image(
    image: Image.Image,
    model: CLIPModel,
    processor: CLIPProcessor,
    labels: list[str] | None = None,
) -> list[tuple[str, float]]:
    """对单张 PIL 图片进行零样本分类，返回 (标签, 置信度) 列表，按置信度降序排列。"""
    if labels is None:
        labels = CANDIDATE_LABELS

    inputs = processor(
        text=labels,
        images=image,
        return_tensors="pt",
        padding=True,
    )

    with torch.no_grad():
        outputs = model(**inputs)
        logits_per_image = outputs.logits_per_image  # shape: (1, num_labels)
        probs = logits_per_image.softmax(dim=1).squeeze(0)

    results = [(labels[i], round(probs[i].item(), 4)) for i in range(len(labels))]
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def classify_file(
    file_path: str | Path,
    model: CLIPModel,
    processor: CLIPProcessor,
    labels: list[str] | None = None,
    top_k: int = 3,
) -> None:
    """分类单个图片文件并打印结果。"""
    image = Image.open(file_path).convert("RGB")
    results = classify_image(image, model, processor, labels)

    print(f"\n📷 {Path(file_path).name}")
    print("-" * 50)
    for label, score in results[:top_k]:
        bar = "█" * int(score * 40)
        print(f"  {score:.2%}  {bar}")
        print(f"          {label}")
    print("-" * 50)


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="零样本图片分类器 (CLIP)")
    parser.add_argument("image", nargs="+", help="图片文件路径(支持多个)")
    parser.add_argument("--top-k", type=int, default=3, help="输出前 K 个结果")
    parser.add_argument(
        "--labels",
        nargs="*",
        default=None,
        help="自定义标签, 例如 --labels 'a chart' 'a photo' 'a diagram'",
    )
    args = parser.parse_args()

    labels = args.labels if args.labels else CANDIDATE_LABELS
    print(f"加载模型: {MODEL_ID} ...", end=" ", flush=True)
    model, processor = load_model()
    print("done")

    for path in args.image:
        classify_file(path, model, processor, labels, top_k=args.top_k)

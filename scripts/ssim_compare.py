#!/usr/bin/env python3
"""Compare two PNG files with Structural Similarity Index (SSIM)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class DependencyError(RuntimeError):
    """Raised when a required runtime dependency is missing."""


def load_grayscale(path: Path) -> tuple[Any, tuple[int, int]]:
    """Load an image as a grayscale PIL image plus its (width, height)."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise DependencyError(
            "ssim_compare.py requires Pillow. Install with: python3 -m pip install Pillow"
        ) from exc

    image = Image.open(path.expanduser().resolve()).convert("L")
    return image, image.size


def compute_ssim(image_a: Path, image_b: Path) -> dict[str, Any]:
    """Compute SSIM between two image paths, resizing image B if needed."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise DependencyError(
            "ssim_compare.py requires numpy and Pillow. "
            "Install with: python3 -m pip install numpy Pillow scikit-image"
        ) from exc

    try:
        from skimage.metrics import structural_similarity
    except ImportError:
        structural_similarity = None

    path_a = image_a.expanduser().resolve()
    path_b = image_b.expanduser().resolve()
    pil_a, size_a = load_grayscale(path_a)
    pil_b, size_b_original = load_grayscale(path_b)

    resized = False
    if pil_a.size != pil_b.size:
        print(f"Resizing image-b from {pil_b.size[0]}x{pil_b.size[1]} to {pil_a.size[0]}x{pil_a.size[1]}", file=sys.stderr)
        resampling = getattr(Image, "Resampling", Image)
        pil_b = pil_b.resize(pil_a.size, resampling.LANCZOS)
        resized = True

    arr_a = np.asarray(pil_a, dtype=np.uint8)
    arr_b = np.asarray(pil_b, dtype=np.uint8)
    kwargs: dict[str, Any] = {"data_range": 255}
    min_dim = min(arr_a.shape)
    if min_dim < 7:
        kwargs["win_size"] = max(3, min_dim if min_dim % 2 == 1 else min_dim - 1)

    if structural_similarity is not None:
        score = float(structural_similarity(arr_a, arr_b, **kwargs))
    else:
        score = fallback_ssim(arr_a, arr_b)
    return {
        "image_a": str(path_a),
        "image_b": str(path_b),
        "ssim": score,
        "resized": resized,
        "shape_a": [size_a[0], size_a[1]],
        "shape_b_original": [size_b_original[0], size_b_original[1]],
    }


def fallback_ssim(arr_a: Any, arr_b: Any, data_range: float = 255.0) -> float:
    """Compute a global SSIM score when scikit-image is unavailable."""
    import numpy as np

    x = np.asarray(arr_a, dtype=np.float64)
    y = np.asarray(arr_b, dtype=np.float64)
    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2
    mean_x = float(x.mean())
    mean_y = float(y.mean())
    var_x = float(((x - mean_x) ** 2).mean())
    var_y = float(((y - mean_y) ** 2).mean())
    cov_xy = float(((x - mean_x) * (y - mean_y)).mean())
    numerator = (2 * mean_x * mean_y + c1) * (2 * cov_xy + c2)
    denominator = (mean_x**2 + mean_y**2 + c1) * (var_x + var_y + c2)
    return float(numerator / denominator) if denominator else 1.0


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    """Write JSON to stdout and, optionally, to a file."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-a", required=True, help="First PNG path.")
    parser.add_argument("--image-b", required=True, help="Second PNG path.")
    parser.add_argument("--json-out", help="Optional path to write the JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = compute_ssim(Path(args.image_a), Path(args.image_b))
    except DependencyError as exc:
        data = {"error": str(exc)}
        write_json(data, args.json_out)
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        data = {"error": str(exc)}
        write_json(data, args.json_out)
        return 1
    write_json(data, args.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

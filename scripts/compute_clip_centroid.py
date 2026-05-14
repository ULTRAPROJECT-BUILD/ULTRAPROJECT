#!/usr/bin/env python3
"""Compute a CLIP image-embedding centroid for visual aesthetic references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CENTROID_DIR = REPO_ROOT / "vault" / "archive" / "visual-aesthetics" / "centroids"


class DependencyError(RuntimeError):
    """Raised when CLIP runtime dependencies are unavailable."""


def load_clip_model(model_name: str) -> tuple[Any, Any, Any, Any]:
    """Load open_clip model, image preprocessor, torch, and device."""
    try:
        import open_clip
        import torch
    except ImportError as exc:
        raise DependencyError(
            "compute_clip_centroid.py requires open-clip-torch, torch, torchvision, and Pillow. "
            "Install with: python3 -m pip install open-clip-torch torch torchvision pillow"
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained="openai", device=device)
    model.eval()
    return model, preprocess, torch, device


def encode_image(path: Path, model: Any, preprocess: Any, torch: Any, device: Any) -> Any:
    """Encode one image path to a normalized numpy float32 embedding."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise DependencyError(
            "compute_clip_centroid.py requires numpy and Pillow. "
            "Install with: python3 -m pip install numpy pillow"
        ) from exc

    image_path = path.expanduser().resolve()
    with Image.open(image_path) as image:
        tensor = preprocess(image.convert("RGB")).unsqueeze(0).to(device)
    with torch.no_grad():
        embedding = model.encode_image(tensor)
        embedding = embedding / embedding.norm(dim=-1, keepdim=True)
    return embedding.squeeze(0).detach().cpu().numpy().astype(np.float32)


def normalize_vector(vector: Any) -> Any:
    """Return an L2-normalized numpy float32 vector."""
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("compute_clip_centroid.py requires numpy. Install with: python3 -m pip install numpy") from exc

    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    if norm == 0:
        raise ValueError("Cannot normalize a zero vector.")
    return (array / norm).astype(np.float32)


def safe_preset_filename(preset_name: str) -> str:
    """Return a conservative filename stem for a preset name."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", preset_name.strip())
    return cleaned.strip("._-") or "preset"


def compute_centroid(
    preset_name: str,
    references: list[Path],
    *,
    out_path: Path | None = None,
    model_name: str = "ViT-B-32",
) -> dict[str, Any]:
    """Compute and save a normalized CLIP centroid for reference images."""
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("compute_clip_centroid.py requires numpy. Install with: python3 -m pip install numpy") from exc

    if not references:
        raise ValueError("At least one reference image is required.")

    model, preprocess, torch, device = load_clip_model(model_name)
    embeddings = [encode_image(path, model, preprocess, torch, device) for path in references]
    centroid = normalize_vector(np.mean(np.stack(embeddings), axis=0))

    destination = out_path.expanduser().resolve() if out_path else CENTROID_DIR / f"{safe_preset_filename(preset_name)}.npy"
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.save(destination, centroid.astype(np.float32))

    return {
        "preset_name": preset_name,
        "model": model_name,
        "n_references": len(references),
        "centroid_path": str(destination),
        "centroid_shape": list(centroid.shape),
    }


def compute_clip_distance(embedding_or_image_path: Any, centroid_path: str | Path) -> float:
    """Return cosine distance between an embedding or image path and a centroid .npy."""
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("compute_clip_centroid.py requires numpy. Install with: python3 -m pip install numpy") from exc

    centroid = normalize_vector(np.load(Path(centroid_path).expanduser().resolve()))
    if isinstance(embedding_or_image_path, (str, Path)):
        source = Path(embedding_or_image_path).expanduser().resolve()
        if source.suffix.lower() == ".npy":
            embedding = np.load(source)
        else:
            model, preprocess, torch, device = load_clip_model("ViT-B-32")
            embedding = encode_image(source, model, preprocess, torch, device)
    else:
        embedding = np.asarray(embedding_or_image_path, dtype=np.float32)

    embedding = normalize_vector(embedding)
    return float(1 - np.dot(embedding, centroid))


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
    parser.add_argument("--preset-name", required=True, help="Preset name for the centroid.")
    parser.add_argument("--references", nargs="+", required=True, help="Reference PNG paths.")
    parser.add_argument("--out", help="Optional output .npy path.")
    parser.add_argument("--model", default="ViT-B-32", help="open_clip model name. Default: ViT-B-32.")
    parser.add_argument("--json-out", help="Optional path to write the JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = compute_centroid(
            args.preset_name,
            [Path(path) for path in args.references],
            out_path=Path(args.out) if args.out else None,
            model_name=args.model,
        )
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

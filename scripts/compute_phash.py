#!/usr/bin/env python3
"""Compute a perceptual hash for a PNG image."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PHASH_CACHE_DIR = REPO_ROOT / "vault" / "cache" / "visual-spec" / "phash"


class DependencyError(RuntimeError):
    """Raised when a required runtime dependency is missing."""


def sha256_file(path: Path) -> str:
    """Return the content SHA-256 for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_phash_distance(hash_a_hex: str, hash_b_hex: str) -> int:
    """Return the Hamming distance between two hexadecimal pHash strings."""
    a = int(hash_a_hex.strip().lower().removeprefix("0x"), 16)
    b = int(hash_b_hex.strip().lower().removeprefix("0x"), 16)
    return bin(a ^ b).count("1")


def fallback_phash_hex(path: Path, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    """Compute a DCT perceptual hash when imagehash is unavailable."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise DependencyError(
            "compute_phash.py requires imagehash and Pillow, or Pillow plus numpy for fallback pHash. "
            "Install with: python3 -m pip install imagehash Pillow numpy"
        ) from exc

    img_size = hash_size * highfreq_factor
    resampling = getattr(Image, "Resampling", Image)
    with Image.open(path) as image:
        pixels = np.asarray(
            image.convert("L").resize((img_size, img_size), resampling.LANCZOS),
            dtype=np.float64,
        )

    coords = np.arange(img_size)
    freqs = np.arange(img_size).reshape(-1, 1)
    dct_matrix = np.cos((np.pi / img_size) * (coords + 0.5) * freqs)
    dct_matrix[0, :] *= np.sqrt(1 / img_size)
    dct_matrix[1:, :] *= np.sqrt(2 / img_size)
    with np.errstate(all="ignore"):
        dct = dct_matrix @ pixels @ dct_matrix.T
    low_freq = dct[:hash_size, :hash_size]
    tolerance = max(float(np.nanmax(np.abs(low_freq))) * 1e-12, 1e-12)
    low_freq = np.where(np.abs(low_freq) < tolerance, 0, low_freq)
    diff = low_freq > np.median(low_freq)
    bit_string = "".join("1" if bit else "0" for bit in diff.flatten())
    return f"{int(bit_string, 2):0{hash_size * hash_size // 4}x}"


def compute_phash(path: Path, *, use_cache: bool = False) -> dict[str, Any]:
    """Compute imagehash.phash metadata for a PNG path."""
    input_path = path.expanduser().resolve()
    content_hash = sha256_file(input_path)
    cache_path = PHASH_CACHE_DIR / f"{content_hash}.json"

    if use_cache and cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        data["path"] = str(input_path)
        return data

    try:
        from PIL import Image
    except ImportError as exc:
        raise DependencyError(
            "compute_phash.py requires Pillow. Install with: python3 -m pip install Pillow"
        ) from exc

    with Image.open(input_path) as image:
        width, height = image.size

    try:
        import imagehash
    except ImportError:
        phash_hex = fallback_phash_hex(input_path)
    else:
        with Image.open(input_path) as image:
            phash_hex = str(imagehash.phash(image)).lower()

    data = {
        "path": str(input_path),
        "phash": phash_hex,
        "phash_int": int(phash_hex, 16),
        "size_bytes": input_path.stat().st_size,
        "width": width,
        "height": height,
    }

    if use_cache:
        PHASH_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return data


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
    parser.add_argument("--input", required=True, help="PNG path to hash.")
    parser.add_argument("--cache", action="store_true", help="Read/write the visual-spec pHash cache.")
    parser.add_argument("--json-out", help="Optional path to write the JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = compute_phash(Path(args.input), use_cache=args.cache)
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

#!/usr/bin/env python3
"""Check whether a produced artifact fits a medium-owned slot contract."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import numpy as np
    from PIL import Image, ImageFilter
except ImportError as exc:  # pragma: no cover - dependency gate
    raise SystemExit(
        "check_slot_integration.py requires Pillow and numpy. "
        "Install with: python3 -m pip install Pillow numpy"
    ) from exc

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import compute_phash

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
GEN_IMAGE_TYPES = {
    "photograph",
    "illustration",
    "icon_set",
    "pattern_texture",
    "product_3d",
    "scene_3d",
    "motion_graphics_loop",
    "cinematic_video",
}


def now_iso() -> str:
    """Return a machine-local timestamp."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    """Read JSON from a path."""
    return json.loads(path.expanduser().read_text(encoding="utf-8"))


def write_json(payload: dict[str, Any], json_out: str | None) -> None:
    """Write report JSON to stdout and optionally to a file."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def extract_slot_contract(payload: Any) -> dict[str, Any]:
    """Accept a raw slot contract, manifest item, or artifact_manifest wrapper."""
    if not isinstance(payload, dict):
        raise ValueError("slot contract JSON must be an object")
    if "slot_contract" in payload and isinstance(payload["slot_contract"], dict):
        return dict(payload["slot_contract"])
    manifest = payload.get("artifact_manifest")
    if isinstance(manifest, list) and manifest:
        first = manifest[0]
        if isinstance(first, dict) and isinstance(first.get("slot_contract"), dict):
            return dict(first["slot_contract"])
    return dict(payload)


def parse_dimensions(value: Any) -> tuple[int, int] | None:
    """Parse a WxH dimensions string or mapping."""
    if isinstance(value, str) and "x" in value:
        left, right = value.lower().split("x", 1)
        if left.isdigit() and right.isdigit():
            return int(left), int(right)
    if isinstance(value, dict):
        width = value.get("width") or value.get("w")
        height = value.get("height") or value.get("h")
        if isinstance(width, int) and isinstance(height, int):
            return width, height
    return None


def parse_aspect_ratio(value: Any) -> float | None:
    """Parse a W:H aspect-ratio string."""
    if not isinstance(value, str) or ":" not in value:
        return None
    left, right = value.split(":", 1)
    if not left.isdigit() or not right.isdigit() or int(right) == 0:
        return None
    return int(left) / int(right)


def image_like(path: Path, artifact_type: str) -> bool:
    """Return whether this artifact can be inspected as an image."""
    return path.suffix.lower() in IMAGE_EXTENSIONS or artifact_type in GEN_IMAGE_TYPES


def sidecar_metadata_paths(path: Path) -> list[Path]:
    """Return metadata sidecar candidates for an artifact."""
    return [
        path.with_suffix(path.suffix + ".metadata.json"),
        path.with_suffix(path.suffix + ".meta.json"),
        path.with_suffix(".metadata.json"),
        path.with_suffix(".json"),
    ]


def read_artifact_metadata(path: Path) -> dict[str, Any]:
    """Read sidecar or embedded image metadata."""
    metadata: dict[str, Any] = {}
    for candidate in sidecar_metadata_paths(path):
        if candidate.exists():
            try:
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(loaded, dict):
                metadata.update(loaded)
                break
    if path.suffix.lower() in IMAGE_EXTENSIONS and path.exists():
        try:
            with Image.open(path) as image:
                for key in ("alt_text", "description", "title", "dimensions"):
                    if key in image.info and key not in metadata:
                        metadata[key] = image.info[key]
        except Exception:
            pass
    return metadata


def inspect_dimensions(path: Path, artifact_type: str, metadata: dict[str, Any]) -> tuple[int, int] | None:
    """Inspect artifact dimensions from image bytes or metadata."""
    if image_like(path, artifact_type):
        try:
            phash_data = compute_phash.compute_phash(path, use_cache=False)
            return int(phash_data["width"]), int(phash_data["height"])
        except Exception:
            pass
        try:
            with Image.open(path) as image:
                return image.size
        except Exception:
            pass
    for key in ("dimensions", "size", "pixel_size"):
        parsed = parse_dimensions(metadata.get(key))
        if parsed:
            return parsed
    width = metadata.get("width")
    height = metadata.get("height")
    if isinstance(width, int) and isinstance(height, int):
        return width, height
    return None


def check_result(verdict: str, details: str = "", **extra: Any) -> dict[str, Any]:
    """Build a single check result object."""
    payload = {"verdict": verdict}
    if details:
        payload["details"] = details
    payload.update(extra)
    return payload


def dimensions_match(
    actual: tuple[int, int] | None,
    target: tuple[int, int] | None,
    artifact_type: str,
) -> dict[str, Any]:
    """Check target dimensions with generative tolerance."""
    if target is None:
        return check_result("pass", "no target_dimensions declared")
    if actual is None:
        return check_result("fail", "artifact dimensions could not be inspected")
    actual_w, actual_h = actual
    target_w, target_h = target
    tolerance = 0.05 if artifact_type in GEN_IMAGE_TYPES else 0.0
    width_delta = abs(actual_w - target_w) / target_w
    height_delta = abs(actual_h - target_h) / target_h
    if width_delta <= tolerance and height_delta <= tolerance:
        detail = f"actual={actual_w}x{actual_h}; target={target_w}x{target_h}; tolerance={tolerance:.0%}"
        return check_result("pass", detail, actual_dimensions=f"{actual_w}x{actual_h}")
    detail = (
        f"actual={actual_w}x{actual_h}; target={target_w}x{target_h}; "
        f"delta_width={width_delta:.1%}; delta_height={height_delta:.1%}; tolerance={tolerance:.0%}"
    )
    return check_result("fail", detail, actual_dimensions=f"{actual_w}x{actual_h}")


def aspect_ratio_match(actual: tuple[int, int] | None, target_ratio: float | None) -> dict[str, Any]:
    """Check the artifact aspect ratio."""
    if target_ratio is None:
        return check_result("pass", "no target_aspect_ratio declared")
    if actual is None:
        return check_result("fail", "artifact dimensions could not be inspected")
    width, height = actual
    actual_ratio = width / height
    delta = abs(actual_ratio - target_ratio) / target_ratio
    if delta <= 0.02:
        return check_result("pass", f"actual_ratio={actual_ratio:.4f}; target_ratio={target_ratio:.4f}")
    return check_result("fail", f"actual_ratio={actual_ratio:.4f}; target_ratio={target_ratio:.4f}; delta={delta:.1%}")


def load_rgb(path: Path) -> Image.Image:
    """Load an image as RGB."""
    with Image.open(path) as image:
        return image.convert("RGB")


def saliency_map(image: Image.Image, max_side: int = 256) -> tuple[np.ndarray, float, float]:
    """Build a simple saliency map and return centroid coordinates in original pixels."""
    width, height = image.size
    scale = min(1.0, max_side / max(width, height))
    small_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    resampling = getattr(Image, "Resampling", Image)
    small = image.resize(small_size, resampling.LANCZOS)
    gray_img = small.convert("L")
    gray = np.asarray(gray_img, dtype=np.float32) / 255.0
    blurred = np.asarray(gray_img.filter(ImageFilter.GaussianBlur(radius=7)), dtype=np.float32) / 255.0
    rgb = np.asarray(small, dtype=np.float32) / 255.0
    saturation = rgb.max(axis=2) - rgb.min(axis=2)
    local_delta = np.abs(gray - blurred)
    global_delta = np.abs(gray - float(gray.mean()))
    saliency = local_delta * 0.55 + global_delta * 0.35 + saturation * 0.10
    saliency = np.maximum(saliency - np.percentile(saliency, 20), 0)
    total = float(saliency.sum())
    if total <= 1e-9:
        return saliency, width / 2, height / 2
    yy, xx = np.indices(saliency.shape)
    cx = float((xx * saliency).sum() / total) / scale
    cy = float((yy * saliency).sum() / total) / scale
    return saliency, cx, cy


def apply_zone_token(token: str, width: int, height: int) -> tuple[float, float, float, float]:
    """Translate a safe-zone token to a bounding box."""
    token = token.lower().strip()
    x0, y0, x1, y1 = 0.0, 0.0, float(width), float(height)
    if not token or token in {"none", "full", "full_bleed", "any"}:
        return x0, y0, x1, y1
    if "center_60pct" in token or "center_60" in token:
        x0, x1 = width * 0.20, width * 0.80
        y0, y1 = height * 0.20, height * 0.80
    if "center_80pct" in token or "center_80" in token:
        x0, x1 = width * 0.10, width * 0.90
        y0, y1 = height * 0.10, height * 0.90
    if "left_third" in token:
        x0, x1 = 0.0, width / 3
    if "right_third" in token:
        x0, x1 = width * 2 / 3, float(width)
    if "middle_third" in token or "center_third" in token:
        x0, x1 = width / 3, width * 2 / 3
    if "upper_third" in token or "top_third" in token:
        y0, y1 = 0.0, height / 3
    if "lower_third" in token or "bottom_third" in token:
        y0, y1 = height * 2 / 3, float(height)
    if "upper_two_thirds" in token or "top_two_thirds" in token:
        y0, y1 = 0.0, height * 2 / 3
    if "lower_two_thirds" in token or "bottom_two_thirds" in token:
        y0, y1 = height / 3, float(height)
    return x0, y0, x1, y1


def crop_safe_zone_respected(path: Path, artifact_type: str, contract: dict[str, Any]) -> dict[str, Any]:
    """Check whether the dominant subject centroid falls inside the crop safe zone."""
    token = str(contract.get("crop_safe_zone") or "").strip()
    if not token:
        return check_result("pass", "no crop_safe_zone declared")
    if not image_like(path, artifact_type):
        return check_result("pass", "crop safe-zone check not applicable to non-image artifact")
    try:
        image = load_rgb(path)
    except Exception as exc:
        return check_result("fail", f"image could not be loaded: {exc}")
    _, cx, cy = saliency_map(image)
    width, height = image.size
    x0, y0, x1, y1 = apply_zone_token(token, width, height)
    inside = x0 <= cx <= x1 and y0 <= cy <= y1
    detail = (
        f"subject_centroid_at_({int(round(cx))}, {int(round(cy))}); "
        f"safe_zone={token} expects centroid in [({int(round(x0))}, {int(round(y0))}), "
        f"({int(round(x1))}, {int(round(y1))})]"
    )
    return check_result("pass" if inside else "fail", detail, subject_centroid=[round(cx, 2), round(cy, 2)])


def overlay_bounds(token: str, width: int, height: int) -> tuple[int, int, int, int]:
    """Translate an overlay-clear token to a region."""
    token = token.lower().strip()
    region_w = int(width * 0.35)
    region_h = int(height * 0.35)
    if "top_left" in token:
        return 0, 0, region_w, region_h
    if "top_right" in token:
        return width - region_w, 0, width, region_h
    if "bottom_left" in token:
        return 0, height - region_h, region_w, height
    if "bottom_right" in token:
        return width - region_w, height - region_h, width, height
    if "top" in token:
        return 0, 0, width, region_h
    if "bottom" in token:
        return 0, height - region_h, width, height
    if "left" in token:
        return 0, 0, region_w, height
    if "right" in token:
        return width - region_w, 0, width, height
    return 0, 0, region_w, region_h


def focal_point_safe_zone_respected(path: Path, artifact_type: str, contract: dict[str, Any]) -> dict[str, Any]:
    """Check whether overlay-clear zones are visually quiet."""
    token = str(contract.get("focal_point_safe_zone") or "").strip()
    if not token:
        return check_result("pass", "no focal_point_safe_zone declared")
    if not image_like(path, artifact_type):
        return check_result("pass", "focal safe-zone check not applicable to non-image artifact")
    try:
        image = load_rgb(path)
    except Exception as exc:
        return check_result("fail", f"image could not be loaded: {exc}")
    saliency, _, _ = saliency_map(image)
    small_h, small_w = saliency.shape
    width, height = image.size
    x0, y0, x1, y1 = overlay_bounds(token, width, height)
    sx0 = max(0, min(small_w - 1, int(x0 * small_w / width)))
    sx1 = max(sx0 + 1, min(small_w, int(math.ceil(x1 * small_w / width))))
    sy0 = max(0, min(small_h - 1, int(y0 * small_h / height)))
    sy1 = max(sy0 + 1, min(small_h, int(math.ceil(y1 * small_h / height))))
    region = saliency[sy0:sy1, sx0:sx1]
    region_busy = float(region.mean() + region.std())
    global_busy = float(saliency.mean() + saliency.std())
    threshold = max(global_busy * 0.70, 0.020)
    passes = region_busy <= threshold
    detail = (
        f"overlay_zone={token}; region_busy={region_busy:.4f}; "
        f"global_busy={global_busy:.4f}; threshold={threshold:.4f}"
    )
    return check_result("pass" if passes else "fail", detail, overlay_bounds=[x0, y0, x1, y1])


def file_size_within_limit(path: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Check file size against the contract maximum."""
    max_kb = contract.get("file_size_max_kb")
    if not isinstance(max_kb, int):
        return check_result("pass", "no file_size_max_kb declared")
    size_kb = math.ceil(path.stat().st_size / 1024)
    if size_kb <= max_kb:
        return check_result("pass", f"size_kb={size_kb}; max_kb={max_kb}", size_kb=size_kb)
    return check_result("fail", f"size_kb={size_kb}; max_kb={max_kb}", size_kb=size_kb)


def visual_hierarchy_role_match(path: Path, artifact_type: str, contract: dict[str, Any]) -> dict[str, Any]:
    """Check whether image prominence matches the slot role."""
    slot_role = str(contract.get("slot_role") or "").lower()
    if not image_like(path, artifact_type):
        return check_result("pass", "visual hierarchy check not applicable to non-image artifact")
    try:
        image = load_rgb(path)
    except Exception as exc:
        return check_result("fail", f"image could not be loaded: {exc}")
    gray = np.asarray(image.convert("L").resize((160, 96)), dtype=np.float32) / 255.0
    saliency, _, _ = saliency_map(image, max_side=192)
    contrast = float(gray.std())
    mean_saliency = float(saliency.mean())
    if mean_saliency <= 1e-9:
        focal_strength = 1.0
    else:
        focal_strength = float(np.percentile(saliency, 95) / mean_saliency)
    if "hero" in slot_role or "foreground" in slot_role:
        passes = contrast >= 0.08 and focal_strength >= 1.35
        detail = f"hero prominence contrast={contrast:.3f}; focal_strength={focal_strength:.2f}"
        return check_result("pass" if passes else "fail", detail, contrast=round(contrast, 4))
    if "background" in slot_role:
        passes = contrast <= 0.24 and focal_strength <= 4.25
        detail = f"background support contrast={contrast:.3f}; focal_strength={focal_strength:.2f}"
        return check_result("pass" if passes else "fail", detail, contrast=round(contrast, 4))
    return check_result("pass", f"slot_role={slot_role or 'unspecified'} has no dominance policy")


def alt_text_present(metadata: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Check required alt text."""
    if contract.get("accessibility_alt_text_required") is not True:
        return check_result("pass", "alt text not required by slot contract")
    value = metadata.get("alt_text") or metadata.get("alt") or metadata.get("description")
    if isinstance(value, str) and value.strip():
        return check_result("pass", "artifact metadata includes alt_text")
    return check_result("fail", "accessibility_alt_text_required=true but artifact metadata has no alt_text")


def remediation_hint(checks: dict[str, dict[str, Any]]) -> str | None:
    """Return a concise remediation hint from the first failed check."""
    order = [
        "dimensions_match",
        "aspect_ratio_match",
        "crop_safe_zone_respected",
        "focal_point_safe_zone_respected",
        "file_size_within_limit",
        "visual_hierarchy_role_match",
        "alt_text_present",
    ]
    for name in order:
        result = checks.get(name, {})
        if result.get("verdict") != "fail":
            continue
        details = str(result.get("details") or "")
        if name == "crop_safe_zone_respected":
            return f"subject placement off - re-prompt with declared crop_safe_zone constraint; {details}"
        if name == "focal_point_safe_zone_respected":
            return f"overlay safe zone is too busy - re-prompt for clear negative space; {details}"
        if name == "dimensions_match":
            return f"dimensions do not fit slot - re-prompt with exact target_dimensions; {details}"
        if name == "visual_hierarchy_role_match":
            return f"visual hierarchy does not match slot role - adjust dominance and focal strength; {details}"
        return f"{name} failed; {details}"
    return None


def build_report(
    artifact_path: Path,
    artifact_type: str,
    slot_contract: dict[str, Any],
    medium: str,
    medium_plugin_path: str | None = None,
) -> dict[str, Any]:
    """Build a complete slot integration report."""
    path = artifact_path.expanduser()
    if not path.exists():
        raise FileNotFoundError(f"artifact path does not exist: {path}")
    metadata = read_artifact_metadata(path)
    actual_dimensions = inspect_dimensions(path, artifact_type, metadata)
    target_dimensions = parse_dimensions(slot_contract.get("target_dimensions"))
    target_ratio = parse_aspect_ratio(slot_contract.get("target_aspect_ratio"))

    checks = {
        "dimensions_match": dimensions_match(actual_dimensions, target_dimensions, artifact_type),
        "aspect_ratio_match": aspect_ratio_match(actual_dimensions, target_ratio),
        "crop_safe_zone_respected": crop_safe_zone_respected(path, artifact_type, slot_contract),
        "focal_point_safe_zone_respected": focal_point_safe_zone_respected(path, artifact_type, slot_contract),
        "file_size_within_limit": file_size_within_limit(path, slot_contract),
        "visual_hierarchy_role_match": visual_hierarchy_role_match(path, artifact_type, slot_contract),
        "alt_text_present": alt_text_present(metadata, slot_contract),
    }
    verdict = "pass" if all(item.get("verdict") == "pass" for item in checks.values()) else "fail"
    report = {
        "artifact_path": str(path),
        "artifact_type": artifact_type,
        "slot_role": slot_contract.get("slot_role"),
        "medium": medium,
        "checked_at": now_iso(),
        "checks": checks,
        "verdict": verdict,
        "remediation_hint": remediation_hint(checks) if verdict == "fail" else None,
    }
    if medium_plugin_path:
        report["medium_plugin_path"] = medium_plugin_path
    return report


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-path", required=True)
    parser.add_argument("--artifact-type", required=True)
    parser.add_argument("--slot-contract-json", required=True)
    parser.add_argument("--medium", required=True)
    parser.add_argument("--medium-plugin-path")
    parser.add_argument("--json-out")
    return parser.parse_args()


def main() -> int:
    """Run the slot integration checker."""
    args = parse_args()
    try:
        slot_contract = extract_slot_contract(read_json(Path(args.slot_contract_json)))
        report = build_report(
            Path(args.artifact_path),
            args.artifact_type,
            slot_contract,
            args.medium,
            args.medium_plugin_path,
        )
    except Exception as exc:
        report = {
            "artifact_path": args.artifact_path,
            "artifact_type": args.artifact_type,
            "slot_role": None,
            "medium": args.medium,
            "checked_at": now_iso(),
            "checks": {},
            "verdict": "fail",
            "remediation_hint": str(exc),
            "error": str(exc),
        }
        write_json(report, args.json_out)
        return 2
    write_json(report, args.json_out)
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

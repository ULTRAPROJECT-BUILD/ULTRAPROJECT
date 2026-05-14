#!/usr/bin/env python3
"""Run quantitative coherence checks for a produced artifact set."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency gate
    raise SystemExit("check_artifact_coherence.py requires PyYAML. Install with: python3 -m pip install PyYAML") from exc

try:
    import numpy as np
    from PIL import Image, ImageFilter
except ImportError as exc:  # pragma: no cover - dependency gate
    raise SystemExit(
        "check_artifact_coherence.py requires Pillow and numpy. "
        "Install with: python3 -m pip install Pillow numpy"
    ) from exc


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
AUDIO_EXTENSIONS = {".wav", ".aiff", ".aif", ".flac", ".mp3", ".m4a", ".ogg"}
MOTION_EXTENSIONS = {".gif", ".mp4", ".mov", ".webm", ".mkv"}
LIGHTING_TYPES = {"photograph", "photo", "product_3d", "scene_3d", "3d_render", "cinematic_video"}
MOTION_TYPES = {"motion_graphics", "motion_graphics_loop", "video", "video_animation", "cinematic_video", "animation"}
AUDIO_TYPES = {"audio", "music", "soundtrack", "voiceover", "sound_design"}
THRESHOLD_KEYS = (
    "palette_delta_e76_max",
    "color_temperature_variance_k_max",
    "type_scale_ratio_variance_max",
    "type_family_consistency_required",
    "lighting_primary_direction_variance_deg_max",
    "lighting_fill_ratio_variance_max",
    "motion_pacing_register_consistency_required",
    "audio_mood_centroid_distance_max",
    "spatial_scale_subject_variance_max",
    "slot_fit_must_be_unanimous",
)
REPORT_HASH_OMIT_KEYS = {"coherence_report_sha256"}


class CoherenceError(RuntimeError):
    """Raised when a coherence input cannot be processed."""


def now_iso() -> str:
    """Return a machine-local timestamp with timezone offset."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    """Read JSON from a path."""
    return json.loads(path.expanduser().read_text(encoding="utf-8"))


def read_yaml(path: Path) -> Any:
    """Read YAML from a path."""
    loaded = yaml.safe_load(path.expanduser().read_text(encoding="utf-8"))
    return loaded if loaded is not None else {}


def write_json(payload: dict[str, Any], json_out: str | None = None) -> None:
    """Write report JSON to stdout and optionally to a file."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def default_report_path(artifact_set_json: Path) -> Path:
    """Return the deterministic report path for an artifact set."""
    resolved = artifact_set_json.expanduser().resolve()
    return resolved.with_name(f"{resolved.stem}-coherence-report.json")


def canonical_report_payload(value: Any) -> Any:
    """Return the payload shape used for coherence report hash pinning."""
    if isinstance(value, dict):
        return {
            key: canonical_report_payload(item)
            for key, item in value.items()
            if key not in REPORT_HASH_OMIT_KEYS
        }
    if isinstance(value, list):
        return [canonical_report_payload(item) for item in value]
    return value


def coherence_report_sha256(payload: dict[str, Any]) -> str:
    """Hash canonical coherence-report JSON, excluding the hash field itself."""
    canonical = json.dumps(
        canonical_report_payload(payload),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def attach_report_binding(report: dict[str, Any], report_path: Path) -> dict[str, Any]:
    """Add report path and canonical hash fields to a report."""
    report["coherence_report_path"] = str(report_path.expanduser().resolve())
    report["coherence_report_sha256"] = coherence_report_sha256(report)
    return report


def comparison_details(check_name: str, value: float, threshold: float, verdict: str, extra: str = "") -> str:
    """Return substantive details for a threshold comparison."""
    rounded_value = round(float(value), 4)
    rounded_threshold = round(float(threshold), 4)
    if float(value) <= float(threshold):
        comparison = f"value {rounded_value} <= max_threshold {rounded_threshold}"
    else:
        delta = rounded_value - rounded_threshold
        if abs(rounded_threshold) > 1e-12:
            pct = (delta / rounded_threshold) * 100.0
            comparison = (
                f"value {rounded_value} exceeds max_threshold {rounded_threshold} "
                f"by {round(delta, 4)} ({pct:.1f}%)"
            )
        else:
            comparison = f"value {rounded_value} exceeds max_threshold {rounded_threshold} by {round(delta, 4)}"
    suffix = f"; {extra}" if extra else ""
    return f"Computed {check_name}: {comparison}{suffix}."


def load_frontmatter_or_mapping(path: Path) -> dict[str, Any]:
    """Load a markdown frontmatter, JSON object, or YAML mapping."""
    resolved = path.expanduser().resolve()
    text = resolved.read_text(encoding="utf-8")
    if resolved.suffix.lower() == ".json":
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else {}
    if text.startswith("---\n") or text.startswith("---\r\n"):
        lines = text.splitlines()
        end_index = None
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_index = index
                break
        if end_index is None:
            raise CoherenceError(f"{resolved} starts with frontmatter but has no closing delimiter")
        loaded = yaml.safe_load("\n".join(lines[1:end_index])) or {}
        return loaded if isinstance(loaded, dict) else {}
    loaded = yaml.safe_load(text) or {}
    return loaded if isinstance(loaded, dict) else {}


def first_text(mapping: dict[str, Any], keys: Iterable[str]) -> str:
    """Return the first non-empty string value from a mapping."""
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def visual_spec_context(vs_path: Path) -> dict[str, Any]:
    """Read medium and preset from Visual Specification frontmatter."""
    frontmatter = load_frontmatter_or_mapping(vs_path)
    medium = first_text(
        frontmatter,
        ("medium", "visual_quality_target_medium", "target_medium", "visual_medium"),
    )
    preset = first_text(
        frontmatter,
        ("preset", "visual_quality_target_preset", "target_preset", "visual_preset"),
    )
    return {"frontmatter": frontmatter, "medium": medium, "preset": preset}


def checked_thresholds(raw: Any, source: str) -> dict[str, Any]:
    """Return a sanitized thresholds object."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CoherenceError(f"{source} threshold override must be an object")
    unknown = sorted(set(raw) - set(THRESHOLD_KEYS))
    if unknown:
        raise CoherenceError(f"{source} contains unknown threshold keys: {', '.join(unknown)}")
    return dict(raw)


def resolve_effective_thresholds(registry: dict[str, Any], medium: str, preset: str) -> dict[str, Any]:
    """Resolve thresholds with deterministic defaults -> medium -> preset precedence."""
    defaults = checked_thresholds(registry.get("defaults"), "defaults")
    missing = [key for key in THRESHOLD_KEYS if key not in defaults]
    if missing:
        raise CoherenceError(f"threshold defaults missing keys: {', '.join(missing)}")
    medium_map = registry.get("per_medium_overrides") or {}
    preset_map = registry.get("per_preset_overrides") or {}
    if not isinstance(medium_map, dict):
        raise CoherenceError("per_medium_overrides must be an object")
    if not isinstance(preset_map, dict):
        raise CoherenceError("per_preset_overrides must be an object")
    medium_override = checked_thresholds(medium_map.get(medium, {}), f"per_medium_overrides[{medium}]") if medium else {}
    preset_override = checked_thresholds(preset_map.get(preset, {}), f"per_preset_overrides[{preset}]") if preset else {}
    effective = copy.deepcopy(defaults)
    effective.update(medium_override)
    effective.update(preset_override)
    return {
        "from_defaults": defaults,
        "from_medium_override": medium_override,
        "from_preset_override": preset_override,
        "effective": effective,
    }


def infer_artifact_type(path: Path | None, metadata: dict[str, Any], item: dict[str, Any]) -> str:
    """Infer an artifact type from explicit fields or the path suffix."""
    for source in (item, metadata):
        for key in ("artifact_type", "type", "kind", "media_type"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    suffix = path.suffix.lower() if path else ""
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in MOTION_EXTENSIONS:
        return "video_animation"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    return "unknown"


def candidate_metadata_paths(path: Path) -> list[Path]:
    """Return sidecar metadata paths for an artifact."""
    return [
        path.with_suffix(path.suffix + ".metadata.json"),
        path.with_suffix(path.suffix + ".meta.json"),
        path.with_suffix(".metadata.json"),
        path.with_suffix(".meta.json"),
        path.with_suffix(".json"),
    ]


def read_sidecar_metadata(path: Path | None) -> dict[str, Any]:
    """Read sidecar and embedded image metadata."""
    if path is None:
        return {}
    metadata: dict[str, Any] = {}
    for candidate in candidate_metadata_paths(path):
        if not candidate.exists() or candidate == path:
            continue
        try:
            loaded = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(loaded, dict):
            metadata.update(loaded)
            break
    if path.suffix.lower() in IMAGE_EXTENSIONS and path.exists():
        try:
            with Image.open(path) as image:
                for key, value in image.info.items():
                    if isinstance(value, (str, int, float, bool)):
                        metadata.setdefault(key, value)
        except Exception:
            pass
    return metadata


def path_from_item(item: dict[str, Any]) -> str:
    """Return the first artifact path-like field."""
    for key in ("path", "file", "artifact_path", "output_path", "uri", "url"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def resolve_artifact_path(raw_path: str, base_dir: Path) -> Path | None:
    """Resolve an artifact path relative to the artifact-set file."""
    if not raw_path:
        return None
    if raw_path.startswith(("http://", "https://")):
        return None
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    first = (base_dir / candidate).resolve()
    if first.exists():
        return first
    return (REPO_ROOT / candidate).resolve()


def raw_artifact_items(payload: Any) -> list[Any]:
    """Extract artifact items from supported artifact-set shapes."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise CoherenceError("artifact-set JSON must be an object or array")
    for key in ("artifacts", "artifact_set", "items", "artifact_manifest", "produced_artifacts"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    raise CoherenceError("artifact-set JSON did not contain an artifacts list")


def normalize_artifacts(artifact_set_path: Path) -> list[dict[str, Any]]:
    """Normalize artifact records into the checker-internal shape."""
    payload = read_json(artifact_set_path)
    base_dir = artifact_set_path.expanduser().resolve().parent
    normalized: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_artifact_items(payload)):
        item = {"path": raw_item} if isinstance(raw_item, str) else dict(raw_item) if isinstance(raw_item, dict) else {}
        if not item:
            raise CoherenceError(f"artifact item {index} must be an object or path string")
        raw_path = path_from_item(item)
        path = resolve_artifact_path(raw_path, base_dir)
        metadata = read_sidecar_metadata(path)
        inline_metadata = item.get("metadata")
        if isinstance(inline_metadata, dict):
            metadata.update(inline_metadata)
        artifact_type = infer_artifact_type(path, metadata, item)
        normalized.append(
            {
                "index": index,
                "id": str(item.get("id") or item.get("artifact_id") or f"artifact-{index + 1}"),
                "path": path,
                "raw_path": raw_path,
                "artifact_type": artifact_type,
                "metadata": metadata,
                "item": item,
            }
        )
    return normalized


def is_image_artifact(artifact: dict[str, Any]) -> bool:
    """Return true when the artifact can be opened as an image."""
    path = artifact.get("path")
    return isinstance(path, Path) and path.suffix.lower() in IMAGE_EXTENSIONS and path.exists()


def load_rgb_image(path: Path) -> Image.Image:
    """Load an image as RGB, flattening transparency over white."""
    with Image.open(path) as image:
        if image.mode in {"RGBA", "LA"}:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            background.alpha_composite(rgba)
            return background.convert("RGB")
        return image.convert("RGB")


def srgb_to_linear(channel: float) -> float:
    """Convert an sRGB channel in 0..1 to linear light."""
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb: Iterable[float]) -> tuple[float, float, float]:
    """Convert sRGB 0..255 to CIELAB using D65 white."""
    r8, g8, b8 = rgb
    r = srgb_to_linear(float(r8) / 255.0)
    g = srgb_to_linear(float(g8) / 255.0)
    b = srgb_to_linear(float(b8) / 255.0)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    x /= 0.95047
    z /= 1.08883

    def pivot(value: float) -> float:
        if value > 0.008856:
            return value ** (1.0 / 3.0)
        return 7.787 * value + 16.0 / 116.0

    fx = pivot(x)
    fy = pivot(y)
    fz = pivot(z)
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


def delta_e76(left: Iterable[float], right: Iterable[float]) -> float:
    """Return CIELAB Delta E 1976 between two sRGB colors."""
    lab_left = rgb_to_lab(left)
    lab_right = rgb_to_lab(right)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab_left, lab_right)))


def dominant_colors(path: Path, *, k: int = 5, max_side: int = 96, max_samples: int = 12000) -> list[tuple[float, float, float]]:
    """Extract dominant colors with deterministic k-means."""
    image = load_rgb_image(path)
    width, height = image.size
    scale = min(1.0, max_side / max(width, height))
    if scale < 1.0:
        resampling = getattr(Image, "Resampling", Image)
        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), resampling.LANCZOS)
    pixels = np.asarray(image, dtype=np.float32).reshape(-1, 3)
    if len(pixels) > max_samples:
        step = max(1, int(math.ceil(len(pixels) / max_samples)))
        pixels = pixels[::step]
    if len(pixels) == 0:
        return []
    unique = np.unique(pixels.astype(np.uint8), axis=0).astype(np.float32)
    if len(unique) <= k:
        return [tuple(map(float, color)) for color in unique]
    luminance = unique @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    ordered = unique[np.argsort(luminance)]
    indexes = np.linspace(0, len(ordered) - 1, k).astype(int)
    centers = ordered[indexes].astype(np.float32)
    labels = np.zeros(len(pixels), dtype=np.int32)
    for _ in range(12):
        distances = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_labels = distances.argmin(axis=1)
        new_centers = centers.copy()
        for cluster in range(k):
            members = pixels[new_labels == cluster]
            if len(members):
                new_centers[cluster] = members.mean(axis=0)
        if np.array_equal(labels, new_labels) and np.allclose(centers, new_centers):
            break
        labels = new_labels
        centers = new_centers
    counts = np.bincount(labels, minlength=k)
    order = list(np.argsort(counts)[::-1])
    colors: list[tuple[float, float, float]] = []
    for cluster in order:
        if counts[cluster] == 0:
            continue
        color = tuple(map(float, centers[cluster]))
        if not any(delta_e76(color, existing) < 0.5 for existing in colors):
            colors.append(color)
    return colors[:k]


def verdict_from_max(value: float, threshold: float) -> str:
    """Return pass when value is at or below threshold."""
    return "pass" if value <= threshold else "fail"


def check_palette_delta(artifacts: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """Check maximum cross-artifact dominant palette distance."""
    images = [artifact for artifact in artifacts if is_image_artifact(artifact)]
    if len(images) < 2:
        return {
            "value": 0.0,
            "max_threshold": threshold,
            "verdict": "pass",
            "details": comparison_details(
                "set_palette_delta",
                0.0,
                threshold,
                "pass",
                "fewer than two visual artifacts were available for palette comparison",
            ),
        }
    palettes = [(artifact["id"], dominant_colors(artifact["path"])) for artifact in images]
    max_delta = 0.0
    max_pair: tuple[str, str] | None = None
    for left_index, (left_id, left_colors) in enumerate(palettes):
        for right_id, right_colors in palettes[left_index + 1 :]:
            for left_color in left_colors:
                for right_color in right_colors:
                    value = delta_e76(left_color, right_color)
                    if value > max_delta:
                        max_delta = value
                        max_pair = (left_id, right_id)
    rounded = round(max_delta, 4)
    verdict = verdict_from_max(max_delta, threshold)
    return {
        "value": rounded,
        "max_threshold": threshold,
        "verdict": verdict,
        "details": comparison_details(
            "set_palette_delta",
            rounded,
            threshold,
            verdict,
            f"max cross-artifact dominant color Delta E76 pair={max_pair or 'none'}",
        ),
    }


def estimate_color_temperature_k(rgb: Iterable[float]) -> float:
    """Estimate warm/cool color temperature from RGB ratios.

    This is a deterministic proxy rather than a color-science CCT solver. It is
    calibrated for set-level warm/cool variance, which is what this gate needs.
    """
    r, g, b = [float(value) for value in rgb]
    blue_red = (b - r) / 255.0
    green_bias = (g - ((r + b) / 2.0)) / 255.0
    kelvin = 6500.0 + blue_red * 4500.0 + green_bias * 1500.0
    return float(min(40000.0, max(1000.0, kelvin)))


def mean_rgb(path: Path) -> tuple[float, float, float]:
    """Return the mean RGB color for an image."""
    image = load_rgb_image(path)
    pixels = np.asarray(image, dtype=np.float32).reshape(-1, 3)
    mean = pixels.mean(axis=0)
    return float(mean[0]), float(mean[1]), float(mean[2])


def check_color_temperature(artifacts: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """Check visual set color temperature range in Kelvin."""
    images = [artifact for artifact in artifacts if is_image_artifact(artifact)]
    if len(images) < 2:
        return {
            "value": 0.0,
            "max_threshold": threshold,
            "verdict": "pass",
            "details": comparison_details(
                "set_color_temp_variance",
                0.0,
                threshold,
                "pass",
                "fewer than two visual artifacts were available for color-temperature comparison",
            ),
        }
    temperatures = {artifact["id"]: estimate_color_temperature_k(mean_rgb(artifact["path"])) for artifact in images}
    value = max(temperatures.values()) - min(temperatures.values())
    rounded = round(value, 4)
    verdict = verdict_from_max(value, threshold)
    return {
        "value": rounded,
        "max_threshold": threshold,
        "verdict": verdict,
        "details": comparison_details(
            "set_color_temp_variance",
            rounded,
            threshold,
            verdict,
            "max-min estimated mean image color temperature across visual artifacts",
        ),
        "temperatures_k": {key: round(val, 2) for key, val in temperatures.items()},
    }


def list_text_values(value: Any) -> list[str]:
    """Normalize a string/list value into strings."""
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def font_families(metadata: dict[str, Any]) -> list[str]:
    """Extract font-family declarations from metadata."""
    values: list[str] = []
    for key in ("font_family", "fontFamily", "font_families", "fontFamilies", "fonts"):
        values.extend(list_text_values(metadata.get(key)))
    families: list[str] = []
    for value in values:
        family = value.split(",")[0].strip().strip("'\"").lower()
        if family and family not in families:
            families.append(family)
    return families


def number_list(value: Any) -> list[float]:
    """Normalize scalar/list numeric metadata."""
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, list):
        numbers: list[float] = []
        for item in value:
            try:
                numbers.append(float(item))
            except (TypeError, ValueError):
                continue
        return numbers
    return []


def type_scale_ratios(metadata: dict[str, Any]) -> list[float]:
    """Extract or derive type-scale ratios from metadata."""
    ratios: list[float] = []
    for key in ("type_scale_ratio", "type_scale_ratios", "font_scale_ratio", "font_scale_ratios"):
        ratios.extend(number_list(metadata.get(key)))
    sizes: list[float] = []
    for key in ("type_sizes", "font_sizes", "text_sizes"):
        sizes.extend(number_list(metadata.get(key)))
    sizes = sorted({size for size in sizes if size > 0})
    for left, right in zip(sizes, sizes[1:]):
        if left > 0:
            ratios.append(right / left)
    return [ratio for ratio in ratios if ratio > 0]


def text_like_image(path: Path) -> bool:
    """Detect likely text glyphs from high-frequency monochrome edge density."""
    image = load_rgb_image(path)
    resampling = getattr(Image, "Resampling", Image)
    image.thumbnail((320, 320), resampling.LANCZOS)
    gray_img = image.convert("L")
    gray = np.asarray(gray_img, dtype=np.float32) / 255.0
    if gray.size < 1000:
        return False
    horizontal = np.abs(np.diff(gray, axis=1))
    vertical = np.abs(np.diff(gray, axis=0))
    edge_density = float((horizontal > 0.20).mean() + (vertical > 0.20).mean()) / 2.0
    dark_pixel_share = float((gray < 0.25).mean())
    return edge_density > 0.055 and 0.001 < dark_pixel_share < 0.45


def artifact_has_text(artifact: dict[str, Any]) -> bool:
    """Return whether an artifact appears to carry text."""
    metadata = artifact["metadata"]
    for key in ("text_content", "text", "copy", "ocr_text", "has_text"):
        value = metadata.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.strip():
            return True
    if font_families(metadata) or type_scale_ratios(metadata):
        return True
    return is_image_artifact(artifact) and text_like_image(artifact["path"])


def check_type_discipline(artifacts: list[dict[str, Any]], thresholds: dict[str, Any]) -> dict[str, Any]:
    """Check font-family consistency and type-scale discipline."""
    text_artifacts = [artifact for artifact in artifacts if artifact_has_text(artifact)]
    if not text_artifacts:
        threshold = float(thresholds["type_scale_ratio_variance_max"])
        return {
            "value": 0.0,
            "max_threshold": threshold,
            "verdict": "pass",
            "details": comparison_details(
                "set_type_discipline",
                0.0,
                threshold,
                "pass",
                "no text-bearing artifacts were detected; family and scale checks are vacuously consistent",
            ),
        }
    family_by_artifact = {artifact["id"]: font_families(artifact["metadata"]) for artifact in text_artifacts}
    known_families = sorted({family for families in family_by_artifact.values() for family in families})
    unknown_family_ids = [artifact_id for artifact_id, families in family_by_artifact.items() if not families]
    family_ok = True
    if thresholds["type_family_consistency_required"]:
        family_ok = len(known_families) <= 1 and not unknown_family_ids
    ratios = []
    missing_ratio_ids: list[str] = []
    for artifact in text_artifacts:
        artifact_ratios = type_scale_ratios(artifact["metadata"])
        if artifact_ratios:
            ratios.append(float(np.median(np.asarray(artifact_ratios, dtype=np.float32))))
        else:
            missing_ratio_ids.append(artifact["id"])
    variance = max(ratios) - min(ratios) if len(ratios) >= 2 else 0.0
    ratio_ok = variance <= float(thresholds["type_scale_ratio_variance_max"])
    metadata_ok = not missing_ratio_ids
    verdict = "pass" if family_ok and ratio_ok and metadata_ok else "fail"
    threshold = float(thresholds["type_scale_ratio_variance_max"])
    rounded = round(variance, 4)
    details = comparison_details(
        "set_type_discipline",
        rounded,
        threshold,
        verdict,
        (
            f"family_ok={family_ok}; ratio_ok={ratio_ok}; metadata_ok={metadata_ok}; "
            f"families={known_families or ['unknown']}; unknown_family_artifacts={unknown_family_ids}; "
            f"missing_type_scale_artifacts={missing_ratio_ids}"
        ),
    )
    return {
        "value": rounded,
        "max_threshold": threshold,
        "verdict": verdict,
        "details": details,
        "families_by_artifact": family_by_artifact,
    }


def lighting_sensitive(artifact: dict[str, Any]) -> bool:
    """Return whether lighting vocabulary should be evaluated."""
    metadata = artifact["metadata"]
    value = metadata.get("lighting_sensitive")
    if isinstance(value, bool):
        return value
    artifact_type = str(artifact.get("artifact_type") or "").lower()
    if artifact_type in LIGHTING_TYPES:
        return True
    return any(token in artifact_type for token in ("photo", "3d", "render", "cinematic"))


def circular_distance_deg(left: float, right: float) -> float:
    """Return smallest distance between two angles in degrees."""
    diff = abs((left - right + 180.0) % 360.0 - 180.0)
    return min(diff, 360.0 - diff)


def max_circular_spread(values: list[float]) -> float:
    """Return max pairwise circular angular spread."""
    spread = 0.0
    for index, left in enumerate(values):
        for right in values[index + 1 :]:
            spread = max(spread, circular_distance_deg(left, right))
    return spread


def lighting_metrics(path: Path) -> tuple[float, float]:
    """Estimate primary light direction and fill ratio for an image."""
    image = load_rgb_image(path)
    resampling = getattr(Image, "Resampling", Image)
    image.thumbnail((160, 160), resampling.LANCZOS)
    gray_img = image.convert("L").filter(ImageFilter.GaussianBlur(radius=1.0))
    gray = np.asarray(gray_img, dtype=np.float32) / 255.0
    gy, gx = np.gradient(gray)
    weights = np.sqrt(gx * gx + gy * gy)
    if float(weights.sum()) > 1e-8:
        vx = float((gx * weights).sum() / weights.sum())
        vy = float((gy * weights).sum() / weights.sum())
        direction = math.degrees(math.atan2(vy, vx)) % 360.0
    else:
        threshold = np.percentile(gray, 90)
        bright = np.maximum(gray - threshold, 0.0)
        if float(bright.sum()) <= 1e-8:
            direction = 0.0
        else:
            yy, xx = np.indices(gray.shape)
            cx = float((xx * bright).sum() / bright.sum())
            cy = float((yy * bright).sum() / bright.sum())
            direction = math.degrees(math.atan2(cy - gray.shape[0] / 2.0, cx - gray.shape[1] / 2.0)) % 360.0
    p15 = float(np.percentile(gray, 15))
    p90 = float(np.percentile(gray, 90))
    fill_ratio = p15 / p90 if p90 > 1e-8 else 1.0
    return direction, fill_ratio


def check_lighting_vocab(artifacts: list[dict[str, Any]], thresholds: dict[str, Any]) -> dict[str, Any]:
    """Check lighting direction and fill-ratio consistency."""
    targets = [artifact for artifact in artifacts if is_image_artifact(artifact) and lighting_sensitive(artifact)]
    if len(targets) < 2:
        threshold = float(thresholds["lighting_primary_direction_variance_deg_max"])
        return {
            "value": 0.0,
            "max_threshold": threshold,
            "verdict": "pass",
            "details": comparison_details(
                "set_lighting_vocab",
                0.0,
                threshold,
                "pass",
                "fewer than two lighting-sensitive artifacts were available for lighting comparison",
            ),
        }
    metrics = {artifact["id"]: lighting_metrics(artifact["path"]) for artifact in targets}
    direction_spread = max_circular_spread([value[0] for value in metrics.values()])
    fill_values = [value[1] for value in metrics.values()]
    fill_spread = max(fill_values) - min(fill_values)
    direction_ok = direction_spread <= float(thresholds["lighting_primary_direction_variance_deg_max"])
    fill_ok = fill_spread <= float(thresholds["lighting_fill_ratio_variance_max"])
    threshold = float(thresholds["lighting_primary_direction_variance_deg_max"])
    rounded_direction = round(direction_spread, 4)
    rounded_fill = round(fill_spread, 4)
    verdict = "pass" if direction_ok and fill_ok else "fail"
    return {
        "value": rounded_direction,
        "max_threshold": threshold,
        "fill_ratio_variance": rounded_fill,
        "fill_ratio_max_threshold": thresholds["lighting_fill_ratio_variance_max"],
        "verdict": verdict,
        "details": comparison_details(
            "set_lighting_vocab",
            rounded_direction,
            threshold,
            verdict,
            (
                f"direction_ok={direction_ok}; fill_ratio_variance {rounded_fill} "
                f"compared with fill_ratio_max_threshold {thresholds['lighting_fill_ratio_variance_max']}; "
                f"fill_ok={fill_ok}"
            ),
        ),
        "metrics_by_artifact": {key: {"direction_deg": round(val[0], 2), "fill_ratio": round(val[1], 4)} for key, val in metrics.items()},
    }


def motion_artifact(artifact: dict[str, Any]) -> bool:
    """Return whether motion tempo should be evaluated."""
    path = artifact.get("path")
    artifact_type = str(artifact.get("artifact_type") or "").lower()
    metadata = artifact["metadata"]
    if any(key in metadata for key in ("pacing_register", "motion_pacing_register", "motion_tempo")):
        return True
    if isinstance(path, Path) and path.suffix.lower() in MOTION_EXTENSIONS:
        return True
    return artifact_type in MOTION_TYPES or any(token in artifact_type for token in ("motion", "video", "animation"))


def pacing_register(metadata: dict[str, Any]) -> str:
    """Extract the declared motion pacing register."""
    for key in ("pacing_register", "motion_pacing_register", "motion_tempo", "tempo_register"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def check_motion_tempo(artifacts: list[dict[str, Any]], thresholds: dict[str, Any]) -> dict[str, Any]:
    """Check motion pacing register consistency."""
    targets = [artifact for artifact in artifacts if motion_artifact(artifact)]
    if not targets:
        return {
            "verdict": "pass",
            "details": (
                "Computed set_motion_tempo: no motion artifacts were detected; "
                "motion_pacing_register_consistency_required comparison is vacuously passing."
            ),
        }
    registers = {artifact["id"]: pacing_register(artifact["metadata"]) for artifact in targets}
    missing = [artifact_id for artifact_id, value in registers.items() if not value]
    unique = sorted({value for value in registers.values() if value})
    required = bool(thresholds["motion_pacing_register_consistency_required"])
    verdict = "pass"
    if required and (missing or len(unique) > 1):
        verdict = "fail"
    return {
        "verdict": verdict,
        "details": (
            f"Computed set_motion_tempo: required={required}; unique_registers={unique}; "
            f"missing={missing}; verdict={verdict}; pacing_registers={registers}."
        ),
        "registers_by_artifact": registers,
    }


def audio_artifact(artifact: dict[str, Any]) -> bool:
    """Return whether audio mood should be evaluated."""
    path = artifact.get("path")
    artifact_type = str(artifact.get("artifact_type") or "").lower()
    metadata = artifact["metadata"]
    if any(key in metadata for key in ("mood_centroid", "audio_mood_centroid", "tempo_bpm", "valence")):
        return True
    if isinstance(path, Path) and path.suffix.lower() in AUDIO_EXTENSIONS:
        return True
    return artifact_type in AUDIO_TYPES or any(token in artifact_type for token in ("audio", "music", "sound"))


def metadata_audio_centroid(metadata: dict[str, Any]) -> list[float]:
    """Extract audio mood centroid from metadata when available."""
    for key in ("mood_centroid", "audio_mood_centroid"):
        values = number_list(metadata.get(key))
        if len(values) >= 3:
            return values[:3]
    if any(key in metadata for key in ("tempo_bpm", "tonal_energy", "valence")):
        tempo = float(metadata.get("tempo_bpm") or 0.0) / 240.0
        tonal = float(metadata.get("tonal_energy") or 0.0)
        valence = float(metadata.get("valence") or 0.0)
        return [max(0.0, min(1.0, tempo)), max(0.0, min(1.0, tonal)), max(0.0, min(1.0, valence))]
    return []


def wav_audio_centroid(path: Path) -> list[float]:
    """Compute a simple tempo/tonal/valence proxy centroid from WAV audio."""
    with wave.open(str(path), "rb") as handle:
        frame_rate = handle.getframerate()
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        frame_count = min(handle.getnframes(), frame_rate * 30)
        frames = handle.readframes(frame_count)
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(sample_width)
    if dtype is None or not frames:
        return [0.0, 0.0, 0.0]
    samples = np.frombuffer(frames, dtype=dtype).astype(np.float32)
    if sample_width == 1:
        samples = (samples - 128.0) / 128.0
    else:
        samples = samples / float(2 ** (sample_width * 8 - 1))
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if len(samples) < frame_rate // 2:
        return [0.0, 0.0, 0.0]
    window = max(1, frame_rate // 10)
    usable = samples[: len(samples) - (len(samples) % window)]
    if len(usable) < window:
        return [0.0, 0.0, 0.0]
    envelope = np.sqrt((usable.reshape(-1, window) ** 2).mean(axis=1))
    envelope = envelope - envelope.mean()
    tempo_proxy = 0.0
    if float(np.abs(envelope).sum()) > 1e-8 and len(envelope) > 8:
        corr = np.correlate(envelope, envelope, mode="full")[len(envelope) - 1 :]
        min_lag = max(1, int(0.3 / 0.1))
        max_lag = min(len(corr) - 1, int(2.0 / 0.1))
        if max_lag > min_lag:
            lag = int(np.argmax(corr[min_lag:max_lag]) + min_lag)
            bpm = 60.0 / (lag * 0.1)
            tempo_proxy = max(0.0, min(1.0, bpm / 240.0))
    sample_window = samples[: min(len(samples), frame_rate * 8)]
    spectrum = np.abs(np.fft.rfft(sample_window * np.hanning(len(sample_window))))
    freqs = np.fft.rfftfreq(len(sample_window), d=1.0 / frame_rate)
    total = float(spectrum.sum())
    if total <= 1e-8:
        return [tempo_proxy, 0.0, 0.0]
    spectral_centroid = float((freqs * spectrum).sum() / total)
    brightness = max(0.0, min(1.0, spectral_centroid / (frame_rate / 2.0)))
    tonal_band = spectrum[(freqs >= 80) & (freqs <= 1000)]
    tonal_energy = float(tonal_band.sum() / total) if len(tonal_band) else 0.0
    valence_proxy = max(0.0, min(1.0, (tonal_energy * 0.65) + ((1.0 - brightness) * 0.35)))
    return [tempo_proxy, max(0.0, min(1.0, tonal_energy)), valence_proxy]


def audio_mood_centroid(artifact: dict[str, Any]) -> list[float]:
    """Return an audio mood centroid for an artifact."""
    metadata_centroid = metadata_audio_centroid(artifact["metadata"])
    if metadata_centroid:
        return metadata_centroid
    path = artifact.get("path")
    if isinstance(path, Path) and path.suffix.lower() == ".wav" and path.exists():
        return wav_audio_centroid(path)
    return []


def euclidean(left: list[float], right: list[float]) -> float:
    """Return Euclidean distance between two equal-length vectors."""
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    return math.sqrt(sum((float(left[index]) - float(right[index])) ** 2 for index in range(size)))


def check_audio_mood(artifacts: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """Check pairwise audio mood centroid distance."""
    targets = [artifact for artifact in artifacts if audio_artifact(artifact)]
    if len(targets) < 2:
        return {
            "value": 0.0,
            "max_threshold": threshold,
            "verdict": "pass",
            "details": comparison_details(
                "set_audio_mood",
                0.0,
                threshold,
                "pass",
                "fewer than two audio artifacts were available for mood-centroid comparison",
            ),
        }
    centroids = {artifact["id"]: audio_mood_centroid(artifact) for artifact in targets}
    missing = [artifact_id for artifact_id, centroid in centroids.items() if not centroid]
    max_distance = 0.0
    ids = list(centroids)
    for left_index, left_id in enumerate(ids):
        for right_id in ids[left_index + 1 :]:
            max_distance = max(max_distance, euclidean(centroids[left_id], centroids[right_id]))
    verdict = verdict_from_max(max_distance, threshold)
    if missing:
        verdict = "fail"
    rounded = round(max_distance, 4)
    return {
        "value": rounded,
        "max_threshold": threshold,
        "verdict": verdict,
        "details": comparison_details(
            "set_audio_mood",
            rounded,
            threshold,
            verdict,
            f"max pairwise centroid distance; missing_centroid_artifacts={missing}",
        ),
        "centroids_by_artifact": {key: [round(x, 4) for x in value] for key, value in centroids.items()},
    }


def subject_area_ratio(path: Path, metadata: dict[str, Any]) -> float:
    """Estimate dominant subject scale as salient area divided by canvas area."""
    for key in ("subject_area_ratio", "dominant_subject_scale", "subject_scale"):
        values = number_list(metadata.get(key))
        if values:
            return max(0.0, min(1.0, values[0]))
    image = load_rgb_image(path)
    resampling = getattr(Image, "Resampling", Image)
    image.thumbnail((240, 240), resampling.LANCZOS)
    gray_img = image.convert("L")
    gray = np.asarray(gray_img, dtype=np.float32) / 255.0
    blurred = np.asarray(gray_img.filter(ImageFilter.GaussianBlur(radius=7)), dtype=np.float32) / 255.0
    rgb = np.asarray(image, dtype=np.float32) / 255.0
    saturation = rgb.max(axis=2) - rgb.min(axis=2)
    local_delta = np.abs(gray - blurred)
    global_delta = np.abs(gray - float(gray.mean()))
    saliency = local_delta * 0.55 + global_delta * 0.30 + saturation * 0.15
    if float(saliency.max()) <= 1e-8:
        return 1.0
    cutoff = max(float(np.percentile(saliency, 70)), float(saliency.max()) * 0.20)
    return float((saliency >= cutoff).mean())


def check_spatial_scale(artifacts: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """Check subject-scale variance across visual artifacts."""
    images = [artifact for artifact in artifacts if is_image_artifact(artifact)]
    if len(images) < 2:
        return {
            "value": 0.0,
            "max_threshold": threshold,
            "verdict": "pass",
            "details": comparison_details(
                "set_spatial_scale",
                0.0,
                threshold,
                "pass",
                "fewer than two visual artifacts were available for subject-scale comparison",
            ),
        }
    ratios = {artifact["id"]: subject_area_ratio(artifact["path"], artifact["metadata"]) for artifact in images}
    value = max(ratios.values()) - min(ratios.values())
    rounded = round(value, 4)
    verdict = verdict_from_max(value, threshold)
    return {
        "value": rounded,
        "max_threshold": threshold,
        "verdict": verdict,
        "details": comparison_details(
            "set_spatial_scale",
            rounded,
            threshold,
            verdict,
            "max-min dominant subject area ratio across visual artifacts",
        ),
        "subject_scale_by_artifact": {key: round(val, 4) for key, val in ratios.items()},
    }


def slot_result_value(artifact: dict[str, Any]) -> str:
    """Extract the slot integration gate verdict from artifact metadata."""
    item = artifact["item"]
    metadata = artifact["metadata"]
    for source in (item, metadata):
        for key in ("slot_integration_gate_result", "slot_fit_result", "slot_gate_result"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
            if isinstance(value, bool):
                return "pass" if value else "fail"
        nested = source.get("slot_integration")
        if isinstance(nested, dict):
            for key in ("verdict", "result", "status"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().lower()
    return ""


def check_slot_fit(artifacts: list[dict[str, Any]], must_be_unanimous: bool) -> dict[str, Any]:
    """Check that every artifact passed its slot integration gate."""
    total = len(artifacts)
    passed_ids = [artifact["id"] for artifact in artifacts if slot_result_value(artifact) == "pass"]
    missing_or_failed = [artifact["id"] for artifact in artifacts if slot_result_value(artifact) != "pass"]
    passed = len(passed_ids)
    verdict = "pass"
    if total == 0 or (must_be_unanimous and passed != total):
        verdict = "fail"
    return {
        "passed": passed,
        "total": total,
        "verdict": verdict,
        "details": (
            f"Computed per_slot_integration: passed {passed} of total {total}; "
            f"slot_fit_must_be_unanimous={must_be_unanimous}; missing_or_failed={missing_or_failed}; "
            f"verdict={verdict}."
        ),
    }


def signoff_pending_path(vs_path: Path) -> Path:
    """Return the path where reviewer signoff should be written."""
    return vs_path.expanduser().resolve().with_name(f"{vs_path.stem}-coherence-signoff.pending.json")


def reviewer_prompt(report: dict[str, Any], artifact_set_path: Path) -> str:
    """Build the visual reviewer prompt for auto mode."""
    return (
        "Fresh visual_spec_review coherence signoff required.\n\n"
        f"Artifact set JSON: {artifact_set_path.resolve()}\n"
        f"Visual spec path: {report['vs_path']}\n"
        f"Pending signoff path: {report['reviewer_signoff_path_pending']}\n\n"
        "Review all produced artifacts and the quantitative coherence report below. "
        "Fill the pending signoff path with JSON matching schemas/coherence-signoff.schema.json. "
        "Cite each quantitative check in reviewer_qualitative_assessment, and set verdict to pass, revise, or fail.\n\n"
        "Quantitative report:\n"
        f"{json.dumps(report, indent=2, sort_keys=True)}\n"
    )


def write_reviewer_ticket(path: Path, project: str, client: str) -> None:
    """Write a minimal ticket so agent_runtime.py spawn-task can detach the reviewer."""
    created = now_iso()
    text = (
        "---\n"
        "type: ticket\n"
        f"id: coherence-signoff-{uuid.uuid4()}\n"
        "title: Coherence signoff review\n"
        "status: open\n"
        "task_type: visual_spec_review\n"
        f"project: {project}\n"
        f"client: {client}\n"
        f"created: {created}\n"
        f"updated: {created}\n"
        "---\n"
        "# Coherence signoff review\n\n"
        "Fresh reviewer session for quantitative coherence signoff.\n"
    )
    path.write_text(text, encoding="utf-8")


def invoke_auto_reviewer(report: dict[str, Any], artifact_set_path: Path, vs_context: dict[str, Any]) -> dict[str, Any]:
    """Spawn a fresh visual reviewer session via agent_runtime.py."""
    pending_path = Path(report["reviewer_signoff_path_pending"])
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path = pending_path.with_suffix(".prompt.txt")
    prompt_path.write_text(reviewer_prompt(report, artifact_set_path), encoding="utf-8")
    fm = vs_context.get("frontmatter") if isinstance(vs_context.get("frontmatter"), dict) else {}
    project = first_text(fm, ("project", "project_id", "name")) or "coherence-review"
    client = first_text(fm, ("client", "client_id")) or "_platform"
    ticket_path = pending_path.with_suffix(".ticket.md")
    write_reviewer_ticket(ticket_path, project, client)
    command = [
        sys.executable,
        str(SCRIPT_DIR / "agent_runtime.py"),
        "spawn-task",
        "--platform",
        str(REPO_ROOT / "vault" / "config" / "platform.md"),
        "--metering",
        str(REPO_ROOT / "vault" / "config" / "metering-observer.md"),
        "--task-type",
        "visual_spec_review",
        "--force-agent",
        "visual_reviewer",
        "--project",
        project,
        "--client",
        client,
        "--cwd",
        str(REPO_ROOT),
        "--ticket-path",
        str(ticket_path),
        "--prompt-file",
        str(prompt_path),
    ]
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "prompt_path": str(prompt_path),
        "ticket_path": str(ticket_path),
    }


def build_report(
    artifact_set_json: Path,
    vs_path: Path,
    thresholds_yaml: Path,
    *,
    reviewer_mode: str = "operator",
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Build the quantitative coherence report."""
    registry = read_yaml(thresholds_yaml)
    if not isinstance(registry, dict):
        raise CoherenceError("threshold registry must be a YAML object")
    vs_context = visual_spec_context(vs_path)
    resolution = resolve_effective_thresholds(registry, vs_context["medium"], vs_context["preset"])
    thresholds = resolution["effective"]
    artifacts = normalize_artifacts(artifact_set_json)

    palette = check_palette_delta(artifacts, float(thresholds["palette_delta_e76_max"]))
    color_temp = check_color_temperature(artifacts, float(thresholds["color_temperature_variance_k_max"]))
    type_discipline = check_type_discipline(artifacts, thresholds)
    lighting = check_lighting_vocab(artifacts, thresholds)
    motion = check_motion_tempo(artifacts, thresholds)
    audio = check_audio_mood(artifacts, float(thresholds["audio_mood_centroid_distance_max"]))
    spatial = check_spatial_scale(artifacts, float(thresholds["spatial_scale_subject_variance_max"]))
    slot_fit = check_slot_fit(artifacts, bool(thresholds["slot_fit_must_be_unanimous"]))

    quantitative_checks = [palette, color_temp, type_discipline, lighting, motion, audio, spatial, slot_fit]
    all_pass = all(check.get("verdict") == "pass" for check in quantitative_checks)
    pending_path = signoff_pending_path(vs_path)
    report: dict[str, Any] = {
        "ran_at": now_iso(),
        "artifact_set_json": str(artifact_set_json.expanduser().resolve()),
        "vs_path": str(vs_path.expanduser().resolve()),
        "visual_spec_medium": vs_context["medium"],
        "visual_spec_preset": vs_context["preset"],
        "applied_thresholds_version": int(registry.get("version") or 0),
        "applied_thresholds_resolution": resolution,
        "set_palette_delta": palette,
        "set_color_temp_variance": color_temp,
        "set_type_discipline": type_discipline,
        "set_lighting_vocab": lighting,
        "set_motion_tempo": motion,
        "set_audio_mood": audio,
        "set_spatial_scale": spatial,
        "per_slot_integration": slot_fit,
        "all_quantitative_checks_pass": all_pass,
        "verdict_quantitative_only": "pass" if all_pass else "fail",
        "reviewer_signoff_required": True,
        "reviewer_signoff_path_pending": str(pending_path),
        "reviewer_qualitative_assessment": "PENDING: visual_reviewer must complete schemas/coherence-signoff.schema.json signoff.",
        "reviewer_mode": reviewer_mode,
        "final_verdict": "pending_reviewer_signoff" if all_pass else "fail",
    }
    if reviewer_mode == "auto":
        try:
            report["reviewer_spawn"] = invoke_auto_reviewer(report, artifact_set_json, vs_context)
        except Exception as exc:
            report["reviewer_spawn"] = {"returncode": 1, "error": str(exc)}
    return attach_report_binding(report, report_path or default_report_path(artifact_set_json))


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-set-json", required=True, help="JSON listing all produced artifacts.")
    parser.add_argument("--vs-path", required=True, help="Visual Specification path used to read medium and preset.")
    parser.add_argument("--thresholds-yaml", required=True, help="Coherence threshold registry YAML path.")
    parser.add_argument("--reviewer-mode", choices=["auto", "operator"], default="operator")
    parser.add_argument("--json-out", help="Optional path to write the JSON report.")
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    report_path = Path(args.json_out) if args.json_out else default_report_path(Path(args.artifact_set_json))
    try:
        report = build_report(
            Path(args.artifact_set_json),
            Path(args.vs_path),
            Path(args.thresholds_yaml),
            reviewer_mode=args.reviewer_mode,
            report_path=report_path,
        )
    except Exception as exc:
        payload = {
            "ran_at": now_iso(),
            "artifact_set_json": args.artifact_set_json,
            "vs_path": args.vs_path,
            "thresholds_yaml": args.thresholds_yaml,
            "error": str(exc),
            "all_quantitative_checks_pass": False,
            "verdict_quantitative_only": "fail",
            "final_verdict": "fail",
        }
        write_json(payload, str(report_path))
        return 2
    write_json(report, str(report_path))
    return 0 if report["verdict_quantitative_only"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

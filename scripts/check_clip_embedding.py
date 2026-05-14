#!/usr/bin/env python3
"""Run CLIP centroid distance checks for locked visual-spec mockups."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CENTROID_DIR = REPO_ROOT / "vault" / "archive" / "visual-aesthetics" / "centroids"
BRAND_SYSTEM_DIR = REPO_ROOT / "vault" / "archive" / "brand-systems"
PLATFORM_CONFIG = REPO_ROOT / "vault" / "config" / "platform.md"
MANIFEST_SCHEMA = REPO_ROOT / "schemas" / "visual-spec-manifest.schema.json"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

sys.path.insert(0, str(SCRIPT_DIR))
from compute_clip_centroid import (  # noqa: E402
    DependencyError as ClipDependencyError,
    encode_image,
    load_clip_model,
    normalize_vector,
    safe_preset_filename,
)


class DependencyError(RuntimeError):
    """Raised when a required runtime dependency is missing."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vs-path", required=True, help="Visual-spec markdown path.")
    parser.add_argument("--references-dir", required=True, help="Visual references directory containing manifest/mockups.")
    parser.add_argument("--json-out", help="Optional path to write the JSON result.")
    parser.add_argument("--read-only", action="store_true", help="Do not update references-dir/manifest.json.")
    return parser.parse_args()


def checked_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def load_yaml_map(text: str) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise DependencyError("check_clip_embedding.py requires PyYAML for VS frontmatter parsing.") from exc
    data = yaml.safe_load(text) if text.strip() else {}
    return data if isinstance(data, dict) else {}


def load_vs_frontmatter(vs_path: Path) -> dict[str, Any]:
    resolved = vs_path.expanduser().resolve()
    if resolved.suffix.lower() == ".json":
        data = json.loads(resolved.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    text = resolved.read_text(encoding="utf-8")
    frontmatter_text, _body = split_frontmatter(text)
    return load_yaml_map(frontmatter_text)


def resolve_path(value: Any, *, vs_path: Path, references_dir: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = Path(value).expanduser()
    if raw.is_absolute():
        return raw
    candidates = [
        REPO_ROOT / raw,
        references_dir / raw,
        vs_path.parent / raw,
        references_dir / raw.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def unique_existing(paths: list[Path | None]) -> list[Path]:
    unique: dict[Path, Path] = {}
    for path in paths:
        if path and path.exists() and path.suffix.lower() in IMAGE_SUFFIXES:
            unique[path.resolve()] = path.resolve()
    return sorted(unique.values(), key=lambda path: str(path))


def load_manifest(references_dir: Path) -> dict[str, Any]:
    path = references_dir / "manifest.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_fixture_vectors(references_dir: Path, vs_path: Path) -> dict[str, Any]:
    """Load deterministic local embeddings for offline fixture gates when present."""
    path = references_dir / "clip-vectors.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    vectors = data.get("image_embeddings")
    if not isinstance(vectors, dict):
        vectors = {}
    resolved_vectors: dict[str, Any] = {}
    for raw_path, vector in vectors.items():
        resolved = resolve_path(raw_path, vs_path=vs_path, references_dir=references_dir)
        if resolved is not None:
            resolved_vectors[str(resolved.resolve())] = vector
    data["image_embeddings"] = resolved_vectors
    return data


def collect_paths(frontmatter: dict[str, Any], references_dir: Path, vs_path: Path) -> tuple[list[Path], list[Path], list[Path]]:
    primary_refs: list[Path | None] = []
    anti_refs: list[Path | None] = []
    mockups: list[Path | None] = []

    for ref in frontmatter.get("references", []) if isinstance(frontmatter.get("references"), list) else []:
        if not isinstance(ref, dict):
            continue
        path = resolve_path(ref.get("file"), vs_path=vs_path, references_dir=references_dir)
        if str(ref.get("role", "")).strip().lower() == "anti_pattern":
            anti_refs.append(path)
        else:
            primary_refs.append(path)

    for mockup in frontmatter.get("mockups", []) if isinstance(frontmatter.get("mockups"), list) else []:
        if isinstance(mockup, dict):
            mockups.append(resolve_path(mockup.get("final_png"), vs_path=vs_path, references_dir=references_dir))

    manifest = load_manifest(references_dir)
    for asset in manifest.get("assets", []) if isinstance(manifest.get("assets"), list) else []:
        if not isinstance(asset, dict):
            continue
        path = resolve_path(asset.get("path"), vs_path=vs_path, references_dir=references_dir)
        role = str(asset.get("role", "")).strip().lower()
        if role == "anti_pattern":
            anti_refs.append(path)
        elif role == "reference":
            primary_refs.append(path)
        elif role == "mockup":
            mockups.append(path)

    if not mockups:
        mockups.extend(path for path in (references_dir / "mockups").glob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
    for dirname in ("anti-patterns", "anti_patterns"):
        folder = references_dir / dirname
        if folder.exists():
            anti_refs.extend(path for path in folder.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
    refs_folder = references_dir / "references"
    if not primary_refs and refs_folder.exists():
        primary_refs.extend(path for path in refs_folder.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)

    return unique_existing(primary_refs), unique_existing(anti_refs), unique_existing(mockups)


def parse_platform_clip_config() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "visual_spec_clip_preset_distance_min": 0.20,
        "visual_spec_clip_preset_distance_max": 0.55,
        "visual_spec_clip_antipattern_distance_min": 0.50,
        "visual_spec_clip_anchor_diversity_min": 0.10,
        "visual_spec_clip_model": "ViT-B-32",
    }
    if not PLATFORM_CONFIG.exists():
        return defaults
    text = PLATFORM_CONFIG.read_text(encoding="utf-8")
    for key in list(defaults):
        match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", text, flags=re.M)
        if not match:
            continue
        raw = match.group(1).strip().strip('"').strip("'")
        if key.endswith("_model"):
            defaults[key] = raw
        else:
            try:
                defaults[key] = float(raw)
            except ValueError:
                pass
    return defaults


def cosine_distance(a: Any, b: Any) -> float:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("check_clip_embedding.py requires numpy. Install with: python3 -m pip install numpy") from exc
    vec_a = normalize_vector(a)
    vec_b = normalize_vector(b)
    return float(1.0 - np.dot(vec_a, vec_b))


def centroid_hash(centroid: Any) -> str:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("check_clip_embedding.py requires numpy. Install with: python3 -m pip install numpy") from exc
    array = np.asarray(centroid, dtype=np.float32)
    return hashlib.sha256(array.tobytes()).hexdigest()


def load_brand_frontmatter(brand_slug: str) -> tuple[Path | None, dict[str, Any]]:
    candidates = [BRAND_SYSTEM_DIR / f"{safe_preset_filename(brand_slug)}.md"]
    candidates.extend(path for path in BRAND_SYSTEM_DIR.glob("*.md") if path.name not in {"_index.md", "_template.md"})
    for path in candidates:
        if not path.exists():
            continue
        frontmatter_text, _body = split_frontmatter(path.read_text(encoding="utf-8"))
        data = load_yaml_map(frontmatter_text)
        if path == candidates[0] or data.get("brand_slug") == brand_slug:
            return path.resolve(), data
    return None, {}


def determine_target_centroid(
    mode: str,
    preset: str,
    primary_refs: list[Path],
    config: dict[str, Any],
    vs_path: Path,
    references_dir: Path,
    fixture_vectors: dict[str, Any] | None = None,
) -> tuple[Any | None, str | None, str | None, list[str]]:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("check_clip_embedding.py requires numpy. Install with: python3 -m pip install numpy") from exc

    warnings: list[str] = []
    model_name = str(config["visual_spec_clip_model"])
    fixture_vectors = fixture_vectors or {}
    if fixture_vectors.get("target_centroid") is not None:
        return normalize_vector(np.asarray(fixture_vectors["target_centroid"], dtype=np.float32)), "fixture-local", preset or "fixture", warnings
    if mode == "preset":
        centroid_path = CENTROID_DIR / f"{safe_preset_filename(preset)}.npy"
        if not centroid_path.exists():
            warnings.append(f"Preset centroid not found: {centroid_path}")
            return None, None, None, warnings
        return normalize_vector(np.load(centroid_path)), str(centroid_path.resolve()), preset, warnings
    if mode == "custom":
        if not primary_refs:
            raise ValueError("custom CLIP mode requires at least one primary reference PNG.")
        model, preprocess, torch, device = load_clip_model(model_name)
        embeddings = [encode_image(path, model, preprocess, torch, device) for path in primary_refs]
        return normalize_vector(np.mean(np.stack(embeddings), axis=0)), None, "custom", warnings
    if mode == "brand_system":
        brand_path, brand_data = load_brand_frontmatter(preset)
        if not brand_path:
            raise ValueError(f"brand_system mode requires vault/archive/brand-systems/{preset}.md.")
        centroid_value = brand_data.get("clip_centroid_path")
        centroid_path = resolve_path(centroid_value, vs_path=vs_path, references_dir=references_dir)
        if not centroid_path or not centroid_path.exists():
            warnings.append(f"Brand-system centroid not found: {centroid_value}")
            return None, None, preset, warnings
        return normalize_vector(np.load(centroid_path)), str(centroid_path.resolve()), preset, warnings
    return None, None, None, warnings


def encode_paths(paths: list[Path], model_name: str) -> dict[str, Any]:
    model, preprocess, torch, device = load_clip_model(model_name)
    return {str(path): encode_image(path, model, preprocess, torch, device) for path in paths}


def encode_paths_with_fixture_vectors(paths: list[Path], model_name: str, fixture_vectors: dict[str, Any]) -> dict[str, Any]:
    """Return fixture vectors when available, falling back to real CLIP encoding."""
    image_embeddings = fixture_vectors.get("image_embeddings") if isinstance(fixture_vectors, dict) else {}
    if isinstance(image_embeddings, dict) and image_embeddings:
        missing = [path for path in paths if str(path.resolve()) not in image_embeddings]
        if missing:
            raise ValueError(f"clip-vectors.json is missing embeddings for: {[str(path) for path in missing]}")
        return {str(path): normalize_vector(image_embeddings[str(path.resolve())]) for path in paths}
    return encode_paths(paths, model_name)


def compute_centroid_from_embeddings(embeddings: list[Any]) -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("check_clip_embedding.py requires numpy. Install with: python3 -m pip install numpy") from exc
    if not embeddings:
        raise ValueError("At least one embedding is required to compute a centroid.")
    return normalize_vector(np.mean(np.stack(embeddings), axis=0))


def check_mockup_to_preset(
    mockup_embeddings: dict[str, Any],
    target_centroid: Any,
    min_distance: float,
    max_distance: float,
) -> dict[str, Any]:
    if not mockup_embeddings:
        return {"verdict": "fail", "details": "No locked mockup PNGs found.", "per_mockup": [], "all_in_band": False}
    per = []
    for path, embedding in mockup_embeddings.items():
        distance = cosine_distance(embedding, target_centroid)
        per.append({"mockup": path, "distance": round(distance, 6), "in_band": min_distance <= distance <= max_distance})
    all_in_band = all(item["in_band"] for item in per)
    return {
        "verdict": "pass" if all_in_band else "fail",
        "distance_min": min_distance,
        "distance_max": max_distance,
        "per_mockup": per,
        "all_in_band": all_in_band,
        "details": "All mockups sit inside the preset distance band." if all_in_band else "One or more mockups are too close to or too far from the target centroid.",
    }


def check_mockup_to_antipattern(
    mockup_embeddings: dict[str, Any],
    anti_embeddings: dict[str, Any],
    threshold: float,
) -> tuple[dict[str, Any], Any | None]:
    if not anti_embeddings:
        return (
            {
                "verdict": "not_applicable_no_antipatterns",
                "details": "No anti-pattern PNGs found for this VS.",
                "per_mockup": [],
                "all_above_threshold": True,
                "distance_min": threshold,
            },
            None,
        )
    anti_centroid = compute_centroid_from_embeddings(list(anti_embeddings.values()))
    per = []
    for path, embedding in mockup_embeddings.items():
        distance = cosine_distance(embedding, anti_centroid)
        per.append({"mockup": path, "distance": round(distance, 6), "above_threshold": distance > threshold})
    all_above = all(item["above_threshold"] for item in per) if per else False
    return (
        {
            "verdict": "pass" if all_above else "fail",
            "distance_min": threshold,
            "per_mockup": per,
            "all_above_threshold": all_above,
            "details": "All mockups are far enough from the anti-pattern centroid." if all_above else "One or more mockups are too close to the anti-pattern centroid.",
        },
        anti_centroid,
    )


def check_anchor_diversity(mockup_embeddings: dict[str, Any], threshold: float) -> dict[str, Any]:
    paths = list(mockup_embeddings)
    if len(paths) < 2:
        return {
            "verdict": "not_applicable_insufficient_anchors",
            "details": "Anchor diversity requires at least two locked mockup PNGs.",
            "pairwise_distances": [],
            "all_above_threshold": True,
            "distance_min": threshold,
        }
    pairs = []
    for index, left in enumerate(paths):
        for right in paths[index + 1 :]:
            distance = cosine_distance(mockup_embeddings[left], mockup_embeddings[right])
            pairs.append({"mockup_a": left, "mockup_b": right, "distance": round(distance, 6), "above_threshold": distance > threshold})
    all_above = all(item["above_threshold"] for item in pairs)
    return {
        "verdict": "pass" if all_above else "fail",
        "distance_min": threshold,
        "pairwise_distances": pairs,
        "all_above_threshold": all_above,
        "details": "Anchor mockups are visually distinct in CLIP space." if all_above else "Two or more anchor mockups are too similar in CLIP space.",
    }


def validation_for_manifest_block(block_name: str, block: dict[str, Any]) -> dict[str, Any]:
    try:
        import jsonschema
    except ImportError:
        return {"valid": False, "errors": ["jsonschema is not installed."]}
    try:
        schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema).evolve(schema=schema["properties"][block_name])
        errors = sorted(validator.iter_errors(block), key=lambda error: list(error.path))
    except Exception as exc:  # pragma: no cover - defensive schema loader path
        return {"valid": False, "errors": [str(exc)]}
    return {
        "valid": not errors,
        "errors": [
            {"path": "/" + "/".join(str(part) for part in error.path), "message": error.message}
            for error in errors
        ],
    }


def manifest_clip_block(
    model_name: str,
    target_centroid: Any,
    check44: dict[str, Any],
    check45: dict[str, Any],
) -> dict[str, Any] | None:
    preset_distances = [item["distance"] for item in check44.get("per_mockup", []) if isinstance(item.get("distance"), (int, float))]
    if not preset_distances:
        return None
    block: dict[str, Any] = {
        "model": model_name,
        "centroid_hash": centroid_hash(target_centroid),
        "distance_to_preset": float(sum(preset_distances) / len(preset_distances)),
    }
    anti_distances = [item["distance"] for item in check45.get("per_mockup", []) if isinstance(item.get("distance"), (int, float))]
    if anti_distances:
        block["distance_to_anti_pattern"] = float(min(anti_distances))
    return block


def update_manifest_clip_block(references_dir: Path, block: dict[str, Any], read_only: bool) -> dict[str, Any]:
    manifest_path = references_dir / "manifest.json"
    validation = validation_for_manifest_block("clip_embedding", block)
    status = {
        "path": str(manifest_path),
        "updated": False,
        "read_only": read_only,
        "schema_validation": validation,
    }
    if read_only or not validation["valid"]:
        return status
    if not manifest_path.exists():
        status["warning"] = "manifest.json not found; clip_embedding block was not written."
        return status
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["clip_embedding"] = block
    manifest_path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    status["updated"] = True
    return status


def skipped_result(
    *,
    vs_path: Path,
    mode: str,
    preset: str | None,
    preset_centroid_path: str | None,
    warnings: list[str],
    reason: str,
) -> dict[str, Any]:
    return {
        "vs_path": str(vs_path),
        "checked_at": checked_at(),
        "mode": mode,
        "preset": preset,
        "preset_centroid_path": preset_centroid_path,
        "warnings": warnings,
        "checks": {
            "44_mockup_to_preset": {"verdict": reason, "per_mockup": [], "all_in_band": True},
            "45_mockup_to_antipattern": {"verdict": reason, "per_mockup": [], "all_above_threshold": True},
            "46_anchor_diversity": {"verdict": reason, "pairwise_distances": [], "all_above_threshold": True},
        },
        "all_passed": True,
        "verdict": "skipped",
    }


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    vs_path = Path(args.vs_path).expanduser().resolve()
    references_dir = Path(args.references_dir).expanduser().resolve()
    frontmatter = load_vs_frontmatter(vs_path)
    config = parse_platform_clip_config()
    model_name = str(config["visual_spec_clip_model"])
    mode = str(frontmatter.get("visual_quality_target_mode") or ("preset" if frontmatter.get("visual_quality_target_preset") else "none")).strip()
    preset = str(frontmatter.get("visual_quality_target_preset") or frontmatter.get("preset") or "").strip()
    primary_refs, anti_refs, mockups = collect_paths(frontmatter, references_dir, vs_path)
    fixture_vectors = load_fixture_vectors(references_dir, vs_path)

    if mode == "none":
        return 0, skipped_result(
            vs_path=vs_path,
            mode=mode,
            preset=preset or None,
            preset_centroid_path=None,
            warnings=[],
            reason="not_applicable_mode_none",
        )

    target_centroid, centroid_path, resolved_preset, warnings = determine_target_centroid(
        mode,
        preset,
        primary_refs,
        config,
        vs_path,
        references_dir,
        fixture_vectors,
    )
    if target_centroid is None:
        return 0, skipped_result(
            vs_path=vs_path,
            mode=mode,
            preset=resolved_preset or preset or None,
            preset_centroid_path=centroid_path,
            warnings=warnings,
            reason="not_applicable_no_centroid",
        )

    all_image_paths = mockups + anti_refs
    mockup_embeddings_all = encode_paths_with_fixture_vectors(all_image_paths, model_name, fixture_vectors) if all_image_paths else {}
    mockup_embeddings = {str(path): mockup_embeddings_all[str(path)] for path in mockups if str(path) in mockup_embeddings_all}
    anti_embeddings = {str(path): mockup_embeddings_all[str(path)] for path in anti_refs if str(path) in mockup_embeddings_all}

    check44 = check_mockup_to_preset(
        mockup_embeddings,
        target_centroid,
        float(config["visual_spec_clip_preset_distance_min"]),
        float(config["visual_spec_clip_preset_distance_max"]),
    )
    check45, _anti_centroid = check_mockup_to_antipattern(
        mockup_embeddings,
        anti_embeddings,
        float(config["visual_spec_clip_antipattern_distance_min"]),
    )
    check46 = check_anchor_diversity(mockup_embeddings, float(config["visual_spec_clip_anchor_diversity_min"]))
    checks = {
        "44_mockup_to_preset": check44,
        "45_mockup_to_antipattern": check45,
        "46_anchor_diversity": check46,
    }
    all_passed = not any(data.get("verdict") == "fail" for data in checks.values())
    block = manifest_clip_block(model_name, target_centroid, check44, check45)
    manifest_update = None
    if block is not None:
        manifest_update = update_manifest_clip_block(references_dir, block, args.read_only)
        if not manifest_update["schema_validation"]["valid"]:
            all_passed = False

    result = {
        "vs_path": str(vs_path),
        "checked_at": checked_at(),
        "mode": mode,
        "preset": resolved_preset or preset or None,
        "preset_centroid_path": centroid_path,
        "model": model_name,
        "references": {
            "primary_reference_count": len(primary_refs),
            "anti_pattern_count": len(anti_refs),
            "mockup_count": len(mockups),
        },
        "warnings": warnings,
        "checks": checks,
        "clip_embedding": block,
        "manifest_update": manifest_update,
        "all_passed": all_passed,
        "verdict": "pass" if all_passed else "fail",
    }
    return (0 if all_passed else 1), result


def main() -> int:
    args = parse_args()
    try:
        code, data = run(args)
    except ClipDependencyError as exc:
        data = {"error": str(exc), "verdict": "error"}
        write_json(data, args.json_out)
        print(str(exc), file=sys.stderr)
        return 2
    except DependencyError as exc:
        data = {"error": str(exc), "verdict": "error"}
        write_json(data, args.json_out)
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        data = {"error": str(exc), "verdict": "error"}
        write_json(data, args.json_out)
        return 1
    write_json(data, args.json_out)
    return code


if __name__ == "__main__":
    sys.exit(main())

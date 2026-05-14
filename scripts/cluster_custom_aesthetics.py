#!/usr/bin/env python3
"""Cluster custom-mode visual specifications into reusable aesthetic cohorts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CUSTOM_DIR = REPO_ROOT / "vault" / "archive" / "visual-aesthetics" / "custom"
DEFAULT_MEMBERSHIP = CUSTOM_DIR / "_cohort-membership.json"
PROMOTION_DIR = REPO_ROOT / "vault" / "archive" / "visual-aesthetics" / "proposals" / "_promising-but-insufficient"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
DISTANCE_THRESHOLD = 0.15
AXIS_WEIGHT = 0.3
CLIP_WEIGHT = 0.7
CLIP_DIM = 512
UUID_NAMESPACE = uuid.UUID("8fd6e9e6-78c8-4f15-93c5-336bc423e8c1")

sys.path.insert(0, str(SCRIPT_DIR))
from compute_clip_centroid import (  # noqa: E402
    DependencyError as ClipDependencyError,
    encode_image,
    load_clip_model,
    normalize_vector,
)


class DependencyError(RuntimeError):
    """Raised when a required non-CLIP dependency is missing."""


@dataclass(frozen=True)
class FeatureBundle:
    vector: Any
    vector_hash: str
    axis_features_norm: Any
    clip_features_norm: Any
    axis_signature: dict[str, Any]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_string() -> str:
    return datetime.now().astimezone().date().isoformat()


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
        raise DependencyError("cluster_custom_aesthetics.py requires PyYAML for VS frontmatter parsing.") from exc
    data = yaml.safe_load(text) if text.strip() else {}
    return data if isinstance(data, dict) else {}


def dump_yaml_map(data: dict[str, Any]) -> str:
    try:
        import yaml
    except ImportError as exc:
        raise DependencyError("cluster_custom_aesthetics.py requires PyYAML for VS frontmatter writing.") from exc
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=False)


def load_vs_frontmatter(vs_path: Path) -> tuple[dict[str, Any], str]:
    resolved = vs_path.expanduser().resolve()
    text = resolved.read_text(encoding="utf-8")
    frontmatter_text, body = split_frontmatter(text)
    return load_yaml_map(frontmatter_text), body


def write_vs_frontmatter(vs_path: Path, frontmatter: dict[str, Any], body: str) -> None:
    vs_path.write_text("---\n" + dump_yaml_map(frontmatter) + "---\n" + body, encoding="utf-8")


def display_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def resolve_member_path(value: str) -> Path:
    raw = Path(value).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (REPO_ROOT / raw).resolve()


def resolve_vs_relative_path(value: Any, *, vs_path: Path, references_dir: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = Path(value).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    candidates = [
        REPO_ROOT / raw,
        vs_path.parent / raw,
        references_dir / raw,
        references_dir / raw.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def references_dir_for(vs_path: Path) -> Path:
    return vs_path.expanduser().resolve().parent / "visual-references"


def collect_primary_reference_paths(frontmatter: dict[str, Any], vs_path: Path) -> list[Path]:
    references_dir = references_dir_for(vs_path)
    paths: dict[str, Path] = {}
    refs = frontmatter.get("references")
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            if str(ref.get("role", "")).strip().lower() == "anti_pattern":
                continue
            resolved = resolve_vs_relative_path(ref.get("file"), vs_path=vs_path, references_dir=references_dir)
            if resolved and resolved.suffix.lower() in IMAGE_SUFFIXES and resolved.exists():
                paths[str(resolved)] = resolved

    refs_folder = references_dir / "references"
    if not paths and refs_folder.exists():
        for candidate in refs_folder.rglob("*"):
            if candidate.suffix.lower() in IMAGE_SUFFIXES and candidate.exists():
                paths[str(candidate.resolve())] = candidate.resolve()
    return [paths[key] for key in sorted(paths)]


def coerce_vector_spec(value: Any) -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("cluster_custom_aesthetics.py requires numpy. Install with: python3 -m pip install numpy") from exc

    if isinstance(value, list):
        return normalize_vector(np.asarray(value, dtype=np.float32))
    if not isinstance(value, dict):
        raise ValueError("Fixture vector must be a list or a compact vector object.")

    dim = int(value.get("dimension", CLIP_DIM))
    if dim != CLIP_DIM:
        raise ValueError(f"Fixture vector dimension must be {CLIP_DIM}; got {dim}.")
    vector = np.zeros(dim, dtype=np.float32)
    if "basis_index" in value:
        index = int(value["basis_index"])
        if index < 0 or index >= dim:
            raise ValueError(f"basis_index out of range: {index}")
        vector[index] = float(value.get("scale", 1.0))
    elif "components" in value and isinstance(value["components"], dict):
        for raw_index, raw_component in value["components"].items():
            index = int(raw_index)
            if index < 0 or index >= dim:
                raise ValueError(f"component index out of range: {index}")
            vector[index] = float(raw_component)
    else:
        raise ValueError("Compact fixture vector must provide basis_index or components.")
    return normalize_vector(vector)


def load_fixture_vectors(references_dir: Path, vs_path: Path) -> dict[str, Any]:
    path = references_dir / "clip-vectors.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}

    result: dict[str, Any] = {}
    if data.get("target_centroid") is not None:
        result["target_centroid"] = coerce_vector_spec(data["target_centroid"])

    image_embeddings = data.get("image_embeddings")
    if isinstance(image_embeddings, dict):
        resolved_embeddings: dict[str, Any] = {}
        for raw_path, vector in image_embeddings.items():
            resolved = resolve_vs_relative_path(raw_path, vs_path=vs_path, references_dir=references_dir)
            if resolved is not None:
                resolved_embeddings[str(resolved.resolve())] = coerce_vector_spec(vector)
        result["image_embeddings"] = resolved_embeddings
    return result


def ensure_clip_dim(vector: Any) -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("cluster_custom_aesthetics.py requires numpy. Install with: python3 -m pip install numpy") from exc
    array = np.asarray(vector, dtype=np.float32)
    if array.shape != (CLIP_DIM,):
        raise ValueError(f"CLIP centroid must be shape ({CLIP_DIM},); got {list(array.shape)}")
    return normalize_vector(array)


def compute_project_clip_centroid(frontmatter: dict[str, Any], vs_path: Path) -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("cluster_custom_aesthetics.py requires numpy. Install with: python3 -m pip install numpy") from exc

    references_dir = references_dir_for(vs_path)
    fixture_vectors = load_fixture_vectors(references_dir, vs_path)
    if fixture_vectors.get("target_centroid") is not None:
        return ensure_clip_dim(fixture_vectors["target_centroid"])

    primary_refs = collect_primary_reference_paths(frontmatter, vs_path)
    if not primary_refs:
        raise ValueError(f"custom VS has no primary reference images: {vs_path}")

    image_embeddings = fixture_vectors.get("image_embeddings")
    if isinstance(image_embeddings, dict) and image_embeddings:
        missing = [path for path in primary_refs if str(path.resolve()) not in image_embeddings]
        if missing:
            raise ValueError(f"clip-vectors.json is missing embeddings for: {[str(path) for path in missing]}")
        embeddings = [ensure_clip_dim(image_embeddings[str(path.resolve())]) for path in primary_refs]
    else:
        model, preprocess, torch, device = load_clip_model("ViT-B-32")
        embeddings = [encode_image(path, model, preprocess, torch, device) for path in primary_refs]
    return ensure_clip_dim(np.mean(np.stack(embeddings), axis=0))


AXIS_BUCKETS: dict[str, tuple[str, str, str]] = {
    "density": ("sparse", "balanced", "dense"),
    "topology": ("single", "list_detail", "multi_region"),
    "expressiveness": ("restrained", "balanced", "expressive"),
    "motion": ("static", "functional", "expressive"),
    "platform": ("web", "native", "specialized"),
    "trust": ("approachable", "professional", "regulated"),
}


def normalize_axis_bucket(axis: str, value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if axis == "density":
        if raw == "ultra_dense":
            return "dense"
        return raw if raw in AXIS_BUCKETS[axis] else "balanced"
    if axis == "topology":
        if raw in {"single_panel", "single_pane"}:
            return "single"
        if raw in {"list_detail", "list"}:
            return "list_detail"
        return "multi_region"
    if axis == "expressiveness":
        if raw in {"quiet", "restrained"}:
            return "restrained"
        if raw in {"balanced", "editorial"}:
            return "balanced"
        return "expressive"
    if axis == "motion":
        if raw in {"static", "calm"}:
            return "static"
        if raw in {"subtle", "functional", "standard"}:
            return "functional"
        return "expressive"
    if axis == "platform":
        if raw in {"web", "web_native", "web_app"}:
            return "web"
        if raw in {"ios_native", "android_native", "desktop_native", "native", "cross_platform"}:
            return "native"
        return "specialized"
    if axis == "trust":
        if raw in {"experimental", "approachable", "consumer"}:
            return "approachable"
        if raw in {"professional", "luxury"}:
            return "professional"
        return "regulated"
    return AXIS_BUCKETS[axis][1]


def one_hot(axis: str, bucket: str) -> list[float]:
    values = AXIS_BUCKETS[axis]
    return [1.0 if item == bucket else 0.0 for item in values]


def canonical_medium_extensions(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): value[key] for key in sorted(value)}


def compose_axis_features(frontmatter: dict[str, Any]) -> tuple[list[float], dict[str, Any]]:
    axes = frontmatter.get("visual_axes")
    if not isinstance(axes, dict):
        raise ValueError("custom VS frontmatter must include visual_axes mapping.")

    features: list[float] = []
    canonical_axes: dict[str, str] = {}
    for axis in ("density", "topology", "expressiveness", "motion", "platform", "trust"):
        bucket = normalize_axis_bucket(axis, axes.get(axis))
        canonical_axes[axis] = bucket
        features.extend(one_hot(axis, bucket))

    extensions = canonical_medium_extensions(frontmatter.get("visual_axes_medium_extensions"))
    for key, value in extensions.items():
        encoded = json.dumps({"key": key, "value": value}, sort_keys=True)
        digest = hashlib.sha256(encoded.encode("utf-8")).digest()
        features[digest[0] % len(features)] += 1.0

    signature = {
        "visual_quality_target_medium": frontmatter.get("visual_quality_target_medium"),
        "visual_axes": canonical_axes,
        "visual_axes_medium_extensions": extensions,
    }
    return features, signature


def feature_vector_hash(vector: Any) -> str:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("cluster_custom_aesthetics.py requires numpy. Install with: python3 -m pip install numpy") from exc
    array = np.asarray(vector, dtype=np.float32)
    return hashlib.sha256(array.tobytes()).hexdigest()


def compose_feature_vector(frontmatter: dict[str, Any], clip_centroid: Any) -> FeatureBundle:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("cluster_custom_aesthetics.py requires numpy. Install with: python3 -m pip install numpy") from exc

    axis_features, axis_signature = compose_axis_features(frontmatter)
    axis_array = np.asarray(axis_features, dtype=np.float32)
    clip_array = ensure_clip_dim(clip_centroid)

    axis_norm = float(np.linalg.norm(axis_array))
    clip_norm = float(np.linalg.norm(clip_array))
    if axis_norm == 0:
        raise ValueError("Cannot normalize empty axis feature block.")
    if clip_norm == 0:
        raise ValueError("Cannot normalize empty CLIP feature block.")

    axis_features_norm = (axis_array / axis_norm).astype(np.float32)
    clip_features_norm = (clip_array / clip_norm).astype(np.float32)
    final = np.concatenate([axis_features_norm * AXIS_WEIGHT, clip_features_norm * CLIP_WEIGHT])
    final = normalize_vector(final)
    return FeatureBundle(
        vector=final.astype(np.float32),
        vector_hash=feature_vector_hash(final),
        axis_features_norm=axis_features_norm,
        clip_features_norm=clip_features_norm,
        axis_signature=axis_signature,
    )


def feature_bundle_for_vs(vs_path: Path) -> tuple[dict[str, Any], str, FeatureBundle]:
    frontmatter, body = load_vs_frontmatter(vs_path)
    mode = str(frontmatter.get("visual_quality_target_mode") or "").strip()
    if mode != "custom":
        raise ValueError(f"VS is not visual_quality_target_mode=custom: {vs_path}")
    clip_centroid = compute_project_clip_centroid(frontmatter, vs_path)
    return frontmatter, body, compose_feature_vector(frontmatter, clip_centroid)


def cosine_distance(left: Any, right: Any) -> float:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("cluster_custom_aesthetics.py requires numpy. Install with: python3 -m pip install numpy") from exc
    left_norm = normalize_vector(left)
    right_norm = normalize_vector(right)
    return float(1.0 - np.dot(left_norm, right_norm))


def state_for_size(size: int) -> str:
    if size <= 1:
        return "singleton"
    if size == 2:
        return "watchlist"
    if size <= 4:
        return "monitored_cohort"
    return "mature_cohort"


def load_membership(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "last_updated": now_iso(), "cohorts": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Membership file is not a JSON object: {path}")
    data.setdefault("version", 1)
    data.setdefault("last_updated", now_iso())
    data.setdefault("cohorts", [])
    return data


def save_membership(path: Path, membership: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(membership, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def member_key(vs_path: Path) -> str:
    return str(vs_path.expanduser().resolve())


def find_existing_assignment(membership: dict[str, Any], vs_path: Path) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    target = member_key(vs_path)
    for cohort in membership.get("cohorts", []):
        if not isinstance(cohort, dict):
            continue
        for member in cohort.get("members", []) if isinstance(cohort.get("members"), list) else []:
            if not isinstance(member, dict):
                continue
            try:
                if member_key(resolve_member_path(str(member.get("vs_path", "")))) == target:
                    return cohort, member
            except Exception:
                continue
    return None, None


def find_cohort_by_id(membership: dict[str, Any], cohort_id: str) -> dict[str, Any] | None:
    for cohort in membership.get("cohorts", []):
        if isinstance(cohort, dict) and cohort.get("cohort_id") == cohort_id:
            return cohort
    return None


def nearest_cohort(membership: dict[str, Any], vector: Any) -> tuple[dict[str, Any] | None, float | None]:
    nearest: dict[str, Any] | None = None
    nearest_distance: float | None = None
    for cohort in membership.get("cohorts", []):
        if not isinstance(cohort, dict) or not cohort.get("centroid"):
            continue
        distance = cosine_distance(vector, cohort["centroid"])
        if nearest_distance is None or distance < nearest_distance:
            nearest = cohort
            nearest_distance = distance
    return nearest, nearest_distance


def stable_new_cohort_id(vs_path: Path, *, deterministic: bool) -> str:
    if deterministic:
        return str(uuid.uuid5(UUID_NAMESPACE, display_path(vs_path)))
    return str(uuid.uuid4())


def member_record(vs_path: Path, feature_hash: str, joined_at: str) -> dict[str, Any]:
    return {
        "vs_path": display_path(vs_path),
        "joined_at": joined_at,
        "feature_vector_hash": feature_hash,
    }


def mode_value(values: Iterable[Any]) -> Any:
    normalized = [json.dumps(value, sort_keys=True) for value in values]
    if not normalized:
        return None
    counts = Counter(normalized)
    winner = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return json.loads(winner)


def aggregate_axis_signature(signatures: list[dict[str, Any]]) -> dict[str, Any]:
    if not signatures:
        return {}
    axes: dict[str, Any] = {}
    for axis in ("density", "topology", "expressiveness", "motion", "platform", "trust"):
        axes[axis] = mode_value(
            (signature.get("visual_axes") or {}).get(axis)
            for signature in signatures
            if isinstance(signature.get("visual_axes"), dict)
        )
    return {
        "visual_quality_target_medium": mode_value(signature.get("visual_quality_target_medium") for signature in signatures),
        "visual_axes": axes,
        "visual_axes_medium_extensions": mode_value(signature.get("visual_axes_medium_extensions") for signature in signatures),
    }


def recompute_cohort_metadata(
    cohort: dict[str, Any],
    vector_by_member_path: dict[str, Any],
    signature_by_member_path: dict[str, dict[str, Any]],
    timestamp: str,
) -> None:
    try:
        import numpy as np
    except ImportError as exc:
        raise DependencyError("cluster_custom_aesthetics.py requires numpy. Install with: python3 -m pip install numpy") from exc

    vectors = []
    signatures = []
    for member in cohort.get("members", []):
        if not isinstance(member, dict):
            continue
        key = member_key(resolve_member_path(str(member.get("vs_path"))))
        vector = vector_by_member_path.get(key)
        if vector is not None:
            vectors.append(normalize_vector(vector))
        signature = signature_by_member_path.get(key)
        if signature is not None:
            signatures.append(signature)
    if vectors:
        centroid = normalize_vector(np.mean(np.stack(vectors), axis=0))
        cohort["centroid"] = [float(x) for x in centroid.tolist()]
        cohort["centroid_last_updated"] = timestamp
    cohort["state"] = state_for_size(len(cohort.get("members", [])))
    cohort["axis_signature"] = aggregate_axis_signature(signatures) if signatures else cohort.get("axis_signature", {})


def positive_outcome(frontmatter: dict[str, Any]) -> bool:
    outcome = frontmatter.get("outcome_data")
    if not isinstance(outcome, dict):
        return False
    final_gate = str(outcome.get("visual_gate_final") or "").strip().upper()
    grade = str(outcome.get("delivery_review_grade") or "").strip().upper()
    acceptance = str(outcome.get("operator_acceptance") or "").strip().lower()
    return final_gate == "PASS" and grade in {"A+", "A", "A-"} and acceptance in {"accepted", "accepted_with_notes"}


def cohort_has_consistent_positive_outcomes(cohort: dict[str, Any]) -> bool:
    members = cohort.get("members", [])
    if not isinstance(members, list) or len(members) < 5:
        return False
    for member in members:
        if not isinstance(member, dict):
            return False
        try:
            frontmatter, _body = load_vs_frontmatter(resolve_member_path(str(member.get("vs_path"))))
        except Exception:
            return False
        if not positive_outcome(frontmatter):
            return False
    return True


def promotion_alert_exists(cohort_id: str, proposal_dir: Path) -> Path | None:
    for path in sorted(proposal_dir.glob(f"{cohort_id}-*-promotion-alert.md")):
        return path
    return None


def write_promotion_alert(cohort: dict[str, Any], proposal_dir: Path, timestamp: str) -> Path | None:
    if not cohort_has_consistent_positive_outcomes(cohort):
        return None
    cohort_id = str(cohort["cohort_id"])
    existing = promotion_alert_exists(cohort_id, proposal_dir)
    if existing:
        return existing
    proposal_dir.mkdir(parents=True, exist_ok=True)
    path = proposal_dir / f"{cohort_id}-{today_string()}-promotion-alert.md"
    signature = cohort.get("axis_signature") or {}
    members = cohort.get("members", [])
    proposed_name = f"custom-{cohort_id.split('-')[0]}"
    member_lines = "\n".join(f"- `{member.get('vs_path')}`" for member in members if isinstance(member, dict))
    reference_paths: list[str] = []
    for member in members:
        if not isinstance(member, dict):
            continue
        try:
            frontmatter, _body = load_vs_frontmatter(resolve_member_path(str(member.get("vs_path"))))
            for ref_path in collect_primary_reference_paths(frontmatter, resolve_member_path(str(member.get("vs_path")))):
                reference_paths.append(display_path(ref_path))
        except Exception:
            continue
    reference_lines = "\n".join(f"- `{item}`" for item in sorted(set(reference_paths))) or "- None resolved"
    text = (
        "---\n"
        "type: custom_aesthetic_promotion_alert\n"
        f"cohort_id: {cohort_id}\n"
        f"proposed_preset_name: {proposed_name}\n"
        f"state: {cohort.get('state')}\n"
        f"cohort_size: {len(members)}\n"
        f"created_at: {timestamp}\n"
        "---\n\n"
        "# Custom Aesthetic Promotion Alert\n\n"
        "This custom aesthetic neighborhood has reached mature-cohort size with consistent positive outcomes.\n\n"
        "## Axis Signature\n\n"
        f"```json\n{json.dumps(signature, indent=2, sort_keys=True)}\n```\n\n"
        "## Proposed Preset Name\n\n"
        f"`{proposed_name}`\n\n"
        "## Reference Set\n\n"
        f"{reference_lines}\n\n"
        "## Members\n\n"
        f"{member_lines}\n"
    )
    path.write_text(text, encoding="utf-8")
    return path


def ensure_frontmatter_cluster_id(vs_path: Path, frontmatter: dict[str, Any], body: str, cohort_id: str) -> None:
    current = str(frontmatter.get("custom_cohort_cluster_id") or "").strip()
    if current == cohort_id:
        return
    if current and current != cohort_id:
        return
    frontmatter["custom_cohort_cluster_id"] = cohort_id
    write_vs_frontmatter(vs_path, frontmatter, body)


def add_vs_to_membership(
    vs_path: Path,
    membership: dict[str, Any],
    *,
    deterministic_ids: bool = False,
    proposal_dir: Path = PROMOTION_DIR,
) -> dict[str, Any]:
    timestamp = now_iso()
    frontmatter, body, bundle = feature_bundle_for_vs(vs_path)
    resolved_key = member_key(vs_path)
    existing_cohort, _existing_member = find_existing_assignment(membership, vs_path)
    vector_by_member_path: dict[str, Any] = {resolved_key: bundle.vector}
    signature_by_member_path: dict[str, dict[str, Any]] = {resolved_key: bundle.axis_signature}

    if existing_cohort is not None:
        cluster_id = str(existing_cohort["cohort_id"])
        state = str(existing_cohort.get("state") or state_for_size(len(existing_cohort.get("members", []))))
        ensure_frontmatter_cluster_id(vs_path, frontmatter, body, cluster_id)
        return {
            "ran_at": timestamp,
            "mode": "single",
            "vs_path": display_path(vs_path),
            "cluster_id": cluster_id,
            "cluster_state_before": state,
            "cluster_state_after": state,
            "cohort_size_before": len(existing_cohort.get("members", [])),
            "cohort_size_after": len(existing_cohort.get("members", [])),
            "promotion_alert_generated": False,
            "promotion_alert_path": None,
            "min_distance_to_existing_cohort": None,
            "feature_vector_hash": bundle.vector_hash,
            "stable_existing_assignment": True,
        }

    recorded_id = str(frontmatter.get("custom_cohort_cluster_id") or "").strip()
    recorded_cohort = find_cohort_by_id(membership, recorded_id) if recorded_id else None
    nearest, min_distance = nearest_cohort(membership, bundle.vector)

    if recorded_cohort is not None:
        target = recorded_cohort
    elif recorded_id:
        target = {
            "cohort_id": recorded_id,
            "state": "singleton",
            "members": [],
            "centroid": [],
            "centroid_last_updated": timestamp,
            "axis_signature": {},
        }
        membership.setdefault("cohorts", []).append(target)
    elif nearest is not None and min_distance is not None and min_distance < DISTANCE_THRESHOLD:
        target = nearest
    else:
        target = {
            "cohort_id": stable_new_cohort_id(vs_path, deterministic=deterministic_ids),
            "state": "singleton",
            "members": [],
            "centroid": [],
            "centroid_last_updated": timestamp,
            "axis_signature": {},
        }
        membership.setdefault("cohorts", []).append(target)

    before_size = len(target.get("members", []))
    before_state = str(target.get("state") or state_for_size(before_size))
    target.setdefault("members", []).append(member_record(vs_path, bundle.vector_hash, timestamp))

    for member in target.get("members", []):
        if not isinstance(member, dict):
            continue
        member_path = resolve_member_path(str(member.get("vs_path")))
        key = member_key(member_path)
        if key in vector_by_member_path:
            continue
        try:
            member_frontmatter, _member_body, member_bundle = feature_bundle_for_vs(member_path)
            vector_by_member_path[key] = member_bundle.vector
            signature_by_member_path[key] = member_bundle.axis_signature
        except Exception:
            continue

    recompute_cohort_metadata(target, vector_by_member_path, signature_by_member_path, timestamp)
    membership["last_updated"] = timestamp
    after_size = len(target.get("members", []))
    after_state = str(target.get("state"))
    ensure_frontmatter_cluster_id(vs_path, frontmatter, body, str(target["cohort_id"]))

    alert_path: Path | None = None
    if after_state == "mature_cohort":
        alert_path = write_promotion_alert(target, proposal_dir, timestamp)

    return {
        "ran_at": timestamp,
        "mode": "single",
        "vs_path": display_path(vs_path),
        "cluster_id": str(target["cohort_id"]),
        "cluster_state_before": before_state if before_size else None,
        "cluster_state_after": after_state,
        "cohort_size_before": before_size,
        "cohort_size_after": after_size,
        "promotion_alert_generated": alert_path is not None,
        "promotion_alert_path": str(alert_path) if alert_path else None,
        "watchlist_alert": after_state == "watchlist" and before_state == "singleton",
        "min_distance_to_existing_cohort": round(min_distance, 6) if min_distance is not None else None,
        "feature_vector_hash": bundle.vector_hash,
    }


def is_custom_vs(path: Path) -> bool:
    try:
        frontmatter, _body = load_vs_frontmatter(path)
    except Exception:
        return False
    return str(frontmatter.get("visual_quality_target_mode") or "").strip() == "custom"


def discover_custom_vs_paths() -> list[Path]:
    candidates: dict[str, Path] = {}
    for pattern_root in (
        CUSTOM_DIR,
        REPO_ROOT / "vault" / "clients",
        REPO_ROOT / "vault" / "snapshots",
    ):
        if not pattern_root.exists():
            continue
        for path in pattern_root.rglob("*.md"):
            if path.name.endswith("-promotion-alert.md"):
                continue
            if is_custom_vs(path):
                candidates[str(path.resolve())] = path.resolve()
    return [candidates[key] for key in sorted(candidates)]


def bulk_recompute(
    vs_paths: list[Path] | None = None,
    *,
    proposal_dir: Path = PROMOTION_DIR,
) -> tuple[dict[str, Any], dict[str, Any]]:
    timestamp = now_iso()
    membership = {"version": 1, "last_updated": timestamp, "cohorts": []}
    selected_paths = sorted(vs_paths if vs_paths is not None else discover_custom_vs_paths(), key=lambda path: display_path(path))
    results: list[dict[str, Any]] = []
    for path in selected_paths:
        result = add_vs_to_membership(path, membership, deterministic_ids=True, proposal_dir=proposal_dir)
        results.append(result)
    membership["last_updated"] = now_iso()
    summary = {
        "ran_at": timestamp,
        "mode": "bulk",
        "vs_path": None,
        "cluster_id": None,
        "cluster_state_before": None,
        "cluster_state_after": None,
        "cohort_size_before": None,
        "cohort_size_after": None,
        "promotion_alert_generated": any(item.get("promotion_alert_generated") for item in results),
        "promotion_alert_path": next((item.get("promotion_alert_path") for item in results if item.get("promotion_alert_path")), None),
        "min_distance_to_existing_cohort": None,
        "feature_vector_hash": None,
        "custom_vs_count": len(selected_paths),
        "cohort_count": len(membership.get("cohorts", [])),
        "assignments": results,
    }
    return membership, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vs-path", help="Single visual-spec markdown path to assign.")
    parser.add_argument("--membership-out", help="Membership JSON path to read/write. Defaults to the archive membership file.")
    parser.add_argument("--json-out", help="Optional path to write the JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    membership_path = Path(args.membership_out).expanduser() if args.membership_out else DEFAULT_MEMBERSHIP
    try:
        if args.vs_path:
            membership = load_membership(membership_path)
            result = add_vs_to_membership(Path(args.vs_path).expanduser().resolve(), membership)
            save_membership(membership_path, membership)
        else:
            membership, result = bulk_recompute()
            save_membership(membership_path, membership)
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

    write_json(result, args.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

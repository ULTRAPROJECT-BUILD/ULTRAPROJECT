#!/usr/bin/env python3
"""Run the Visual Specification System mechanical gate across named profiles."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
VAULT_ROOT = REPO_ROOT / "vault"
CACHE_ROOT = VAULT_ROOT / "cache" / "visual-spec"
SCHEMA_DIR = REPO_ROOT / "schemas"
PLATFORM_CONFIG = VAULT_ROOT / "config" / "platform.md"
MEDIUM_PLUGIN_DIR = VAULT_ROOT / "archive" / "visual-aesthetics" / "mediums"
PRESET_DIR = VAULT_ROOT / "archive" / "visual-aesthetics" / "presets"
CENTROID_DIR = VAULT_ROOT / "archive" / "visual-aesthetics" / "centroids"
BRAND_SYSTEM_DIR = VAULT_ROOT / "archive" / "brand-systems"
DEFAULT_TAXONOMY = VAULT_ROOT / "archive" / "visual-aesthetics" / "_banned_vague_taxonomy.md"
COLLUSION_BASELINE = VAULT_ROOT / "config" / "brief-contract-collusion-baseline.json"
WAIVER_LOG = VAULT_ROOT / "config" / "visual-spec-waivers.md"
UNSUPPORTED_MEDIUM_PROPOSALS_DIR = VAULT_ROOT / "archive" / "visual-aesthetics" / "proposals"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from profile_dispatch_config import CHECK_DEFINITIONS, get_cache_categories, get_check, get_profile

CHECK_GROUPS: tuple[tuple[int, int], ...] = (
    (1, 14),
    (15, 34),
    (35, 46),
    (47, 61),
    (62, 80),
    (81, 87),
    (89, 97),
)
SECTION_LABELS: tuple[tuple[range, str], ...] = (
    (range(1, 15), "Form"),
    (range(15, 33), "Substance"),
    (range(33, 35), "Provenance"),
    (range(35, 44), "Semantic"),
    (range(44, 47), "CLIP"),
    (range(47, 52), "Medium"),
    (range(52, 58), "Specificity"),
    (range(58, 62), "Mode"),
    (range(62, 81), "State"),
    (range(81, 85), "Brief/Telemetry"),
    (range(85, 89), "Operations"),
    (range(89, 98), "Artifacts"),
)
SPECIFICITY_FIELDS = [
    "domain_entities",
    "workflow_signatures",
    "data_texture_requirements",
    "brand_or_context_invariants",
    "signature_affordances",
    "forbidden_generic_signals",
    "audience_context",
]
VALID_MODES = {"preset", "custom", "brand_system", "none"}
VALID_VERDICTS = {"pass", "fail", "error", "skipped", "not_applicable", "not_run_runtime_budget_exceeded"}
ACTIVE_PRODUCER_STATES = {"active", "repaired_active"}
COHERENCE_CHECK_FIELDS = (
    "set_palette_delta",
    "set_color_temp_variance",
    "set_type_discipline",
    "set_lighting_vocab",
    "set_motion_tempo",
    "set_audio_mood",
    "set_spatial_scale",
    "per_slot_integration",
)
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
HEX_NAME_RE = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
SECTION_RE_TEMPLATE = r"^##\s+{heading}\b(?P<body>.*?)(?=^##\s+|\Z)"
SENTENCE_RE = re.compile(r"[.!?]")
DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
COHERENCE_FLOAT_TOLERANCE = 0.001
COHERENCE_REPORT_HASH_OMIT_KEYS = {"coherence_report_sha256"}
COHERENCE_COMPARABLE_KEYS = ("value", "max_threshold", "passed", "total", "verdict")


def local_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vs-path", default="", help="Visual spec markdown path.")
    parser.add_argument("--references-dir", required=True, help="References directory path.")
    parser.add_argument("--ticket-path", default="", help="Optional ticket markdown path.")
    parser.add_argument("--signoff-paths", nargs="*", default=[], help="Optional adjudication/adversarial sign-off report paths.")
    parser.add_argument("--medium", required=True, help="Medium identifier.")
    parser.add_argument("--profile", required=True, choices=sorted({"brief", "runtime", "telemetry", "vs_fast", "vs_full"}))
    parser.add_argument("--candidates", help="Optional specificity candidates JSON path.")
    parser.add_argument("--brief", help="Optional creative brief markdown path.")
    parser.add_argument("--strict", action="store_true", help="Escalate warn-on-skip profile policy to fail-on-skip.")
    parser.add_argument("--json-out", help="Optional JSON report output path.")
    parser.add_argument("--markdown-out", help="Optional markdown report output path.")
    return parser.parse_args()


def clean_path(raw: str | None) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    return Path(text).expanduser().resolve()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def load_frontmatter(path: Path) -> dict[str, Any]:
    frontmatter_text, _body = split_frontmatter(path.read_text(encoding="utf-8"))
    if not frontmatter_text:
        return {}
    data = yaml.safe_load(frontmatter_text)
    return data if isinstance(data, dict) else {}


def load_body(path: Path) -> str:
    _frontmatter, body = split_frontmatter(path.read_text(encoding="utf-8"))
    return body


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def parse_datetime(value: Any) -> datetime | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone()


def is_uuid(value: Any) -> bool:
    return bool(UUID_RE.match(str(value or "").strip()))


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_token_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[_/#.-]+", " ", text)
    text = re.sub(r"[^a-z0-9%$]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def unique_paths(paths: Iterable[Path | None]) -> list[Path]:
    seen: set[str] = set()
    ordered: list[Path] = []
    for path in paths:
        if path is None:
            continue
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path.resolve())
    return ordered


def rel_or_abs(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def file_signature(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": None, "exists": False}
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return {"path": str(resolved), "exists": False}
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def import_module_safe(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except SystemExit as exc:
        raise RuntimeError(str(exc)) from exc


def read_platform_scalar(key: str, default: Any) -> Any:
    if not PLATFORM_CONFIG.exists():
        return default
    text = PLATFORM_CONFIG.read_text(encoding="utf-8")
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", text, flags=re.M)
    if not match:
        return default
    raw = match.group(1).strip()
    if isinstance(default, int):
        try:
            return int(raw)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(raw)
        except ValueError:
            return default
    if isinstance(default, bool):
        return raw.lower() in {"true", "yes", "1"}
    return raw.strip('"').strip("'")


def resolve_report_timestamp(path: Path, frontmatter: dict[str, Any]) -> datetime | None:
    for key in ("captured", "updated", "checked_at", "created", "waiver_acknowledged_at"):
        parsed = parse_datetime(frontmatter.get(key))
        if parsed is not None:
            return parsed
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).astimezone()
    except OSError:
        pass
    match = DATE_IN_NAME_RE.search(path.name)
    if match:
        try:
            return datetime.fromisoformat(match.group(1)).astimezone()
        except ValueError:
            pass
    return None


def resolve_url_plausible(value: Any) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def flatten_tokens(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_tokens(child, path))
        return flattened
    return {prefix: value}


def count_named_family_entries(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    total = 0
    for child in value.values():
        if isinstance(child, dict):
            total += max(1, count_named_family_entries(child))
        elif isinstance(child, list):
            total += len(child)
        else:
            total += 1
    return total


def markdown_section(body: str, heading: str) -> str:
    match = re.search(SECTION_RE_TEMPLATE.format(heading=re.escape(heading)), body, flags=re.M | re.S | re.I)
    return match.group("body").strip() if match else ""


def summarize_details(details: Any) -> str:
    if isinstance(details, str):
        return details
    if isinstance(details, (int, float, bool)) or details is None:
        return str(details)
    if isinstance(details, list):
        preview = ", ".join(summarize_details(item) for item in details[:3])
        return preview if len(details) <= 3 else f"{preview}, …"
    if isinstance(details, dict):
        parts: list[str] = []
        for key, value in list(details.items())[:4]:
            if isinstance(value, (list, dict)):
                continue
            parts.append(f"{key}={value}")
        return ", ".join(parts) if parts else json.dumps(details, sort_keys=True)[:160]
    return str(details)


def normalize_helper_verdict(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"pass", "fail", "error", "skipped"}:
        return text
    if text.startswith("not_applicable"):
        return "not_applicable"
    if text in {"n/a", "na"}:
        return "not_applicable"
    if text in {"true", "yes"}:
        return "pass"
    if text in {"false", "no"}:
        return "fail"
    return "skipped"


def run_json_helper(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    stdout = completed.stdout.strip() or "{}"
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {
            "verdict": "error",
            "error": f"helper did not emit valid JSON: {exc}",
            "_returncode": completed.returncode,
            "_stdout": completed.stdout[-1000:],
            "_stderr": completed.stderr[-1000:],
        }
    if not isinstance(payload, dict):
        payload = {"verdict": "error", "error": "helper JSON output was not an object"}
    payload["_returncode"] = completed.returncode
    if completed.stderr.strip():
        payload["_stderr"] = completed.stderr.strip()[-1000:]
    return payload


def effective_skip_policy(profile: dict[str, Any], *, strict: bool) -> str:
    policy = str(profile.get("skip_policy") or "pass").strip().lower()
    if policy not in {"fail", "warn", "pass"}:
        policy = "pass"
    if strict and policy == "warn":
        return "fail"
    return policy


def make_check_result(verdict: str, details: Any, *, error_message: str | None = None) -> dict[str, Any]:
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"Unsupported verdict: {verdict}")
    payload = {"verdict": verdict, "details": details}
    if error_message:
        payload["error_message"] = error_message
    return payload


def resolve_artifact_path(raw: Any, *, vs_path: Path | None, references_dir: Path | None) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    search: list[Path] = []
    if references_dir is not None:
        search.extend([references_dir / candidate, references_dir / candidate.name])
    if vs_path is not None:
        search.append(vs_path.parent / candidate)
    search.append(REPO_ROOT / candidate)
    for path in search:
        if path.exists():
            return path.resolve()
    return search[0].resolve() if search else candidate.resolve()


def rgb_to_xyz(red: int, green: int, blue: int) -> tuple[float, float, float]:
    def srgb_to_linear(channel: int) -> float:
        value = channel / 255.0
        if value <= 0.04045:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    r = srgb_to_linear(red)
    g = srgb_to_linear(green)
    b = srgb_to_linear(blue)
    x = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) * 100
    y = (r * 0.2126729 + g * 0.7151522 + b * 0.0721750) * 100
    z = (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) * 100
    return x, y, z


def xyz_to_lab(x: float, y: float, z: float) -> tuple[float, float, float]:
    x /= 95.047
    y /= 100.0
    z /= 108.883

    def f(value: float) -> float:
        if value > 0.008856:
            return value ** (1 / 3)
        return 7.787 * value + 16 / 116

    fx = f(x)
    fy = f(y)
    fz = f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    raw = color.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) >= 6:
        raw = raw[:6]
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def delta_e76(first: str, second: str) -> float:
    lab1 = xyz_to_lab(*rgb_to_xyz(*hex_to_rgb(first)))
    lab2 = xyz_to_lab(*rgb_to_xyz(*hex_to_rgb(second)))
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(lab1, lab2)))


def check_id_section(check_id: int) -> str:
    for id_range, label in SECTION_LABELS:
        if check_id in id_range:
            return label
    return "Other"


class CacheStore:
    def __init__(self, root: Path, enabled_categories: Iterable[str]) -> None:
        self.root = root
        self.enabled_categories = set(enabled_categories)

    def enabled(self, category: str) -> bool:
        return category in self.enabled_categories

    def _path(self, category: str, key: str) -> Path:
        return self.root / category / f"{key}.json"

    def load_json(self, category: str, key: str, *, sources: list[Path]) -> dict[str, Any] | None:
        if not self.enabled(category):
            return None
        path = self._path(category, key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        meta = payload.get("_meta", {})
        if meta.get("sources") != [file_signature(item) for item in unique_paths(sources)]:
            return None
        data = payload.get("payload")
        return data if isinstance(data, dict) else None

    def save_json(self, category: str, key: str, *, sources: list[Path], payload: dict[str, Any]) -> None:
        if not self.enabled(category):
            return
        path = self._path(category, key)
        write_text(
            path,
            json.dumps(
                {
                    "_meta": {
                        "cached_at": local_now(),
                        "sources": [file_signature(item) for item in unique_paths(sources)],
                    },
                    "payload": payload,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )


@dataclass
class GateContext:
    args: argparse.Namespace
    profile_name: str
    profile: dict[str, Any]
    cache: CacheStore
    started_at: datetime = field(default_factory=lambda: datetime.now().astimezone())
    started_monotonic: float = field(default_factory=time.perf_counter)
    input_warnings: list[str] = field(default_factory=list)
    _memo: dict[str, Any] = field(default_factory=dict)
    _memo_lock: threading.RLock = field(default_factory=threading.RLock)

    @property
    def repo_root(self) -> Path:
        return REPO_ROOT

    @property
    def frontmatter(self) -> dict[str, Any]:
        return self.vs_frontmatter()

    @property
    def medium(self) -> str:
        return str(self.args.medium).strip()

    @property
    def vs_path(self) -> Path | None:
        return clean_path(self.args.vs_path)

    @property
    def references_dir(self) -> Path | None:
        return clean_path(self.args.references_dir)

    @property
    def ticket_path(self) -> Path | None:
        return clean_path(self.args.ticket_path)

    @property
    def brief_path(self) -> Path | None:
        return clean_path(self.args.brief)

    @property
    def candidates_path_arg(self) -> Path | None:
        return clean_path(self.args.candidates)

    @property
    def signoff_paths(self) -> list[Path]:
        return [Path(raw).expanduser().resolve() for raw in self.args.signoff_paths]

    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.started_monotonic

    def memo(self, key: str, factory: Callable[[], Any]) -> Any:
        with self._memo_lock:
            if key in self._memo:
                return self._memo[key]
            value = factory()
            self._memo[key] = value
            return value

    def validate_inputs(self) -> list[str]:
        warnings: list[str] = []
        refs_dir = self.references_dir
        if refs_dir is None:
            warnings.append("--references-dir was empty.")
        elif not refs_dir.exists():
            warnings.append(f"references dir does not exist: {refs_dir}")
        if self.vs_path is not None and not self.vs_path.exists():
            warnings.append(f"vs path does not exist: {self.vs_path}")
        if self.ticket_path is not None and not self.ticket_path.exists():
            warnings.append(f"ticket path does not exist: {self.ticket_path}")
        if self.brief_path is not None and not self.brief_path.exists():
            warnings.append(f"brief path does not exist: {self.brief_path}")
        if self.candidates_path_arg is not None and not self.candidates_path_arg.exists():
            warnings.append(f"candidates path does not exist: {self.candidates_path_arg}")
        for path in self.signoff_paths:
            if not path.exists():
                warnings.append(f"signoff path does not exist: {path}")
        self.input_warnings = warnings
        return warnings

    def vs_frontmatter(self) -> dict[str, Any]:
        def factory() -> dict[str, Any]:
            path = self.vs_path
            if path is None or not path.exists():
                return {}
            return load_frontmatter(path)

        return self.memo("vs_frontmatter", factory)

    def vs_body(self) -> str:
        def factory() -> str:
            path = self.vs_path
            if path is None or not path.exists():
                return ""
            return load_body(path)

        return self.memo("vs_body", factory)

    def manifest_path(self) -> Path | None:
        refs_dir = self.references_dir
        if refs_dir is None:
            return None
        return refs_dir / "manifest.json"

    def manifest(self) -> dict[str, Any]:
        def factory() -> dict[str, Any]:
            path = self.manifest_path()
            if path is None or not path.exists():
                return {}
            try:
                return load_json(path)
            except Exception:
                return {}

        return self.memo("manifest", factory)

    def brief_frontmatter(self) -> dict[str, Any]:
        def factory() -> dict[str, Any]:
            path = self.brief_path
            if path is None or not path.exists():
                return {}
            return load_frontmatter(path)

        return self.memo("brief_frontmatter", factory)

    def ticket_frontmatter(self) -> dict[str, Any]:
        def factory() -> dict[str, Any]:
            path = self.ticket_path
            if path is None or not path.exists():
                return {}
            return load_frontmatter(path)

        return self.memo("ticket_frontmatter", factory)

    def operator_id(self) -> str | None:
        for frontmatter in (self.vs_frontmatter(), self.ticket_frontmatter()):
            for key in ("operator_id", "operator", "operator_session_id", "approved_by"):
                value = str(frontmatter.get(key) or "").strip()
                if value:
                    return value
        return None

    def project_slug(self) -> str:
        frontmatter = self.vs_frontmatter()
        if str(frontmatter.get("project") or "").strip():
            return str(frontmatter["project"]).strip()
        brief_frontmatter = self.brief_frontmatter()
        if str(brief_frontmatter.get("project") or "").strip():
            return str(brief_frontmatter["project"]).strip()
        if self.vs_path is not None:
            return self.vs_path.stem
        if self.brief_path is not None:
            return self.brief_path.stem
        return "unknown-project"

    def resolve_path(self, raw: Any) -> Path | None:
        return resolve_artifact_path(raw, vs_path=self.vs_path, references_dir=self.references_dir)

    def medium_plugin_path(self) -> Path:
        frontmatter = self.vs_frontmatter()
        declared = frontmatter.get("medium_plugin_path")
        resolved = self.resolve_path(declared)
        if resolved is not None:
            return resolved
        return (MEDIUM_PLUGIN_DIR / f"{self.medium}.md").resolve()

    def medium_plugin_frontmatter(self) -> dict[str, Any]:
        def factory() -> dict[str, Any]:
            path = self.medium_plugin_path()
            if not path.exists():
                return {}
            return load_frontmatter(path)

        return self.memo("medium_plugin_frontmatter", factory)

    def reference_records(self) -> list[dict[str, Any]]:
        def factory() -> list[dict[str, Any]]:
            records: list[dict[str, Any]] = []
            frontmatter = self.vs_frontmatter()
            for item in frontmatter.get("references", []) if isinstance(frontmatter.get("references"), list) else []:
                if not isinstance(item, dict):
                    continue
                path = self.resolve_path(item.get("file"))
                if path is None:
                    continue
                records.append({**item, "_path": path, "_source": "vs_frontmatter"})
            if not records:
                manifest = self.manifest()
                for item in manifest.get("assets", []) if isinstance(manifest.get("assets"), list) else []:
                    if not isinstance(item, dict):
                        continue
                    role = str(item.get("role") or "").strip().lower()
                    if role not in {"reference", "anti_pattern"}:
                        continue
                    path = self.resolve_path(item.get("path"))
                    if path is None:
                        continue
                    records.append({**item, "_path": path, "_source": "manifest"})
            return records

        return self.memo("reference_records", factory)

    def mockup_records(self) -> list[dict[str, Any]]:
        def factory() -> list[dict[str, Any]]:
            records: list[dict[str, Any]] = []
            frontmatter = self.vs_frontmatter()
            for item in frontmatter.get("mockups", []) if isinstance(frontmatter.get("mockups"), list) else []:
                if not isinstance(item, dict):
                    continue
                final_png = self.resolve_path(item.get("final_png"))
                final_html = self.resolve_path(item.get("final_html"))
                revisions: list[dict[str, Any]] = []
                for revision in item.get("revisions", []) if isinstance(item.get("revisions"), list) else []:
                    if not isinstance(revision, dict):
                        continue
                    revisions.append(
                        {
                            **revision,
                            "_png_path": self.resolve_path(revision.get("png")),
                            "_html_path": self.resolve_path(revision.get("html")),
                        }
                    )
                records.append({**item, "_final_png_path": final_png, "_final_html_path": final_html, "_revisions": revisions})
            if not records:
                manifest = self.manifest()
                by_screen: dict[str, dict[str, Any]] = {}
                for item in manifest.get("assets", []) if isinstance(manifest.get("assets"), list) else []:
                    if not isinstance(item, dict) or str(item.get("role") or "").lower() != "mockup":
                        continue
                    screen = str(item.get("screen") or Path(str(item.get("path") or "")).stem)
                    path = self.resolve_path(item.get("path"))
                    if path is None:
                        continue
                    current = by_screen.setdefault(screen, {"screen": screen, "role": "other", "_revisions": []})
                    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                        current["_final_png_path"] = path
                    elif path.suffix.lower() in {".html", ".htm"}:
                        current["_final_html_path"] = path
                records.extend(by_screen.values())
            return records

        return self.memo("mockup_records", factory)

    def reference_pngs(self, role: str | None = None) -> list[Path]:
        paths = []
        for record in self.reference_records():
            path = record.get("_path")
            if not isinstance(path, Path):
                continue
            if path.suffix.lower() != ".png":
                continue
            record_role = str(record.get("role") or "").strip().lower()
            if role is None and record_role == "anti_pattern":
                continue
            if role and record_role != role:
                continue
            paths.append(path)
        if not paths and self.references_dir is not None:
            folder_names = ["references"] if role != "anti_pattern" else ["anti-patterns", "anti_patterns"]
            for folder_name in folder_names:
                folder = self.references_dir / folder_name
                if folder.exists():
                    paths.extend(path for path in folder.rglob("*.png") if path.is_file())
        return unique_paths(paths)

    def mockup_pngs(self) -> list[Path]:
        paths = [record.get("_final_png_path") for record in self.mockup_records() if isinstance(record.get("_final_png_path"), Path)]
        if not paths and self.references_dir is not None:
            mockups_dir = self.references_dir / "mockups"
            if mockups_dir.exists():
                paths.extend(path for path in mockups_dir.rglob("*.png") if path.is_file())
        return unique_paths(paths)

    def mockup_htmls(self) -> list[Path]:
        return unique_paths(record.get("_final_html_path") for record in self.mockup_records() if isinstance(record.get("_final_html_path"), Path))

    def all_png_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for record in self.reference_records():
            path = record.get("_path")
            if isinstance(path, Path) and path.suffix.lower() == ".png":
                records.append({"path": path, "label": f"reference:{path.name}", "timestamp": parse_datetime(record.get("captured_at"))})
        for record in self.mockup_records():
            final_png = record.get("_final_png_path")
            if isinstance(final_png, Path):
                records.append({"path": final_png, "label": f"mockup:{record.get('screen') or final_png.name}", "timestamp": parse_datetime(record.get("locked_at"))})
            for revision in record.get("_revisions", []):
                path = revision.get("_png_path")
                if isinstance(path, Path):
                    records.append(
                        {
                            "path": path,
                            "label": f"revision:{record.get('screen') or path.name}:rev{revision.get('rev')}",
                            "timestamp": parse_datetime(revision.get("captured_at")),
                        }
                    )
        return records

    def report_paths(self) -> list[Path]:
        def factory() -> list[Path]:
            paths = list(self.signoff_paths)
            frontmatter = self.vs_frontmatter()
            for item in frontmatter.get("adjudications", []) if isinstance(frontmatter.get("adjudications"), list) else []:
                if isinstance(item, dict):
                    resolved = self.resolve_path(item.get("report") or item.get("report_path"))
                    if resolved is not None:
                        paths.append(resolved)
            adversarial = frontmatter.get("adversarial_pass")
            if isinstance(adversarial, dict):
                resolved = self.resolve_path(adversarial.get("report") or adversarial.get("report_path"))
                if resolved is not None:
                    paths.append(resolved)
            return unique_paths(paths)

        return self.memo("report_paths", factory)

    def report_records(self) -> list[dict[str, Any]]:
        def factory() -> list[dict[str, Any]]:
            records: list[dict[str, Any]] = []
            for path in self.report_paths():
                if not path.exists():
                    records.append({"path": path, "frontmatter": {}, "body": "", "missing": True})
                    continue
                text = path.read_text(encoding="utf-8")
                frontmatter_text, body = split_frontmatter(text)
                data = yaml.safe_load(frontmatter_text) if frontmatter_text else {}
                frontmatter = data if isinstance(data, dict) else {}
                records.append({"path": path, "frontmatter": frontmatter, "body": body, "missing": False})
            return records

        return self.memo("report_records", factory)

    def brief_score(self) -> dict[str, Any] | None:
        def factory() -> dict[str, Any] | None:
            path = self.brief_path
            if path is None or not path.exists():
                return None
            module = import_module_safe("score_brief_specificity")
            return module.score_text(path.read_text(encoding="utf-8"), str(path))

        return self.memo("brief_score", factory)

    def brief_adequacy(self) -> dict[str, Any] | None:
        def factory() -> dict[str, Any] | None:
            path = self.brief_path
            if path is None or not path.exists():
                return None
            module = import_module_safe("check_brief_specificity_adequacy")
            return module.evaluate_brief(path)

        return self.memo("brief_adequacy", factory)

    def ensured_candidates_path(self) -> Path | None:
        def factory() -> Path | None:
            explicit = self.candidates_path_arg
            if explicit is not None and explicit.exists():
                return explicit
            brief_path = self.brief_path
            if brief_path is None or not brief_path.exists():
                return None
            module = import_module_safe("extract_specificity_candidates")
            brief_text = brief_path.read_text(encoding="utf-8")
            taxonomy_text = module.DEFAULT_TAXONOMY.read_text(encoding="utf-8")
            raw = module.stub_extract(brief_text, taxonomy_text)
            payload = module.normalize_payload(
                raw,
                project=self.project_slug(),
                client=None,
                brief_path=brief_path,
                brief_text=brief_text,
                extractor="stub",
            )
            module.validate_schema(payload)
            key = stable_hash({"brief": file_signature(brief_path), "project": self.project_slug()})
            target = CACHE_ROOT / "llm" / f"{key}-specificity-candidates.json"
            write_text(target, json.dumps(payload, indent=2, sort_keys=True) + "\n")
            return target

        return self.memo("ensured_candidates_path", factory)

    def specificity_score(self) -> dict[str, Any] | None:
        def factory() -> dict[str, Any] | None:
            vs_path = self.vs_path
            candidates_path = self.ensured_candidates_path()
            if vs_path is None or not vs_path.exists() or candidates_path is None or not candidates_path.exists():
                return None
            module = import_module_safe("score_specificity")
            key = stable_hash({"vs": file_signature(vs_path), "candidates": file_signature(candidates_path)})
            cached = self.cache.load_json("schema", key, sources=[vs_path, candidates_path, DEFAULT_TAXONOMY])
            if cached is not None:
                return cached
            payload = module.score_contract(vs_path, candidates_path, DEFAULT_TAXONOMY)
            self.cache.save_json("schema", key, sources=[vs_path, candidates_path, DEFAULT_TAXONOMY], payload=payload)
            return payload

        return self.memo("specificity_score", factory)

    def visual_specificity(self) -> dict[str, Any] | None:
        def factory() -> dict[str, Any] | None:
            vs_path = self.vs_path
            refs_dir = self.references_dir
            if vs_path is None or refs_dir is None or not vs_path.exists() or not refs_dir.exists():
                return None
            module = import_module_safe("check_visual_specificity")
            return module.run_checks(vs_path, refs_dir, self.medium)

        return self.memo("visual_specificity", factory)

    def semantic_layout(self) -> dict[str, Any] | None:
        def factory() -> dict[str, Any] | None:
            vs_path = self.vs_path
            refs_dir = self.references_dir
            if vs_path is None or refs_dir is None or not vs_path.exists() or not refs_dir.exists():
                return None
            module = import_module_safe("check_semantic_layout")
            _code, payload = module.run(SimpleNamespace(vs_path=str(vs_path), references_dir=str(refs_dir), medium=self.medium))
            return payload

        return self.memo("semantic_layout", factory)

    def clip_embedding(self) -> dict[str, Any] | None:
        def factory() -> dict[str, Any] | None:
            vs_path = self.vs_path
            refs_dir = self.references_dir
            if vs_path is None or refs_dir is None or not vs_path.exists() or not refs_dir.exists():
                return None
            sources = [vs_path, refs_dir]
            manifest_path = self.manifest_path()
            if manifest_path is not None:
                sources.append(manifest_path)
            sources.extend(self.reference_pngs())
            sources.extend(self.mockup_pngs())
            key = stable_hash({"vs": file_signature(vs_path), "refs": [file_signature(item) for item in unique_paths(sources)]})
            cached = self.cache.load_json("clip", key, sources=unique_paths(sources))
            if cached is not None:
                return cached
            module = import_module_safe("check_clip_embedding")
            _code, payload = module.run(
                SimpleNamespace(vs_path=str(vs_path), references_dir=str(refs_dir), json_out=None, read_only=True)
            )
            self.cache.save_json("clip", key, sources=unique_paths(sources), payload=payload)
            return payload

        return self.memo("clip_embedding", factory)

    def concurrency_report(self) -> dict[str, Any] | None:
        def factory() -> dict[str, Any] | None:
            module = import_module_safe("check_vs_concurrency")
            payload, _has_concerns = module.run(SimpleNamespace(vault_root=None, json_out=None))
            return payload

        return self.memo("concurrency_report", factory)

    def resolver_generation_report(self) -> dict[str, Any] | None:
        def factory() -> dict[str, Any] | None:
            ticket_path = self.ticket_path
            if ticket_path is None or not ticket_path.exists():
                return None
            module = import_module_safe("check_resolver_generation")
            return module.build_payload(SimpleNamespace(ticket_path=str(ticket_path), json_out=None, vault_root=None))

        return self.memo("resolver_generation_report", factory)

    def clock_skew_report(self) -> dict[str, Any] | None:
        def factory() -> dict[str, Any] | None:
            command = [sys.executable, str(SCRIPT_DIR / "check_clock_skew.py")]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            stdout = completed.stdout.strip() or "{}"
            payload = json.loads(stdout)
            if isinstance(payload, dict):
                payload["_returncode"] = completed.returncode
                if completed.stderr.strip():
                    payload["_stderr"] = completed.stderr.strip()
                return payload
            return {"_returncode": completed.returncode, "error": "invalid-json-output"}

        return self.memo("clock_skew_report", factory)

    def project_visual_specs(self) -> list[dict[str, Any]]:
        def factory() -> list[dict[str, Any]]:
            project = self.project_slug()
            results: list[dict[str, Any]] = []
            roots: list[Path] = [VAULT_ROOT / "snapshots" / project]
            if self.vs_path is not None:
                roots.append(self.vs_path.parent)
            clients_root = VAULT_ROOT / "clients"
            if clients_root.exists():
                roots.extend(path / "snapshots" / project for path in clients_root.iterdir() if path.is_dir())
            seen: set[str] = set()
            explicit_paths: list[Path] = [self.vs_path] if self.vs_path is not None and self.vs_path.exists() else []
            for path in explicit_paths:
                resolved = path.resolve()
                seen.add(str(resolved))
                try:
                    frontmatter = load_frontmatter(resolved)
                except Exception:
                    continue
                if str(frontmatter.get("project") or "").strip() == project:
                    results.append({"path": resolved, "frontmatter": frontmatter})
            for root in roots:
                if not root.exists():
                    continue
                for path in root.rglob("*-visual-spec-*.md"):
                    resolved = path.resolve()
                    if str(resolved) in seen:
                        continue
                    seen.add(str(resolved))
                    try:
                        frontmatter = load_frontmatter(resolved)
                    except Exception:
                        continue
                    if str(frontmatter.get("project") or "").strip() != project:
                        continue
                    results.append({"path": resolved, "frontmatter": frontmatter})
            return results

        return self.memo("project_visual_specs", factory)

    def redline_diff_paths(self) -> list[Path]:
        def factory() -> list[Path]:
            paths: list[Path] = []
            refs_dir = self.references_dir
            if refs_dir and refs_dir.exists():
                paths.extend(refs_dir.rglob("*redline*diff*.json"))
            for record in self.report_records():
                report_path = record["path"]
                if report_path.exists():
                    paths.extend(report_path.parent.glob("*redline*diff*.json"))
            return unique_paths(paths)

        return self.memo("redline_diff_paths", factory)


def artifact_manifest_items(ctx: GateContext) -> list[dict[str, Any]]:
    value = ctx.vs_frontmatter().get("artifact_manifest")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def coherence_signoff(ctx: GateContext) -> dict[str, Any]:
    value = ctx.vs_frontmatter().get("coherence_signoff")
    return value if isinstance(value, dict) else {}


def context_vault_root(ctx: GateContext) -> Path:
    candidates: list[Path] = []
    env_root = os.environ.get("ONESHOT_VAULT_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    refs_dir = ctx.references_dir
    if refs_dir is not None:
        candidates.append(refs_dir.parent / "vault")
    if ctx.vs_path is not None:
        candidates.append(ctx.vs_path.parent / "vault")
    candidates.append(VAULT_ROOT)
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / "config").exists() or (resolved / "archive").exists():
            return resolved
    return VAULT_ROOT


def load_registry_producers_from_path(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            producers_value = data.get("producers") if isinstance(data, dict) else []
            return [item for item in producers_value if isinstance(item, dict)] if isinstance(producers_value, list) else []
        text = path.read_text(encoding="utf-8")
        _frontmatter, body = split_frontmatter(text)
        for match in re.finditer(r"```ya?ml\s*\n(.*?)\n```", body, flags=re.S | re.I):
            data = yaml.safe_load(match.group(1)) or {}
            if isinstance(data, dict) and isinstance(data.get("producers"), list):
                return [item for item in data["producers"] if isinstance(item, dict)]
        data = yaml.safe_load(body) or {}
        if isinstance(data, dict) and isinstance(data.get("producers"), list):
            return [item for item in data["producers"] if isinstance(item, dict)]
    except Exception:
        return []
    return []


def producer_records(ctx: GateContext) -> list[dict[str, Any]]:
    def factory() -> list[dict[str, Any]]:
        paths: list[Path] = []
        if ctx.references_dir is not None:
            paths.extend(
                [
                    ctx.references_dir / "artifact-producers.md",
                    ctx.references_dir / "artifact-producers.json",
                ]
            )
        vault_root = context_vault_root(ctx)
        paths.append(vault_root / "config" / "artifact-producers.md")
        if vault_root != VAULT_ROOT:
            paths.append(VAULT_ROOT / "config" / "artifact-producers.md")
        by_id: dict[str, dict[str, Any]] = {}
        for path in paths:
            for producer in load_registry_producers_from_path(path):
                producer_id = str(producer.get("producer_id") or "").strip()
                if producer_id and producer_id not in by_id:
                    by_id[producer_id] = producer
        return list(by_id.values())

    return ctx.memo("artifact_producer_records", factory)


def find_producer_record(ctx: GateContext, producer_id: str) -> dict[str, Any] | None:
    for producer in producer_records(ctx):
        if str(producer.get("producer_id") or "").strip() == producer_id:
            return producer
    return None


def producer_supports_artifact(producer: dict[str, Any], artifact_type: str, medium: str | None) -> bool:
    if artifact_type not in [str(item) for item in producer.get("artifact_types", []) if str(item)]:
        return False
    if medium:
        applicable = [str(item) for item in producer.get("applicable_mediums", []) if str(item)]
        if medium not in applicable:
            return False
    return True


def resolve_manifest_producer(ctx: GateContext, item: dict[str, Any]) -> dict[str, Any] | None:
    artifact_type = str(item.get("type") or "").strip()
    slot_contract = item.get("slot_contract") if isinstance(item.get("slot_contract"), dict) else {}
    medium = str(slot_contract.get("medium") or ctx.medium or "").strip() or None
    for producer in producer_records(ctx):
        if str(producer.get("state") or "") not in ACTIVE_PRODUCER_STATES:
            continue
        if producer_supports_artifact(producer, artifact_type, medium):
            return producer
    return None


def latest_attempt_producer_id(item: dict[str, Any]) -> str:
    attempts = item.get("production_attempts") if isinstance(item.get("production_attempts"), list) else []
    for attempt in reversed(attempts):
        if not isinstance(attempt, dict):
            continue
        producer_id = str(attempt.get("producer_id") or "").strip()
        if producer_id:
            return producer_id
    return ""


def producer_id_for_manifest_item(ctx: GateContext, item: dict[str, Any]) -> tuple[str, str]:
    for key, source in (
        ("producer_substitution_for_slot", "producer_substitution_for_slot"),
        ("producer_override", "producer_override"),
    ):
        value = str(item.get(key) or "").strip()
        if value:
            return value, source
    attempt_producer = latest_attempt_producer_id(item)
    if attempt_producer:
        return attempt_producer, "production_attempts"
    resolved = resolve_manifest_producer(ctx, item)
    if resolved is not None:
        return str(resolved.get("producer_id") or ""), "resolved_by_type"
    return "", "unresolved"


def resolve_manifest_artifact_path(ctx: GateContext, item: dict[str, Any]) -> Path | None:
    return ctx.resolve_path(item.get("locked_artifact_path"))


def locked_artifact_pin_valid(ctx: GateContext, item: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    path = resolve_manifest_artifact_path(ctx, item)
    details: dict[str, Any] = {"path": str(path) if path else None, "exists": bool(path and path.exists())}
    if path is None or not path.exists():
        return False, details
    expected_hash = str(item.get("locked_artifact_hash") or "").strip().lower()
    if expected_hash:
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        details["expected_hash"] = expected_hash
        details["actual_hash"] = actual_hash
        if actual_hash != expected_hash:
            return False, details
    return True, details


def coherence_check_passed(field: str, value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    verdict = str(value.get("verdict") or "").strip().lower()
    if field == "per_slot_integration":
        passed = value.get("passed")
        total = value.get("total")
        if verdict == "pass":
            return isinstance(passed, int) and isinstance(total, int) and total > 0 and passed == total
        return False
    if verdict != "pass":
        return False
    if "value" in value or "max_threshold" in value:
        return numeric_threshold_consistent(value)
    return True


def numeric_threshold_consistent(value: dict[str, Any]) -> bool:
    observed = value.get("value")
    threshold = value.get("max_threshold")
    verdict = str(value.get("verdict") or "").strip().lower()
    if not isinstance(observed, (int, float)) or not isinstance(threshold, (int, float)):
        return False
    if verdict == "pass":
        return float(observed) <= float(threshold) + COHERENCE_FLOAT_TOLERANCE
    if verdict == "fail":
        return True
    return False


def coherence_internal_inconsistencies(field: str, value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["missing_or_not_object"]
    verdict = str(value.get("verdict") or "").strip().lower()
    if verdict not in {"pass", "fail"}:
        return ["invalid_or_missing_verdict"]
    if field == "per_slot_integration":
        passed = value.get("passed")
        total = value.get("total")
        if not isinstance(passed, int) or not isinstance(total, int):
            return ["missing_passed_or_total"]
        if total <= 0:
            return ["non_positive_total"]
        should_pass = passed == total
        if verdict == "pass" and not should_pass:
            return ["verdict_pass_but_not_all_slots_passed"]
        if verdict == "fail" and should_pass:
            return ["verdict_fail_but_all_slots_passed"]
        return []
    if "value" in value or "max_threshold" in value:
        if not numeric_threshold_consistent(value):
            return ["verdict_inconsistent_with_value_and_max_threshold"]
    return []


def canonical_coherence_report_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: canonical_coherence_report_payload(item)
            for key, item in value.items()
            if key not in COHERENCE_REPORT_HASH_OMIT_KEYS
        }
    if isinstance(value, list):
        return [canonical_coherence_report_payload(item) for item in value]
    return value


def coherence_report_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        canonical_coherence_report_payload(payload),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def comparable_values_match(expected: Any, signed: Any) -> bool:
    if isinstance(expected, (int, float)) and isinstance(signed, (int, float)):
        return abs(float(expected) - float(signed)) <= COHERENCE_FLOAT_TOLERANCE
    return expected == signed


def coherence_report_binding_failures(ctx: GateContext, signoff: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    artifact_set_path = ctx.resolve_path(signoff.get("artifact_set_json"))
    report_path = ctx.resolve_path(signoff.get("coherence_report_path"))
    expected_hash = str(signoff.get("coherence_report_sha256") or "").strip().lower()
    if artifact_set_path is None:
        failures.append({"reason": "missing_artifact_set_json"})
    elif not artifact_set_path.exists():
        failures.append({"reason": "artifact_set_json_missing", "path": rel_or_abs(artifact_set_path)})
    if report_path is None:
        failures.append({"reason": "missing_coherence_report_path"})
    elif not report_path.exists():
        failures.append({"reason": "coherence_report_missing", "path": rel_or_abs(report_path)})
    if not SHA256_RE.match(expected_hash):
        failures.append({"reason": "missing_or_invalid_coherence_report_sha256"})

    report_payload: dict[str, Any] | None = None
    if report_path is not None and report_path.exists() and SHA256_RE.match(expected_hash):
        try:
            loaded = load_json(report_path)
            if isinstance(loaded, dict):
                report_payload = loaded
            else:
                failures.append({"reason": "coherence_report_not_object", "path": rel_or_abs(report_path)})
        except Exception as exc:
            failures.append({"reason": "coherence_report_unreadable", "path": rel_or_abs(report_path), "error": str(exc)})
        if report_payload is not None:
            actual_hash = coherence_report_sha256(report_payload)
            if actual_hash != expected_hash:
                failures.append(
                    {
                        "reason": "coherence_report_sha256_mismatch",
                        "path": rel_or_abs(report_path),
                        "expected_sha256": expected_hash,
                        "actual_sha256": actual_hash,
                    }
                )

    internal_failures = []
    for field in COHERENCE_CHECK_FIELDS:
        reasons = coherence_internal_inconsistencies(field, signoff.get(field))
        if reasons:
            internal_failures.append({"field": field, "reasons": reasons})
    if internal_failures:
        failures.append({"reason": "internal_consistency_failed", "fields": internal_failures})

    if artifact_set_path is None or not artifact_set_path.exists() or ctx.vs_path is None or not ctx.vs_path.exists():
        return failures
    try:
        module = import_module_safe("check_artifact_coherence")
        recomputed = module.build_report(
            artifact_set_path,
            ctx.vs_path,
            threshold_registry_path(ctx),
            reviewer_mode="operator",
        )
    except Exception as exc:
        failures.append({"reason": "coherence_recompute_failed", "error": str(exc)})
        return failures

    mismatches = []
    for field in COHERENCE_CHECK_FIELDS:
        expected = recomputed.get(field)
        signed = signoff.get(field)
        if not isinstance(expected, dict) or not isinstance(signed, dict):
            mismatches.append({"field": field, "reason": "missing_recomputed_or_signed_check"})
            continue
        for key in COHERENCE_COMPARABLE_KEYS:
            if key not in expected and key not in signed:
                continue
            if key not in expected or key not in signed:
                mismatches.append(
                    {
                        "field": field,
                        "key": key,
                        "expected": expected.get(key),
                        "signed": signed.get(key),
                        "reason": "missing_comparable_value",
                    }
                )
                continue
            if not comparable_values_match(expected.get(key), signed.get(key)):
                mismatches.append({"field": field, "key": key, "expected": expected.get(key), "signed": signed.get(key)})
    quantitative_verdict = str(recomputed.get("verdict_quantitative_only") or "").strip().lower()
    signed_overall = str(signoff.get("verdict") or "").strip().lower()
    expected_overall = "pass" if quantitative_verdict == "pass" else "fail"
    if signed_overall in {"pass", "fail"} and signed_overall != expected_overall:
        mismatches.append({"field": "verdict", "expected": expected_overall, "signed": signed_overall})
    if mismatches:
        failures.append(
            {
                "reason": "coherence_signoff inconsistent with recomputed values.",
                "mismatches": mismatches,
            }
        )
    return failures


def details_substantive(value: Any) -> bool:
    text = normalize_text(value)
    if len(text) < 20:
        return False
    return len(re.findall(r"[A-Za-z0-9]+", text)) >= 4


def fail_details_reference_computation(field: str, check: dict[str, Any]) -> bool:
    details = normalize_text(check.get("details")).lower()
    if not details_substantive(details):
        return False
    if "value" in check and "max_threshold" in check:
        observed = check.get("value")
        threshold = check.get("max_threshold")
        has_value_reference = (
            "value" in details
            and ("max_threshold" in details or "threshold" in details)
            and str(observed) in details
            and str(threshold) in details
        )
        if isinstance(observed, (int, float)) and isinstance(threshold, (int, float)) and float(observed) > float(threshold):
            return has_value_reference and any(token in details for token in ("exceed", "above", "greater", ">", "fail"))
        return has_value_reference and any(token in details for token in ("fail", "missing", "inconsistent", "mismatch", "required", "fill_ratio"))
    if field == "per_slot_integration":
        passed = check.get("passed")
        total = check.get("total")
        return (
            ("passed" in details or "slot" in details)
            and str(passed) in details
            and str(total) in details
            and any(token in details for token in ("fail", "missing", "not all", "unanimous"))
        )
    return any(token in details for token in ("fail", "missing", "inconsistent", "mismatch", "required", "exceed"))


def threshold_registry_path(ctx: GateContext) -> Path:
    candidate = context_vault_root(ctx) / "config" / "artifact-coherence-thresholds.yml"
    return candidate if candidate.exists() else VAULT_ROOT / "config" / "artifact-coherence-thresholds.yml"


def checked_threshold_map(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {key: raw[key] for key in THRESHOLD_KEYS if key in raw}


def resolve_expected_thresholds(registry: dict[str, Any], medium: str, preset: str) -> dict[str, dict[str, Any]]:
    defaults = checked_threshold_map(registry.get("defaults"))
    medium_overrides = registry.get("per_medium_overrides") if isinstance(registry.get("per_medium_overrides"), dict) else {}
    preset_overrides = registry.get("per_preset_overrides") if isinstance(registry.get("per_preset_overrides"), dict) else {}
    medium_override = checked_threshold_map(medium_overrides.get(medium)) if medium else {}
    preset_override = checked_threshold_map(preset_overrides.get(preset)) if preset else {}
    effective = dict(defaults)
    effective.update(medium_override)
    effective.update(preset_override)
    return {
        "from_defaults": defaults,
        "from_medium_override": medium_override,
        "from_preset_override": preset_override,
        "effective": effective,
    }


def threshold_values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) < 1e-9
    return left == right


def threshold_resolution_mismatches(actual: Any, expected: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(actual, dict):
        return [{"path": "/", "reason": "missing_or_invalid_resolution"}]
    mismatches: list[dict[str, Any]] = []
    for section, expected_map in expected.items():
        actual_map = actual.get(section)
        if not isinstance(actual_map, dict):
            mismatches.append({"path": section, "reason": "missing_section"})
            continue
        for key, expected_value in expected_map.items():
            if key not in actual_map:
                mismatches.append({"path": f"{section}.{key}", "reason": "missing_threshold", "expected": expected_value})
                continue
            if not threshold_values_equal(actual_map[key], expected_value):
                mismatches.append(
                    {
                        "path": f"{section}.{key}",
                        "reason": "value_mismatch",
                        "expected": expected_value,
                        "actual": actual_map[key],
                    }
                )
    return mismatches


def membership_paths(ctx: GateContext) -> list[Path]:
    paths: list[Path] = []
    vault_root = context_vault_root(ctx)
    paths.append(vault_root / "archive" / "visual-aesthetics" / "custom" / "_cohort-membership.json")
    if ctx.references_dir is not None:
        paths.append(ctx.references_dir / "_cohort-membership.json")
    if vault_root != VAULT_ROOT:
        paths.append(VAULT_ROOT / "archive" / "visual-aesthetics" / "custom" / "_cohort-membership.json")
    return unique_paths(paths)


def load_membership(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def member_vs_path_matches(raw: Any, ctx: GateContext) -> bool:
    if ctx.vs_path is None:
        return False
    value = str(raw or "").strip()
    if not value:
        return False
    raw_path = Path(value).expanduser()
    candidates = [raw_path] if raw_path.is_absolute() else [REPO_ROOT / raw_path]
    if ctx.references_dir is not None and not raw_path.is_absolute():
        candidates.append(ctx.references_dir.parent / raw_path)
    for candidate in candidates:
        try:
            if candidate.resolve() == ctx.vs_path.resolve():
                return True
        except OSError:
            continue
    return False


def find_custom_membership(ctx: GateContext, cluster_id: str | None = None) -> dict[str, Any]:
    project = ctx.project_slug()
    for path in membership_paths(ctx):
        membership = load_membership(path)
        cohorts = membership.get("cohorts") if isinstance(membership.get("cohorts"), list) else []
        for cohort in cohorts:
            if not isinstance(cohort, dict):
                continue
            if cluster_id and str(cohort.get("cohort_id") or "") != cluster_id:
                continue
            members = cohort.get("members") if isinstance(cohort.get("members"), list) else []
            for member in members:
                if not isinstance(member, dict):
                    continue
                if str(member.get("project") or "").strip() == project or member_vs_path_matches(member.get("vs_path"), ctx):
                    return {"membership_path": path, "cohort": cohort, "member": member}
    return {}


def find_custom_cohort(ctx: GateContext, cluster_id: str) -> dict[str, Any]:
    for path in membership_paths(ctx):
        membership = load_membership(path)
        cohorts = membership.get("cohorts") if isinstance(membership.get("cohorts"), list) else []
        for cohort in cohorts:
            if not isinstance(cohort, dict):
                continue
            if str(cohort.get("cohort_id") or "") == cluster_id:
                return {"membership_path": path, "cohort": cohort}
    return {}


def numeric_version(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def centroid_version_from_meta(ctx: GateContext, centroid: dict[str, Any]) -> int | None:
    meta_path = ctx.resolve_path(centroid.get("centroid_meta_path"))
    if meta_path is None:
        centroid_path = ctx.resolve_path(centroid.get("centroid_path"))
        if centroid_path is not None:
            candidates = [
                centroid_path.with_suffix(centroid_path.suffix + ".meta.json"),
                centroid_path.with_suffix(".meta.json"),
            ]
            meta_path = next((path for path in candidates if path.exists()), None)
    if meta_path is None or not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return numeric_version(data.get("centroid_version")) if isinstance(data, dict) else None


def centroid_usage_records(ctx: GateContext) -> list[dict[str, Any]]:
    lock_versions = ctx.vs_frontmatter().get("centroid_versions_at_lock")
    lock_versions = lock_versions if isinstance(lock_versions, dict) else {}
    records: list[dict[str, Any]] = []
    for item in artifact_manifest_items(ctx):
        centroids = item.get("contributing_centroids") if isinstance(item.get("contributing_centroids"), list) else []
        if not centroids and item.get("centroid_version") is not None:
            centroids = [
                {
                    "centroid_id": str(item.get("quality_centroid_override_path") or item.get("type") or item.get("id") or "artifact_centroid"),
                    "centroid_version": item.get("centroid_version"),
                    "lock_time_centroid_version": item.get("lock_time_centroid_version"),
                }
            ]
        for centroid in centroids:
            if not isinstance(centroid, dict):
                continue
            centroid_id = str(centroid.get("centroid_id") or centroid.get("centroid_path") or "").strip()
            item_version = numeric_version(centroid.get("centroid_version"))
            meta_version = centroid_version_from_meta(ctx, centroid)
            current_version = meta_version if meta_version is not None else item_version
            lock_version = numeric_version(centroid.get("lock_time_centroid_version"))
            if lock_version is None and centroid_id in lock_versions:
                lock_version = numeric_version(lock_versions.get(centroid_id))
            records.append(
                {
                    "artifact_id": item.get("id"),
                    "centroid_id": centroid_id,
                    "centroid_version": current_version,
                    "lock_time_centroid_version": lock_version,
                }
            )
    return records


def _run_check_1(ctx: GateContext) -> dict[str, Any]:
    path = ctx.vs_path
    if path is None:
        return make_check_result("fail", "VS path was empty.")
    return make_check_result("pass" if path.exists() else "fail", {"vs_path": str(path), "exists": path.exists()})


def _run_check_2(ctx: GateContext) -> dict[str, Any]:
    frontmatter = ctx.vs_frontmatter()
    axes = frontmatter.get("visual_axes")
    if not isinstance(axes, dict):
        return make_check_result("fail", "visual_axes missing or not a mapping.")
    required = {"density", "topology", "expressiveness", "motion", "platform", "trust"}
    missing = sorted(required - set(axes))
    return make_check_result("pass" if not missing else "fail", {"axes": axes, "missing": missing})


def _run_check_3(ctx: GateContext) -> dict[str, Any]:
    frontmatter = ctx.vs_frontmatter()
    return make_check_result("pass" if frontmatter.get("tokens_locked") is True else "fail", {"tokens_locked": frontmatter.get("tokens_locked")})


def _run_check_4(ctx: GateContext) -> dict[str, Any]:
    refs_dir = ctx.references_dir
    exists = refs_dir is not None and refs_dir.exists() and refs_dir.is_dir()
    return make_check_result("pass" if exists else "fail", {"references_dir": str(refs_dir) if refs_dir else "", "exists": exists})


def _run_check_5(ctx: GateContext) -> dict[str, Any]:
    path = ctx.manifest_path()
    if path is None or not path.exists():
        return make_check_result("fail", "manifest.json is missing.")
    try:
        manifest = ctx.manifest()
    except Exception as exc:
        return make_check_result("fail", "manifest.json could not be parsed.", error_message=str(exc))
    required = {"medium", "project", "tokens", "assets"}
    missing = sorted(required - set(manifest))
    return make_check_result("pass" if not missing else "fail", {"manifest_path": str(path), "missing_keys": missing})


def _run_check_6(ctx: GateContext) -> dict[str, Any]:
    references = [path for path in ctx.reference_pngs() if path.exists() and path.stat().st_size > 0]
    return make_check_result("pass" if len(references) >= 3 else "fail", {"reference_png_count": len(references), "paths": [rel_or_abs(path) for path in references]})


def _run_check_7(ctx: GateContext) -> dict[str, Any]:
    anti_patterns = [path for path in ctx.reference_pngs("anti_pattern") if path.exists() and path.stat().st_size > 0]
    return make_check_result("pass" if anti_patterns else "fail", {"anti_pattern_count": len(anti_patterns), "paths": [rel_or_abs(path) for path in anti_patterns]})


def _run_check_8(ctx: GateContext) -> dict[str, Any]:
    mockups = ctx.mockup_records()
    qualifying = [record for record in mockups if len(record.get("_revisions", [])) >= 3]
    return make_check_result(
        "pass" if len(qualifying) >= 2 else "fail",
        {
            "mockup_count": len(mockups),
            "qualifying_anchors": [
                {"screen": record.get("screen"), "revisions": len(record.get("_revisions", []))}
                for record in qualifying
            ],
        },
    )


def _run_check_9(ctx: GateContext) -> dict[str, Any]:
    token_root = ctx.manifest().get("tokens")
    required = {"color", "type", "spacing", "radius", "elevation", "motion", "density", "focus"}
    if not isinstance(token_root, dict):
        return make_check_result("fail", "manifest.tokens missing or not an object.")
    missing = sorted(required - set(token_root))
    return make_check_result("pass" if not missing else "fail", {"missing_families": missing})


def _run_check_10(ctx: GateContext) -> dict[str, Any]:
    token_root = ctx.manifest().get("tokens")
    if not isinstance(token_root, dict):
        return make_check_result("fail", "manifest.tokens missing or not an object.")
    counts = {
        "color": count_named_family_entries(token_root.get("color")),
        "type": count_named_family_entries(token_root.get("type")),
        "spacing": count_named_family_entries(token_root.get("spacing")),
        "radius": count_named_family_entries(token_root.get("radius")),
        "motion": count_named_family_entries(token_root.get("motion")),
    }
    thresholds = {"color": 10, "type": 5, "spacing": 6, "radius": 4, "motion": 3}
    failed = {name: {"count": counts[name], "required": minimum} for name, minimum in thresholds.items() if counts[name] < minimum}
    return make_check_result("pass" if not failed else "fail", {"counts": counts, "failed": failed})


def _run_check_11(ctx: GateContext) -> dict[str, Any]:
    section = markdown_section(ctx.vs_body(), "Anti-Patterns")
    if not section:
        return make_check_result("fail", "Anti-Patterns section missing.")
    items = [line.strip() for line in section.splitlines() if re.match(r"^\s*[-*]\s+", line)]
    bad_items = [item for item in items if len(SENTENCE_RE.findall(item)) < 1]
    return make_check_result("pass" if len(items) >= 3 and not bad_items else "fail", {"item_count": len(items), "bad_items": bad_items[:5]})


def _run_check_12(ctx: GateContext) -> dict[str, Any]:
    section = markdown_section(ctx.vs_body(), "Build Agent Gospel")
    return make_check_result("pass" if section else "fail", {"present": bool(section)})


def _run_check_13(ctx: GateContext) -> dict[str, Any]:
    reports = ctx.report_records()
    if not reports:
        return make_check_result("fail", "No sign-off reports were discoverable.")
    missing = [rel_or_abs(item["path"]) for item in reports if item.get("missing")]
    incomplete: list[str] = []
    for report in reports:
        if report.get("missing"):
            continue
        frontmatter = report.get("frontmatter", {})
        required = {"reviewer_session_id", "verdict"}
        absent = sorted(key for key in required if not str(frontmatter.get(key) or "").strip())
        if absent:
            incomplete.append(f"{rel_or_abs(report['path'])}: missing {', '.join(absent)}")
            continue
        if len(str(report.get("body") or "").strip()) < 40:
            incomplete.append(f"{rel_or_abs(report['path'])}: body too short")
    verdict = "pass" if not missing and not incomplete else "fail"
    return make_check_result(verdict, {"missing_reports": missing, "incomplete_reports": incomplete})


def _run_check_14(ctx: GateContext) -> dict[str, Any]:
    locked_at = parse_datetime(ctx.vs_frontmatter().get("tokens_locked_at"))
    if locked_at is None:
        return make_check_result("fail", "tokens_locked_at missing or invalid.")
    max_days = read_platform_scalar("visual_spec_signoff_freshness_max_days", 14)
    violations = []
    for report in ctx.report_records():
        if report.get("missing"):
            violations.append({"path": rel_or_abs(report["path"]), "reason": "missing"})
            continue
        report_ts = resolve_report_timestamp(report["path"], report.get("frontmatter", {}))
        if report_ts is None:
            violations.append({"path": rel_or_abs(report["path"]), "reason": "timestamp unavailable"})
            continue
        if report_ts < locked_at or report_ts > locked_at + timedelta(days=max_days):
            violations.append({"path": rel_or_abs(report["path"]), "report_ts": report_ts.isoformat(), "locked_at": locked_at.isoformat()})
    return make_check_result("pass" if not violations else "fail", {"max_days": max_days, "violations": violations})


def _run_check_15(ctx: GateContext) -> dict[str, Any]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for PNG dimension checks.") from exc
    failures = []
    for record in ctx.all_png_records():
        with Image.open(record["path"]) as image:
            width, height = image.size
        if width < 800 or height < 600:
            failures.append({"path": rel_or_abs(record["path"]), "width": width, "height": height})
    return make_check_result("pass" if not failures else "fail", {"failed": failures})


def _run_check_16(ctx: GateContext) -> dict[str, Any]:
    try:
        from PIL import Image, ImageStat
    except ImportError as exc:
        raise RuntimeError("Pillow is required for PNG nonblank checks.") from exc
    failures = []
    for record in ctx.all_png_records():
        with Image.open(record["path"]) as image:
            grayscale = image.convert("L")
            histogram = grayscale.histogram()
            total = float(sum(histogram) or 1)
            entropy = -sum((count / total) * math.log2(count / total) for count in histogram if count)
            variance = ImageStat.Stat(grayscale).var[0]
        if entropy < 0.3 or variance < 1.0:
            failures.append({"path": rel_or_abs(record["path"]), "entropy": round(entropy, 4), "variance": round(variance, 4)})
    return make_check_result("pass" if not failures else "fail", {"failed": failures})


def _run_check_17(ctx: GateContext) -> dict[str, Any]:
    module = import_module_safe("compute_phash")
    references = ctx.reference_pngs()
    if len(references) < 2:
        return make_check_result("not_applicable", "Need at least two reference PNGs.")
    threshold = read_platform_scalar("visual_spec_phash_noise_floor", 8)
    hashed = {str(path): module.compute_phash(path, use_cache=ctx.cache.enabled("phash"))["phash"] for path in references}
    failures = []
    paths = list(hashed)
    for index, first in enumerate(paths):
        for second in paths[index + 1 :]:
            distance = module.compute_phash_distance(hashed[first], hashed[second])
            if distance <= threshold:
                failures.append({"a": rel_or_abs(Path(first)), "b": rel_or_abs(Path(second)), "distance": distance, "required_gt": threshold})
    return make_check_result("pass" if not failures else "fail", {"failed_pairs": failures})


def _run_check_18(ctx: GateContext) -> dict[str, Any]:
    module = import_module_safe("compute_phash")
    mockups = ctx.mockup_pngs()
    anti_patterns = ctx.reference_pngs("anti_pattern")
    if not mockups or not anti_patterns:
        return make_check_result("not_applicable", "Need both mockup and anti-pattern PNGs.")
    threshold = read_platform_scalar("visual_spec_phash_forbidden_proximity", 12)
    hashed = {}
    for path in unique_paths(mockups + anti_patterns):
        hashed[str(path)] = module.compute_phash(path, use_cache=ctx.cache.enabled("phash"))["phash"]
    failures = []
    for mockup in mockups:
        for anti in anti_patterns:
            distance = module.compute_phash_distance(hashed[str(mockup)], hashed[str(anti)])
            if distance <= threshold:
                failures.append({"mockup": rel_or_abs(mockup), "anti_pattern": rel_or_abs(anti), "distance": distance, "required_gt": threshold})
    return make_check_result("pass" if not failures else "fail", {"failed_pairs": failures})


def _run_check_19(ctx: GateContext) -> dict[str, Any]:
    module = import_module_safe("compute_phash")
    references = ctx.reference_pngs()
    mockups = ctx.mockup_pngs()
    if not references or not mockups:
        return make_check_result("not_applicable", "Need reference and mockup PNGs.")
    take_min = read_platform_scalar("visual_spec_phash_take_min", 14)
    literal_max = read_platform_scalar("visual_spec_phash_literal_max", 32)
    primary = references[0]
    primary_hash = module.compute_phash(primary, use_cache=ctx.cache.enabled("phash"))["phash"]
    failures = []
    for mockup in mockups:
        mockup_hash = module.compute_phash(mockup, use_cache=ctx.cache.enabled("phash"))["phash"]
        distance = module.compute_phash_distance(primary_hash, mockup_hash)
        if distance < take_min or distance > literal_max:
            failures.append({"mockup": rel_or_abs(mockup), "primary_reference": rel_or_abs(primary), "distance": distance, "band": [take_min, literal_max]})
    return make_check_result("pass" if not failures else "fail", {"primary_reference": rel_or_abs(primary), "failed_mockups": failures})


def _run_check_20(ctx: GateContext) -> dict[str, Any]:
    plugin = ctx.medium_plugin_frontmatter()
    parity = plugin.get("parity_methodology") if isinstance(plugin.get("parity_methodology"), dict) else {}
    method = str(parity.get("method") or "")
    if method not in {"ssim", "mixed"}:
        return make_check_result("not_applicable", {"parity_method": method or None})
    render_module = import_module_safe("regen_mockup")
    ssim_module = import_module_safe("ssim_compare")
    failures = []
    for record in ctx.mockup_records():
        html_path = record.get("_final_html_path")
        png_path = record.get("_final_png_path")
        if not isinstance(html_path, Path) or not isinstance(png_path, Path):
            continue
        out_png = CACHE_ROOT / "render" / f"{stable_hash({'html': file_signature(html_path), 'screen': record.get('screen')})}.png"
        render_module.regenerate_mockup(html_path, out_png, "1440x900", use_cache=ctx.cache.enabled("render"))
        comparison = ssim_module.compute_ssim(png_path, out_png)
        if float(comparison.get("ssim") or 0.0) < 0.92:
            failures.append({"screen": record.get("screen"), "ssim": round(float(comparison.get("ssim") or 0.0), 4), "captured_png": rel_or_abs(png_path), "regen_png": rel_or_abs(out_png)})
    if not failures and not ctx.mockup_htmls():
        return make_check_result("not_applicable", "No HTML-backed mockups available for regeneration.")
    return make_check_result("pass" if not failures else "fail", {"failed": failures})


def _run_check_21(ctx: GateContext) -> dict[str, Any]:
    if ctx.medium != "web_ui":
        return make_check_result("not_applicable", "CSS token AST parity is implemented for web_ui.")
    manifest_path = ctx.manifest_path()
    if manifest_path is None or not manifest_path.exists():
        return make_check_result("fail", "manifest.json missing.")
    module = import_module_safe("extract_tokens_from_web_ui")
    reports = []
    failures = []
    for html_path in ctx.mockup_htmls():
        payload = module.build_payload(html_path)
        manifest_report = module.compare_manifest(payload, manifest_path)
        reports.append({"mockup": rel_or_abs(html_path), "valid": manifest_report["valid"]})
        if not manifest_report["valid"]:
            failures.append({"mockup": rel_or_abs(html_path), **manifest_report})
    if not reports:
        return make_check_result("not_applicable", "No HTML mockups available for CSS token extraction.")
    return make_check_result("pass" if not failures else "fail", {"reports": reports, "failures": failures})


def _run_check_22(ctx: GateContext) -> dict[str, Any]:
    manifest_path = ctx.manifest_path()
    if manifest_path is None or not manifest_path.exists():
        return make_check_result("fail", "manifest.json missing.")
    module = import_module_safe("check_contrast")
    payload = module.check_manifest_contrast(manifest_path)
    return make_check_result("pass" if payload.get("verdict") == "pass" else "fail", payload)


def _run_check_23(ctx: GateContext) -> dict[str, Any]:
    module = import_module_safe("compute_phash")
    threshold = read_platform_scalar("visual_spec_phash_noise_floor", 8)
    failures = []
    qualifying = 0
    for record in ctx.mockup_records():
        revisions = record.get("_revisions", [])
        if len(revisions) < 2:
            failures.append({"screen": record.get("screen"), "reason": "fewer than two revisions"})
            continue
        changed_pairs = 0
        for left, right in zip(revisions, revisions[1:]):
            left_png = left.get("_png_path")
            right_png = right.get("_png_path")
            changed = False
            if isinstance(left_png, Path) and isinstance(right_png, Path) and left_png.exists() and right_png.exists():
                left_hash = module.compute_phash(left_png, use_cache=ctx.cache.enabled("phash"))["phash"]
                right_hash = module.compute_phash(right_png, use_cache=ctx.cache.enabled("phash"))["phash"]
                changed = module.compute_phash_distance(left_hash, right_hash) > threshold
            if not changed:
                changed = str(left.get("sha256_html") or "") != str(right.get("sha256_html") or "")
            if changed:
                changed_pairs += 1
        if changed_pairs >= 2:
            qualifying += 1
        else:
            failures.append({"screen": record.get("screen"), "changed_pairs": changed_pairs})
    return make_check_result("pass" if qualifying >= 2 and not failures else "fail", {"qualifying_anchors": qualifying, "failures": failures})


def _run_check_24(ctx: GateContext) -> dict[str, Any]:
    adjudications = ctx.vs_frontmatter().get("adjudications")
    if not isinstance(adjudications, list):
        return make_check_result("fail", "adjudications missing or not a list.")
    sessions = [str(item.get("reviewer_session_id") or "").strip() for item in adjudications if isinstance(item, dict)]
    duplicates = sorted({session for session in sessions if session and sessions.count(session) > 1})
    return make_check_result("pass" if len(sessions) == len(set(sessions)) and "" not in sessions else "fail", {"sessions": sessions, "duplicates": duplicates})


def _run_check_25(ctx: GateContext) -> dict[str, Any]:
    frontmatter = ctx.vs_frontmatter()
    adjudications = frontmatter.get("adjudications") if isinstance(frontmatter.get("adjudications"), list) else []
    adversarial = frontmatter.get("adversarial_pass") if isinstance(frontmatter.get("adversarial_pass"), dict) else {}
    adjudication_sessions = {str(item.get("reviewer_session_id") or "").strip() for item in adjudications if isinstance(item, dict)}
    adversarial_session = str(adversarial.get("reviewer_session_id") or "").strip()
    verdict = "pass" if adversarial_session and adversarial_session not in adjudication_sessions else "fail"
    return make_check_result(verdict, {"adjudication_sessions": sorted(adjudication_sessions), "adversarial_session": adversarial_session})


def _run_check_26(ctx: GateContext) -> dict[str, Any]:
    adjudications = [item for item in ctx.vs_frontmatter().get("adjudications", []) if isinstance(item, dict)]
    if not adjudications:
        return make_check_result("fail", "No adjudications present.")
    last = sorted(adjudications, key=lambda item: int(item.get("round") or 0))[-1]
    verdict = str(last.get("verdict") or "").strip().upper()
    return make_check_result("pass" if verdict == "PASS" else "fail", {"last_round": last.get("round"), "verdict": verdict})


def _run_check_27(ctx: GateContext) -> dict[str, Any]:
    adversarial = ctx.vs_frontmatter().get("adversarial_pass")
    if not isinstance(adversarial, dict):
        return make_check_result("fail", "adversarial_pass missing or invalid.")
    raw = str(adversarial.get("verdict") or "").strip().lower()
    actionable = {"original_defended", "restart_required", "selected_upheld", "adjacent_preferred", "revise"}
    return make_check_result("pass" if raw in actionable else "fail", {"verdict": raw})


def _run_check_28(ctx: GateContext) -> dict[str, Any]:
    refs_dir = ctx.references_dir
    if refs_dir is None:
        return make_check_result("fail", "references dir missing.")
    path = refs_dir / "iteration-log.md"
    if not path.exists():
        return make_check_result("fail", "iteration-log.md missing.")
    text = path.read_text(encoding="utf-8")
    entries = re.findall(r"\brev(?:ision)?\s*#?\s*\d+\b", text, flags=re.I)
    count = max(len(entries), sum(len(record.get("_revisions", [])) for record in ctx.mockup_records()))
    empty_diff_entries = re.findall(
        r"(?im)^\s*[-*]?\s*(?:diff|delta|changes?)\s*:\s*(?:none|empty|no\s+change|0\s+(?:files?|changes?))\s*$",
        text,
    )
    return make_check_result(
        "pass" if count >= 6 and not empty_diff_entries else "fail",
        {"entry_count": count, "empty_diff_entries": empty_diff_entries, "path": rel_or_abs(path)},
    )


def _run_check_29(ctx: GateContext) -> dict[str, Any]:
    color_tokens = ctx.manifest().get("tokens", {}).get("color", {})
    if not isinstance(color_tokens, dict):
        return make_check_result("fail", "manifest.tokens.color missing or invalid.")
    bad_keys = [key for key in color_tokens if HEX_NAME_RE.match(str(key))]
    return make_check_result("pass" if not bad_keys else "fail", {"bad_keys": bad_keys})


def _run_check_30(ctx: GateContext) -> dict[str, Any]:
    color_tokens = ctx.manifest().get("tokens", {}).get("color", {})
    if not isinstance(color_tokens, dict):
        return make_check_result("fail", "manifest.tokens.color missing or invalid.")
    values: dict[str, str] = {}
    for key, value in color_tokens.items():
        if isinstance(value, dict):
            raw = value.get("value", value.get("$value"))
        else:
            raw = value
        if isinstance(raw, str) and raw.strip().startswith("#"):
            values[str(key)] = raw
    failures = []
    keys = list(values)
    for index, first in enumerate(keys):
        for second in keys[index + 1 :]:
            delta = delta_e76(values[first], values[second])
            if 0 < delta < 3:
                failures.append({"a": first, "b": second, "delta_e76": round(delta, 3)})
    return make_check_result("pass" if not failures else "fail", {"near_duplicates": failures})


def _run_check_31(ctx: GateContext) -> dict[str, Any]:
    violations = []
    for record in ctx.all_png_records():
        timestamp = record.get("timestamp")
        if not isinstance(timestamp, datetime):
            violations.append({"path": rel_or_abs(record["path"]), "reason": "missing timestamp"})
            continue
        delta_seconds = abs(record["path"].stat().st_mtime - timestamp.timestamp())
        if delta_seconds > 3600:
            violations.append({"path": rel_or_abs(record["path"]), "delta_seconds": round(delta_seconds, 1)})
    return make_check_result("pass" if not violations else "fail", {"violations": violations})


def _run_check_32(ctx: GateContext) -> dict[str, Any]:
    failures = []
    for record in ctx.reference_records():
        url = record.get("source_url")
        if url is None:
            failures.append({"path": rel_or_abs(record["_path"]), "source_url": None})
        elif not resolve_url_plausible(url):
            failures.append({"path": rel_or_abs(record["_path"]), "source_url": url})
    return make_check_result("pass" if not failures else "fail", {"invalid_urls": failures})


def _run_check_33(ctx: GateContext) -> dict[str, Any]:
    report_map = {str(item["path"].resolve()): item for item in ctx.report_records() if not item.get("missing")}
    failures = []
    for adjudication in ctx.vs_frontmatter().get("adjudications", []) if isinstance(ctx.vs_frontmatter().get("adjudications"), list) else []:
        if not isinstance(adjudication, dict):
            continue
        report_path = ctx.resolve_path(adjudication.get("report") or adjudication.get("report_path"))
        if report_path is None:
            failures.append({"round": adjudication.get("round"), "reason": "report missing"})
            continue
        report = report_map.get(str(report_path.resolve()))
        if not report:
            failures.append({"round": adjudication.get("round"), "reason": "report not loaded", "report": rel_or_abs(report_path)})
            continue
        expected = str(adjudication.get("reviewer_session_id") or "").strip()
        actual = str(report["frontmatter"].get("reviewer_session_id") or "").strip()
        if expected and actual and expected != actual:
            failures.append({"round": adjudication.get("round"), "expected": expected, "actual": actual})
    return make_check_result("pass" if not failures else "fail", {"failures": failures})


def _run_check_34(ctx: GateContext) -> dict[str, Any]:
    author_session = str(ctx.vs_frontmatter().get("agent") or "").strip()
    if not author_session:
        return make_check_result("not_applicable", "VS author session was not declared.")
    reviewer_sessions = set()
    for item in ctx.vs_frontmatter().get("adjudications", []) if isinstance(ctx.vs_frontmatter().get("adjudications"), list) else []:
        if isinstance(item, dict):
            reviewer_sessions.add(str(item.get("reviewer_session_id") or "").strip())
    adversarial = ctx.vs_frontmatter().get("adversarial_pass")
    if isinstance(adversarial, dict):
        reviewer_sessions.add(str(adversarial.get("reviewer_session_id") or "").strip())
    return make_check_result("pass" if author_session not in reviewer_sessions else "fail", {"author_session": author_session, "reviewer_sessions": sorted(item for item in reviewer_sessions if item)})


def _semantic_check(ctx: GateContext, key: str) -> dict[str, Any]:
    payload = ctx.semantic_layout()
    if payload is None:
        return make_check_result("skipped", "Semantic layout helper inputs were unavailable.")
    data = payload.get("checks", {}).get(key)
    if not isinstance(data, dict):
        return make_check_result("skipped", f"Semantic helper did not produce {key}.")
    return make_check_result(normalize_helper_verdict(data.get("verdict")), data)


def _run_check_35(ctx: GateContext) -> dict[str, Any]:
    return _semantic_check(ctx, "35_equal_weight_grid")


def _run_check_36(ctx: GateContext) -> dict[str, Any]:
    return _semantic_check(ctx, "36_hierarchy_contrast")


def _run_check_37(ctx: GateContext) -> dict[str, Any]:
    return _semantic_check(ctx, "37_pane_dominance")


def _run_check_38(ctx: GateContext) -> dict[str, Any]:
    return _semantic_check(ctx, "38_component_role_mix")


def _run_check_39(ctx: GateContext) -> dict[str, Any]:
    return _semantic_check(ctx, "39_visible_token_instances")


def _run_check_40(ctx: GateContext) -> dict[str, Any]:
    return _semantic_check(ctx, "40_density_target")


def _run_check_41(ctx: GateContext) -> dict[str, Any]:
    return _semantic_check(ctx, "41_brand_identity_application_diversity")


def _run_check_42(ctx: GateContext) -> dict[str, Any]:
    return _semantic_check(ctx, "42_video_sequential_frame_change")


def _run_check_43(ctx: GateContext) -> dict[str, Any]:
    return _semantic_check(ctx, "43_3d_lighting_source_detection")


def _clip_check(ctx: GateContext, key: str) -> dict[str, Any]:
    payload = ctx.clip_embedding()
    if payload is None:
        return make_check_result("skipped", "CLIP helper inputs were unavailable.")
    data = payload.get("checks", {}).get(key)
    if not isinstance(data, dict):
        return make_check_result("skipped", f"CLIP helper did not produce {key}.")
    return make_check_result(normalize_helper_verdict(data.get("verdict")), data)


def _run_check_44(ctx: GateContext) -> dict[str, Any]:
    return _clip_check(ctx, "44_mockup_to_preset")


def _run_check_45(ctx: GateContext) -> dict[str, Any]:
    return _clip_check(ctx, "45_mockup_to_antipattern")


def _run_check_46(ctx: GateContext) -> dict[str, Any]:
    return _clip_check(ctx, "46_anchor_diversity")


def _run_check_47(ctx: GateContext) -> dict[str, Any]:
    vs_version = str(ctx.vs_frontmatter().get("medium_plugin_version") or "").strip()
    plugin_version = str(ctx.medium_plugin_frontmatter().get("version") or "").strip()
    if not plugin_version:
        return make_check_result("fail", {"plugin_path": rel_or_abs(ctx.medium_plugin_path()), "reason": "plugin version missing"})
    return make_check_result("pass" if vs_version == plugin_version else "fail", {"vs_version": vs_version, "plugin_version": plugin_version})


def _run_check_48(ctx: GateContext) -> dict[str, Any]:
    plugin = ctx.medium_plugin_frontmatter()
    format_name = str(plugin.get("mockup_format") or "").strip()
    mockups = ctx.mockup_records()
    if not mockups:
        return make_check_result("fail", "No mockups declared.")
    failures = []
    if format_name == "html_css":
        for record in mockups:
            if not isinstance(record.get("_final_html_path"), Path) or not isinstance(record.get("_final_png_path"), Path):
                failures.append({"screen": record.get("screen"), "required": ["final_html", "final_png"]})
    elif format_name in {"png_only", "image_only"}:
        for record in mockups:
            if not isinstance(record.get("_final_png_path"), Path):
                failures.append({"screen": record.get("screen"), "required": ["final_png"]})
    else:
        return make_check_result("not_applicable", {"mockup_format": format_name or None})
    return make_check_result("pass" if not failures else "fail", {"mockup_format": format_name, "failures": failures})


def _run_check_49(ctx: GateContext) -> dict[str, Any]:
    minimum = int(ctx.medium_plugin_frontmatter().get("mockup_anchor_count_min") or 0)
    count = len(ctx.mockup_records())
    return make_check_result("pass" if minimum and count >= minimum else "fail", {"count": count, "required_min": minimum})


def _run_check_50(ctx: GateContext) -> dict[str, Any]:
    minimum = int(ctx.medium_plugin_frontmatter().get("mockup_revisions_per_anchor_min") or 0)
    failures = []
    for record in ctx.mockup_records():
        revisions = len(record.get("_revisions", []))
        if revisions < minimum:
            failures.append({"screen": record.get("screen"), "revisions": revisions, "required_min": minimum})
    return make_check_result("pass" if minimum and not failures else "fail", {"failures": failures, "required_min": minimum})


def _run_check_51(ctx: GateContext) -> dict[str, Any]:
    plugin_families = ctx.medium_plugin_frontmatter().get("token_families")
    tokens = ctx.manifest().get("tokens", {})
    if not isinstance(plugin_families, list) or not isinstance(tokens, dict):
        return make_check_result("fail", "Medium plugin token families or manifest tokens missing.")
    missing = [family for family in plugin_families if not isinstance(tokens.get(family), dict) or not tokens.get(family)]
    return make_check_result("pass" if not missing else "fail", {"missing_families": missing})


def _specificity_check(ctx: GateContext, key: str) -> dict[str, Any]:
    payload = ctx.visual_specificity()
    if payload is None:
        return make_check_result("skipped", "Visual specificity helper inputs were unavailable.")
    data = payload.get("checks", {}).get(key)
    if not isinstance(data, dict):
        return make_check_result("skipped", f"Visual specificity helper did not produce {key}.")
    return make_check_result(normalize_helper_verdict(data.get("status")), data)


def _run_check_52(ctx: GateContext) -> dict[str, Any]:
    return _specificity_check(ctx, "52")


def _run_check_53(ctx: GateContext) -> dict[str, Any]:
    return _specificity_check(ctx, "53")


def _run_check_54(ctx: GateContext) -> dict[str, Any]:
    return _specificity_check(ctx, "54")


def _run_check_55(ctx: GateContext) -> dict[str, Any]:
    return _specificity_check(ctx, "55")


def _run_check_56(ctx: GateContext) -> dict[str, Any]:
    return _specificity_check(ctx, "56")


def _run_check_57(ctx: GateContext) -> dict[str, Any]:
    return _specificity_check(ctx, "57")


def _run_check_58(ctx: GateContext) -> dict[str, Any]:
    module = import_module_safe("validate_schema")
    path = ctx.medium_plugin_path()
    if not path.exists():
        return make_check_result("fail", {"plugin_path": rel_or_abs(path), "reason": "missing"})
    payload = module.validate_artifact(path, SCHEMA_DIR / "medium-plugin.schema.json", "yaml-frontmatter")
    return make_check_result("pass" if payload.get("valid") else "fail", payload)


def _run_check_59(ctx: GateContext) -> dict[str, Any]:
    frontmatter = ctx.vs_frontmatter()
    plugin = ctx.medium_plugin_frontmatter()
    mode = str(frontmatter.get("visual_quality_target_mode") or "").strip()
    preset = str(frontmatter.get("visual_quality_target_preset") or "").strip()
    if mode not in VALID_MODES:
        return make_check_result("fail", {"mode": mode, "reason": "invalid_mode"})
    if mode == "preset":
        applicable = plugin.get("applicable_presets") if isinstance(plugin.get("applicable_presets"), list) else []
        return make_check_result("pass" if preset and preset in applicable else "fail", {"mode": mode, "preset": preset, "applicable_presets": applicable})
    if mode == "brand_system":
        brand_path = BRAND_SYSTEM_DIR / f"{preset}.md"
        return make_check_result("pass" if preset and brand_path.exists() else "fail", {"mode": mode, "preset": preset, "brand_path": rel_or_abs(brand_path)})
    if mode == "custom":
        return make_check_result("pass", {"mode": mode})
    return make_check_result("pass", {"mode": mode})


def _run_check_60(ctx: GateContext) -> dict[str, Any]:
    mode = str(ctx.vs_frontmatter().get("visual_quality_target_mode") or "").strip()
    if mode != "custom":
        return make_check_result("not_applicable", {"mode": mode or None})
    payload = ctx.clip_embedding()
    if payload is None:
        return make_check_result("fail", "CLIP helper unavailable for custom mode.")
    clip_block = payload.get("clip_embedding") if isinstance(payload.get("clip_embedding"), dict) else {}
    passed = payload.get("mode") == "custom" and bool(clip_block.get("centroid_hash"))
    return make_check_result("pass" if passed else "fail", {"mode": payload.get("mode"), "clip_embedding": clip_block})


def _run_check_61(ctx: GateContext) -> dict[str, Any]:
    mode = str(ctx.vs_frontmatter().get("visual_quality_target_mode") or "").strip()
    if mode != "brand_system":
        return make_check_result("not_applicable", {"mode": mode or None})
    payload = ctx.clip_embedding()
    if payload is None:
        return make_check_result("fail", "CLIP helper unavailable for brand_system mode.")
    centroid_path = payload.get("preset_centroid_path")
    passed = payload.get("mode") == "brand_system" and bool(centroid_path)
    return make_check_result("pass" if passed else "fail", {"mode": payload.get("mode"), "preset_centroid_path": centroid_path})


def _run_check_62(ctx: GateContext) -> dict[str, Any]:
    frontmatter = ctx.vs_frontmatter()
    visual_spec_id = frontmatter.get("visual_spec_id")
    revision_id = frontmatter.get("revision_id")
    supersedes = frontmatter.get("supersedes") if isinstance(frontmatter.get("supersedes"), list) else []
    failures = []
    if not is_uuid(visual_spec_id):
        failures.append("visual_spec_id invalid")
    if not is_uuid(revision_id):
        failures.append("revision_id invalid")
    bad_supersedes = [item for item in supersedes if not is_uuid(item)]
    if bad_supersedes:
        failures.append(f"supersedes contains invalid UUIDs: {bad_supersedes}")
    sibling_revisions = [
        item["frontmatter"].get("revision_id")
        for item in ctx.project_visual_specs()
        if str(item["frontmatter"].get("visual_spec_id") or "").strip() == str(visual_spec_id or "").strip()
    ]
    missing_links = [item for item in supersedes if item not in sibling_revisions]
    if missing_links:
        failures.append(f"supersedes IDs not found among sibling revisions: {missing_links}")
    return make_check_result("pass" if not failures else "fail", {"visual_spec_id": visual_spec_id, "revision_id": revision_id, "failures": failures})


def _run_check_63(ctx: GateContext) -> dict[str, Any]:
    visual_spec_id = str(ctx.vs_frontmatter().get("visual_spec_id") or "").strip()
    if not visual_spec_id:
        return make_check_result("fail", "visual_spec_id missing.")
    matching = [
        item for item in ctx.project_visual_specs() if str(item["frontmatter"].get("visual_spec_id") or "").strip() == visual_spec_id
    ]
    active = [item for item in matching if item["frontmatter"].get("active") is True]
    return make_check_result("pass" if len(active) == 1 else "fail", {"visual_spec_id": visual_spec_id, "active_revisions": [rel_or_abs(item["path"]) for item in active], "matching_revisions": len(matching)})


def _run_check_64(ctx: GateContext) -> dict[str, Any]:
    payload = ctx.concurrency_report()
    if payload is None:
        return make_check_result("fail", "Concurrency report unavailable.")
    stale_locks = payload.get("stale_locks") or []
    return make_check_result("pass" if not stale_locks else "fail", {"stale_locks": stale_locks})


def _run_check_65(ctx: GateContext) -> dict[str, Any]:
    return _specificity_check(ctx, "65")


def _run_check_66(ctx: GateContext) -> dict[str, Any]:
    return _specificity_check(ctx, "66")


def _run_check_67(ctx: GateContext) -> dict[str, Any]:
    reports = ctx.report_records()
    if not reports:
        return make_check_result("fail", "No adjudication reports loaded.")
    failures = []
    for report in reports:
        if report.get("missing"):
            continue
        frontmatter = report.get("frontmatter", {})
        linked = frontmatter.get("linked_specificity_fields") if isinstance(frontmatter.get("linked_specificity_fields"), list) else []
        linked = [field for field in linked if field in SPECIFICITY_FIELDS]
        body = str(report.get("body") or "")
        mentions = [field for field in SPECIFICITY_FIELDS if field in body]
        if not linked and not mentions:
            failures.append(rel_or_abs(report["path"]))
    return make_check_result("pass" if not failures else "fail", {"reports_without_field_links": failures})


def _run_check_68(ctx: GateContext) -> dict[str, Any]:
    payload = ctx.specificity_score()
    if payload is None:
        return make_check_result("skipped", "Need both VS and brief-derived specificity candidates.")
    items = payload.get("item_scores") if isinstance(payload.get("item_scores"), list) else []
    total = len(items)
    matched = sum(1 for item in items if isinstance(item, dict) and item.get("matched_candidate"))
    pct = (matched / total * 100.0) if total else 0.0
    return make_check_result("pass" if pct >= 70.0 else "fail", {"matched_items": matched, "total_items": total, "overlap_pct": round(pct, 2)})


def _run_check_69(ctx: GateContext) -> dict[str, Any]:
    payload = ctx.specificity_score()
    if payload is None:
        return make_check_result("skipped", "Specificity score unavailable.")
    failures = [
        {"field": item.get("field"), "name": item.get("name"), "term_score": item.get("term_score")}
        for item in payload.get("item_scores", [])
        if isinstance(item, dict) and float(item.get("term_score") or 0.0) <= 0.0
    ]
    return make_check_result("pass" if not failures else "fail", {"failures": failures})


def _run_check_70(ctx: GateContext) -> dict[str, Any]:
    payload = ctx.specificity_score()
    if payload is None:
        return make_check_result("skipped", "Specificity score unavailable.")
    passed = (
        payload.get("passes_per_item_threshold") is True
        and payload.get("passes_average_threshold") is True
        and payload.get("passes_distribution_threshold") is True
    )
    return make_check_result("pass" if passed else "fail", payload)


def _run_check_71(ctx: GateContext) -> dict[str, Any]:
    frontmatter = ctx.vs_frontmatter()
    mode = str(frontmatter.get("visual_quality_target_mode") or "").strip()
    if mode != "none":
        return make_check_result("not_applicable", {"mode": mode or None})
    brief_path = ctx.brief_path
    if brief_path is None or not brief_path.exists():
        return make_check_result("skipped", "Need brief to assess visual ambition.")
    ambition_module = import_module_safe("detect_visual_ambition")
    ambition = ambition_module.detect_ambition(brief_path)
    if ambition.get("ambition_detected") is not True:
        return make_check_result("pass", {"ambition_detected": False})
    vs_path = ctx.vs_path
    if vs_path is None:
        return make_check_result("fail", "VS path missing for waiver lookup.")
    waiver_paths = sorted(vs_path.parent.glob("*visual-spec-waiver-*.md"))
    if not waiver_paths:
        return make_check_result("fail", {"ambition": ambition, "waivers_found": []})
    module = import_module_safe("validate_schema")
    validations = [
        module.validate_artifact(path, SCHEMA_DIR / "waiver.schema.json", "yaml-frontmatter")
        for path in waiver_paths
    ]
    valid = [item["artifact"] for item in validations if item.get("valid")]
    return make_check_result("pass" if valid else "fail", {"ambition": ambition, "waivers_found": [rel_or_abs(path) for path in waiver_paths], "valid_waivers": valid})


def _run_check_72(ctx: GateContext) -> dict[str, Any]:
    payload = ctx.concurrency_report()
    if payload is None:
        return make_check_result("fail", "Concurrency report unavailable.")
    concerns = {
        "stale_locks": payload.get("stale_locks") or [],
        "conflicting_amendments": payload.get("conflicting_amendments") or [],
        "orphaned_locks": payload.get("orphaned_locks") or [],
        "concurrent_modifications": payload.get("concurrent_modifications") or [],
    }
    failed = any(concerns.values())
    return make_check_result("pass" if not failed else "fail", concerns)


def _run_check_73(ctx: GateContext) -> dict[str, Any]:
    payload = ctx.resolver_generation_report()
    if payload is None:
        return make_check_result("skipped", "Ticket path unavailable for resolver generation check.")
    passed = payload.get("consistent") is True and payload.get("recommended_action") == "none"
    return make_check_result("pass" if passed else "fail", payload)


def _run_check_74(ctx: GateContext) -> dict[str, Any]:
    return make_check_result("skipped", "Deferred to telemetry data once proposal cohorts exist.")


def _run_check_75(ctx: GateContext) -> dict[str, Any]:
    return make_check_result("skipped", "Deferred to telemetry data once effect-size baselines exist.")


def _run_check_76(ctx: GateContext) -> dict[str, Any]:
    return make_check_result("skipped", "Deferred to telemetry data once holdout replay exists.")


def _run_check_77(ctx: GateContext) -> dict[str, Any]:
    return _specificity_check(ctx, "77")


def _run_check_78(ctx: GateContext) -> dict[str, Any]:
    replay = ctx.medium_plugin_frontmatter().get("regression_replay_contract")
    if not isinstance(replay, dict):
        return make_check_result("fail", "regression_replay_contract missing from medium plugin.")
    supported = replay.get("supported") is True
    required = {"renderer_script", "required_source_artifacts", "replay_fixture", "replay_determinism_test"}
    missing = sorted(key for key in required if not replay.get(key))
    return make_check_result("pass" if supported and not missing else "fail", {"supported": supported, "missing_fields": missing})


def schema_target_for_artifact(path: Path, *, ctx: GateContext) -> tuple[Path, str] | None:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if path == ctx.vs_path:
        return SCHEMA_DIR / "visual-spec-frontmatter.schema.json", "yaml-frontmatter"
    if path == ctx.medium_plugin_path():
        return SCHEMA_DIR / "medium-plugin.schema.json", "yaml-frontmatter"
    if name == "manifest.json":
        return SCHEMA_DIR / "visual-spec-manifest.schema.json", "json"
    if "specificity-candidates" in name and suffix == ".json":
        return SCHEMA_DIR / "specificity-candidates.schema.json", "json"
    if "redline" in name and "diff" in name and suffix == ".json":
        return SCHEMA_DIR / "redline-diff.schema.json", "json"
    if "regression" in name and suffix == ".json":
        return SCHEMA_DIR / "regression-report.schema.json", "json"
    if "outcome" in name and suffix == ".json":
        return SCHEMA_DIR / "outcome-data.schema.json", "json"
    if "resolution" == path.stem and suffix == ".json":
        return SCHEMA_DIR / "resolver-output.schema.json", "json"
    if "waiver" in name and suffix == ".md":
        return SCHEMA_DIR / "waiver.schema.json", "yaml-frontmatter"
    if "adjudication" in name and suffix == ".md":
        return SCHEMA_DIR / "adjudication-record.schema.json", "yaml-frontmatter"
    return None


def _run_check_79(ctx: GateContext) -> dict[str, Any]:
    module = import_module_safe("validate_schema")
    paths: list[Path] = []
    if ctx.vs_path is not None and ctx.vs_path.exists():
        paths.append(ctx.vs_path)
    manifest_path = ctx.manifest_path()
    if manifest_path is not None and manifest_path.exists():
        paths.append(manifest_path)
    plugin_path = ctx.medium_plugin_path()
    if plugin_path.exists():
        paths.append(plugin_path)
    if ctx.references_dir is not None and ctx.references_dir.exists():
        for suffix in ("*.json", "*.yaml", "*.yml", "*.md"):
            paths.extend(ctx.references_dir.rglob(suffix))
    paths.extend(ctx.report_paths())
    paths.extend(ctx.redline_diff_paths())
    candidates_path = ctx.ensured_candidates_path()
    if candidates_path is not None and candidates_path.exists():
        paths.append(candidates_path)
    failures = []
    skipped = []
    for path in unique_paths(paths):
        target = schema_target_for_artifact(path, ctx=ctx)
        if target is None:
            if path.suffix.lower() in {".json", ".yaml", ".yml", ".md"}:
                skipped.append(rel_or_abs(path))
            continue
        schema_path, artifact_type = target
        payload = module.validate_artifact(path, schema_path, artifact_type)
        if not payload.get("valid"):
            failures.append(payload)
    return make_check_result("pass" if not failures else "fail", {"failures": failures, "skipped_unknown_schema": skipped[:50]})


def _run_check_80(ctx: GateContext) -> dict[str, Any]:
    diff_paths = ctx.redline_diff_paths()
    if not diff_paths:
        return make_check_result("not_applicable", "No redline diff artifacts found.")
    module = import_module_safe("validate_schema")
    validations = [module.validate_artifact(path, SCHEMA_DIR / "redline-diff.schema.json", "json") for path in diff_paths]
    invalid = [payload for payload in validations if not payload.get("valid")]
    if invalid:
        return make_check_result("fail", {"invalid_diffs": invalid})
    diffs = [load_json(path) for path in diff_paths]
    linked_fields: set[str] = set()
    has_redlines = False
    for report in ctx.report_records():
        frontmatter = report.get("frontmatter", {})
        fields = frontmatter.get("linked_specificity_fields") if isinstance(frontmatter.get("linked_specificity_fields"), list) else []
        linked_fields.update(field for field in fields if field in SPECIFICITY_FIELDS)
        redlines = frontmatter.get("redlines") if isinstance(frontmatter.get("redlines"), list) else []
        if redlines:
            has_redlines = True
    if not has_redlines and not linked_fields:
        return make_check_result("not_applicable", "No redline-linked signoff data found.")
    covered = {str(diff.get("redline_target_field") or "") for diff in diffs if diff.get("addressed") is True}
    missing = sorted(field for field in linked_fields if field not in covered)
    return make_check_result("pass" if not missing and bool(covered) else "fail", {"linked_fields": sorted(linked_fields), "covered_fields": sorted(covered), "missing_fields": missing})


def _run_check_81(ctx: GateContext) -> dict[str, Any]:
    payload = ctx.brief_adequacy()
    if payload is None:
        return make_check_result("skipped", "Brief path unavailable.")
    verdict = str(payload.get("verdict") or "").lower()
    if verdict == "pass":
        return make_check_result("pass", payload)
    if verdict == "pass_with_low_confidence_flag":
        details = dict(payload)
        details["low_confidence"] = True
        return make_check_result("pass", details)
    if verdict == "needs_operator":
        return make_check_result("fail", payload)
    return make_check_result("error", payload, error_message=f"Unexpected brief adequacy verdict: {verdict or 'missing'}")


def _frontmatter_bool(frontmatter: dict[str, Any], keys: Iterable[str]) -> bool:
    for key in keys:
        value = frontmatter.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.strip().lower() in {"true", "yes", "completed", "done"}:
            return True
    return False


def _recent_frontmatter_timestamp(frontmatter: dict[str, Any], keys: Iterable[str], *, hours: int) -> bool:
    now = datetime.now(timezone.utc).astimezone()
    earliest = now - timedelta(hours=max(hours, 24))
    for key in keys:
        parsed = parse_datetime(frontmatter.get(key))
        if parsed is not None and earliest <= parsed <= now:
            return True
    return False


def _cooling_until_elapsed(frontmatter: dict[str, Any], keys: Iterable[str], *, hours: int) -> bool:
    now = datetime.now(timezone.utc).astimezone()
    earliest = now - timedelta(hours=max(hours, 24))
    for key in keys:
        parsed = parse_datetime(frontmatter.get(key))
        if parsed is not None and earliest <= parsed <= now:
            return True
    return False


def governance_red_control_completed(ctx: GateContext, *, scope: str, payload: dict[str, Any]) -> bool:
    cooling_hours = int(payload.get("cooling_off_hours") or 24)
    bool_keys = (
        f"{scope}_second_review_completed",
        f"{scope}_cooling_off_completed",
        "visual_spec_second_review_completed",
        "visual_spec_cooling_off_completed",
        "second_review_completed",
        "cooling_off_completed",
    )
    completed_at_keys = (
        f"{scope}_second_review_completed_at",
        f"{scope}_cooling_off_completed_at",
        "visual_spec_second_review_completed_at",
        "visual_spec_cooling_off_completed_at",
        "second_review_completed_at",
        "cooling_off_completed_at",
    )
    until_keys = (
        f"{scope}_cooling_off_until",
        "visual_spec_cooling_off_until",
        "cooling_off_until",
    )
    for frontmatter in (ctx.vs_frontmatter(), ctx.ticket_frontmatter()):
        if _frontmatter_bool(frontmatter, bool_keys):
            return True
        if _recent_frontmatter_timestamp(frontmatter, completed_at_keys, hours=cooling_hours):
            return True
        if _cooling_until_elapsed(frontmatter, until_keys, hours=cooling_hours):
            return True
    return False


def _map_rate_payload(ctx: GateContext, payload: dict[str, Any], *, scope: str) -> dict[str, Any]:
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict == "ok":
        return make_check_result("pass", payload)
    if verdict == "yellow":
        details = dict(payload)
        details["warning"] = f"{scope}_yellow_alert"
        return make_check_result("pass", details)
    if verdict == "red":
        details = dict(payload)
        details["red_control_completed"] = governance_red_control_completed(ctx, scope=scope, payload=payload)
        return make_check_result("pass" if details["red_control_completed"] else "fail", details)
    if verdict == "error" or payload.get("_returncode", 0) != 0:
        return make_check_result("error", payload, error_message=str(payload.get("error") or "rate helper failed"))
    return make_check_result("error", payload, error_message=f"Unexpected rate helper verdict: {verdict or 'missing'}")


def _run_check_82(ctx: GateContext) -> dict[str, Any]:
    brief_score = ctx.brief_score()
    specificity_score = ctx.specificity_score()
    if brief_score is None or specificity_score is None:
        return make_check_result("skipped", "Need both brief and VS specificity scores.")
    if not COLLUSION_BASELINE.exists():
        return make_check_result("skipped", "cold_start_no_baseline")
    with tempfile.TemporaryDirectory(prefix="oneshot-collusion-") as tmp:
        tmp_path = Path(tmp)
        brief_score_path = tmp_path / "brief-score.json"
        vs_score_path = tmp_path / "vs-score.json"
        brief_score_path.write_text(json.dumps(brief_score, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        vs_score_path.write_text(json.dumps(specificity_score, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload = run_json_helper(
            [
                sys.executable,
                str(SCRIPT_DIR / "detect_brief_contract_collusion.py"),
                "--brief-score-json",
                str(brief_score_path),
                "--vs-score-json",
                str(vs_score_path),
                "--historical-baseline",
                str(COLLUSION_BASELINE),
            ]
        )
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict == "pass":
        return make_check_result("pass", payload)
    if verdict == "fail":
        return make_check_result("fail", payload)
    if verdict == "cold_start":
        return make_check_result("skipped", payload)
    return make_check_result("error", payload, error_message=f"Unexpected collusion helper verdict: {verdict or 'missing'}")


def _run_check_83(ctx: GateContext) -> dict[str, Any]:
    operator_id = ctx.operator_id()
    if not operator_id:
        return make_check_result("skipped", "no_operator_id_in_frontmatter")
    payload = run_json_helper(
        [
            sys.executable,
            str(SCRIPT_DIR / "check_operator_waiver_rate.py"),
            "--waivers-log",
            str(WAIVER_LOG),
            "--operator-id",
            operator_id,
        ]
    )
    return _map_rate_payload(ctx, payload, scope="operator_waiver_rate")


def _run_check_84(ctx: GateContext) -> dict[str, Any]:
    operator_id = ctx.operator_id()
    if not operator_id:
        return make_check_result("skipped", "no_operator_id_in_frontmatter")
    payload = run_json_helper(
        [
            sys.executable,
            str(SCRIPT_DIR / "check_unsupported_medium_approval_rate.py"),
            "--proposals-dir",
            str(UNSUPPORTED_MEDIUM_PROPOSALS_DIR),
            "--operator-id",
            operator_id,
        ]
    )
    return _map_rate_payload(ctx, payload, scope="unsupported_medium_approval_rate")


def _run_check_85(ctx: GateContext) -> dict[str, Any]:
    path = VAULT_ROOT / "config" / "lock-backend.json"
    if not path.exists():
        return make_check_result("fail", {"path": rel_or_abs(path), "reason": "missing"})
    payload = load_json(path)
    return make_check_result("pass" if payload.get("probe_passed") is True else "fail", payload)


def _run_check_86(ctx: GateContext) -> dict[str, Any]:
    payload = ctx.clock_skew_report()
    if payload is None:
        return make_check_result("fail", "Clock skew report unavailable.")
    if payload.get("multi_host_detected") is not True:
        return make_check_result("not_applicable", payload)
    passed = payload.get("ntp_synced") is True and payload.get("skew_within_bounds") is True and payload.get("_returncode") == 0
    return make_check_result("pass" if passed else "fail", payload)


def _run_check_87(ctx: GateContext) -> dict[str, Any]:
    try:
        profile = get_profile(ctx.profile_name)
    except KeyError as exc:
        return make_check_result("fail", {"profile": ctx.profile_name}, error_message=str(exc))
    return make_check_result("pass", {"profile": ctx.profile_name, "description": profile.get("description")})


def _run_check_88(ctx: GateContext) -> dict[str, Any]:
    elapsed = ctx.elapsed_seconds()
    max_runtime = float(ctx.profile.get("max_runtime_s") or 0)
    verdict = "pass" if elapsed <= max_runtime else "fail"
    return make_check_result(verdict, {"elapsed_seconds": round(elapsed, 3), "max_runtime_s": max_runtime})


def _run_check_89(ctx: GateContext) -> dict[str, Any]:
    items = artifact_manifest_items(ctx)
    if not items:
        return make_check_result("not_applicable", "not_applicable_no_artifact_manifest")
    checked = []
    failures = []
    for item in items:
        if not str(item.get("locked_artifact_path") or "").strip():
            continue
        producer_id, source = producer_id_for_manifest_item(ctx, item)
        producer = find_producer_record(ctx, producer_id) if producer_id else None
        state = str(producer.get("state") or "") if producer else ""
        record = {
            "artifact_id": item.get("id"),
            "artifact_type": item.get("type"),
            "producer_id": producer_id,
            "producer_id_source": source,
            "state": state or None,
        }
        checked.append(record)
        if producer is None:
            failures.append({**record, "reason": "producer_not_found"})
        elif state not in ACTIVE_PRODUCER_STATES:
            failures.append({**record, "reason": "producer_not_active_at_gate_run"})
    if not checked:
        return make_check_result("not_applicable", "artifact_manifest_has_no_locked_artifacts")
    return make_check_result("pass" if not failures else "fail", {"checked": checked, "failures": failures})


def _run_check_90(ctx: GateContext) -> dict[str, Any]:
    items = artifact_manifest_items(ctx)
    if not items:
        return make_check_result("not_applicable", "not_applicable_no_artifact_manifest")
    slot_items = [item for item in items if isinstance(item.get("slot_contract"), dict)]
    if not slot_items:
        return make_check_result("not_applicable", "not_applicable_no_slot_contracts")
    failures = [
        {
            "artifact_id": item.get("id"),
            "slot": item.get("slot"),
            "slot_integration_gate_result": item.get("slot_integration_gate_result"),
        }
        for item in slot_items
        if str(item.get("slot_integration_gate_result") or "").strip().lower() != "pass"
    ]
    return make_check_result("pass" if not failures else "fail", {"slot_contract_count": len(slot_items), "failures": failures})


def _run_check_91(ctx: GateContext) -> dict[str, Any]:
    if not artifact_manifest_items(ctx):
        return make_check_result("not_applicable", "not_applicable_no_artifact_manifest")
    signoff = coherence_signoff(ctx)
    if not signoff:
        return make_check_result("fail", "coherence_signoff missing.")
    binding_failures = coherence_report_binding_failures(ctx, signoff)
    failed_fields = [
        field
        for field in COHERENCE_CHECK_FIELDS
        if not coherence_check_passed(field, signoff.get(field))
    ]
    overall = str(signoff.get("verdict") or "").strip().lower()
    if overall != "pass":
        failed_fields.append("verdict")
    return make_check_result(
        "pass" if not failed_fields and not binding_failures else "fail",
        {
            "failed_fields": failed_fields,
            "coherence_verdict": overall or None,
            "binding_failures": binding_failures,
            "message": "coherence_signoff inconsistent with recomputed values." if binding_failures else None,
        },
    )


def _run_check_92(ctx: GateContext) -> dict[str, Any]:
    if not artifact_manifest_items(ctx):
        return make_check_result("not_applicable", "not_applicable_no_artifact_manifest")
    signoff = coherence_signoff(ctx)
    if not signoff:
        return make_check_result("fail", "coherence_signoff missing.")
    missing = [field for field in COHERENCE_CHECK_FIELDS if not isinstance(signoff.get(field), dict) or not signoff.get(field)]
    trivial_details = []
    fail_details_without_computation = []
    for field in COHERENCE_CHECK_FIELDS:
        check = signoff.get(field)
        if not isinstance(check, dict) or not check:
            continue
        if not details_substantive(check.get("details")):
            trivial_details.append(field)
        if str(check.get("verdict") or "").strip().lower() == "fail" and not fail_details_reference_computation(field, check):
            fail_details_without_computation.append(field)
    assessment = normalize_text(signoff.get("reviewer_qualitative_assessment"))
    assessment_ok = len(assessment) >= 40
    return make_check_result(
        "pass" if not missing and not trivial_details and not fail_details_without_computation and assessment_ok else "fail",
        {
            "missing_or_empty_fields": missing,
            "trivial_or_empty_details_fields": trivial_details,
            "fail_details_without_computation": fail_details_without_computation,
            "reviewer_qualitative_assessment_chars": len(assessment),
            "reviewer_qualitative_assessment_min_chars": 40,
        },
    )


def _run_check_93(ctx: GateContext) -> dict[str, Any]:
    if not artifact_manifest_items(ctx):
        return make_check_result("not_applicable", "not_applicable_no_artifact_manifest")
    records = centroid_usage_records(ctx)
    if not records:
        return make_check_result("not_applicable", "not_applicable_no_centroid_usage")
    failures = []
    for record in records:
        current = record.get("centroid_version")
        lock_time = record.get("lock_time_centroid_version")
        if current is None or lock_time is None:
            failures.append({**record, "reason": "missing_centroid_or_lock_time_version"})
            continue
        if int(current) < int(lock_time):
            failures.append({**record, "reason": "centroid_version_older_than_lock_time"})
    return make_check_result("pass" if not failures else "fail", {"records": records, "failures": failures})


def _run_check_94(ctx: GateContext) -> dict[str, Any]:
    mode = str(ctx.vs_frontmatter().get("visual_quality_target_mode") or "").strip()
    if mode != "custom":
        return make_check_result("not_applicable", {"mode": mode or None})
    cluster_id = str(ctx.vs_frontmatter().get("custom_cohort_cluster_id") or "").strip()
    membership = find_custom_membership(ctx)
    passed = bool(cluster_id) and bool(membership)
    details = {
        "mode": mode,
        "custom_cohort_cluster_id": cluster_id or None,
        "membership_path": rel_or_abs(membership["membership_path"]) if membership.get("membership_path") else None,
        "cohort_id": (membership.get("cohort") or {}).get("cohort_id") if membership else None,
    }
    return make_check_result("pass" if passed else "fail", details)


def _run_check_95(ctx: GateContext) -> dict[str, Any]:
    if not artifact_manifest_items(ctx):
        return make_check_result("not_applicable", "not_applicable_no_artifact_manifest")
    remediated_items = []
    failures = []
    for item in artifact_manifest_items(ctx):
        remediation = item.get("slot_integration_remediation")
        if not isinstance(remediation, dict) or remediation.get("attempted") is not True:
            if str(item.get("slot_integration_gate_result") or "").strip().lower() == "fail":
                failures.append(
                    {
                        "artifact_id": item.get("id"),
                        "slot": item.get("slot"),
                        "reason": "missing_remediation_after_slot_integration_failure",
                    }
                )
            continue
        artifact_id = item.get("id")
        final_verdict = str(remediation.get("final_verdict") or "").strip()
        pin_ok, pin_details = locked_artifact_pin_valid(ctx, item)
        record = {"artifact_id": artifact_id, "final_verdict": final_verdict, "pin": pin_details}
        remediated_items.append(record)
        if final_verdict in {"pass_via_reprompt", "pass_via_substitution"}:
            if not pin_ok or str(item.get("slot_integration_gate_result") or "").strip().lower() != "pass":
                failures.append({**record, "reason": "remediation_pass_without_pinned_passing_artifact"})
            continue
        if final_verdict == "paused_with_incompatibility_report":
            report_path = ctx.resolve_path(remediation.get("incompatibility_report_path"))
            operator_decision = normalize_text(remediation.get("operator_decision"))
            if report_path is None or not report_path.exists() or not operator_decision:
                failures.append(
                    {
                        **record,
                        "incompatibility_report_path": str(report_path) if report_path else None,
                        "operator_decision_recorded": bool(operator_decision),
                        "reason": "missing_report_or_operator_decision",
                    }
                )
            continue
        failures.append({**record, "reason": "unsupported_or_failed_remediation_verdict"})
    if not remediated_items and not failures:
        return make_check_result("not_applicable", "not_applicable_no_slot_integration_failures")
    return make_check_result("pass" if not failures else "fail", {"remediated_items": remediated_items, "failures": failures})


def _run_check_96(ctx: GateContext) -> dict[str, Any]:
    if not artifact_manifest_items(ctx):
        return make_check_result("not_applicable", "not_applicable_no_artifact_manifest")
    signoff = coherence_signoff(ctx)
    if not signoff:
        return make_check_result("fail", "coherence_signoff missing.")
    path = threshold_registry_path(ctx)
    if not path.exists():
        return make_check_result("fail", {"thresholds_path": rel_or_abs(path), "reason": "missing"})
    registry = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(registry, dict):
        return make_check_result("fail", {"thresholds_path": rel_or_abs(path), "reason": "not_mapping"})
    current_version = numeric_version(registry.get("version"))
    applied_version = numeric_version(signoff.get("applied_thresholds_version"))
    prior_justification = normalize_text(signoff.get("documented_prior_thresholds_version_justification"))
    version_ok = applied_version == current_version or (applied_version is not None and applied_version < (current_version or 0) and bool(prior_justification))
    expected = resolve_expected_thresholds(
        registry,
        str(ctx.vs_frontmatter().get("visual_quality_target_medium") or ctx.medium or ""),
        str(ctx.vs_frontmatter().get("visual_quality_target_preset") or ""),
    )
    mismatches = threshold_resolution_mismatches(signoff.get("applied_thresholds_resolution"), expected)
    details = {
        "thresholds_path": rel_or_abs(path),
        "current_version": current_version,
        "applied_thresholds_version": applied_version,
        "version_ok": version_ok,
        "resolution_mismatches": mismatches,
    }
    return make_check_result("pass" if version_ok and not mismatches else "fail", details)


def _run_check_97(ctx: GateContext) -> dict[str, Any]:
    mode = str(ctx.vs_frontmatter().get("visual_quality_target_mode") or "").strip()
    if mode != "custom":
        return make_check_result("not_applicable", {"mode": mode or None})
    cluster_id = str(ctx.vs_frontmatter().get("custom_cohort_cluster_id") or "").strip()
    membership = find_custom_cohort(ctx, cluster_id=cluster_id) if is_uuid(cluster_id) else {}
    passed = is_uuid(cluster_id) and bool(membership)
    details = {
        "mode": mode,
        "custom_cohort_cluster_id": cluster_id or None,
        "uuid_valid": is_uuid(cluster_id),
        "membership_path": rel_or_abs(membership["membership_path"]) if membership.get("membership_path") else None,
        "cohort_id": (membership.get("cohort") or {}).get("cohort_id") if membership else None,
    }
    return make_check_result("pass" if passed else "fail", details)


def _run_check_98(ctx: GateContext) -> dict[str, Any]:
    """Subject-presence contract: when required, locked mockups for declared
    locations must contain the subject in at least one allowed modality."""
    frontmatter = ctx.frontmatter
    contract = frontmatter.get("subject_presence_contract") if isinstance(frontmatter, dict) else None

    if not isinstance(contract, dict):
        return make_check_result("not_applicable", "No subject_presence_contract declared.")

    if contract.get("required") is False:
        waiver = contract.get("waiver_reason")
        if not isinstance(waiver, str) or not waiver.strip():
            return make_check_result("fail", "subject_presence_contract.required=false but waiver_reason missing.")
        return make_check_result("pass", {"waived": True, "reason": waiver})

    subject = contract.get("subject", "")
    required_locations = contract.get("required_locations", []) or []
    allowed_modalities = contract.get("allowed_modalities", []) or []
    if not subject or not required_locations or not allowed_modalities:
        return make_check_result("fail", "subject_presence_contract missing subject, required_locations, or allowed_modalities.")

    locked_mockups = []
    for mockup in (frontmatter.get("mockups") or []):
        if isinstance(mockup, dict) and mockup.get("locked") is True:
            path = mockup.get("path") or mockup.get("source_path")
            if isinstance(path, str):
                locked_mockups.append(path)

    if not locked_mockups:
        return make_check_result("fail", "No locked mockups found for subject-presence check.")

    failures = []
    for location in required_locations:
        location_mockups = [m for m in locked_mockups if location.replace("_", "-") in m.lower() or location.replace("_", "") in m.lower()]
        if not location_mockups:
            failures.append({"location": location, "reason": "no locked mockup matches this location"})
            continue

        location_has_subject = False
        for mockup_path in location_mockups:
            mockup_full_path = ctx.repo_root / mockup_path
            if not mockup_full_path.exists():
                continue
            try:
                content = mockup_full_path.read_text(encoding="utf-8", errors="replace").lower()
            except Exception:
                continue

            has_img_or_svg = ("<img" in content or "<picture" in content
                              or "<svg" in content or "background-image" in content)
            mentions_subject = subject.lower() in content
            has_modality = False
            for modality in allowed_modalities:
                modality_marker = modality.replace("_", "-")
                if modality_marker in content or modality.replace("_", " ") in content:
                    has_modality = True
                    break

            if has_img_or_svg and (mentions_subject or has_modality):
                location_has_subject = True
                break

        if not location_has_subject:
            failures.append({
                "location": location,
                "subject": subject,
                "allowed_modalities": allowed_modalities,
                "checked_mockups": location_mockups,
                "reason": f"locked mockup(s) at {location} contain no <img>/<picture>/<svg>/background-image of {subject} in any of {allowed_modalities}",
            })

    if failures:
        return make_check_result("fail", {"failures": failures, "subject": subject})

    return make_check_result("pass", {
        "subject": subject,
        "required_locations_satisfied": list(required_locations),
    })


CHECK_RUNNERS: dict[int, Callable[[GateContext], dict[str, Any]]] = {
    check_id: globals()[f"_run_check_{check_id}"] for check_id in CHECK_DEFINITIONS if f"_run_check_{check_id}" in globals()
}


def run_single_check(check_id: int, ctx: GateContext) -> dict[str, Any]:
    definition = get_check(check_id)
    start = time.perf_counter()
    try:
        handler = CHECK_RUNNERS.get(check_id)
        if handler is None:
            result = make_check_result("skipped", "Check implementation missing.")
        else:
            result = handler(ctx)
    except Exception as exc:  # pragma: no cover - orchestration guard
        result = make_check_result("error", {"traceback": traceback.format_exc(limit=20)}, error_message=str(exc))
    verdict = str(result.get("verdict") or "error")
    if verdict not in VALID_VERDICTS:
        result = make_check_result("error", {"bad_verdict": verdict}, error_message="handler returned invalid verdict")
    result["id"] = check_id
    result["name"] = definition["name"]
    result["description"] = definition["description"]
    result["runtime_ms"] = int((time.perf_counter() - start) * 1000)
    return result


def staged_groups(selected_checks: list[int]) -> list[list[int]]:
    groups: list[list[int]] = []
    selected_without_budget = [check_id for check_id in selected_checks if check_id != 88]
    for start_id, end_id in CHECK_GROUPS:
        group = [check_id for check_id in selected_without_budget if start_id <= check_id <= end_id]
        if group:
            groups.append(group)
    remaining = [check_id for check_id in selected_without_budget if not any(group and check_id in group for group in groups)]
    if remaining:
        groups.append(remaining)
    return groups


def aggregate_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(result["verdict"] for result in results)
    return {
        "total": len(results),
        "passed": counts["pass"],
        "failed": counts["fail"],
        "skipped": counts["skipped"],
        "errored": counts["error"],
        "not_applicable": counts["not_applicable"],
        "not_run_runtime_budget_exceeded": counts["not_run_runtime_budget_exceeded"],
    }


def overall_verdict(summary: dict[str, int], *, skip_policy: str, budget_exceeded: bool) -> str:
    if budget_exceeded:
        return "fail"
    if summary["failed"] or summary["errored"] or summary["not_run_runtime_budget_exceeded"]:
        return "fail"
    if skip_policy == "fail" and summary["skipped"]:
        return "fail"
    return "pass"


def skip_warnings(results: list[dict[str, Any]], *, skip_policy: str) -> list[str]:
    if skip_policy != "warn":
        return []
    return [
        f"Check {result['id']:02d} {result['name']} skipped: {summarize_details(result.get('details'))}"
        for result in results
        if result.get("verdict") == "skipped"
    ]


def build_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Visual Spec Gate Report",
        "",
        f"- Gate: `{report['gate']}`",
        f"- Profile: `{report['profile']}`",
        f"- Verdict: `{report['verdict']}`",
        f"- Skip policy: `{report.get('effective_skip_policy', report.get('skip_policy', 'pass'))}`",
        f"- Runtime: `{report['runtime_seconds']}`s / max `{report['max_runtime_s']}`s",
        f"- VS: `{report['vs_path']}`",
        f"- References: `{report['references_dir']}`",
        f"- Medium: `{report['medium']}`",
        "",
        "## Summary",
        "",
        f"- Total: {report['summary']['total']}",
        f"- Passed: {report['summary']['passed']}",
        f"- Failed: {report['summary']['failed']}",
        f"- Skipped: {report['summary']['skipped']}",
        f"- Errored: {report['summary']['errored']}",
        f"- Not applicable: {report['summary']['not_applicable']}",
        f"- Not run (budget): {report['summary'].get('not_run_runtime_budget_exceeded', 0)}",
    ]
    if report.get("input_warnings"):
        lines.extend(["", "## Input Warnings", ""])
        for warning in report["input_warnings"]:
            lines.append(f"- {warning}")
    if report.get("skip_warnings"):
        lines.extend(["", "## Skip Warnings", ""])
        for warning in report["skip_warnings"]:
            lines.append(f"- {warning}")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for check in report["checks"]:
        grouped.setdefault(check_id_section(check["id"]), []).append(check)
    for section in [label for _range, label in SECTION_LABELS]:
        checks = grouped.get(section)
        if not checks:
            continue
        lines.extend(["", f"## {section}", ""])
        for check in checks:
            lines.append(
                f"- [{check['verdict'].upper()}] {check['id']:02d} `{check['name']}` "
                f"({check['runtime_ms']}ms) — {summarize_details(check.get('details'))}"
            )
            if check.get("error_message"):
                lines.append(f"  error: {check['error_message']}")
    return "\n".join(lines).rstrip() + "\n"


def build_json_report(ctx: GateContext, results: list[dict[str, Any]], *, budget_exceeded: bool) -> dict[str, Any]:
    summary = aggregate_summary(results)
    runtime_seconds = round(ctx.elapsed_seconds(), 3)
    skip_policy = effective_skip_policy(ctx.profile, strict=ctx.args.strict)
    return {
        "gate": "visual-spec",
        "profile": ctx.profile_name,
        "skip_policy": ctx.profile.get("skip_policy", "pass"),
        "effective_skip_policy": skip_policy,
        "strict": bool(ctx.args.strict),
        "ran_at": ctx.started_at.isoformat(timespec="seconds"),
        "vs_path": str(ctx.vs_path) if ctx.vs_path else "",
        "references_dir": str(ctx.references_dir) if ctx.references_dir else "",
        "ticket_path": str(ctx.ticket_path) if ctx.ticket_path else "",
        "medium": ctx.medium,
        "runtime_seconds": runtime_seconds,
        "runtime_budget_s": ctx.profile.get("target_runtime_s"),
        "max_runtime_s": ctx.profile.get("max_runtime_s"),
        "budget_exceeded": budget_exceeded,
        "input_warnings": ctx.input_warnings,
        "skip_warnings": skip_warnings(results, skip_policy=skip_policy),
        "checks": results,
        "summary": summary,
        "verdict": overall_verdict(summary, skip_policy=skip_policy, budget_exceeded=budget_exceeded),
    }


def emit_report(report: dict[str, Any], *, json_out: str | None, markdown_out: str | None) -> None:
    json_text = json.dumps(report, indent=2, sort_keys=False) + "\n"
    sys.stdout.write(json_text)
    if json_out:
        write_text(Path(json_out).expanduser().resolve(), json_text)
    if markdown_out:
        write_text(Path(markdown_out).expanduser().resolve(), build_markdown_report(report))


def main() -> int:
    args = parse_args()
    profile = get_profile(args.profile)
    cache = CacheStore(CACHE_ROOT, get_cache_categories(args.profile))
    ctx = GateContext(args=args, profile_name=args.profile, profile=profile, cache=cache)
    ctx.validate_inputs()

    selected_checks = list(profile["checks"])
    groups = staged_groups(selected_checks)
    results_by_id: dict[int, dict[str, Any]] = {}
    budget_exceeded = False
    max_runtime = float(profile.get("max_runtime_s") or 0.0)

    for group in groups:
        if budget_exceeded:
            break
        max_workers = min(max(len(group), 1), 8)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_single_check, check_id, ctx): check_id for check_id in group}
            group_results: dict[int, dict[str, Any]] = {}
            for future in concurrent.futures.as_completed(futures):
                check_id = futures[future]
                group_results[check_id] = future.result()
        for check_id in group:
            results_by_id[check_id] = group_results[check_id]
        if ctx.elapsed_seconds() > max_runtime:
            budget_exceeded = True
            break

    if not budget_exceeded and 88 in selected_checks:
        results_by_id[88] = run_single_check(88, ctx)
        if ctx.elapsed_seconds() > max_runtime or results_by_id[88]["verdict"] == "fail":
            budget_exceeded = ctx.elapsed_seconds() > max_runtime

    remaining = [check_id for check_id in selected_checks if check_id not in results_by_id]
    if remaining:
        for check_id in remaining:
            definition = get_check(check_id)
            results_by_id[check_id] = {
                "id": check_id,
                "name": definition["name"],
                "description": definition["description"],
                "verdict": "not_run_runtime_budget_exceeded" if budget_exceeded else "skipped",
                "details": "Skipped because the gate exceeded its runtime budget." if budget_exceeded else "Skipped before execution.",
                "runtime_ms": 0,
            }

    ordered_results = [results_by_id[check_id] for check_id in selected_checks]
    report = build_json_report(ctx, ordered_results, budget_exceeded=budget_exceeded)
    emit_report(report, json_out=args.json_out, markdown_out=args.markdown_out)
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

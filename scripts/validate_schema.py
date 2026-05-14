#!/usr/bin/env python3
"""Validate a JSON, YAML, or YAML-frontmatter artifact against a JSON Schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ARTIFACT_TYPES = {"json", "yaml", "yaml-frontmatter"}


class DependencyError(RuntimeError):
    """Raised when a validation dependency is missing."""


def detect_artifact_type(path: Path) -> str:
    """Infer artifact type from a file suffix."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".md":
        return "yaml-frontmatter"
    raise ValueError(f"Cannot auto-detect artifact type for {path}; pass --artifact-type.")


def load_yaml_text(text: str) -> Any:
    """Load YAML text with PyYAML."""
    try:
        import yaml
    except ImportError as exc:
        raise DependencyError("validate_schema.py requires PyYAML. Install with: python3 -m pip install PyYAML") from exc
    loaded = yaml.safe_load(text)
    return loaded if loaded is not None else {}


def load_frontmatter(path: Path) -> Any:
    """Load the first YAML frontmatter block from a markdown file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} does not start with YAML frontmatter.")
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        raise ValueError(f"{path} has no closing YAML frontmatter delimiter.")
    return load_yaml_text("\n".join(lines[1:closing_index]))


def load_artifact(path: Path, artifact_type: str | None = None) -> Any:
    """Load an artifact according to the requested or inferred type."""
    resolved = path.expanduser().resolve()
    resolved_type = artifact_type or detect_artifact_type(resolved)
    if resolved_type not in ARTIFACT_TYPES:
        raise ValueError(f"Unsupported artifact type {resolved_type!r}.")
    if resolved_type == "json":
        return json.loads(resolved.read_text(encoding="utf-8"))
    if resolved_type == "yaml":
        return load_yaml_text(resolved.read_text(encoding="utf-8"))
    return load_frontmatter(resolved)


def json_pointer(parts: Any) -> str:
    """Format a deque-like jsonschema path as a JSON pointer."""
    items = list(parts)
    if not items:
        return "/"
    escaped = [str(item).replace("~", "~0").replace("/", "~1") for item in items]
    return "/" + "/".join(escaped)


def validate_artifact(artifact_path: Path, schema_path: Path, artifact_type: str | None = None) -> dict[str, Any]:
    """Validate an artifact against a Draft 2020-12 JSON Schema."""
    try:
        import jsonschema
    except ImportError as exc:
        raise DependencyError("validate_schema.py requires jsonschema. Install with: python3 -m pip install jsonschema") from exc

    artifact_resolved = artifact_path.expanduser().resolve()
    schema_resolved = schema_path.expanduser().resolve()
    instance = load_artifact(artifact_resolved, artifact_type)
    schema = json.loads(schema_resolved.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))

    return {
        "artifact": str(artifact_resolved),
        "schema": str(schema_resolved),
        "valid": not errors,
        "errors": [
            {
                "path": json_pointer(error.path),
                "message": error.message,
                "schema_path": json_pointer(error.schema_path),
            }
            for error in errors
        ],
    }


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
    parser.add_argument("--artifact", required=True, help="JSON/YAML/markdown artifact path.")
    parser.add_argument("--schema", required=True, help="JSON Schema path.")
    parser.add_argument("--artifact-type", choices=sorted(ARTIFACT_TYPES), help="Override artifact type detection.")
    parser.add_argument("--json-out", help="Optional path to write the JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = validate_artifact(Path(args.artifact), Path(args.schema), args.artifact_type)
    except DependencyError as exc:
        data = {"artifact": str(Path(args.artifact)), "schema": str(Path(args.schema)), "valid": False, "errors": [{"path": "/", "message": str(exc), "schema_path": "/"}]}
        write_json(data, args.json_out)
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        data = {"artifact": str(Path(args.artifact)), "schema": str(Path(args.schema)), "valid": False, "errors": [{"path": "/", "message": str(exc), "schema_path": "/"}]}
        write_json(data, args.json_out)
        return 1
    write_json(data, args.json_out)
    return 0 if data["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())

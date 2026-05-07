#!/usr/bin/env python3
from __future__ import annotations

"""
Multimodal media indexer — indexes images, screenshots, generated video keyframes, PDFs, and visual assets
into ChromaDB using Gemini vision + embeddings.

Text files are NOT indexed here (project-scoped text retrieval handles text search).
This is specifically for visual/media semantic search. Videos are indexed through
generated keyframes rather than raw video blobs.

Usage:
    python3 scripts/index_media.py          # incremental
    python3 scripts/index_media.py --full   # full rebuild
    python3 scripts/index_media.py --paths-from vault/clients/acme/projects/sample-project.derived/image-evidence-index.yaml
"""

import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PLATFORM_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VAULT_DIR = PLATFORM_DIR / "vault"
CHROMA_DIR = PLATFORM_DIR / "data" / "chromadb_media"
INDEX_STATE_FILE = PLATFORM_DIR / "data" / "media_index_state.json"
COLLECTION_NAME = "media_embeddings"

# Source .env
env_file = PLATFORM_DIR / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                # Only load the key we need — don't pull unrelated credentials into memory
                if key.strip() == "GEMINI_API_KEY":
                    os.environ.setdefault(key.strip(), val.strip())

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Media file extensions to index
MEDIA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".bmp"}

# Directories to skip
SKIP_DIRS = {".git", ".obsidian", "node_modules", "__pycache__", ".nexus",
             "chromadb", "chromadb_media", "practice", ".venv", "venv"}

# Max image size for Gemini (4MB)
MAX_IMAGE_SIZE = 4 * 1024 * 1024

# ---------------------------------------------------------------------------
# Gemini Client
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not GEMINI_API_KEY:
        raise EnvironmentError("GEMINI_API_KEY not set. Get one at https://aistudio.google.com/apikey")
    from google import genai
    _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def describe_image(image_path: Path, max_retries: int = 3) -> str:
    """Use Gemini vision to describe an image for embedding. Handles rate limiting."""
    import time
    client = _get_client()

    image_bytes = image_path.read_bytes()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        return ""

    suffix = image_path.suffix.lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }
    mime = mime_map.get(suffix, "image/png")

    from google.genai import types

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime),
                    "Describe this image in detail for search indexing. Include: visual style, colors, layout, text content, UI elements, type of image (screenshot, photo, illustration, logo, chart). Be specific and factual. 2-3 sentences max."
                ],
            )
            return response.text.strip() if response.text else ""
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                # Extract retry delay or default to exponential backoff
                wait = (attempt + 1) * 15  # 15s, 30s, 45s
                print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    return ""


def describe_svg(svg_path: Path) -> str:
    """Extract meaningful content from SVG files."""
    try:
        text = svg_path.read_text(encoding="utf-8", errors="ignore")
        # Extract text elements
        texts = re.findall(r'<text[^>]*>([^<]+)</text>', text)
        # Extract title
        titles = re.findall(r'<title>([^<]+)</title>', text)
        parts = titles + texts
        if parts:
            return f"SVG graphic containing: {', '.join(parts[:20])}"
        return f"SVG graphic ({len(text)} bytes)"
    except Exception:
        return ""


def describe_pdf(pdf_path: Path) -> str:
    """Get basic PDF info for indexing."""
    # Just index the filename and path context — full PDF parsing needs extra deps
    parent = pdf_path.parent.name
    return f"PDF document: {pdf_path.stem}. Located in: {parent}"


def embed_text(text: str, max_retries: int = 3) -> list:
    """Embed text using Gemini text-embedding-004. Handles rate limiting."""
    import time
    client = _get_client()

    for attempt in range(max_retries):
        try:
            result = client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
            )
            return result.embeddings[0].values
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = (attempt + 1) * 10
                print(f"  Embedding rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("embed_text failed after retries")


# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------

_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    import chromadb
    os.makedirs(str(CHROMA_DIR), exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


# ---------------------------------------------------------------------------
# Scanning & Indexing
# ---------------------------------------------------------------------------


def _file_hash(path: Path) -> str:
    try:
        stat = path.stat()
        return hashlib.md5(f"{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()
    except Exception:
        return ""


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(PLATFORM_DIR))
    except ValueError:
        return str(path)


def _should_index(path: Path) -> bool:
    if path.suffix.lower() not in MEDIA_EXTENSIONS:
        return False
    for part in path.parts:
        if part in SKIP_DIRS:
            return False
    try:
        size = path.stat().st_size
        if size < 100 or size > MAX_IMAGE_SIZE:
            return False
    except Exception:
        return False
    return True


def _scan_media_files(target_paths: list[Path] | None = None) -> list:
    if target_paths is not None:
        files = []
        seen: set[str] = set()
        for path in target_paths:
            resolved = path.resolve()
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            if resolved.is_file() and _should_index(resolved):
                files.append(resolved)
        return files
    files = []
    # Scan entire platform dir for media
    for f in PLATFORM_DIR.rglob("*"):
        if f.is_file() and _should_index(f):
            files.append(f)
    return files


def _load_state() -> dict:
    try:
        return json.loads(INDEX_STATE_FILE.read_text())
    except Exception:
        return {}


def _save_state(state: dict):
    os.makedirs(str(INDEX_STATE_FILE.parent), exist_ok=True)
    INDEX_STATE_FILE.write_text(json.dumps(state, indent=2))


def _normalize_target_path(raw_path: str) -> Path:
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = PLATFORM_DIR / path
    return path.resolve()


def load_target_manifest(manifest_path: Path) -> tuple[list[Path], dict[str, dict]]:
    text = manifest_path.read_text(encoding="utf-8")
    metadata_by_rel_path: dict[str, dict] = {}

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = None

    if isinstance(data, dict):
        images = ((data.get("image_evidence") or {}).get("images") or [])
        semantic_paths = data.get("semantic_image_corpus") or []
        paths: list[Path] = []
        if images:
            for image in images:
                raw_path = str(image.get("path", "")).strip()
                if not raw_path:
                    continue
                paths.append(_normalize_target_path(raw_path))
                metadata_by_rel_path[raw_path] = {
                    "project": data.get("project", ""),
                    "client": data.get("client", ""),
                    "evidence_category": image.get("category", ""),
                    "source_docs": ", ".join(image.get("source_docs") or []),
                }
        else:
            paths = [_normalize_target_path(raw_path) for raw_path in semantic_paths if str(raw_path).strip()]
            for raw_path in semantic_paths:
                raw_text = str(raw_path).strip()
                if raw_text:
                    metadata_by_rel_path[raw_text] = {
                        "project": data.get("project", ""),
                        "client": data.get("client", ""),
                    }
        return paths, metadata_by_rel_path

    paths = [_normalize_target_path(line.strip()) for line in text.splitlines() if line.strip()]
    return paths, metadata_by_rel_path


def index_media(full: bool = False, target_paths: list[Path] | None = None, target_metadata: dict[str, dict] | None = None):
    """Index all media files or a targeted subset."""
    collection = _get_collection()
    target_metadata = target_metadata or {}

    if full:
        try:
            existing = collection.get()
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass
        prev_state = {}
    else:
        prev_state = _load_state()

    files = _scan_media_files(target_paths=target_paths)
    new_state = dict(prev_state) if target_paths is not None and not full else {}
    stats = {"scanned": len(files), "added": 0, "updated": 0, "skipped": 0, "errors": 0}

    batch_ids = []
    batch_embeddings = []
    batch_documents = []
    batch_metadatas = []

    for f in files:
        rel_path = _relative_path(f)
        current_hash = _file_hash(f)
        new_state[rel_path] = current_hash

        if not full and prev_state.get(rel_path) == current_hash:
            stats["skipped"] += 1
            continue

        # Describe the media
        suffix = f.suffix.lower()
        try:
            import time
            if suffix == ".svg":
                description = describe_svg(f)
            elif suffix == ".pdf":
                description = describe_pdf(f)
            elif suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
                description = describe_image(f)
                time.sleep(4)  # Rate limit: ~15 requests/min on free tier
            else:
                stats["skipped"] += 1
                continue

            if not description:
                stats["skipped"] += 1
                continue

            # Add file context to description
            context = f"File: {rel_path}\n{description}"
            embedding = embed_text(context)

        except Exception as e:
            print(f"  Error indexing {rel_path}: {e}", file=sys.stderr)
            stats["errors"] += 1
            continue

        # Determine metadata
        client = ""
        project = ""
        parts = Path(rel_path).parts
        if "clients" in parts:
            idx = list(parts).index("clients")
            if idx + 1 < len(parts):
                client = parts[idx + 1]
        if "deliverables" in parts or "snapshots" in parts:
            # Try to find project from nearby project files
            for p in f.parents:
                for proj_file in (p / "projects").glob("*.md") if (p / "projects").exists() else []:
                    project = proj_file.stem
                    break
                if project:
                    break
        manifest_meta = target_metadata.get(rel_path, {})
        client = manifest_meta.get("client", "") or client
        project = manifest_meta.get("project", "") or project

        batch_ids.append(rel_path)
        batch_embeddings.append(embedding)
        batch_documents.append(context[:1000])
        batch_metadatas.append({
            "path": rel_path,
            "filename": f.name,
            "extension": suffix,
            "client": client,
            "project": project,
            "description": description[:500],
            "evidence_category": manifest_meta.get("evidence_category", ""),
            "source_docs": manifest_meta.get("source_docs", ""),
            "media_kind": manifest_meta.get("media_kind", "image"),
            "source_video": manifest_meta.get("source_video", ""),
            "source_video_category": manifest_meta.get("source_video_category", ""),
            "timestamp_seconds": manifest_meta.get("timestamp_seconds"),
            "timestamp_label": manifest_meta.get("timestamp_label", ""),
            "indexed_at": datetime.now().isoformat(),
        })

        if prev_state.get(rel_path):
            stats["updated"] += 1
        else:
            stats["added"] += 1

        # Flush batch
        if len(batch_ids) >= 20:
            collection.upsert(
                ids=batch_ids, embeddings=batch_embeddings,
                documents=batch_documents, metadatas=batch_metadatas,
            )
            batch_ids, batch_embeddings, batch_documents, batch_metadatas = [], [], [], []

    # Flush remaining
    if batch_ids:
        collection.upsert(
            ids=batch_ids, embeddings=batch_embeddings,
            documents=batch_documents, metadatas=batch_metadatas,
        )

    # Remove deleted files only for full-vault mode; targeted mode should not erase
    # unrelated entries from the global media index.
    if not full and target_paths is None:
        deleted = set(prev_state.keys()) - set(new_state.keys())
        if deleted:
            try:
                collection.delete(ids=list(deleted))
                stats["removed"] = len(deleted)
            except Exception:
                pass

    _save_state(new_state)
    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]
    full = "--full" in args
    target_paths = None
    target_metadata = {}
    if "--paths-from" in args:
        idx = args.index("--paths-from")
        if idx + 1 >= len(args):
            raise SystemExit("--paths-from requires a manifest path")
        manifest_path = _normalize_target_path(args[idx + 1])
        target_paths, target_metadata = load_target_manifest(manifest_path)
    stats = index_media(full=full, target_paths=target_paths, target_metadata=target_metadata)

    added = stats.get("added", 0)
    updated = stats.get("updated", 0)

    if added + updated > 0:
        print(f"Media indexed: {added} new, {updated} updated, {stats.get('skipped', 0)} unchanged, {stats.get('errors', 0)} errors")

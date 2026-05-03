#!/usr/bin/env python3
from __future__ import annotations

"""
Project-scoped text semantic retrieval over artifact-index semantic corpora.

This keeps text retrieval curated at the project level instead of relying on
vault-wide embeddings for every conceptual lookup.
"""

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CHROMA_DIR = DATA_DIR / "chromadb"
COLLECTION_NAME = "project_text_embeddings"
INDEXABLE_EXTENSIONS = {".md", ".html", ".py", ".sh", ".txt", ".csv", ".json", ".yaml", ".yml"}
MAX_CONTENT_LENGTH = 6000

_embed_client = None
_collection = None

TITLE_RE = re.compile(r'^title:\s*"?(.+?)"?\s*$', re.M)
TYPE_RE = re.compile(r"^type:\s*(\S+)", re.M)
PROJECT_RE = re.compile(r'^project:\s*"?(.+?)"?\s*$', re.M)
TAGS_RE = re.compile(r"^tags:\s*\[(.+?)\]", re.M)


def source_env() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S %Z %z")


def relative_to_platform(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def normalize_target_path(raw_path: str) -> Path:
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.expanduser().resolve()


def manifest_identity(manifest_data: dict[str, Any]) -> tuple[str, str, str]:
    project = str(manifest_data.get("project") or "").strip()
    client = str(manifest_data.get("client") or "").strip()
    project_key = f"{client}/{project}" if client else project
    return project, client, project_key


def load_manifest_data(manifest_path: Path) -> tuple[dict[str, Any], str]:
    text = manifest_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        data = {}
    return data, text


def load_target_manifest(manifest_path: Path) -> tuple[list[Path], dict[str, dict[str, Any]], dict[str, Any], str]:
    manifest_path = manifest_path.expanduser().resolve()
    data, manifest_text = load_manifest_data(manifest_path)
    project, client, project_key = manifest_identity(data)
    semantic_paths = data.get("semantic_corpus") or []
    target_paths: list[Path] = []
    metadata_by_rel_path: dict[str, dict[str, Any]] = {}

    for raw_path in semantic_paths:
        raw_text = str(raw_path or "").strip()
        if not raw_text:
            continue
        target_paths.append(normalize_target_path(raw_text))
        metadata_by_rel_path[raw_text] = {
            "project": project,
            "client": client,
            "source_project_key": project_key,
            "source_project": project,
        }

    return target_paths, metadata_by_rel_path, data, manifest_text


def file_signature(path: Path) -> str:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return "missing"
    return hashlib.md5(f"{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")).hexdigest()


def corpus_digest(manifest_text: str, target_paths: list[Path]) -> str:
    hasher = hashlib.sha256()
    hasher.update(manifest_text.encode("utf-8"))
    for path in sorted(target_paths, key=lambda item: str(item)):
        rel_path = relative_to_platform(path)
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(file_signature(path).encode("utf-8"))
    return hasher.hexdigest()


def _get_embed_client():
    global _embed_client
    if _embed_client is not None:
        return _embed_client

    source_env()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY environment variable is not set.")

    from google import genai

    _embed_client = genai.Client(api_key=api_key)
    return _embed_client


def embed_text(text: str) -> list[float]:
    client = _get_embed_client()
    result = client.models.embed_content(model="gemini-embedding-001", contents=text)
    return result.embeddings[0].values


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection

    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def extract_content(file_path: Path) -> str:
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    suffix = file_path.suffix.lower()

    if suffix == ".md":
        frontmatter, body = split_frontmatter(text)
        title_match = TITLE_RE.search(frontmatter)
        type_match = TYPE_RE.search(frontmatter)
        project_match = PROJECT_RE.search(frontmatter)
        tags_match = TAGS_RE.search(frontmatter)

        metadata_parts = [f"Title: {title_match.group(1) if title_match else file_path.stem}"]
        if type_match:
            metadata_parts.append(f"Type: {type_match.group(1)}")
        if project_match:
            metadata_parts.append(f"Project: {project_match.group(1)}")
        if tags_match:
            metadata_parts.append(f"Tags: {tags_match.group(1)}")
        content = " | ".join(metadata_parts) + "\n\n" + body
    elif suffix == ".html":
        content = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()
    elif suffix == ".csv":
        content = "\n".join(text.splitlines()[:10])
    elif suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            content = text
        else:
            if isinstance(data, dict):
                content = f"JSON keys: {', '.join(str(key) for key in data.keys())}"
                for key, value in data.items():
                    if isinstance(value, dict):
                        content += f"\n{key}: {', '.join(str(nested) for nested in value.keys())}"
            else:
                content = text
    else:
        content = text

    return content[:MAX_CONTENT_LENGTH]


def parse_file_metadata(file_path: Path, manifest_meta: dict[str, Any]) -> dict[str, Any]:
    text = ""
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass

    title = file_path.stem
    file_type = ""
    project = str(manifest_meta.get("project") or "").strip()

    if file_path.suffix.lower() == ".md" and text:
        title_match = TITLE_RE.search(text)
        type_match = TYPE_RE.search(text)
        project_match = PROJECT_RE.search(text)
        if title_match:
            title = title_match.group(1)
        if type_match:
            file_type = type_match.group(1)
        if project_match:
            project = project_match.group(1)

    return {
        "title": title,
        "type": file_type,
        "project": project,
        "client": str(manifest_meta.get("client") or "").strip(),
        "source_project_key": str(manifest_meta.get("source_project_key") or "").strip(),
        "source_project": str(manifest_meta.get("source_project") or "").strip(),
        "extension": file_path.suffix.lower(),
        "path": relative_to_platform(file_path),
    }


def build_document(file_path: Path, content: str, metadata: dict[str, Any]) -> str:
    title = metadata.get("title") or file_path.stem
    type_label = metadata.get("type") or ""
    path_label = metadata.get("path") or relative_to_platform(file_path)
    header = [f"Path: {path_label}", f"Title: {title}"]
    if type_label:
        header.append(f"Type: {type_label}")
    if metadata.get("project"):
        header.append(f"Project: {metadata['project']}")
    return "\n".join(header) + "\n\n" + content


def corpus_id(source_project_key: str, rel_path: str) -> str:
    return f"{source_project_key}::{rel_path}"


def index_project_text_corpus(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    target_paths, metadata_by_rel_path, manifest_data, _ = load_target_manifest(manifest_path)
    project, client, project_key = manifest_identity(manifest_data)
    collection = _get_collection()

    current_ids = {
        corpus_id(project_key, relative_to_platform(path))
        for path in target_paths
        if relative_to_platform(path)
    }

    existing = collection.get(where={"source_project_key": project_key}, include=["metadatas"])
    existing_ids = set(existing.get("ids") or [])
    stale_ids = sorted(existing_ids - current_ids)
    if stale_ids:
        collection.delete(ids=stale_ids)

    stats = {"scanned": len(target_paths), "added": 0, "updated": 0, "skipped": 0, "errors": 0, "removed": len(stale_ids)}
    batch_ids: list[str] = []
    batch_embeddings: list[list[float]] = []
    batch_documents: list[str] = []
    batch_metadatas: list[dict[str, Any]] = []

    for path in target_paths:
        rel_path = relative_to_platform(path)
        manifest_meta = metadata_by_rel_path.get(rel_path, {})
        if not path.exists() or path.suffix.lower() not in INDEXABLE_EXTENSIONS:
            stats["skipped"] += 1
            continue

        content = extract_content(path)
        if len(content.strip()) < 20:
            stats["skipped"] += 1
            continue

        try:
            metadata = parse_file_metadata(path, manifest_meta)
            document = build_document(path, content, metadata)
            embedding = embed_text(document)
        except Exception:
            stats["errors"] += 1
            continue

        doc_id = corpus_id(project_key, rel_path)
        batch_ids.append(doc_id)
        batch_embeddings.append(embedding)
        batch_documents.append(document[:1000])
        batch_metadatas.append(
            {
                **metadata,
                "client": metadata.get("client") or client,
                "project": metadata.get("project") or project,
                "source_project_key": project_key,
                "source_project": project,
                "indexed_at": datetime.now().isoformat(),
            }
        )
        if doc_id in existing_ids:
            stats["updated"] += 1
        else:
            stats["added"] += 1

        if len(batch_ids) >= 50:
            collection.upsert(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_documents,
                metadatas=batch_metadatas,
            )
            batch_ids, batch_embeddings, batch_documents, batch_metadatas = [], [], [], []

    if batch_ids:
        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            documents=batch_documents,
            metadatas=batch_metadatas,
        )

    return {
        **stats,
        "project": project,
        "client": client,
        "source_project_key": project_key,
        "manifest": relative_to_platform(manifest_path),
    }


def search_project_text(query: str, manifest_path: Path, *, top_k: int = 8) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    manifest_data, _ = load_manifest_data(manifest_path)
    project, client, project_key = manifest_identity(manifest_data)
    collection = _get_collection()
    query_embedding = embed_text(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(1, min(top_k, 20)),
        where={"source_project_key": project_key},
        include=["documents", "metadatas", "distances"],
    )

    output: list[dict[str, Any]] = []
    if results and results.get("ids") and results["ids"][0]:
        for idx, _doc_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][idx] if results.get("metadatas") else {}
            distance = results["distances"][0][idx] if results.get("distances") else 0
            document = results["documents"][0][idx] if results.get("documents") else ""
            output.append(
                {
                    "path": metadata.get("path", ""),
                    "similarity": round(1 - distance, 4),
                    "title": metadata.get("title", ""),
                    "type": metadata.get("type", ""),
                    "project": metadata.get("project", project),
                    "preview": document[:300] if document else "",
                }
            )

    return {
        "query": query,
        "project": project,
        "client": client,
        "results": output,
        "count": len(output),
        "manifest": relative_to_platform(manifest_path),
    }

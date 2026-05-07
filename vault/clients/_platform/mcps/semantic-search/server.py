"""
Semantic Search MCP Server — Vault-wide semantic search using Gemini embeddings + ChromaDB.

Embeds vault files (markdown, HTML, code, CSV headers) into a local ChromaDB vector store.
Agents query it to find relevant files by meaning, not just filename or keyword.

Requires GEMINI_API_KEY environment variable.
"""

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
VAULT_DIR = Path(os.environ.get("VAULT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "vault")))
PLATFORM_DIR = VAULT_DIR.parent
CHROMA_DIR = PLATFORM_DIR / "data" / "chromadb"
COLLECTION_NAME = "vault_embeddings"
INDEX_STATE_FILE = PLATFORM_DIR / "data" / "index_state.json"

# File extensions to index
INDEXABLE_EXTENSIONS = {".md", ".html", ".py", ".sh", ".txt", ".csv", ".json"}

# Max content length for embedding (Gemini limit is 2048 tokens, ~8000 chars)
MAX_CONTENT_LENGTH = 6000

# Directories to skip
SKIP_DIRS = {".git", ".obsidian", "node_modules", "__pycache__", ".nexus",
             ".conversations", ".workspaces", "chromadb"}

# ---------------------------------------------------------------------------
# Gemini Embedding Client
# ---------------------------------------------------------------------------

_embed_client = None


def _get_embed_client():
    """Lazy-init the Gemini embedding client."""
    global _embed_client
    if _embed_client is not None:
        return _embed_client

    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set. "
            "Get a free key at https://aistudio.google.com/apikey"
        )

    from google import genai
    _embed_client = genai.Client(api_key=GEMINI_API_KEY)
    return _embed_client


def embed_text(text: str) -> list[float]:
    """Embed a text string using Gemini text-embedding-004."""
    client = _get_embed_client()
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
    )
    return result.embeddings[0].values


# ---------------------------------------------------------------------------
# ChromaDB Store
# ---------------------------------------------------------------------------

_chroma_collection = None


def _get_collection():
    """Lazy-init ChromaDB collection."""
    global _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection

    import chromadb

    os.makedirs(str(CHROMA_DIR), exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _chroma_collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _chroma_collection


# ---------------------------------------------------------------------------
# Content Extraction
# ---------------------------------------------------------------------------


def _extract_content(file_path: Path) -> str:
    """Extract indexable content from a file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    suffix = file_path.suffix.lower()

    if suffix == ".md":
        # Extract frontmatter + first section of body
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1].strip()
            body = parts[2].strip()
        else:
            frontmatter = ""
            body = text

        # Get title from frontmatter
        title_match = re.search(r'^title:\s*"?(.+?)"?\s*$', frontmatter, re.M)
        title = title_match.group(1) if title_match else file_path.stem

        # Get type, project, tags
        type_match = re.search(r'^type:\s*(\S+)', frontmatter, re.M)
        project_match = re.search(r'^project:\s*"?(.+?)"?\s*$', frontmatter, re.M)
        tags_match = re.search(r'^tags:\s*\[(.+?)\]', frontmatter, re.M)

        metadata_parts = [f"Title: {title}"]
        if type_match:
            metadata_parts.append(f"Type: {type_match.group(1)}")
        if project_match:
            metadata_parts.append(f"Project: {project_match.group(1)}")
        if tags_match:
            metadata_parts.append(f"Tags: {tags_match.group(1)}")

        content = " | ".join(metadata_parts) + "\n\n" + body

    elif suffix == ".html":
        # Strip HTML tags, keep text
        content = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        content = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        content = re.sub(r'<[^>]+>', ' ', content)
        content = re.sub(r'\s+', ' ', content).strip()

    elif suffix == ".csv":
        # Just index headers + first few rows
        lines = text.splitlines()[:10]
        content = "\n".join(lines)

    elif suffix == ".json":
        # Index keys and structure, not full content
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                content = f"JSON keys: {', '.join(data.keys())}"
                # Add first level of nested keys
                for k, v in data.items():
                    if isinstance(v, dict):
                        content += f"\n{k}: {', '.join(v.keys())}"
            else:
                content = text[:MAX_CONTENT_LENGTH]
        except json.JSONDecodeError:
            content = text[:MAX_CONTENT_LENGTH]
    else:
        content = text

    return content[:MAX_CONTENT_LENGTH]


def _file_hash(file_path: Path) -> str:
    """Quick hash of file modification time + size for change detection."""
    try:
        stat = file_path.stat()
        return hashlib.md5(f"{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()
    except Exception:
        return ""


def _relative_path(file_path: Path) -> str:
    """Get path relative to platform dir."""
    try:
        return str(file_path.relative_to(PLATFORM_DIR))
    except ValueError:
        return str(file_path)


def _should_index(file_path: Path) -> bool:
    """Check if a file should be indexed."""
    if file_path.suffix.lower() not in INDEXABLE_EXTENSIONS:
        return False

    # Skip directories
    for part in file_path.parts:
        if part in SKIP_DIRS:
            return False

    # Skip very small files (< 50 bytes) and very large files (> 500KB)
    try:
        size = file_path.stat().st_size
        if size < 50 or size > 500_000:
            return False
    except Exception:
        return False

    return True


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def _load_index_state() -> dict[str, str]:
    """Load the last-indexed file hashes."""
    try:
        return json.loads(INDEX_STATE_FILE.read_text())
    except Exception:
        return {}


def _save_index_state(state: dict[str, str]):
    """Save file hashes after indexing."""
    os.makedirs(str(INDEX_STATE_FILE.parent), exist_ok=True)
    INDEX_STATE_FILE.write_text(json.dumps(state, indent=2))


def _scan_vault_files() -> list[Path]:
    """Find all indexable files in the vault and platform."""
    files = []

    # Index vault
    for f in VAULT_DIR.rglob("*"):
        if f.is_file() and _should_index(f):
            files.append(f)

    # Index skills
    skills_dir = PLATFORM_DIR / "skills"
    if skills_dir.exists():
        for f in skills_dir.glob("*.md"):
            if f.is_file():
                files.append(f)

    # Index scripts
    scripts_dir = PLATFORM_DIR / "scripts"
    if scripts_dir.exists():
        for f in scripts_dir.glob("*.py"):
            if f.is_file():
                files.append(f)

    return files


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("semantic-search")


@mcp.tool()
def search(query: str, top_k: int = 10, file_type: str = "") -> str:
    """Search the vault semantically. Returns the most relevant files for a natural language query.

    Args:
        query: Natural language search query (e.g., "projects similar to restaurant website",
               "stock analysis methodology", "email delivery issues")
        top_k: Number of results to return (default 10, max 30)
        file_type: Optional filter by frontmatter type (e.g., "project", "ticket", "skill", "snapshot")

    Returns:
        JSON with ranked results: file path, relevance score, title, type, and content preview.
    """
    if not query.strip():
        return json.dumps({"error": "Query is required."})

    top_k = max(1, min(30, top_k))

    try:
        query_embedding = embed_text(query)
        collection = _get_collection()

        # Build where clause for type filter
        where = None
        if file_type:
            where = {"type": file_type}

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0
                document = results["documents"][0][i] if results["documents"] else ""

                # Convert cosine distance to similarity (0-1, higher is better)
                similarity = round(1 - distance, 4)

                output.append({
                    "path": metadata.get("path", doc_id),
                    "similarity": similarity,
                    "title": metadata.get("title", ""),
                    "type": metadata.get("type", ""),
                    "project": metadata.get("project", ""),
                    "preview": document[:300] if document else "",
                })

        return json.dumps({"query": query, "results": output, "count": len(output)}, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Search failed: {e}"})


@mcp.tool()
def search_similar(file_path: str, top_k: int = 10) -> str:
    """Find files similar to a given file. Useful for finding related projects, similar briefs, etc.

    Args:
        file_path: Path to the reference file (relative to platform dir or absolute)
        top_k: Number of similar files to return (default 10)

    Returns:
        JSON with ranked similar files.
    """
    # Resolve path
    path = Path(file_path)
    if not path.is_absolute():
        path = PLATFORM_DIR / path

    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        content = _extract_content(path)
        if not content:
            return json.dumps({"error": f"Could not extract content from: {file_path}"})

        query_embedding = embed_text(content)
        collection = _get_collection()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k + 1,  # +1 to exclude self
            include=["documents", "metadatas", "distances"],
        )

        ref_path = _relative_path(path)
        output = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                # Skip the reference file itself
                if metadata.get("path", "") == ref_path:
                    continue

                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = round(1 - distance, 4)

                output.append({
                    "path": metadata.get("path", doc_id),
                    "similarity": similarity,
                    "title": metadata.get("title", ""),
                    "type": metadata.get("type", ""),
                })

                if len(output) >= top_k:
                    break

        return json.dumps({
            "reference": ref_path,
            "similar": output,
            "count": len(output),
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Similarity search failed: {e}"})


@mcp.tool()
def reindex(full: bool = False) -> str:
    """Reindex the vault. Incremental by default (only new/changed files). Set full=True for complete rebuild.

    Args:
        full: If True, rebuild the entire index from scratch. If False, only index new/changed files.

    Returns:
        JSON with indexing stats: files scanned, added, updated, skipped.
    """
    try:
        collection = _get_collection()

        if full:
            # Delete all existing embeddings
            try:
                existing = collection.get()
                if existing["ids"]:
                    collection.delete(ids=existing["ids"])
            except Exception:
                pass
            prev_state = {}
        else:
            prev_state = _load_index_state()

        files = _scan_vault_files()
        new_state = {}
        stats = {"scanned": len(files), "added": 0, "updated": 0, "skipped": 0, "errors": 0}

        # Batch processing
        batch_ids = []
        batch_embeddings = []
        batch_documents = []
        batch_metadatas = []

        for f in files:
            rel_path = _relative_path(f)
            current_hash = _file_hash(f)
            new_state[rel_path] = current_hash

            # Skip if unchanged
            if not full and prev_state.get(rel_path) == current_hash:
                stats["skipped"] += 1
                continue

            # Extract content
            content = _extract_content(f)
            if not content or len(content.strip()) < 20:
                stats["skipped"] += 1
                continue

            try:
                embedding = embed_text(content)
            except Exception:
                stats["errors"] += 1
                continue

            # Extract metadata
            title = f.stem
            file_type = ""
            project = ""

            if f.suffix == ".md":
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                    title_match = re.search(r'^title:\s*"?(.+?)"?\s*$', text, re.M)
                    type_match = re.search(r'^type:\s*(\S+)', text, re.M)
                    proj_match = re.search(r'^project:\s*"?(.+?)"?\s*$', text, re.M)
                    if title_match:
                        title = title_match.group(1)
                    if type_match:
                        file_type = type_match.group(1)
                    if proj_match:
                        project = proj_match.group(1)
                except Exception:
                    pass

            batch_ids.append(rel_path)
            batch_embeddings.append(embedding)
            batch_documents.append(content[:1000])  # Store truncated for previews
            batch_metadatas.append({
                "path": rel_path,
                "title": title,
                "type": file_type,
                "project": project,
                "extension": f.suffix,
                "indexed_at": datetime.now().isoformat(),
            })

            if prev_state.get(rel_path):
                stats["updated"] += 1
            else:
                stats["added"] += 1

            # Flush batch every 50 files (Gemini rate limits)
            if len(batch_ids) >= 50:
                collection.upsert(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    documents=batch_documents,
                    metadatas=batch_metadatas,
                )
                batch_ids, batch_embeddings, batch_documents, batch_metadatas = [], [], [], []

        # Flush remaining
        if batch_ids:
            collection.upsert(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_documents,
                metadatas=batch_metadatas,
            )

        # Remove deleted files from index
        if not full:
            deleted = set(prev_state.keys()) - set(new_state.keys())
            if deleted:
                try:
                    collection.delete(ids=list(deleted))
                    stats["removed"] = len(deleted)
                except Exception:
                    pass

        _save_index_state(new_state)

        return json.dumps(stats, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Indexing failed: {e}"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()

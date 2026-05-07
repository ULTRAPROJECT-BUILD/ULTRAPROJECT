#!/usr/bin/env python3
"""
Semantic media search — find images, screenshots, video keyframes, and visual assets by description.

Usage:
    python3 scripts/search_media.py "green website with bonsai logo"
    python3 scripts/search_media.py "screenshot of mobile hamburger menu" --top 5
    python3 scripts/search_media.py "trust dashboard badge overflow" --project employee-agent-framework
    python3 scripts/search_media.py --similar vault/clients/shly-nonprofit/deliverables/saasybonsai-redesign.html
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

PLATFORM_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Source .env
env_file = PLATFORM_DIR / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if key.strip() == "GEMINI_API_KEY":
                    os.environ.setdefault(key.strip(), val.strip())

sys.path.insert(0, str(PLATFORM_DIR / "scripts"))
from index_media import _get_collection, embed_text, _get_client, describe_image, _relative_path

RETRIEVAL_USAGE_DIR = PLATFORM_DIR / "logs" / "retrieval"


def append_retrieval_usage_event(event: dict) -> None:
    try:
        RETRIEVAL_USAGE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone()
        payload = {
            "timestamp": stamp.isoformat(),
            "date": stamp.strftime("%Y-%m-%d"),
            **event,
        }
        log_path = RETRIEVAL_USAGE_DIR / f"retrieval-{stamp.strftime('%Y-%m-%d')}.jsonl"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception:
        return


def search(
    query: str,
    top_k: int = 10,
    client_filter: str = "",
    project_filter: str = "",
    media_kind_filter: str = "",
    category_prefix: str = "",
) -> list:
    """Search media by natural language description."""
    collection = _get_collection()
    query_embedding = embed_text(query)

    where = None
    if client_filter:
        where = {"client": client_filter}

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
            if project_filter and metadata.get("project", "") != project_filter:
                continue
            if media_kind_filter and metadata.get("media_kind", "") != media_kind_filter:
                continue
            if category_prefix and not str(metadata.get("evidence_category", "")).startswith(category_prefix):
                continue
            distance = results["distances"][0][i] if results["distances"] else 0
            similarity = round(1 - distance, 4)
            output.append({
                "path": metadata.get("path", doc_id),
                "similarity": similarity,
                "client": metadata.get("client", ""),
                "project": metadata.get("project", ""),
                "category": metadata.get("evidence_category", ""),
                "description": metadata.get("description", ""),
                "media_kind": metadata.get("media_kind", ""),
                "source_video": metadata.get("source_video", ""),
                "source_video_category": metadata.get("source_video_category", ""),
                "timestamp_seconds": metadata.get("timestamp_seconds"),
                "timestamp_label": metadata.get("timestamp_label", ""),
            })

    append_retrieval_usage_event(
        {
            "kind": "media_search",
            "query": query,
            "client": client_filter,
            "project": project_filter,
            "media_kind_filter": media_kind_filter,
            "category_prefix": category_prefix,
            "top_k": top_k,
            "result_count": len(output),
            "ticket_id": os.environ.get("AGENT_PLATFORM_TICKET_ID", ""),
            "task_type": os.environ.get("AGENT_PLATFORM_TASK_TYPE", ""),
        }
    )
    return output


def search_similar_image(image_path: str, top_k: int = 10) -> list:
    """Find media visually similar to a given image."""
    path = Path(image_path)
    if not path.is_absolute():
        path = PLATFORM_DIR / path

    # Security: only allow paths within the platform directory
    try:
        path.resolve().relative_to(PLATFORM_DIR.resolve())
    except ValueError:
        print(f"Blocked: path outside platform directory: {image_path}", file=sys.stderr)
        return []

    if not path.exists():
        print(f"File not found: {image_path}", file=sys.stderr)
        return []

    # Describe the reference image
    description = describe_image(path)
    if not description:
        print(f"Could not describe image: {image_path}", file=sys.stderr)
        return []

    # Search for similar
    results = search(description, top_k=top_k + 1)

    # Exclude self
    ref_rel = _relative_path(path)
    return [r for r in results if r["path"] != ref_rel][:top_k]


def main():
    args = sys.argv[1:]

    if not args:
        print("Usage: python3 scripts/search_media.py 'query' [--top N] [--client slug] [--project slug] [--similar path]")
        sys.exit(1)

    top_k = 10
    client_filter = ""
    project_filter = ""
    similar_path = ""
    query_parts = []

    i = 0
    while i < len(args):
        if args[i] == "--top" and i + 1 < len(args):
            top_k = int(args[i + 1])
            i += 2
        elif args[i] == "--client" and i + 1 < len(args):
            client_filter = args[i + 1]
            i += 2
        elif args[i] == "--project" and i + 1 < len(args):
            project_filter = args[i + 1]
            i += 2
        elif args[i] == "--similar" and i + 1 < len(args):
            similar_path = args[i + 1]
            i += 2
        else:
            query_parts.append(args[i])
            i += 1

    if similar_path:
        results = search_similar_image(similar_path, top_k)
    elif query_parts:
        query = " ".join(query_parts)
        results = search(query, top_k, client_filter, project_filter)
    else:
        print("Provide a query or --similar path")
        sys.exit(1)

    # Output as JSON for agent consumption
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

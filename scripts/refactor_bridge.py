#!/usr/bin/env python3
"""Bridge between the automation platform and Refactor Engine.

Invokes Refactor Engine's Python API directly (within this subprocess)
and returns structured JSON via stdout. Every command outputs:

    {"ok": bool, "version": 1, "data": {...}, "error": str|null}

Usage:
    python3 scripts/refactor_bridge.py index --target <path>
    python3 scripts/refactor_bridge.py build-context --target <path> --files <paths> --token-budget <N>
    python3 scripts/refactor_bridge.py analyze --target <path>
    python3 scripts/refactor_bridge.py validate --target <path> --changed-files <paths>
    python3 scripts/refactor_bridge.py query --target <path> --question <text>

Environment:
    REFACTOR_ENGINE_PATH: Path to the Refactor Engine source root.
        Default: vault/clients/davis-digital/deliverables/refactor-engine
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

BRIDGE_VERSION = 1

_EXCLUDED_DIRS = {"build", "dist", "node_modules", ".venv", "__pycache__", ".tox"}
_EXCLUDED_SUFFIXES = {".egg-info"}


def _is_excluded_path(file_path: str) -> bool:
    """Check if entity is from a generated/build artifact directory."""
    parts = file_path.replace("\\", "/").split("/")
    for part in parts:
        if part in _EXCLUDED_DIRS:
            return True
        if any(part.endswith(suffix) for suffix in _EXCLUDED_SUFFIXES):
            return True
    return False


def _sanitize_entity_name(name: str) -> str:
    """Normalize entity names without collapsing valid signature variants."""
    clean_name = re.sub(r"\s+", " ", name.strip().replace("\r", "").replace("\n", " "))
    if "(" in clean_name:
        open_paren = clean_name.index("(")
        if ")" not in clean_name[open_paren:]:
            clean_name = clean_name[:open_paren]
    return clean_name.strip()


def _serialize_unique_entities(entities: list) -> list[tuple[object, dict]]:
    """Filter excluded paths and deduplicate on sanitized output keys."""
    seen: set = set()
    result = []
    for entity in entities:
        if _is_excluded_path(entity.file_path):
            continue
        entity_dict = _entity_to_dict(entity)
        key = (entity_dict["name"], entity_dict["file_path"])
        if key not in seen:
            seen.add(key)
            result.append((entity, entity_dict))
    return result


def _normalized_file_variants(file_path: str, target_path: Path) -> tuple[str, str]:
    """Return relative and absolute path variants for a requested file."""
    raw = file_path.strip().replace("\\", "/")
    requested_path = Path(raw)
    if requested_path.is_absolute():
        abs_path = requested_path.resolve().as_posix()
        try:
            rel_path = requested_path.resolve().relative_to(target_path).as_posix()
        except ValueError:
            rel_path = raw
    else:
        rel_path = raw
        abs_path = (target_path / rel_path).resolve().as_posix()
    return rel_path, abs_path


def _get_indexed_file_set(db, target_path: Path) -> set[str]:
    """Return indexed file paths in both relative and absolute forms."""
    indexed_paths: set[str] = set()
    for state in db.get_all_file_index_states():
        rel_path = state["file_path"].replace("\\", "/")
        indexed_paths.add(rel_path)
        indexed_paths.add((target_path / rel_path).resolve().as_posix())
    if indexed_paths:
        return indexed_paths

    for entity in db.get_all_entities():
        rel_path = entity.file_path.replace("\\", "/")
        indexed_paths.add(rel_path)
        indexed_paths.add((target_path / rel_path).resolve().as_posix())
    return indexed_paths


def _warnings_for_missing_files(
    requested_files: list[str],
    indexed_files: set[str],
    target_path: Path,
) -> list[str]:
    """Return caller-visible warnings for requested files absent from the index."""
    warnings = []
    for requested_file in requested_files:
        rel_path, abs_path = _normalized_file_variants(requested_file, target_path)
        if rel_path not in indexed_files and abs_path not in indexed_files:
            warnings.append(f"requested file not found in index: {requested_file}")
    return warnings


def _get_entities_for_requested_file(graph, requested_file: str, target_path: Path) -> list:
    """Resolve a requested file path against the graph's relative/absolute storage."""
    rel_path, abs_path = _normalized_file_variants(requested_file, target_path)
    entities = graph.get_entities_by_file(rel_path)
    if not entities:
        entities = graph.get_entities_by_file(abs_path)
    return entities

DEFAULT_ENGINE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "vault", "clients", "davis-digital", "deliverables", "refactor-engine",
)


def _resolve_engine_path() -> Path:
    """Resolve and validate the Refactor Engine source path."""
    raw = os.environ.get("REFACTOR_ENGINE_PATH", DEFAULT_ENGINE_PATH)
    p = Path(raw)
    if not p.is_dir():
        _fail(f"Engine not found at {p}. Set REFACTOR_ENGINE_PATH.")
    # Validate engine path contains expected files
    engine_init = p / "refactor_engine" / "__init__.py"
    if not engine_init.exists():
        _fail(f"Engine path {p} does not contain refactor_engine package (missing refactor_engine/__init__.py)")
    # Ensure engine is importable
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
    return p


def _ok(data: dict) -> None:
    """Print success JSON and exit 0."""
    print(json.dumps({"ok": True, "version": BRIDGE_VERSION, "data": data, "error": None}))
    sys.exit(0)


def _fail(msg: str) -> None:
    """Print error JSON and exit 1."""
    print(json.dumps({"ok": False, "version": BRIDGE_VERSION, "data": None, "error": msg}))
    sys.exit(1)


def _entity_to_dict(e) -> dict:
    """Convert a CodeEntity to a JSON-serializable dict."""
    return {
        "id": e.id,
        "kind": e.kind.value,
        "name": _sanitize_entity_name(e.name),
        "file_path": e.file_path,
        "line_start": e.line_start,
        "line_end": e.line_end,
        "language": e.language,
        "complexity_cyclomatic": e.complexity_cyclomatic,
        "complexity_cognitive": e.complexity_cognitive,
        "change_frequency": e.change_frequency,
        "is_dead_code": e.is_dead_code,
        "source_code": e.source_code,
    }


def _ensure_index(target: str) -> tuple:
    """Ensure the target has an index. Returns (config, database, graph).

    If no index exists, runs indexing first.
    """
    from refactor_engine.config import Config
    from refactor_engine.database import Database
    from refactor_engine.knowledge_graph.graph_builder import GraphBuilder
    from refactor_engine.knowledge_graph.indexer import Indexer

    target_path = Path(target).resolve()
    if not target_path.is_dir():
        _fail(f"Target directory not found: {target_path}")

    db_dir = target_path / ".refactor-engine"
    db_path = db_dir / "refactor_engine.db"

    # Detect languages from files present
    lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".java": "java"}
    detected_langs = set()
    for ext, lang in lang_map.items():
        if list(target_path.rglob(f"*{ext}"))[:1]:
            detected_langs.add(lang)
    languages = list(detected_langs) if detected_langs else ["python"]

    cfg = Config(
        target=str(target_path),
        languages=languages,
        database_path=str(db_path),
    )

    db_dir.mkdir(parents=True, exist_ok=True)
    db = Database(str(db_path))
    db.initialize()

    # Check if index exists and has data
    needs_index = db.entity_count() == 0

    if needs_index:
        indexer = Indexer(cfg, db)
        indexer.run()

    # Rebuild graph from database
    graph = GraphBuilder()
    for entity in db.get_all_entities():
        graph.add_entity(entity)
    for rel in db.get_all_relationships():
        graph.add_relationship(rel)

    return cfg, db, graph


# --- Commands ---


def cmd_index(args: argparse.Namespace) -> None:
    """Index a codebase and return stats."""
    try:
        _resolve_engine_path()

        from refactor_engine.config import Config
        from refactor_engine.database import Database
        from refactor_engine.knowledge_graph.indexer import Indexer

        target_path = Path(args.target).resolve()
        if not target_path.is_dir():
            _fail(f"Target directory not found: {target_path}")

        db_dir = target_path / ".refactor-engine"
        db_path = db_dir / "refactor_engine.db"

        lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".java": "java"}
        detected_langs = set()
        for ext, lang in lang_map.items():
            if list(target_path.rglob(f"*{ext}"))[:1]:
                detected_langs.add(lang)
        languages = list(detected_langs) if detected_langs else ["python"]

        unsupported = []
        supported_exts = set(lang_map.keys())
        for f in target_path.rglob("*"):
            if f.is_file() and f.suffix and f.suffix not in supported_exts:
                if not any(part.startswith(".") for part in f.parts):
                    unsupported.append(str(f.relative_to(target_path)))

        cfg = Config(
            target=str(target_path),
            languages=languages,
            database_path=str(db_path),
        )

        db_dir.mkdir(parents=True, exist_ok=True)
        db = Database(str(db_path))
        db.initialize()

        indexer = Indexer(cfg, db)
        report = indexer.run(full=getattr(args, "full", False))

        _ok({
            "files_discovered": report.files_discovered,
            "files_parsed": report.files_parsed,
            "files_skipped": report.files_skipped,
            "files_unchanged": report.files_unchanged,
            "files_deleted": report.files_deleted,
            "entity_count": report.entity_count,
            "relationship_count": report.relationship_count,
            "errors": report.errors,
            "incremental": report.incremental,
            "unsupported_files": unsupported[:50],
            "languages": languages,
        })
    except SystemExit:
        raise
    except Exception as exc:
        _fail(str(exc))


def cmd_build_context(args: argparse.Namespace) -> None:
    """Build token-budgeted context for entities in specified files."""
    try:
        _resolve_engine_path()

        cfg, db, graph = _ensure_index(args.target)

        from refactor_engine.refactoring.context_builder import RefactoringContextBuilder

        file_paths = [f.strip() for f in args.files.split(",") if f.strip()]
        token_budget = args.token_budget

        # Override the refactoring token budget
        cfg.refactoring.max_context_tokens = token_budget

        builder = RefactoringContextBuilder(graph, db, cfg)

        # Find entities in the specified files
        target_path = Path(args.target).resolve()
        indexed_files = _get_indexed_file_set(db, target_path)
        warnings = _warnings_for_missing_files(file_paths, indexed_files, target_path)
        all_contexts = []

        for file_rel in file_paths:
            serialized_entities = _serialize_unique_entities(
                _get_entities_for_requested_file(graph, file_rel, target_path)
            )

            for entity, entity_dict in serialized_entities:
                ctx = builder.build_context(entity)
                callers = [(name, src) for name, src in ctx.caller_sources]
                callees = [(name, src) for name, src in ctx.callee_sources]

                all_contexts.append({
                    "entity": entity_dict,
                    "target_source": ctx.target_source,
                    "interface_contracts": ctx.interface_contracts,
                    "characterization_tests": ctx.characterization_tests,
                    "callers": [{"name": n, "source": s} for n, s in callers],
                    "callees": [{"name": n, "source": s} for n, s in callees],
                    "type_definitions": [{"name": n, "source": s} for n, s in ctx.type_definitions],
                    "siblings": [{"name": n, "source": s} for n, s in ctx.sibling_sources],
                    "total_tokens": ctx.total_tokens,
                })

        _ok({
            "file_paths": file_paths,
            "token_budget": token_budget,
            "warnings": warnings,
            "contexts": all_contexts,
            "entity_count": len(all_contexts),
        })
    except SystemExit:
        raise
    except Exception as exc:
        _fail(str(exc))


def cmd_analyze(args: argparse.Namespace) -> None:
    """Analyze a codebase: domains, hotspots, complexity."""
    try:
        _resolve_engine_path()

        cfg, db, graph = _ensure_index(args.target)

        from refactor_engine.analysis.hotspots import compute_hotspot_scores
        from refactor_engine.decomposer.community_detection import CommunityDetector

        # Hotspots — filter excluded paths, then deduplicate by (name, file_path)
        target_path = Path(args.target).resolve()
        hotspots = compute_hotspot_scores(graph, repo_path=str(target_path), limit=20)
        hotspot_list = []
        for hs in hotspots:
            serialized = _serialize_unique_entities([hs.entity])
            if not serialized:
                continue
            _, entity_dict = serialized[0]
            hotspot_list.append({
                "entity": entity_dict,
                "complexity": hs.complexity,
                "change_frequency": hs.change_frequency,
                "fan_in": hs.fan_in,
                "score": hs.score,
            })

        # Domains
        detector = CommunityDetector(graph, cfg)
        communities = detector.detect()
        domain_list = []
        for c in communities:
            domain_list.append({
                "id": c.community_id,
                "name": f"community-{c.community_id}",
                "entity_count": c.size,
            })

        # Summary stats
        entity_count = graph.entity_count
        relationship_count = graph.relationship_count
        all_entities = db.get_all_entities()
        avg_complexity = 0
        if all_entities:
            avg_complexity = sum(e.complexity_cyclomatic for e in all_entities) / len(all_entities)

        _ok({
            "entity_count": entity_count,
            "relationship_count": relationship_count,
            "average_complexity": round(avg_complexity, 2),
            "domains": domain_list,
            "hotspots": hotspot_list,
        })
    except SystemExit:
        raise
    except Exception as exc:
        _fail(str(exc))


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate changes against the knowledge graph."""
    try:
        _resolve_engine_path()

        cfg, db, graph = _ensure_index(args.target)

        from refactor_engine.validation.blast_radius import BlastRadiusAnalyzer

        changed_files = [f.strip() for f in args.changed_files.split(",") if f.strip()]
        target_path = Path(args.target).resolve()
        indexed_files = _get_indexed_file_set(db, target_path)
        warnings = _warnings_for_missing_files(changed_files, indexed_files, target_path)

        results = []
        for file_rel in changed_files:
            serialized_entities = _serialize_unique_entities(
                _get_entities_for_requested_file(graph, file_rel, target_path)
            )

            for entity, entity_dict in serialized_entities:
                # Blast radius
                br_analyzer = BlastRadiusAnalyzer(graph)
                affected = br_analyzer.analyze(entity.id, max_depth=3)

                # Interface check: callers that depend on this entity
                callers = graph.get_callers(entity.id)

                results.append({
                    "entity": entity_dict,
                    "blast_radius": [
                        {
                            "entity": _entity_to_dict(a.entity),
                            "depth": a.depth,
                            "relationship": a.relationship,
                        }
                        for a in affected
                    ],
                    "blast_radius_count": len(affected),
                    "callers": [_entity_to_dict(c) for c in callers],
                    "caller_count": len(callers),
                    "interface_violations": [],
                    "complexity_cyclomatic": entity.complexity_cyclomatic,
                    "complexity_cognitive": entity.complexity_cognitive,
                    "complexity_deltas": {
                        "cyclomatic": entity.complexity_cyclomatic,
                        "cognitive": entity.complexity_cognitive,
                    },
                })

        _ok({
            "changed_files": changed_files,
            "warnings": warnings,
            "entities_analyzed": len(results),
            "results": results,
            "complexity_deltas": [
                {
                    "entity": r["entity"]["name"],
                    "file": r["entity"]["file_path"],
                    "cyclomatic": r["complexity_deltas"]["cyclomatic"],
                    "cognitive": r["complexity_deltas"]["cognitive"],
                }
                for r in results
            ],
        })
    except SystemExit:
        raise
    except Exception as exc:
        _fail(str(exc))


def cmd_query(args: argparse.Namespace) -> None:
    """Query the knowledge graph with natural language."""
    try:
        _resolve_engine_path()

        cfg, db, graph = _ensure_index(args.target)

        from refactor_engine.knowledge_graph.query import QueryEngine

        engine = QueryEngine(graph)
        result = engine.natural_language_query(args.question)

        serialized_entities = _serialize_unique_entities(result.entities)

        _ok({
            "question": args.question,
            "query_description": result.query_description,
            "total_matches": len(serialized_entities),
            "entities": [entity_dict for _, entity_dict in serialized_entities],
        })
    except SystemExit:
        raise
    except Exception as exc:
        _fail(str(exc))


class _JsonArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that outputs JSON errors instead of plain text."""

    def print_help(self, file=None) -> None:
        print(json.dumps({
            "ok": True,
            "version": BRIDGE_VERSION,
            "data": {"help": self.format_help()},
            "error": None,
        }))

    def error(self, message: str) -> None:
        _fail(f"argument_error: {message}")


def _build_parser() -> _JsonArgumentParser:
    parser = _JsonArgumentParser(
        description="Bridge between platform and Refactor Engine",
    )
    sub = parser.add_subparsers(
        dest="command",
        required=True,
        parser_class=_JsonArgumentParser,
    )

    # index
    p_index = sub.add_parser("index", help="Index a codebase")
    p_index.add_argument("--target", required=True, help="Path to codebase")
    p_index.add_argument("--full", action="store_true", help="Force full re-index")

    # build-context
    p_ctx = sub.add_parser("build-context", help="Build token-budgeted context")
    p_ctx.add_argument("--target", required=True, help="Path to codebase")
    p_ctx.add_argument("--files", required=True, help="Comma-separated file paths (relative to target)")
    p_ctx.add_argument("--token-budget", type=int, default=8000, help="Token budget")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze codebase: domains + hotspots")
    p_analyze.add_argument("--target", required=True, help="Path to codebase")

    # validate
    p_validate = sub.add_parser("validate", help="Validate changes against graph")
    p_validate.add_argument("--target", required=True, help="Path to codebase")
    p_validate.add_argument("--changed-files", required=True, help="Comma-separated changed file paths")

    # query
    p_query = sub.add_parser("query", help="Natural language query")
    p_query.add_argument("--target", required=True, help="Path to codebase")
    p_query.add_argument("--question", required=True, help="Natural language question")
    return parser


def main() -> None:
    parser = _build_parser()

    try:
        args = parser.parse_args()
    except SystemExit as exc:
        if exc.code == 0:
            return
        raise

    try:
        if args.command == "index":
            cmd_index(args)
        elif args.command == "build-context":
            cmd_build_context(args)
        elif args.command == "analyze":
            cmd_analyze(args)
        elif args.command == "validate":
            cmd_validate(args)
        elif args.command == "query":
            cmd_query(args)
    except Exception as exc:
        _fail(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Synchronize viewer.html with the OKF Markdown corpus."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import okf_semantic

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "viewer.html"
OKF_ROOT_FILES = {"index.md", "sources-index.md", "log.md"}
OKF_DIRS = {
    "document",
    "federated",
    "frameworks",
    "glossary",
    "organisations",
    "research",
    "stack",
    "standards",
    "uk-government",
}
# OKF v0.2 requires only ``type`` on concept Markdown.  Reserved index/log
# files are navigation documents and therefore have no concept frontmatter
# (apart from ``okf_version`` on the root index).
REQUIRED_FIELDS = ("type",)
RESERVED_MARKDOWN = {"index.md", "log.md"}
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def iter_okf_markdown() -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*.md"):
        parts = path.relative_to(ROOT).parts
        if not parts or parts[0] in {"_site", "tmp"}:
            continue
        if parts[0] in OKF_DIRS or (len(parts) == 1 and parts[0] in OKF_ROOT_FILES):
            paths.append(path)
    return sorted(paths, key=rel)


def first_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


def first_description(body: str) -> str:
    after_heading = False
    for line in body.splitlines():
        stripped = line.strip()
        if not after_heading:
            after_heading = line.startswith("# ")
            continue
        if not stripped or stripped.startswith(("#", "-", "*", ">")):
            continue
        return stripped
    return ""


def reserved_metadata(path: Path, body: str, declared: dict[str, object] | None = None) -> dict[str, object]:
    metadata = dict(declared or {})
    metadata.update(
        {
            "type": "Log" if path.name == "log.md" else "Index",
            "title": first_heading(body, rel(path)),
            "description": first_description(body),
            "status": "stable",
        }
    )
    return metadata


def parse_frontmatter(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") and path.name in RESERVED_MARKDOWN:
        body = text.strip("\n")
        return reserved_metadata(path, body), body
    try:
        document = okf_semantic.parse_markdown(path)
    except okf_semantic.SemanticError as exc:
        raise ValueError(str(exc).replace(str(ROOT) + "/", "")) from exc
    if path.name in RESERVED_MARKDOWN:
        return reserved_metadata(path, document.body, document.metadata), document.body
    return document.metadata, document.body


def section_for(path_id: str) -> str:
    first = path_id.split("/", 1)[0]
    return first if first in OKF_DIRS else "root"


def resolve_link(source_id: str, href: str) -> str | None:
    href = href.strip()
    if not href or href.startswith("#"):
        return None
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href):
        return None
    href = href.split("#", 1)[0].split("?", 1)[0]
    if not href:
        return None
    href = unquote(href)
    if href.startswith("/"):
        target = Path(href.lstrip("/"))
    else:
        target = Path(source_id).parent / href
    normalized = os.path.normpath(target.as_posix())
    return normalized.replace("\\", "/")


def find_edges(path_id: str, body: str, known_ids: set[str]) -> tuple[list[tuple[str, str]], list[str]]:
    edges: set[tuple[str, str]] = set()
    errors: list[str] = []
    for match in LINK_RE.finditer(body):
        target = resolve_link(path_id, match.group(1))
        if not target:
            continue
        if target.endswith(".md"):
            if target in known_ids:
                edges.add((path_id, target))
            else:
                errors.append(f"{path_id} links to missing Markdown file {target}")
    return sorted(edges), errors


def validate_v02_metadata(path_id: str, meta: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if "timestamp" in meta:
        errors.append(f"{path_id} uses superseded timestamp; use generated.at")
    status = meta.get("status", "stable")
    if status not in {"draft", "stable", "deprecated"}:
        errors.append(f"{path_id} has invalid lifecycle status {status!r}")
    generated = meta.get("generated")
    if generated is not None and (
        not isinstance(generated, dict)
        or not isinstance(generated.get("by"), str)
        or not generated["by"].strip()
    ):
        errors.append(f"{path_id} generated must be a mapping with non-empty by")
    verified = meta.get("verified")
    events = [verified] if isinstance(verified, dict) else verified
    if verified is not None and not isinstance(events, list):
        errors.append(f"{path_id} verified must be a mapping or list")
    elif isinstance(events, list):
        for index, event in enumerate(events):
            if not isinstance(event, dict) or not all(
                isinstance(event.get(key), str) and event[key].strip() for key in ("by", "at")
            ):
                errors.append(f"{path_id} verified[{index}] must contain non-empty by and at")
    sources = meta.get("sources")
    if sources is not None:
        if not isinstance(sources, list):
            errors.append(f"{path_id} sources must be a list")
        else:
            for index, source in enumerate(sources):
                if (
                    not isinstance(source, dict)
                    or not isinstance(source.get("resource"), str)
                    or not source["resource"].strip()
                ):
                    errors.append(f"{path_id} sources[{index}] must contain non-empty resource")
    return errors


def build_graph() -> tuple[dict[str, object], list[str]]:
    nodes: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    parsed: dict[str, tuple[dict[str, object], str]] = {}

    for path in iter_okf_markdown():
        path_id = rel(path)
        try:
            meta, body = parse_frontmatter(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        parsed[path_id] = (meta, body)
        is_reserved = Path(path_id).name in RESERVED_MARKDOWN
        if not is_reserved:
            for field in REQUIRED_FIELDS:
                if not meta.get(field):
                    errors.append(f"{path_id} is missing required frontmatter field {field}")
            errors.extend(validate_v02_metadata(path_id, meta))
        node = dict(meta)
        node.update(
            {
                "type": meta.get("type", ""),
                "title": meta.get("title", path_id),
                "description": meta.get("description", ""),
                "resource": meta.get("resource", ""),
                "aliases": meta.get("aliases", ""),
                "section": section_for(path_id),
                "body": body,
            }
        )
        nodes[path_id] = node

    known_ids = set(nodes)
    edge_set: set[tuple[str, str]] = set()
    for path_id, (_meta, body) in parsed.items():
        edges, link_errors = find_edges(path_id, body, known_ids)
        edge_set.update(edges)
        errors.extend(link_errors)

    graph = {"nodes": nodes, "edges": [list(edge) for edge in sorted(edge_set)]}
    return graph, errors


def rendered_viewer(graph: dict[str, object]) -> str:
    text = VIEWER.read_text(encoding="utf-8")
    start_marker = "const G="
    end_marker = ";\nconst COL="
    start = text.find(start_marker)
    if start == -1:
        raise ValueError("viewer.html does not contain const G=")
    start += len(start_marker)
    end = text.find(end_marker, start)
    if end == -1:
        raise ValueError("viewer.html does not contain const COL= after const G")
    graph_json = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    return text[:start] + graph_json + text[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if viewer.html is not synchronized")
    args = parser.parse_args(argv)

    graph, errors = build_graph()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    if not VIEWER.exists():
        print(
            "canonical graph validated with "
            f"{len(graph['nodes'])} nodes and {len(graph['edges'])} edges; "
            "this publication has no legacy viewer.html template"
        )
        return 0

    updated = rendered_viewer(graph)
    current = VIEWER.read_text(encoding="utf-8")
    if args.check:
        if updated != current:
            print("viewer.html is not synchronized; run python3 scripts/update_viewer.py", file=sys.stderr)
            return 1
        print(f"viewer.html is synchronized with {len(graph['nodes'])} nodes and {len(graph['edges'])} edges")
        return 0

    if updated != current:
        VIEWER.write_text(updated, encoding="utf-8")
        print(f"updated viewer.html with {len(graph['nodes'])} nodes and {len(graph['edges'])} edges")
    else:
        print(f"viewer.html already synchronized with {len(graph['nodes'])} nodes and {len(graph['edges'])} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

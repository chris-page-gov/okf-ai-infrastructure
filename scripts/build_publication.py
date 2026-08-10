#!/usr/bin/env python3
"""Build the deterministic GitHub Pages publication directory."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
from pathlib import Path

import build_okf_bundle
import okf_semantic
import semantic_projection


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bundle"
DIRS = (
    "document",
    "federated",
    "frameworks",
    "glossary",
    "organisations",
    "research",
    "stack",
    "standards",
    "uk-government",
)
FILES = ("index.md", "sources-index.md", "log.md", "okf.config.json")
GENERATED_FILES = (
    "okf-bundle.json",
    "okf-bundle.yamlld",
    "okf-bundle.jsonld",
    "relationships.json",
    "semantic-validation.json",
    "index.html",
)
CHECKSUM_FILE = "checksums.json"
MAX_SOURCE_FILE_BYTES = 4_000_000
MAX_PUBLICATION_FILE_BYTES = 8_000_000


def render_json(value: object, *, compact: bool = False) -> str:
    if compact:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, value: object, *, compact: bool = False) -> None:
    path.write_text(render_json(value, compact=compact), encoding="utf-8")


def publication_source_files(root: Path | None = None) -> dict[str, Path]:
    base = ROOT if root is None else root
    inventory: dict[str, Path] = {}

    for name in FILES:
        path = base / name
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise ValueError(f"publication source is unreadable: {name}: {exc}") from exc
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise ValueError(f"publication source must be a regular non-symlink file: {name}")
        if path.lstat().st_size > MAX_SOURCE_FILE_BYTES:
            raise ValueError(
                f"publication source exceeds the {MAX_SOURCE_FILE_BYTES:,}-byte limit: {name}"
            )
        inventory[name] = path

    for directory in DIRS:
        source_root = base / directory
        try:
            root_mode = source_root.lstat().st_mode
        except OSError as exc:
            raise ValueError(
                f"publication source directory is unreadable: {directory}: {exc}"
            ) from exc
        if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
            raise ValueError(
                f"publication source directory must be a non-symlink directory: {directory}"
            )
        for path in sorted(source_root.rglob("*")):
            relative = path.relative_to(base).as_posix()
            try:
                mode = path.lstat().st_mode
            except OSError as exc:
                raise ValueError(
                    f"publication source is unreadable: {relative}: {exc}"
                ) from exc
            if stat.S_ISLNK(mode):
                raise ValueError(f"publication source must not be a symlink: {relative}")
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise ValueError(f"publication source must be a regular file: {relative}")
            if path.lstat().st_size > MAX_SOURCE_FILE_BYTES:
                raise ValueError(
                    "publication source exceeds the "
                    f"{MAX_SOURCE_FILE_BYTES:,}-byte limit: {relative}"
                )
            if path.suffix != ".md":
                raise ValueError(f"unexpected publication source file: {relative}")
            inventory[relative] = path
    return dict(sorted(inventory.items()))


def read_regular_source(path: Path) -> bytes:
    return okf_semantic.read_regular_file_bytes(
        path,
        max_bytes=MAX_SOURCE_FILE_BYTES,
        label="publication source",
        repository_root=ROOT,
    )


def read_regular_publication_file(path: Path, output: Path) -> bytes:
    return okf_semantic.read_regular_file_bytes(
        path,
        max_bytes=MAX_PUBLICATION_FILE_BYTES,
        label="generated publication file",
        repository_root=output,
    )


def publication_output_inventory(output: Path) -> tuple[set[str], list[str]]:
    files: set[str] = set()
    errors: list[str] = []
    try:
        root_mode = output.lstat().st_mode
    except OSError as exc:
        return files, [f"publication directory is unreadable: {exc}"]
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        return files, ["publication path must be a non-symlink directory"]
    for path in sorted(output.rglob("*")):
        relative = path.relative_to(output).as_posix()
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            errors.append(f"published path is unreadable: {relative}: {exc}")
            continue
        if stat.S_ISLNK(mode):
            errors.append(f"published path must not be a symlink: {relative}")
        elif stat.S_ISDIR(mode):
            continue
        elif stat.S_ISREG(mode):
            files.add(relative)
        else:
            errors.append(f"published path must be a regular file: {relative}")
    return files, errors


def publication_html(
    node_count: int,
    navigation_count: int,
    relationship_count: int,
) -> str:
    concept_count = node_count - navigation_count
    return (
        '<!doctype html><html lang="en-GB"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width">'
        '<title>AI Infrastructure OKF</title><style>'
        'body{font:18px/1.55 system-ui;max-width:850px;margin:4rem auto;padding:0 1.5rem}'
        'a{color:#1d70b8}</style></head><body>'
        '<h1>AI Infrastructure OKF Bundle Wiki</h1>'
        f'<p>OKF v0.2 with {node_count} route-bearing records '
        f'({concept_count} concepts and {navigation_count} reserved navigation records) and '
        f'{relationship_count} evidence-bearing directed relationships.</p>'
        '<p><a href="https://chris-page-gov.github.io/okf-explorer/?bundle='
        'https%3A%2F%2Fchris-page-gov.github.io%2Fokf-ai-infrastructure%2Fokf-bundle.json">'
        'Open in OKF Explorer</a></p><ul>'
        '<li><a href="okf-bundle.yamlld">YAML-LD semantic graph</a></li>'
        '<li><a href="okf-bundle.jsonld">JSON-LD semantic graph</a></li>'
        '<li><a href="okf-bundle.json">Explorer JSON</a></li>'
        '<li><a href="relationships.json">Rich relationship rows</a></li>'
        '<li><a href="semantic-validation.json">Semantic validation receipt</a></li>'
        '<li><a href="index.md">Markdown wiki index</a></li>'
        '<li><a href="checksums.json">Checksums</a></li>'
        '</ul></body></html>\n'
    )


def navigation_record_count(nodes: dict[str, object]) -> int:
    return sum(
        1 for route in nodes if Path(route).name in {"index.md", "log.md"}
    )


def main() -> int:
    source_files = publication_source_files()
    bundle, errors = build_okf_bundle.build_bundle()
    if errors:
        raise ValueError("; ".join(errors))
    semantic = semantic_projection.semantic_graph(bundle)
    semantic_errors = semantic_projection.validate_relationships(bundle, semantic)
    if semantic_errors:
        raise ValueError("; ".join(semantic_errors))

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for relative, source in source_files.items():
        destination = OUT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(read_regular_source(source))

    write_json(OUT / "okf-bundle.json", bundle)
    # JSON is a valid YAML 1.2 representation. One canonical data model keeps
    # the parsed .yamlld and .jsonld structures comparable and deterministic.
    write_json(OUT / "okf-bundle.yamlld", semantic)
    write_json(OUT / "okf-bundle.jsonld", semantic, compact=True)
    corpus = bundle["corpora"]["ai-infrastructure-wiki"]
    write_json(OUT / "relationships.json", corpus["relationships"])
    write_json(
        OUT / "semantic-validation.json",
        semantic_projection.semantic_validation_receipt(bundle, semantic),
    )
    navigation_count = navigation_record_count(corpus["nodes"])
    (OUT / "index.html").write_text(
        publication_html(
            len(corpus["nodes"]),
            navigation_count,
            len(corpus["relationships"]),
        ),
        encoding="utf-8",
    )

    expected_files = set(source_files) | set(GENERATED_FILES)
    actual_files, inventory_errors = publication_output_inventory(OUT)
    if inventory_errors or actual_files != expected_files:
        details = inventory_errors
        details.extend(
            f"generated publication is missing: {relative}"
            for relative in sorted(expected_files - actual_files)
        )
        details.extend(
            f"generated publication has an unexpected file: {relative}"
            for relative in sorted(actual_files - expected_files)
        )
        raise ValueError("; ".join(details))
    rows = {}
    for relative in sorted(expected_files):
        content = read_regular_publication_file(OUT / relative, OUT)
        rows[relative] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }
    write_json(
        OUT / CHECKSUM_FILE,
        {"schema": "okf-checksums.v1", "files": rows},
    )
    print(
        f"published {len(rows):,} files with {len(corpus['nodes']):,} nodes and "
        f"{len(corpus['relationships']):,} rich directed relationships"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate the generated Explorer and semantic publication planes."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

import build_okf_bundle
import build_publication
import semantic_projection


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bundle"
MAX_PUBLICATION_DOCUMENT_BYTES = 8_000_000


def strict_json_document(path: Path) -> object:
    raw = build_publication.read_regular_publication_file(path, OUT)
    if len(raw) > MAX_PUBLICATION_DOCUMENT_BYTES:
        raise ValueError(
            f"{path.name} exceeds the {MAX_PUBLICATION_DOCUMENT_BYTES:,}-byte limit"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key {key!r} in {path.name}")
            value[key] = item
        return value

    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=reject_duplicate_keys,
    )


def main() -> int:
    errors: list[str] = []
    try:
        source_files = build_publication.publication_source_files(ROOT)
    except ValueError as exc:
        print(f"publication source inventory failed: {exc}")
        return 1
    expected_published_files = set(source_files) | set(
        build_publication.GENERATED_FILES
    )
    actual_disk_files, inventory_errors = (
        build_publication.publication_output_inventory(OUT)
    )
    errors.extend(inventory_errors)
    expected_disk_files = expected_published_files | {
        build_publication.CHECKSUM_FILE
    }
    for missing in sorted(expected_disk_files - actual_disk_files):
        errors.append(f"published file is missing: {missing}")
    for extra in sorted(actual_disk_files - expected_disk_files):
        errors.append(f"unexpected published file: {extra}")
    if errors:
        print("publication validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    try:
        bundle = strict_json_document(OUT / "okf-bundle.json")
        semantic_yaml = strict_json_document(OUT / "okf-bundle.yamlld")
        semantic_json = strict_json_document(OUT / "okf-bundle.jsonld")
        relationship_rows = strict_json_document(OUT / "relationships.json")
        semantic_receipt = strict_json_document(OUT / "semantic-validation.json")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"publication document load failed: {exc}")
        return 1

    if not all(
        isinstance(value, dict)
        for value in (bundle, semantic_yaml, semantic_json, semantic_receipt)
    ) or not isinstance(relationship_rows, list):
        print("publication document root types are invalid")
        return 1

    try:
        corpus = bundle["corpora"]["ai-infrastructure-wiki"]
        nodes = corpus["nodes"]
        relationships = corpus.get("relationships", corpus.get("edges", []))
    except (KeyError, TypeError) as exc:
        print(f"publication bundle shape is invalid: {exc}")
        return 1
    if not isinstance(nodes, dict) or not isinstance(relationships, list):
        print("publication bundle nodes or relationships have invalid types")
        return 1
    expected_bundle, build_errors = build_okf_bundle.build_bundle()
    errors.extend(build_errors)
    config = build_okf_bundle.load_config()
    expected_generated_at = build_okf_bundle.bundle_generated_at(config)
    try:
        expected_counts = build_okf_bundle.release_expected_counts(config)
    except ValueError as exc:
        errors.append(str(exc))
        expected_counts = {"nodes": -1, "relationships": -1}
    expected_semantic: dict[str, object] | None = None
    expected_receipt: dict[str, object] | None = None
    expected_documents: dict[str, str] = {}
    if not build_errors:
        expected_semantic = semantic_projection.semantic_graph(expected_bundle)
        if bundle != expected_bundle:
            errors.append("bundle/okf-bundle.json is not synchronised with authored Markdown")
        if semantic_yaml != expected_semantic:
            errors.append("bundle semantic graph is not synchronised with authored Markdown")
        try:
            expected_receipt = semantic_projection.semantic_validation_receipt(
                expected_bundle, expected_semantic
            )
        except ValueError as exc:
            errors.append(f"expected semantic receipt cannot be generated: {exc}")
    if bundle.get("okf_version") != "0.2":
        errors.append("expected OKF 0.2")
    if bundle.get("generated") != {
        "by": "process:okf-ai-infrastructure-publication",
        "at": expected_generated_at,
    }:
        errors.append("missing structured publication provenance")
    if len(nodes) != expected_counts["nodes"]:
        errors.append(
            f"expected {expected_counts['nodes']} nodes, found {len(nodes)}"
        )
    if len(relationships) != expected_counts["relationships"]:
        errors.append(
            "expected "
            f"{expected_counts['relationships']} relationships, found {len(relationships)}"
        )
    if relationship_rows != relationships:
        errors.append("relationships.json differs from the Explorer relationship projection")
    if semantic_yaml != semantic_json:
        errors.append("YAML-LD and JSON-LD do not represent the same semantic graph")
    if semantic_yaml.get("generated") != {
        "by": "process:okf-ai-infrastructure-semantic-projection",
        "at": expected_generated_at,
    }:
        errors.append("missing structured semantic-projection provenance")
    expected_graph_count = len(nodes) + len(relationships)
    if len(semantic_yaml.get("@graph", [])) != expected_graph_count:
        errors.append(
            "expected semantic @graph with "
            f"{len(nodes)} entities and {len(relationships)} assertions"
        )
    relationship_errors = semantic_projection.validate_relationships(
        bundle, semantic_yaml
    )
    errors.extend(relationship_errors)
    if not relationship_errors:
        current_expected_receipt = semantic_projection.semantic_validation_receipt(
            bundle, semantic_yaml
        )
        if semantic_receipt != current_expected_receipt:
            errors.append(
                "semantic-validation.json does not bind the current schema and assertion planes"
            )

    if expected_semantic is not None and expected_receipt is not None:
        expected_corpus = expected_bundle["corpora"]["ai-infrastructure-wiki"]
        navigation_count = build_publication.navigation_record_count(
            expected_corpus["nodes"]
        )
        expected_documents = {
            "okf-bundle.json": build_publication.render_json(expected_bundle),
            "okf-bundle.yamlld": build_publication.render_json(expected_semantic),
            "okf-bundle.jsonld": build_publication.render_json(
                expected_semantic, compact=True
            ),
            "relationships.json": build_publication.render_json(
                expected_corpus["relationships"]
            ),
            "semantic-validation.json": build_publication.render_json(
                expected_receipt
            ),
            "index.html": build_publication.publication_html(
                len(expected_corpus["nodes"]),
                navigation_count,
                len(expected_corpus["relationships"]),
            ),
        }
        for relative, expected_text in expected_documents.items():
            try:
                actual_text = build_publication.read_regular_publication_file(
                    OUT / relative, OUT
                ).decode("utf-8")
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                errors.append(f"generated publication file is unreadable: {relative}: {exc}")
                continue
            if actual_text != expected_text:
                errors.append(
                    f"generated publication file is not byte-exact: {relative}"
                )

    semantic_ids: set[str] = set()
    for node_id, node in nodes.items():
        semantic_id = str(node.get("semantic_id") or "")
        if not semantic_projection.absolute_iri(semantic_id):
            errors.append(f"{node_id} missing absolute semantic_id")
        if semantic_id in semantic_ids:
            errors.append(f"duplicate semantic_id {semantic_id}")
        semantic_ids.add(semantic_id)
        if node_id.endswith("/index.md") or node_id in {"index.md", "log.md"}:
            continue
        if not str(node.get("type", "")).strip():
            errors.append(f"{node_id} missing type")
        if "timestamp" in node:
            errors.append(f"{node_id} retains legacy timestamp")
        if node.get("status") not in {"draft", "stable", "deprecated"}:
            errors.append(f"{node_id} has invalid status")
        sources = node.get("sources")
        if sources is not None and (
            not isinstance(sources, list)
            or any(not isinstance(source, dict) or not source.get("resource") for source in sources)
        ):
            errors.append(f"{node_id} has invalid sources")

    for relative, source_path in source_files.items():
        published_path = OUT / relative
        if relative not in actual_disk_files:
            continue
        try:
            source_content = build_publication.read_regular_source(source_path)
            published_content = build_publication.read_regular_publication_file(
                published_path, OUT
            )
        except (OSError, ValueError) as exc:
            errors.append(f"published source copy cannot be compared: {relative}: {exc}")
            continue
        if source_content != published_content:
            errors.append(f"published source copy is stale: {relative}")

    expected_checksum_document: dict[str, object] | None = None
    if expected_documents:
        expected_contents: dict[str, bytes] = {
            relative: text.encode("utf-8")
            for relative, text in expected_documents.items()
        }
        try:
            expected_contents.update(
                {
                    relative: build_publication.read_regular_source(path)
                    for relative, path in source_files.items()
                }
            )
        except ValueError as exc:
            errors.append(f"publication source cannot be checksummed: {exc}")
        if set(expected_contents) == expected_published_files:
            expected_checksum_document = {
                "schema": "okf-checksums.v1",
                "files": {
                    relative: {
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "bytes": len(content),
                    }
                    for relative, content in sorted(expected_contents.items())
                },
            }

    try:
        checksum_document = strict_json_document(OUT / build_publication.CHECKSUM_FILE)
        if not isinstance(checksum_document, dict):
            raise ValueError("checksums.json root must be an object")
        if checksum_document.get("schema") != "okf-checksums.v1":
            errors.append("checksums.json has the wrong schema")
        declared_files = checksum_document.get("files")
        if not isinstance(declared_files, dict):
            errors.append("checksums.json files must be an object")
            declared_files = {}
        declared_paths = set(declared_files)
        for missing in sorted(expected_published_files - declared_paths):
            errors.append(f"checksum entry is missing: {missing}")
        for extra in sorted(declared_paths - expected_published_files):
            errors.append(f"checksum entry is undeclared: {extra}")
        for relative, expected in declared_files.items():
            portable = PurePosixPath(relative)
            if (
                not relative
                or portable.is_absolute()
                or portable.as_posix() != relative
                or "." in portable.parts
                or ".." in portable.parts
                or "\\" in relative
            ):
                errors.append(f"unsafe checksum path: {relative}")
                continue
            if not isinstance(expected, dict) or set(expected) != {"sha256", "bytes"}:
                errors.append(f"invalid checksum entry shape: {relative}")
                continue
            if not re.fullmatch(r"[0-9a-f]{64}", str(expected.get("sha256") or "")):
                errors.append(f"invalid checksum digest: {relative}")
                continue
            if not isinstance(expected.get("bytes"), int) or expected["bytes"] < 0:
                errors.append(f"invalid checksum byte size: {relative}")
                continue
            path = OUT / relative
            if relative not in actual_disk_files:
                continue
            content = build_publication.read_regular_publication_file(path, OUT)
            actual = hashlib.sha256(content).hexdigest()
            if actual != expected.get("sha256"):
                errors.append(f"checksum mismatch: {relative}")
            if len(content) != expected.get("bytes"):
                errors.append(f"byte-size mismatch: {relative}")
        if expected_checksum_document is not None:
            if checksum_document != expected_checksum_document:
                errors.append("checksums.json does not bind the exact expected publication")
            expected_checksum_text = build_publication.render_json(
                expected_checksum_document
            )
            actual_checksum_text = build_publication.read_regular_publication_file(
                OUT / build_publication.CHECKSUM_FILE, OUT
            ).decode("utf-8")
            if actual_checksum_text != expected_checksum_text:
                errors.append("checksums.json is not in canonical deterministic form")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        errors.append(f"invalid checksums.json: {exc}")

    if errors:
        print("publication validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    node_count = len(nodes)
    relationship_count = len(relationships)
    print(
        "publication validation passed: "
        f"{node_count} nodes, {relationship_count} rich relationships, "
        f"{relationship_count} direct triples, {relationship_count} runtime "
        f"assertions and {relationship_count} reified assertions validated "
        "against the exact shared schema"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

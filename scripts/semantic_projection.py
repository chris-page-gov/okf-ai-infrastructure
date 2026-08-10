#!/usr/bin/env python3
"""Compile the AI infrastructure Markdown graph into rich semantic assertions.

Markdown links are authoritative for direction and endpoints.  They are
projected conservatively as ``dcterms:references``; presentation categories
from the legacy Explorer are retained separately and are never promoted into
unsupported domain predicates.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import okf_semantic


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_BASE = "https://chris-page-gov.github.io/okf-ai-infrastructure/"
PROFILE_CONTEXT_URL = (
    "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
)
SEMANTIC_CONTEXT_URL = (
    "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/semantic-context.jsonld"
)
REFERENCES_PREDICATE = "http://purl.org/dc/terms/references"
DERIVATION_IRI = PUBLIC_BASE + "rules/markdown-reference-normalization-v1"
CC0_IRI = "https://creativecommons.org/publicdomain/zero/1.0/"
ABSOLUTE_IRI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:.+$")
BUILD_INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_RELATIONSHIP_FIELDS = (
    "id",
    "source",
    "target",
    "source_iri",
    "target_iri",
    "predicate",
    "kind",
    "label",
    "inverse_label",
    "assertion_status",
    "assertion_scope",
    "authority",
    "derivation",
    "observed_at",
    "evidence",
    "rights",
)
AUTHORED_ASSERTION_JSON_LD_FIELDS = {"@id", "@type"}
ENTITY_METADATA_FIELDS = {
    "@id",
    "@type",
    "route",
    "type",
    "title",
    "description",
    "status",
    "source_document",
}
INLINE_ASSERTION_CONTEXT: dict[str, Any] = {
    "route": "okf:route",
    "source_document": {"@id": "dcterms:source", "@type": "@id"},
    "source": {"@id": "rdf:subject", "@type": "@id"},
    "source_route": "okf:sourceRoute",
    "predicate": {"@id": "rdf:predicate", "@type": "@id"},
    "target": {"@id": "rdf:object", "@type": "@id"},
    "target_route": "okf:targetRoute",
    "kind": "rdfs:label",
    "label": "rdfs:label",
    "inverse_label": "okf:inverseLabel",
    "presentation_kind": "okf:presentationKind",
    "assertion_status": {
        "@id": "okf:assertionStatus",
        "@type": "@vocab",
    },
    "assertion_scope": {
        "@id": "okf:assertionScope",
        "@type": "@vocab",
    },
    "official": "okf:OfficialAssertion",
    "normalized": "okf:NormalizedAssertion",
    "inferred": "okf:InferredAssertion",
    "model-derived": "okf:ModelDerivedAssertion",
    "real-world": "okf:RealWorldScope",
    "synthetic-fixture": "okf:SyntheticFixtureScope",
    "authority": {
        "@id": "okf:authority",
        "@context": {
            "class": {
                "@id": "okf:authorityClass",
                "@type": "@vocab",
            },
            "official": "okf:OfficialAuthority",
            "derived": "okf:DerivedAuthority",
            "model-assisted": "okf:ModelAssistedAuthority",
            "synthetic": "okf:SyntheticAuthority",
            "unclassified": "okf:UnclassifiedAuthority",
            "label": "rdfs:label",
            "source": {
                "@id": "http://purl.org/dc/terms/source",
                "@type": "@id",
            },
        },
    },
    "derivation": {"@id": "okf:derivationMethod", "@type": "@id"},
    "derivation_activity": {"@id": "prov:wasGeneratedBy", "@type": "@id"},
    "rule": {"@id": "okf:rule", "@type": "@id"},
    "supporting_assertions": {
        "@id": "prov:wasDerivedFrom",
        "@type": "@id",
        "@container": "@set",
    },
    "confidence_score": {
        "@id": "okf:confidenceScore",
        "@type": "xsd:decimal",
    },
    "strength": {
        "@id": "okf:strength",
        "@type": "xsd:decimal",
    },
    "count": {
        "@id": "okf:count",
        "@type": "xsd:integer",
    },
    "observed_at": {"@id": "prov:generatedAtTime", "@type": "xsd:dateTime"},
    "stale_after": {"@id": "okf:staleAfter", "@type": "xsd:dateTime"},
    "review_status": "okf:reviewStatus",
    "freshness": "okf:freshness",
    "evidence": {
        "@id": "prov:hadPrimarySource",
        "@container": "@set",
        "@context": {
            "type": "okf:evidenceType",
            "url": {"@id": "https://schema.org/url", "@type": "@id"},
            "resource": {
                "@id": "http://purl.org/dc/terms/source",
                "@type": "@id",
            },
            "source_artifact": "okf:sourceArtifact",
            "source_sha256": "okf:sourceSha256",
            "source_field": "okf:sourceField",
            "field_provenance": "okf:fieldProvenance",
            "source_value": "okf:sourceValue",
            "source_value_sha256": "okf:sourceValueSha256",
            "source_value_hash_canonicalization": "okf:sourceValueHashCanonicalization",
            "literal_sha256": "okf:literalSha256",
            "locator": "okf:sourceLocator",
            "normalization": {"@id": "okf:normalizationRule", "@type": "@id"},
            "rule_id": {"@id": "okf:rule", "@type": "@id"},
            "rationale": "okf:rationale",
            "retrieved_at": {"@id": "prov:generatedAtTime", "@type": "xsd:dateTime"},
        },
    },
    "rights": {
        "@id": "okf:rights",
        "@context": {
            "source": {
                "@id": "http://purl.org/dc/terms/license",
                "@type": "@id",
            },
            "assertion": "okf:assertionRights",
        },
    },
}


def absolute_iri(value: object) -> bool:
    return isinstance(value, str) and bool(ABSOLUTE_IRI_RE.fullmatch(value))


def projection_activity_iri(generated_at: object) -> str:
    """Bind one deterministic projection activity to its declared build date."""
    if not isinstance(generated_at, str) or not BUILD_INSTANT_RE.fullmatch(generated_at):
        raise ValueError(
            "publicationGeneratedAt must be a UTC instant in YYYY-MM-DDTHH:MM:SSZ form"
        )
    return PUBLIC_BASE + "activities/semantic-projection-" + generated_at[:10]


def route_stem(path_id: str) -> str:
    return path_id.removesuffix(".md")


def entity_iri(path_id: str, node: dict[str, Any]) -> str:
    """Return an authored concept IRI or a deterministic reserved-node IRI."""
    value = str(node.get("@id") or "").strip()
    if value:
        if not absolute_iri(value):
            raise ValueError(f"{path_id} has non-absolute @id {value!r}")
        return value
    if Path(path_id).name not in {"index.md", "log.md"}:
        raise ValueError(f"{path_id} is missing the required authored @id")
    return PUBLIC_BASE + "id/" + route_stem(path_id)


def entity_type_iri(path_id: str, node: dict[str, Any]) -> str | list[str]:
    value = node.get("@type")
    if value:
        return value
    reserved = "Log" if Path(path_id).name == "log.md" else "Index"
    return f"https://chris-page-gov.github.io/okf-explorer/ns#{reserved}"


def _digest(*values: str, length: int | None = None) -> str:
    value = hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()
    return value[:length] if length else value


def rich_relationship(
    source_id: str,
    target_id: str,
    nodes: dict[str, dict[str, Any]],
    *,
    presentation_kind: str,
    observed_at: str,
) -> dict[str, Any]:
    """Create one evidence-bearing reference assertion with `normalized` status."""
    source_iri = entity_iri(source_id, nodes[source_id])
    target_iri = entity_iri(target_id, nodes[target_id])
    digest = _digest(source_iri, REFERENCES_PREDICATE, target_iri, length=24)
    source_path = ROOT / source_id
    source_bytes = okf_semantic.read_regular_file_bytes(
        source_path,
        max_bytes=okf_semantic.MARKDOWN_MAX_BYTES,
        label="relationship evidence Markdown source",
        repository_root=ROOT,
    )
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    source_value_sha256 = _digest(source_id, target_id)
    source_url = PUBLIC_BASE + source_id
    return {
        "schema": "okf-relationship-assertion.v2",
        "id": PUBLIC_BASE + "assertions/" + digest,
        "source": source_id,
        "target": target_id,
        "source_iri": source_iri,
        "target_iri": target_iri,
        "kind": "references",
        "label": "references",
        "inverse_label": "referenced by",
        "predicate": REFERENCES_PREDICATE,
        "presentation_kind": presentation_kind,
        "assertion_status": "normalized",
        "assertion_scope": "real-world",
        "authority": {
            "class": "derived",
            "label": "Deterministic normalisation of an authored local Markdown link",
            "source": source_url,
        },
        "derivation": DERIVATION_IRI,
        "derivation_activity": projection_activity_iri(observed_at),
        "observed_at": observed_at,
        "freshness": "publication-snapshot",
        "evidence": [
            {
                "@id": PUBLIC_BASE + "evidence/markdown-reference/" + digest,
                "type": "authored-markdown-link",
                "url": source_url,
                "source_artifact": source_id,
                "source_sha256": source_sha256,
                "source_field": "local Markdown link",
                "source_value_sha256": source_value_sha256,
                "source_value_hash_canonicalization": "utf8-source-route-null-target-route",
                "locator": f"{source_id} -> {target_id}",
                "normalization": DERIVATION_IRI,
                "retrieved_at": observed_at,
            }
        ],
        "rights": {
            "source": CC0_IRI,
            "assertion": "CC0-1.0 repository-authored reference assertion with `normalized` status",
        },
    }


def _id_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("@id") or "")
    return ""


def _json_ld_control_fields(
    value: object,
    *,
    allowed: set[str] | None = None,
    path: str = "",
) -> list[str]:
    """Return JSON-LD controls that could change assertion expansion.

    Authored declarations consume their root ``@id`` and ``@type`` before
    projection. Nested ``@id`` values are retained for evidence and IRI-value
    objects; no other nested JSON-LD keyword is data in the assertion model.
    """
    permitted = set() if allowed is None else allowed
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            field_path = f"{path}.{key}" if path else str(key)
            if isinstance(key, str) and key.startswith("@"):
                if key not in permitted:
                    errors.append(field_path)
                # A rejected control field owns its subtree. Do not mistake
                # the JSON-LD syntax inside it for additional data fields.
                continue
            errors.extend(
                _json_ld_control_fields(
                    item,
                    allowed={"@id"},
                    path=field_path,
                )
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]" if path else f"[{index}]"
            errors.extend(
                _json_ld_control_fields(
                    item,
                    allowed={"@id"},
                    path=item_path,
                )
            )
    return sorted(errors)


def explicit_relationship(
    source_id: str,
    declaration: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compile one fully authored domain assertion from concept front matter."""
    control_fields = _json_ld_control_fields(
        declaration, allowed=AUTHORED_ASSERTION_JSON_LD_FIELDS
    )
    if control_fields:
        raise ValueError(
            f"{source_id} assertion must not declare assertion-local JSON-LD "
            f"control fields: {', '.join(control_fields)}"
        )
    target_id = str(declaration.get("target_route") or "").strip()
    if not target_id or target_id not in nodes:
        raise ValueError(f"{source_id} assertion has unknown target_route {target_id!r}")
    source_iri = entity_iri(source_id, nodes[source_id])
    target_iri = entity_iri(target_id, nodes[target_id])
    declared_source = _id_value(declaration.get("source"))
    declared_target = _id_value(declaration.get("target"))
    if declared_source and declared_source != source_iri:
        raise ValueError(f"{source_id} assertion source does not match the document @id")
    if declared_target != target_iri:
        raise ValueError(f"{source_id} assertion target does not match target_route {target_id}")
    declared_source_route = str(declaration.get("source_route") or "").strip()
    if declared_source_route and declared_source_route != source_id:
        raise ValueError(
            f"{source_id} assertion source_route does not match its document route"
        )
    assertion_id = str(declaration.get("@id") or declaration.get("id") or "").strip()
    predicate = _id_value(declaration.get("predicate"))
    if not absolute_iri(assertion_id):
        raise ValueError(f"{source_id} assertion requires an absolute @id")
    if not absolute_iri(predicate):
        raise ValueError(f"{source_id} assertion requires an absolute predicate IRI")
    row = {
        **declaration,
        "schema": "okf-relationship-assertion.v2",
        "id": assertion_id,
        "source": source_id,
        "source_iri": source_iri,
        "predicate": predicate,
        "target": target_id,
        "target_iri": target_iri,
        "kind": str(declaration.get("kind") or declaration.get("label") or "").strip(),
        "label": str(declaration.get("label") or declaration.get("kind") or "").strip(),
    }
    row.pop("@id", None)
    row.pop("@type", None)
    row.pop("source_route", None)
    row.pop("target_route", None)
    return row


def authored_relationships(nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Compile explicit domain assertions embedded in Markdown front matter."""
    relationships: list[dict[str, Any]] = []
    for source_id, node in sorted(nodes.items()):
        declarations = node.get("assertions") or []
        if isinstance(declarations, dict):
            declarations = [declarations]
        if not isinstance(declarations, list):
            raise ValueError(f"{source_id} assertions must be a mapping or list")
        for index, declaration in enumerate(declarations):
            if not isinstance(declaration, dict):
                raise ValueError(f"{source_id} assertions[{index}] must be a mapping")
            relationships.append(explicit_relationship(source_id, declaration, nodes))
    return relationships


def semantic_assertion(relationship: dict[str, Any]) -> dict[str, Any]:
    """Map one runtime row to the exact shared-schema semantic assertion."""
    control_fields = _json_ld_control_fields(relationship)
    if control_fields:
        raise ValueError(
            "runtime relationship must not contain assertion-local JSON-LD "
            f"control fields: {', '.join(control_fields)}"
        )
    return {
        "@id": relationship["id"],
        "@type": ["rdf:Statement", "okf:RelationshipAssertion"],
        "source": {"@id": relationship["source_iri"]},
        "source_route": relationship["source"],
        "predicate": {"@id": relationship["predicate"]},
        "target": {"@id": relationship["target_iri"]},
        "target_route": relationship["target"],
        **{
            key: value
            for key, value in relationship.items()
            if key
            not in {
                "schema",
                "id",
                "source",
                "source_iri",
                "source_route",
                "predicate",
                "target",
                "target_iri",
                "target_route",
            }
        },
    }


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def semantic_direct_triples(
    semantic: dict[str, Any],
) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Extract the complete governed direct-triple multiset from entity rows."""
    triples: list[tuple[str, str, str]] = []
    errors: list[str] = []
    graph = semantic.get("@graph", [])
    if not isinstance(graph, list):
        return [], ["semantic @graph must be an array"]
    for index, item in enumerate(graph):
        if not isinstance(item, dict):
            errors.append(f"semantic @graph[{index}] must be an object")
            continue
        item_types = item.get("@type")
        if not isinstance(item_types, list):
            item_types = [item_types]
        if "okf:RelationshipAssertion" in item_types:
            continue
        source = str(item.get("@id") or "")
        if not absolute_iri(source):
            errors.append(f"semantic entity[{index}] has no absolute @id")
        for predicate, raw_values in item.items():
            if predicate in ENTITY_METADATA_FIELDS:
                continue
            if not absolute_iri(predicate):
                errors.append(
                    f"semantic entity {source or index!r} has an ungoverned property: "
                    f"{predicate}"
                )
                continue
            values = raw_values if isinstance(raw_values, list) else [raw_values]
            if not values:
                errors.append(
                    f"semantic entity {source or index!r} has an empty direct predicate: "
                    f"{predicate}"
                )
                continue
            for value_index, value in enumerate(values):
                if not isinstance(value, dict) or set(value) != {"@id"}:
                    errors.append(
                        f"semantic entity {source or index!r} direct predicate "
                        f"{predicate} value[{value_index}] must be exactly an @id object"
                    )
                    continue
                target = value.get("@id")
                if not absolute_iri(target):
                    errors.append(
                        f"semantic entity {source or index!r} direct predicate "
                        f"{predicate} value[{value_index}] has no absolute @id"
                    )
                    continue
                triples.append((source, predicate, target))
    return triples, errors


def semantic_validation_receipt(
    bundle: dict[str, Any], semantic: dict[str, Any]
) -> dict[str, Any]:
    """Bind the exact shared schema and synchronised relationship planes."""
    validation_errors = validate_relationships(bundle, semantic)
    if validation_errors:
        raise ValueError(
            "cannot issue a passing semantic receipt for an invalid projection:\n- "
            + "\n- ".join(validation_errors)
        )
    relationships = bundle["corpora"]["ai-infrastructure-wiki"]["relationships"]
    assertions = sorted(
        (
            item
            for item in semantic["@graph"]
            if isinstance(item, dict)
            and "okf:RelationshipAssertion"
            in (
                item.get("@type")
                if isinstance(item.get("@type"), list)
                else [item.get("@type")]
            )
        ),
        key=lambda item: item["@id"],
    )
    assertion_ids = sorted(relationship["id"] for relationship in relationships)
    direct_triples, direct_errors = semantic_direct_triples(semantic)
    if direct_errors:
        raise ValueError(
            "cannot issue a passing semantic receipt for an invalid direct graph:\n- "
            + "\n- ".join(direct_errors)
        )
    triples = sorted([source, predicate, target] for source, predicate, target in direct_triples)
    return {
        "schema": "okf-semantic-validation-receipt.v1",
        "result": "pass",
        "shared_schema": {
            "$id": okf_semantic.SEMANTIC_ASSERTION_SCHEMA_ID,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "bytes": okf_semantic.SEMANTIC_ASSERTION_SCHEMA_BYTES,
            "sha256": okf_semantic.SEMANTIC_ASSERTION_SCHEMA_SHA256,
        },
        "counts": {
            "entities": len(semantic["@graph"]) - len(assertions),
            "runtime_assertions_validated": len(relationships),
            "semantic_assertions_validated": len(assertions),
            "direct_triples_reconciled": len(triples),
            "validation_failures": 0,
        },
        "digests": {
            "assertion_ids_sha256": _canonical_sha256(assertion_ids),
            "assertion_payload_sha256": _canonical_sha256(assertions),
            "triple_set_sha256": _canonical_sha256(triples),
        },
    }


def semantic_graph(bundle: dict[str, Any]) -> dict[str, Any]:
    """Build direct triples and reified assertions from one runtime bundle."""
    generated = bundle.get("generated")
    generated_at = generated.get("at") if isinstance(generated, dict) else None
    projection_activity_iri(generated_at)
    corpus = bundle["corpora"]["ai-infrastructure-wiki"]
    relationships = corpus.get("relationships", corpus.get("edges", []))
    graph_by_iri: dict[str, dict[str, Any]] = {}
    for route, node in corpus["nodes"].items():
        semantic_id = str(node["semantic_id"])
        entity: dict[str, Any] = {
            "@id": semantic_id,
            "@type": node["semantic_type"],
            "route": route,
            "type": node.get("type", ""),
            "title": node.get("title", route),
            "description": node.get("description", ""),
            "status": node.get("status", "stable"),
            "source_document": {"@id": PUBLIC_BASE + route},
        }
        graph_by_iri[semantic_id] = entity

    for relationship in relationships:
        source_node = graph_by_iri[relationship["source_iri"]]
        value = {"@id": relationship["target_iri"]}
        current = source_node.get(relationship["predicate"])
        if current is None:
            source_node[relationship["predicate"]] = value
        elif isinstance(current, list):
            current.append(value)
        else:
            source_node[relationship["predicate"]] = [current, value]

    assertions = [semantic_assertion(relationship) for relationship in relationships]

    return {
        "@context": [PROFILE_CONTEXT_URL, SEMANTIC_CONTEXT_URL, INLINE_ASSERTION_CONTEXT],
        "@id": PUBLIC_BASE + "semantic/ai-infrastructure",
        "@type": "okf:Bundle",
        "okf_version": "0.2",
        "title": corpus["title"],
        "description": corpus["subtitle"],
        "version": "0.6.0",
        "status": "stable",
        "profile": {
            "@id": "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/"
        },
        "descriptor": {"@id": PUBLIC_BASE + "okf-bundle.json"},
        "semanticDescriptor": {"@id": PUBLIC_BASE + "okf-bundle.yamlld"},
        "home": {"@id": PUBLIC_BASE},
        "publisher": {"@id": "https://github.com/chris-page-gov"},
        "license": {"@id": CC0_IRI},
        "generated": {
            "by": "process:okf-ai-infrastructure-semantic-projection",
            "at": generated_at,
        },
        "@graph": [*graph_by_iri.values(), *assertions],
    }


def validate_relationships(bundle: dict[str, Any], semantic: dict[str, Any]) -> list[str]:
    """Validate routes, IRIs, rich fields and direct/reified lockstep."""
    errors, assertion_validator = okf_semantic.semantic_assertion_schema_validator()
    corpus = bundle["corpora"]["ai-infrastructure-wiki"]
    nodes = corpus["nodes"]
    relationships = corpus.get("relationships", corpus.get("edges", []))
    graph = semantic.get("@graph", [])
    if not isinstance(graph, list):
        return [*errors, "semantic @graph must be an array"]
    entity_rows = [
        item
        for item in graph
        if isinstance(item, dict)
        and "okf:RelationshipAssertion"
        not in (item.get("@type") if isinstance(item.get("@type"), list) else [item.get("@type")])
    ]
    assertion_rows = [
        item
        for item in graph
        if isinstance(item, dict)
        and "okf:RelationshipAssertion"
        in (item.get("@type") if isinstance(item.get("@type"), list) else [item.get("@type")])
    ]
    entity_ids = [str(item.get("@id") or "") for item in entity_rows]
    assertion_ids = [str(item.get("@id") or "") for item in assertion_rows]
    semantic_entities = {str(item.get("@id") or ""): item for item in entity_rows}
    semantic_assertions = {str(item.get("@id") or ""): item for item in assertion_rows}
    for label, identities in (
        ("semantic entity", entity_ids),
        ("semantic assertion", assertion_ids),
    ):
        duplicates = sorted(
            identity for identity, count in Counter(identities).items() if count > 1
        )
        for identity in duplicates:
            errors.append(f"duplicate {label} @id: {identity}")
    expected_entity_ids = {
        entity_iri(route, node) for route, node in nodes.items()
    }
    actual_entity_ids = set(entity_ids)
    for identity in sorted(expected_entity_ids - actual_entity_ids):
        errors.append(f"missing semantic entity: {identity}")
    for identity in sorted(actual_entity_ids - expected_entity_ids):
        errors.append(f"unexpected semantic entity: {identity}")
    expected_assertion_ids = {
        str(relationship.get("id") or "") for relationship in relationships
    }
    actual_assertion_ids = set(assertion_ids)
    for identity in sorted(expected_assertion_ids - actual_assertion_ids):
        errors.append(f"missing semantic assertion: {identity}")
    for identity in sorted(actual_assertion_ids - expected_assertion_ids):
        errors.append(f"unexpected semantic assertion: {identity}")
    seen_ids: set[str] = set()
    seen_triples: set[tuple[str, str, str]] = set()
    expected_direct_triples: Counter[tuple[str, str, str]] = Counter()
    for index, relationship in enumerate(relationships):
        prefix = f"relationship[{index}]"
        missing = [
            field
            for field in REQUIRED_RELATIONSHIP_FIELDS
            if relationship.get(field) in (None, "", [])
        ]
        if missing:
            errors.append(f"{prefix} lacks rich fields: {', '.join(missing)}")
            continue
        control_fields = _json_ld_control_fields(relationship)
        if control_fields:
            errors.append(
                f"{prefix} contains forbidden assertion-local JSON-LD control "
                f"fields: {', '.join(control_fields)}"
            )
            continue
        expected_assertion = semantic_assertion(relationship)
        if assertion_validator is not None:
            errors.extend(
                f"{prefix} runtime projection {error}"
                for error in okf_semantic.validator_errors(
                    expected_assertion, assertion_validator
                )
            )
        for field in ("id", "source_iri", "target_iri", "predicate", "derivation"):
            if not absolute_iri(relationship.get(field)):
                errors.append(f"{prefix} {field} is not an absolute IRI")
        for route_field, iri_field in (
            ("source", "source_iri"),
            ("target", "target_iri"),
        ):
            route = relationship[route_field]
            if route not in nodes:
                errors.append(f"{prefix} has an unresolved {route_field} route endpoint")
                continue
            try:
                expected_iri = entity_iri(route, nodes[route])
            except ValueError as exc:
                errors.append(f"{prefix} {route_field} route has no valid semantic identity: {exc}")
                continue
            if relationship[iri_field] != expected_iri:
                errors.append(
                    f"{prefix} {route_field} route does not identify {iri_field}: "
                    f"expected {expected_iri!r}, got {relationship[iri_field]!r}"
                )
        authority = relationship.get("authority")
        expected_authority = (
            "synthetic"
            if relationship.get("assertion_scope") == "synthetic-fixture"
            else {
                "official": "official",
                "normalized": "derived",
                "inferred": "derived",
                "model-derived": "model-assisted",
            }.get(str(relationship.get("assertion_status") or ""))
        )
        if not isinstance(authority, dict) or authority.get("class") != expected_authority:
            errors.append(f"{prefix} has incompatible assertion status and authority class")
        evidence = relationship.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix} requires evidence")
        else:
            for evidence_index, item in enumerate(evidence):
                if not isinstance(item, dict):
                    errors.append(f"{prefix} evidence[{evidence_index}] must be an object")
                    continue
                for field in ("@id", "url"):
                    if not absolute_iri(item.get(field)):
                        errors.append(f"{prefix} evidence[{evidence_index}].{field} is not an absolute IRI")
                digest = str(item.get("source_value_sha256") or "")
                if not re.fullmatch(r"[0-9a-f]{64}", digest):
                    errors.append(f"{prefix} evidence[{evidence_index}] has invalid source_value_sha256")
        if relationship["id"] in seen_ids:
            errors.append(f"duplicate assertion ID: {relationship['id']}")
        seen_ids.add(relationship["id"])
        triple = (
            relationship["source_iri"],
            relationship["predicate"],
            relationship["target_iri"],
        )
        if triple in seen_triples:
            errors.append(f"duplicate governed runtime triple: {triple!r}")
        seen_triples.add(triple)
        expected_direct_triples[triple] += 1
        assertion = semantic_assertions.get(relationship["id"])
        if not assertion:
            errors.append(f"missing reified assertion: {relationship['id']}")
            continue
        if assertion_validator is not None:
            errors.extend(
                f"{prefix} semantic assertion {error}"
                for error in okf_semantic.validator_errors(
                    assertion, assertion_validator
                )
            )
        if assertion != expected_assertion:
            errors.append(
                "reified assertion differs from the governed runtime projection: "
                f"{relationship['id']}"
            )
        reified = (
            _id_value(assertion.get("source")),
            _id_value(assertion.get("predicate")),
            _id_value(assertion.get("target")),
        )
        if reified != triple:
            errors.append(f"reified assertion differs from runtime triple: {relationship['id']}")
        source_node = semantic_entities.get(relationship["source_iri"], {})
        direct_values = source_node.get(relationship["predicate"], [])
        if not isinstance(direct_values, list):
            direct_values = [direct_values]
        if relationship["target_iri"] not in {_id_value(value) for value in direct_values}:
            errors.append(f"missing direct triple for assertion: {relationship['id']}")
    actual_direct_rows, direct_errors = semantic_direct_triples(semantic)
    errors.extend(direct_errors)
    actual_direct_triples = Counter(actual_direct_rows)
    for triple, count in sorted((expected_direct_triples - actual_direct_triples).items()):
        errors.append(f"direct graph is missing {count} occurrence(s) of triple: {triple!r}")
    for triple, count in sorted((actual_direct_triples - expected_direct_triples).items()):
        errors.append(f"direct graph has {count} unexpected occurrence(s) of triple: {triple!r}")
    if len(entity_rows) != len(nodes):
        errors.append(
            f"semantic entity count {len(entity_rows)} differs from runtime node count {len(nodes)}"
        )
    if len(assertion_rows) != len(relationships):
        errors.append(
            "semantic assertion count "
            f"{len(assertion_rows)} differs from runtime relationship count {len(relationships)}"
        )
    return errors

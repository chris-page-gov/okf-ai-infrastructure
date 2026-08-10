from __future__ import annotations

import copy
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_okf_bundle  # noqa: E402
import build_publication  # noqa: E402
import check_publication  # noqa: E402
import okf_semantic  # noqa: E402
import semantic_projection  # noqa: E402
import update_viewer  # noqa: E402


class OkfSemanticTest(unittest.TestCase):
    fixture_root = ROOT / "tests" / "fixtures" / "yaml_ld"

    def release_counts(self) -> dict[str, int]:
        return build_okf_bundle.release_expected_counts(
            build_okf_bundle.load_config()
        )

    def test_publication_landing_distinguishes_concepts_from_navigation(self) -> None:
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        corpus = bundle["corpora"]["ai-infrastructure-wiki"]
        expected_counts = self.release_counts()
        self.assertEqual(expected_counts["nodes"], len(corpus["nodes"]))
        self.assertEqual(
            expected_counts["relationships"], len(corpus["relationships"])
        )
        navigation_count = build_publication.navigation_record_count(corpus["nodes"])
        self.assertEqual(13, navigation_count)
        html = build_publication.publication_html(
            len(corpus["nodes"]),
            navigation_count,
            len(corpus["relationships"]),
        )
        concept_count = expected_counts["nodes"] - navigation_count
        self.assertIn(
            f"{expected_counts['nodes']} route-bearing records "
            f"({concept_count} concepts and {navigation_count} reserved navigation records)",
            html,
        )
        self.assertIn(
            f"{expected_counts['relationships']} evidence-bearing directed relationships",
            html,
        )

    def test_yaml_ld_frontmatter_parses_and_expands_with_pinned_context(self) -> None:
        page = okf_semantic.parse_markdown(self.fixture_root / "concept.md")
        self.assertEqual("https://example.gov.uk/okf/concepts/example", page.metadata["@id"])
        self.assertEqual(["example", "government"], page.metadata["tags"])
        self.assertEqual("human:fixture-reviewer", page.metadata["verified"]["by"])
        self.assertEqual("https://www.gov.uk/example", page.metadata["sources"][0]["resource"])
        self.assertIn("Human-readable Markdown", page.body)
        self.assertFalse(okf_semantic.schema_errors(page.metadata, "concept.schema.json"))
        expanded = okf_semantic.expand(page.metadata)
        self.assertEqual("https://example.gov.uk/okf/concepts/example", expanded[0]["@id"])
        self.assertIn("http://purl.org/dc/terms/title", expanded[0])

    def test_bundle_descriptor_matches_profile_schema(self) -> None:
        bundle = okf_semantic.load_yaml_ld(self.fixture_root / "bundle.yamlld")
        self.assertIsInstance(bundle, dict)
        assert isinstance(bundle, dict)
        self.assertEqual([], okf_semantic.schema_errors(bundle, "bundle.schema.json"))
        self.assertTrue(okf_semantic.expand(bundle))

    def test_yaml_12_and_yaml_ld_representation_rules(self) -> None:
        document = okf_semantic.load_yaml_ld_text("yes: no\nwhen: 2026-07-11\n")
        self.assertEqual({"yes": "no", "when": "2026-07-11"}, document)
        with self.assertRaises(okf_semantic.SemanticError):
            okf_semantic.load_yaml_ld_text("value: .inf\n")
        with self.assertRaises(okf_semantic.SemanticError):
            okf_semantic.load_yaml_ld_text("? [not, a, string]\n: invalid\n")

    def test_remote_contexts_are_allowlisted(self) -> None:
        with self.assertRaises(okf_semantic.SemanticError):
            okf_semantic.expand({"@context": "https://untrusted.example/context", "@id": "https://example.test/item"})

    def test_canonical_corpus_and_projection_are_okf_v02(self) -> None:
        graph, errors = update_viewer.build_graph()
        self.assertEqual([], errors)
        expected_counts = self.release_counts()
        self.assertEqual(expected_counts["nodes"], len(graph["nodes"]))
        self.assertEqual(expected_counts["relationships"], len(graph["edges"]))
        root = graph["nodes"]["index.md"]
        self.assertEqual("0.2", root["okf_version"])
        self.assertEqual("Index", root["type"])
        source = graph["nodes"]["standards/openapi.md"]
        self.assertNotIn("timestamp", source)
        self.assertNotIn("verified", source)
        self.assertEqual("stable", source["status"])
        self.assertEqual(
            "https://spec.openapis.org/oas/v3.2.0.html",
            source["sources"][0]["resource"],
        )

        bundle, bundle_errors = build_okf_bundle.build_bundle()
        self.assertEqual([], bundle_errors)
        self.assertEqual("0.2", bundle["okf_version"])
        self.assertEqual(
            "process:okf-ai-infrastructure-publication",
            bundle["generated"]["by"],
        )
        projected = bundle["corpora"]["ai-infrastructure-wiki"]["nodes"][
            "standards/openapi.md"
        ]
        self.assertEqual(source["sources"], projected["sources"])
        self.assertEqual(
            "https://chris-page-gov.github.io/okf-ai-infrastructure/id/standards/openapi",
            projected["semantic_id"],
        )

    def test_all_concepts_have_authored_semantic_identity(self) -> None:
        graph, errors = update_viewer.build_graph()
        self.assertEqual([], errors)
        concept_count = 0
        for path_id, node in graph["nodes"].items():
            if Path(path_id).name in {"index.md", "log.md"}:
                continue
            concept_count += 1
            self.assertEqual(okf_semantic.CONTEXT_URL, node.get("@context"), path_id)
            self.assertTrue(semantic_projection.absolute_iri(node.get("@id")), path_id)
            self.assertEqual("okf:Concept", node.get("@type"), path_id)
            authored = okf_semantic.parse_markdown(ROOT / path_id).metadata
            self.assertEqual(
                [],
                okf_semantic.schema_errors(authored, "concept.schema.json"),
                path_id,
            )
        expected_navigation = build_publication.navigation_record_count(graph["nodes"])
        self.assertEqual(
            self.release_counts()["nodes"] - expected_navigation,
            concept_count,
        )

    def test_semantic_graph_reconciles_direct_and_reified_relationships(self) -> None:
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        semantic = semantic_projection.semantic_graph(bundle)
        self.assertEqual([], semantic_projection.validate_relationships(bundle, semantic))
        corpus = bundle["corpora"]["ai-infrastructure-wiki"]
        relationships = corpus["relationships"]
        expected_counts = self.release_counts()
        relationship_count = expected_counts["relationships"]
        self.assertEqual(relationship_count, len(relationships))
        self.assertEqual(
            expected_counts["nodes"] + relationship_count,
            len(semantic["@graph"]),
        )
        self.assertEqual(
            {semantic_projection.REFERENCES_PREDICATE},
            {relationship["predicate"] for relationship in relationships},
        )
        assertion = next(
            item
            for item in semantic["@graph"]
            if "okf:RelationshipAssertion" in item.get("@type", [])
        )
        self.assertEqual([], okf_semantic.schema_errors(assertion, "semantic-assertion.schema.json"))
        expanded = okf_semantic.expand(semantic)
        expanded_graph = expanded[0]["@graph"]
        self.assertEqual(
            relationship_count,
            sum(
                len(item.get(semantic_projection.REFERENCES_PREDICATE, []))
                for item in expanded_graph
            ),
        )
        relationship_assertion_iri = (
            "https://chris-page-gov.github.io/okf-explorer/ns#RelationshipAssertion"
        )
        expanded_assertions = [
            item
            for item in expanded_graph
            if relationship_assertion_iri in item.get("@type", [])
        ]
        self.assertEqual(relationship_count, len(expanded_assertions))
        self.assertIn(
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#subject",
            expanded_assertions[0],
        )

        receipt = semantic_projection.semantic_validation_receipt(bundle, semantic)
        self.assertEqual("pass", receipt["result"])
        self.assertEqual(
            {
                "entities": expected_counts["nodes"],
                "runtime_assertions_validated": relationship_count,
                "semantic_assertions_validated": relationship_count,
                "direct_triples_reconciled": relationship_count,
                "validation_failures": 0,
            },
            receipt["counts"],
        )

    def test_shared_assertion_schema_is_exact_and_rejects_unsafe_sources(self) -> None:
        raw = okf_semantic.SEMANTIC_ASSERTION_SCHEMA_PATH.read_bytes()
        self.assertEqual(7_308, len(raw))
        self.assertEqual(
            okf_semantic.SEMANTIC_ASSERTION_SCHEMA_SHA256,
            hashlib.sha256(raw).hexdigest(),
        )
        self.assertEqual([], okf_semantic.semantic_assertion_schema_pin_errors())

        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        relationship = bundle["corpora"]["ai-infrastructure-wiki"][
            "relationships"
        ][0]
        valid = semantic_projection.semantic_assertion(relationship)
        self.assertEqual(
            [], okf_semantic.schema_errors(valid, "semantic-assertion.schema.json")
        )
        cases = {
            "missing label": lambda row: row.pop("label"),
            "credentialed authority": lambda row: row["authority"].__setitem__(
                "source", "https://user@example.test/evidence"
            ),
            "malformed evidence escape": lambda row: row["evidence"][0].__setitem__(
                "url", "https://example.test/evidence/%GG"
            ),
            "out-of-range rights port": lambda row: row["rights"].__setitem__(
                "source", "https://example.test:65536/licence"
            ),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                invalid = copy.deepcopy(valid)
                mutate(invalid)
                self.assertTrue(
                    okf_semantic.schema_errors(
                        invalid, "semantic-assertion.schema.json"
                    )
                )

    def test_relationship_ids_and_evidence_are_deterministic(self) -> None:
        first, first_errors = build_okf_bundle.build_bundle()
        second, second_errors = build_okf_bundle.build_bundle()
        self.assertEqual([], first_errors)
        self.assertEqual([], second_errors)
        first_relationships = first["corpora"]["ai-infrastructure-wiki"]["relationships"]
        second_relationships = second["corpora"]["ai-infrastructure-wiki"]["relationships"]
        self.assertEqual(first_relationships, second_relationships)
        relationship = first_relationships[0]
        self.assertEqual("normalized", relationship["assertion_status"])
        self.assertEqual("derived", relationship["authority"]["class"])
        self.assertRegex(relationship["evidence"][0]["source_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(
            relationship["evidence"][0]["source_value_sha256"], r"^[0-9a-f]{64}$"
        )

    def test_explicit_domain_assertion_authoring_preserves_predicate_and_routes(self) -> None:
        source_iri = "https://example.test/id/source"
        target_iri = "https://example.test/id/target"
        assertion_iri = "https://example.test/assertions/source-governed-by-target"
        nodes = {
            "source.md": {"@id": source_iri, "@type": "okf:Concept"},
            "target.md": {"@id": target_iri, "@type": "okf:Concept"},
        }
        declaration = {
            "@id": assertion_iri,
            "@type": ["rdf:Statement", "okf:RelationshipAssertion"],
            "target": {"@id": target_iri},
            "target_route": "target.md",
            "predicate": {"@id": "https://example.test/terms/governedBy"},
            "label": "governed by",
            "inverse_label": "governs",
            "assertion_status": "official",
            "assertion_scope": "real-world",
            "authority": {
                "class": "official",
                "label": "Example authority",
                "source": "https://example.test/evidence",
            },
            "derivation": "https://example.test/rules/direct-field-v1",
            "observed_at": "2026-08-09T00:00:00Z",
            "evidence": [
                {
                    "@id": "https://example.test/evidence/1",
                    "type": "source-field",
                    "url": "https://example.test/evidence",
                    "source_field": "governed_by",
                    "source_value_sha256": "a" * 64,
                    "retrieved_at": "2026-08-09T00:00:00Z",
                }
            ],
            "rights": {
                "source": "https://creativecommons.org/publicdomain/zero/1.0/",
                "assertion": "example assertion",
            },
        }
        relationship = semantic_projection.explicit_relationship(
            "source.md", declaration, nodes
        )
        self.assertEqual("source.md", relationship["source"])
        self.assertEqual(source_iri, relationship["source_iri"])
        self.assertEqual("target.md", relationship["target"])
        self.assertEqual(target_iri, relationship["target_iri"])
        self.assertEqual("https://example.test/terms/governedBy", relationship["predicate"])
        self.assertEqual(assertion_iri, relationship["id"])
        malicious = copy.deepcopy(declaration)
        malicious["source_route"] = "wrong/source.md"
        with self.assertRaisesRegex(ValueError, "source_route does not match"):
            semantic_projection.explicit_relationship(
                "source.md", malicious, nodes
            )
        relationship["source_route"] = "wrong/source.md"
        self.assertEqual(
            "source.md",
            semantic_projection.semantic_assertion(relationship)["source_route"],
        )

    def test_markdown_domain_assertion_survives_complete_publication_build(self) -> None:
        fixture_root = ROOT / "tests/fixtures/semantic_domain"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "publication"
            with (
                mock.patch.object(update_viewer, "ROOT", fixture_root),
                mock.patch.object(semantic_projection, "ROOT", fixture_root),
                mock.patch.object(
                    build_okf_bundle, "CONFIG", fixture_root / "okf.config.json"
                ),
                mock.patch.object(build_publication, "ROOT", fixture_root),
                mock.patch.object(build_publication, "OUT", output),
                mock.patch.object(build_publication, "DIRS", ("frameworks",)),
                mock.patch.object(
                    build_publication,
                    "FILES",
                    ("index.md", "okf.config.json"),
                ),
                mock.patch.object(check_publication, "ROOT", fixture_root),
                mock.patch.object(check_publication, "OUT", output),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(0, build_publication.main())
                self.assertEqual(0, check_publication.main())

            runtime = json.loads(
                (output / "relationships.json").read_text(encoding="utf-8")
            )
            semantic = json.loads(
                (output / "okf-bundle.jsonld").read_text(encoding="utf-8")
            )
            receipt = json.loads(
                (output / "semantic-validation.json").read_text(encoding="utf-8")
            )

            self.assertEqual(1, len(runtime))
            self.assertEqual(
                "https://example.test/terms/governedBy", runtime[0]["predicate"]
            )
            self.assertEqual("frameworks/source.md", runtime[0]["source"])
            self.assertEqual("frameworks/target.md", runtime[0]["target"])
            self.assertEqual(
                "https://example.test/id/source-service", runtime[0]["source_iri"]
            )
            self.assertEqual(
                "https://example.test/id/authority", runtime[0]["target_iri"]
            )
            self.assertEqual([], semantic_projection.validate_relationships(
                json.loads((output / "okf-bundle.json").read_text(encoding="utf-8")),
                semantic,
            ))
            self.assertEqual("pass", receipt["result"])
            self.assertEqual(1, receipt["counts"]["direct_triples_reconciled"])

    def test_semantic_receipt_refuses_an_invalid_projection(self) -> None:
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        semantic = semantic_projection.semantic_graph(bundle)
        assertion = next(
            item
            for item in semantic["@graph"]
            if "okf:RelationshipAssertion" in item.get("@type", [])
        )
        assertion["authority"]["source"] = "https://user@example.test/evidence"
        with self.assertRaisesRegex(
            ValueError, "cannot issue a passing semantic receipt"
        ):
            semantic_projection.semantic_validation_receipt(bundle, semantic)

    def test_semantic_receipt_refuses_an_extra_direct_triple(self) -> None:
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        semantic = semantic_projection.semantic_graph(bundle)
        entity = next(
            item
            for item in semantic["@graph"]
            if isinstance(item, dict)
            and "okf:RelationshipAssertion" not in item.get("@type", [])
        )
        predicate = semantic_projection.REFERENCES_PREDICATE
        values = entity.setdefault(predicate, [])
        if not isinstance(values, list):
            values = [values]
            entity[predicate] = values
        values.append({"@id": "https://example.test/id/unasserted-target"})

        validation_errors = semantic_projection.validate_relationships(bundle, semantic)
        self.assertTrue(
            any("unexpected occurrence" in error for error in validation_errors),
            validation_errors,
        )
        with self.assertRaisesRegex(
            ValueError, "cannot issue a passing semantic receipt"
        ):
            semantic_projection.semantic_validation_receipt(bundle, semantic)

    def test_direct_triples_require_exact_json_ld_id_objects(self) -> None:
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        for label, replacement in (
            ("URL-looking literal", "https://example.test/id/literal-not-link"),
            (
                "nested unreceipted content",
                {
                    "@id": "https://example.test/id/link-with-hidden-content",
                    "https://example.test/terms/hidden": "literal",
                },
            ),
        ):
            with self.subTest(label=label):
                semantic = semantic_projection.semantic_graph(bundle)
                entity = next(
                    item
                    for item in semantic["@graph"]
                    if isinstance(item, dict)
                    and semantic_projection.REFERENCES_PREDICATE in item
                )
                values = entity[semantic_projection.REFERENCES_PREDICATE]
                if not isinstance(values, list):
                    values = [values]
                    entity[semantic_projection.REFERENCES_PREDICATE] = values
                values[0] = replacement

                validation_errors = semantic_projection.validate_relationships(
                    bundle, semantic
                )
                self.assertTrue(
                    any("must be exactly an @id object" in error for error in validation_errors),
                    validation_errors,
                )
                with self.assertRaisesRegex(
                    ValueError, "cannot issue a passing semantic receipt"
                ):
                    semantic_projection.semantic_validation_receipt(bundle, semantic)

    def test_runtime_routes_must_bind_their_absolute_semantic_identities(self) -> None:
        original, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        corpus = original["corpora"]["ai-infrastructure-wiki"]
        relationship = corpus["relationships"][0]
        alternate_routes = [
            route
            for route in corpus["nodes"]
            if route not in {relationship["source"], relationship["target"]}
        ]
        self.assertGreaterEqual(len(alternate_routes), 2)

        for route_field, alternate_route in zip(
            ("source", "target"), alternate_routes[:2], strict=True
        ):
            with self.subTest(route_field=route_field):
                bundle = copy.deepcopy(original)
                mutated = bundle["corpora"]["ai-infrastructure-wiki"][
                    "relationships"
                ][0]
                mutated[route_field] = alternate_route
                semantic = semantic_projection.semantic_graph(bundle)

                validation_errors = semantic_projection.validate_relationships(
                    bundle, semantic
                )
                self.assertTrue(
                    any(
                        f"{route_field} route does not identify {route_field}_iri"
                        in error
                        for error in validation_errors
                    ),
                    validation_errors,
                )
                with self.assertRaisesRegex(
                    ValueError, "cannot issue a passing semantic receipt"
                ):
                    semantic_projection.semantic_validation_receipt(bundle, semantic)

    def test_synthetic_fixture_scope_uses_synthetic_authority(self) -> None:
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        relationship = bundle["corpora"]["ai-infrastructure-wiki"][
            "relationships"
        ][0]
        relationship["assertion_scope"] = "synthetic-fixture"
        relationship["authority"]["class"] = "synthetic"
        semantic = semantic_projection.semantic_graph(bundle)

        self.assertEqual(
            [], semantic_projection.validate_relationships(bundle, semantic)
        )
        self.assertEqual(
            "pass",
            semantic_projection.semantic_validation_receipt(bundle, semantic)[
                "result"
            ],
        )

    def test_projection_provenance_uses_one_declared_build_instant(self) -> None:
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        generated_at = bundle["generated"]["at"]
        relationship = bundle["corpora"]["ai-infrastructure-wiki"][
            "relationships"
        ][0]
        semantic = semantic_projection.semantic_graph(bundle)

        self.assertEqual(generated_at, relationship["observed_at"])
        self.assertEqual(generated_at, relationship["evidence"][0]["retrieved_at"])
        self.assertEqual(generated_at, semantic["generated"]["at"])
        self.assertEqual(
            semantic_projection.PUBLIC_BASE
            + "activities/semantic-projection-"
            + generated_at[:10],
            relationship["derivation_activity"],
        )

    def test_publication_cleans_stale_files_and_requires_exact_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            output.mkdir()
            stale = output / "stale-private.txt"
            stale.write_text("must not publish\n", encoding="utf-8")
            with mock.patch.object(build_publication, "OUT", output):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(0, build_publication.main())
            self.assertFalse(stale.exists())

            checksum_path = output / "checksums.json"
            checksum_document = json.loads(checksum_path.read_text(encoding="utf-8"))
            pristine_checksums = copy.deepcopy(checksum_document)
            actual_files = {
                path.relative_to(output).as_posix()
                for path in output.rglob("*")
                if path.is_file() and path.name != "checksums.json"
            }
            self.assertEqual(actual_files, set(checksum_document["files"]))
            checksum_document["files"].pop("relationships.json")
            checksum_document["files"].pop("semantic-validation.json")
            checksum_path.write_text(
                json.dumps(checksum_document, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            messages = io.StringIO()
            with mock.patch.object(check_publication, "OUT", output):
                with contextlib.redirect_stdout(messages):
                    self.assertEqual(1, check_publication.main())
            self.assertIn("checksum entry is missing: relationships.json", messages.getvalue())
            self.assertIn(
                "checksum entry is missing: semantic-validation.json",
                messages.getvalue(),
            )

            private_path = output / "undeclared-private.txt"
            private_content = b"must never be self-declared\n"
            private_path.write_bytes(private_content)
            pristine_checksums["files"][private_path.name] = {
                "sha256": hashlib.sha256(private_content).hexdigest(),
                "bytes": len(private_content),
            }
            checksum_path.write_text(
                json.dumps(pristine_checksums, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            messages = io.StringIO()
            with mock.patch.object(check_publication, "OUT", output):
                with contextlib.redirect_stdout(messages):
                    self.assertEqual(1, check_publication.main())
            self.assertIn(
                "unexpected published file: undeclared-private.txt",
                messages.getvalue(),
            )

    def test_v02_optional_families_reject_invalid_dates_and_counts(self) -> None:
        errors = update_viewer.validate_v02_metadata(
            "bad.md",
            {
                "type": "Reference",
                "generated": {"by": "process:test", "at": "not-a-date"},
                "verified": {"by": "human:reviewer", "at": "still-not-a-date"},
                "stale_after": "2026-99-99",
                "sources": [
                    {
                        "resource": "scope descriptor",
                        "last_modified": "yesterday",
                        "usage_count": -1,
                    }
                ],
            },
        )
        self.assertIn("bad.md generated.at must be an ISO 8601 datetime", errors)
        self.assertIn("bad.md verified[0].at must be an ISO 8601 datetime", errors)
        self.assertIn("bad.md sources[0].last_modified must be an ISO date", errors)
        self.assertIn("bad.md sources[0].usage_count must be a non-negative integer", errors)
        self.assertIn("bad.md stale_after must be an ISO date", errors)


if __name__ == "__main__":
    unittest.main()
